"""
Link-INVENT-style linker optimization (policy-gradient refinement).
====================================================================
Implements the RL optimization spirit of Link-INVENT (DAP-like reward-
weighted updates) on OUR char-GRU linker policy:

  1. sample a batch of linkers from the policy (with log-probs)
  2. score each with the Link-INVENT recipe + ADMET penalty (reward)
  3. REINFORCE update: loss = -mean((reward - baseline) * log_prob)
  4. repeat for `rounds`; return the diverse top-N best-of-all-rounds

The optimized policy can be persisted (linker_generator.optimized.pt) for
reuse; the base checkpoint is never overwritten. Bounded compute:
rounds(3) x batch(48) x (score + batched ADMET) ~ 1-2 min on CPU.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional

import torch

from synglue_agent.backend.schemas import LinkerRecord
from synglue_agent.tools.linker_scoring import rank_linkers, score_linker_smiles
from synglue_agent.tools.protac_toolbox import ProtacDesignToolbox

logger = logging.getLogger("protacpilot.linker_optimizer")

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "data" / "linkers" / "linker_generator.pt"
OPT = ROOT / "data" / "linkers" / "linker_generator.optimized.pt"


class LinkerOptimizer:
    def __init__(self, checkpoint: Path = BASE, lr: float = 1e-3):
        self.toolbox = ProtacDesignToolbox()
        self._model = None
        self._vocab = {}
        self._ivocab = {}
        self._lr = lr
        if checkpoint.exists():
            try:
                from scripts.train_linker_generator import CharGRU
                ckpt = torch.load(checkpoint, map_location="cpu", weights_only=False)
                self._vocab = ckpt["vocab"]
                self._ivocab = {i: c for c, i in self._vocab.items()}
                cfg = ckpt["config"]
                self._model = CharGRU(len(self._vocab), cfg["emb"], cfg["hidden"], cfg["layers"])
                self._model.load_state_dict(ckpt["state"])
                self._model.train()
            except Exception as exc:  # noqa: BLE001
                logger.warning("optimizer init failed: %s", exc)
                self._model = None

    @property
    def available(self) -> bool:
        return self._model is not None

    def _sample_batch(self, n: int, temperature: float) -> List:
        """Sample (smiles, seq_tensor) pairs from the policy."""
        import random
        start = self._vocab.get("<S>")
        stop = self._vocab.get("</S>")
        out = []
        with torch.no_grad():
            for _ in range(n):
                x = torch.tensor([[start]], dtype=torch.long)
                hidden = None
                seq_ids = [start]
                for _ in range(80):
                    logits, hidden = self._model(x, hidden)
                    probs = torch.softmax(logits[0, 0] / max(temperature, 1e-3), dim=0)
                    idx = torch.multinomial(probs, 1).item()
                    if idx == stop:
                        break
                    seq_ids.append(idx)
                    x = torch.tensor([[idx]], dtype=torch.long)
                smi = "".join(self._ivocab.get(i, "") for i in seq_ids[1:])
                if smi:
                    out.append((smi, torch.tensor(seq_ids, dtype=torch.long)))
        return out

    def optimize(
        self,
        rounds: int = 3,
        batch: int = 48,
        temperature: float = 1.0,
        keep: int = 24,
        use_admet: bool = True,
        persist: bool = False,
    ) -> List[LinkerRecord]:
        """Run policy-gradient refinement; return diverse top-K linkers."""
        from rdkit import Chem

        if not self.available:
            return []
        opt = torch.optim.Adam(self._model.parameters(), lr=self._lr)
        best: List[tuple] = []  # (score, smiles, admet_risk)
        seen: set = set()
        for r in range(rounds):
            batch_items = self._sample_batch(batch, temperature)
            if not batch_items:
                break
            rewards = []
            kept = []
            for smi, seq in batch_items:
                if "[" in smi:  # dummy tokens learned from corpus — reject
                    rewards.append(0.0)
                    continue
                mol = Chem.MolFromSmiles(smi)
                if mol is None:
                    rewards.append(0.0)
                    continue
                canon = Chem.MolToSmiles(mol)
                if canon in seen:
                    rewards.append(0.0)
                    continue
                seen.add(canon)
                sc = score_linker_smiles(f"[*:1]{canon}[*:2]", use_admet=False)
                reward = float(sc.composite)
                kept.append((smi, seq, canon, reward))
                rewards.append(reward)
            baseline = sum(rewards) / max(len(rewards), 1)
            # REINFORCE update on kept samples (detached baseline)
            if kept:
                loss_terms = []
                for smi, seq, canon, reward in kept:
                    logp = self._model.log_prob(seq)
                    loss_terms.append((reward - baseline) * logp)
                if loss_terms:
                    loss = -torch.stack(loss_terms).mean()
                    opt.zero_grad()
                    loss.backward()
                    opt.step()
            # collect best-of-round
            for smi, seq, canon, reward in kept:
                best.append((reward, f"[*:1]{canon}[*:2]", 0.0))
            logger.info("round %d: %d valid, mean reward %.3f", r + 1, len(kept), baseline)

        # ADMET penalties (batched) for the best candidates
        ranked = rank_linkers([_mk_record(s, score) for score, s, _ in sorted(best, reverse=True)[:max(keep * 2, 24)]],
                              use_admet=use_admet)
        if persist:
            torch.save({"state": self._model.state_dict(), "vocab": self._vocab,
                        "ivocab": self._ivocab, "chars": sorted(self._vocab.keys()),
                        "config": {"emb": 64, "hidden": 128, "layers": 2},
                        "optimized": True}, OPT)
            logger.info("optimized policy saved -> %s", OPT)
        return ranked[:keep]


def _mk_record(smiles: str, score: float) -> LinkerRecord:
    from rdkit import Chem
    clean = smiles.replace("[*:1]", "").replace("[*:2]", "")
    mol = Chem.MolFromSmiles(clean)
    ha = mol.GetNumHeavyAtoms() if mol else 0
    return LinkerRecord(
        name="opt_linker", smiles=smiles, linker_class="generative",
        source="linker_optimizer", graph_length=ha,
        effective_length=max(3.0, ha * 0.7), rotatable_bonds=8,
        tpsa_contribution=0.0, hbd=0, hba=0,
        synthetic_feasibility_proxy=score,
        validity_status="valid" if mol else "invalid",
        provenance={"generation_method": "linkinvent-style-optimizer"})


_OPTIMIZER: Optional[LinkerOptimizer] = None


def optimize_linkers(**kwargs) -> List[LinkerRecord]:
    """Module entry with cached optimizer; [] when unavailable."""
    global _OPTIMIZER
    if _OPTIMIZER is None:
        _OPTIMIZER = LinkerOptimizer()
    return _OPTIMIZER.optimize(**kwargs)


if __name__ == "__main__":
    links = optimize_linkers(rounds=2, batch=32, keep=10, persist=False)
    print(f"optimized {len(links)} linkers")
    for l in links[:5]:
        print(f"  {l.smiles[:45]:47} score={l.synthetic_feasibility_proxy:.3f}")
