"""Compact character-level GRU linker generator (SMILES-RNN style).

Package copy of the model class historically defined in
``scripts/train_linker_generator.py`` so that the shipped
``linker_generator.pt`` checkpoint is usable from a clean one-command
installation (no repository/``scripts`` on the path). Training remains a
repo-script concern; inference (``generate``/``optimize``) uses this class.
"""

from __future__ import annotations

import torch
import torch.nn as nn


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


def load_char_gru() -> type:
    """Import CharGRU — packaged copy first, repo ``scripts`` fallback.

    Returns the class object; raises ImportError when neither is available
    (e.g. torch not installed).
    """
    try:
        from protacxtend.tools.linker_char_gru import CharGRU  # noqa: F401
        return CharGRU
    except Exception:  # pragma: no cover - legacy repo layout
        from scripts.train_linker_generator import CharGRU  # type: ignore
        return CharGRU
