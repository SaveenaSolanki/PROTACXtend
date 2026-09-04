#!/usr/bin/env python3
"""Train a compact character-level GRU linker generator (SMILES-RNN style).

Corpus: PROTAC-DB BRICS-extracted linkers + curated + fragment-combination
linkers. CPU-friendly (< 3 min). Saves data/linkers/linker_generator.pt
(state dict + vocab + config).
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import torch
import torch.nn as nn

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DATA = ROOT / "data" / "linkers" / "linker_smiles.txt"
CURATED = ROOT / "protacxtend" / "data" / "curated_linkers.csv"
OUT = ROOT / "data" / "linkers" / "linker_generator.pt"


class CharGRU(nn.Module):
    def __init__(self, vocab_size: int, emb: int = 64, hidden: int = 128, layers: int = 2):
        super().__init__()
        self.emb = nn.Embedding(vocab_size, emb)
        self.gru = nn.GRU(emb, hidden, layers, batch_first=True, dropout=0.2)
        self.out = nn.Linear(hidden, vocab_size)

    def forward(self, x, hidden=None):
        e = self.emb(x)
        out, hidden = self.gru(e, hidden)
        return self.out(out), hidden

    def log_prob(self, seq: torch.Tensor) -> torch.Tensor:
        """Log-probability of a full sequence (for policy-gradient updates)."""
        if len(seq) < 2:
            return torch.tensor(0.0)
        x = seq[:-1].unsqueeze(0)
        target = seq[1:]
        logits, _ = self.forward(x)
        logp = torch.log_softmax(logits, dim=-1).squeeze(0)
        return logp.gather(1, target.unsqueeze(1)).sum()


def load_corpus() -> list[str]:
    seqs = []
    for line in DATA.read_text().splitlines():
        s = line.strip()
        if s:
            seqs.append(s)
    # curated + fragment-combination linkers as extra training examples
    import csv
    import re as _re
    from rdkit import Chem
    if CURATED.exists():
        for row in csv.DictReader(open(CURATED)):
            smi = (row.get("smiles") or "").strip()
            if smi:
                cleaned = _re.sub(r"\[\*:?\d*\]|\[\d\*\]", "", smi)
                cleaned = _re.sub(r"\(\)", "", cleaned)
                mol = Chem.MolFromSmiles(cleaned)
                if mol:
                    seqs.append(Chem.MolToSmiles(mol))
    # hard corpus hygiene: drop anything containing dummy tokens
    seqs = [x for x in seqs if "[" not in x]
    return list(dict.fromkeys(seqs))


def main() -> int:
    random.seed(7)
    torch.manual_seed(7)
    seqs = load_corpus()
    print(f"corpus: {len(seqs)} linkers")
    chars = sorted({ch for s in seqs for ch in s} | {"<S>", "</S>", "X"})
    vocab = {c: i for i, c in enumerate(chars)}
    ivocab = {i: c for c, i in vocab.items()}

    def encode(s: str):
        return [vocab["<S>"]] + [vocab[c] for c in s] + [vocab["</S>"]]

    data = [torch.tensor(encode(s), dtype=torch.long) for s in seqs]
    model = CharGRU(len(chars))
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = nn.CrossEntropyLoss()

    for epoch in range(80):
        random.shuffle(data)
        total = 0.0
        n = 0
        for seq in data:
            if len(seq) < 3:
                continue
            x = seq[:-1].unsqueeze(0)
            y = seq[1:]
            logits, _ = model(x)
            loss = loss_fn(logits.squeeze(0), y)
            opt.zero_grad()
            loss.backward()
            opt.step()
            total += loss.item()
            n += 1
        if epoch % 20 == 0 or epoch == 79:
            print(f"epoch {epoch}: loss {total/max(n,1):.3f}")

    torch.save({"state": model.state_dict(), "vocab": vocab, "ivocab": ivocab,
                "chars": chars, "config": {"emb": 64, "hidden": 128, "layers": 2}},
               OUT)
    print(f"saved -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
