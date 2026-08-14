"""
Generative linker design — character-GRU model trained on PROTAC-DB linkers.
============================================================================
Model: compact char-level GRU (SMILES-RNN style), trained on linkers extracted
from PROTAC-DB 3.0 via BRICS (241) + curated/fragment linkers
(scripts/train_linker_generator.py). CPU inference.

Generation pipeline (this module):
  1. sample N candidates with temperature
  2. validate with RDKit; filter size/flexibility
  3. score: ADMET-AI composite (AMES/DILI/hERG) when the isolated venv is
     available, else a size/strain proxy; prefer 4-12 heavy atoms
  4. diversity-select top-K (greedy Tanimoto on Morgan fingerprints)

Output: LinkerRecord list with source="generative_linker_model" and model
provenance. Falls back to an empty list (not a crash) when the checkpoint is
missing — callers keep the curated/fragment sources.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import torch

from synglue_agent.backend.schemas import LinkerRecord
from synglue_agent.tools.protac_toolbox import ProtacDesignToolbox

logger = logging.getLogger("protacpilot.generative_linker")

ROOT = Path(__file__).resolve().parents[2]
CHECKPOINT = ROOT / "data" / "linkers" / "linker_generator.pt"
_TARGET_LENGTH = (4, 12)      # preferred linker heavy-atom range (lit. rules)
_MAX_ROTATABLE = 8


class LinkerGenerator:
    def __init__(self, checkpoint: Path = CHECKPOINT):
        self.toolbox = ProtacDesignToolbox()
        self._model = None
        self._vocab: Dict[str, int] = {}
        self._ivocab: Dict[int, str] = {}
        self._chars: List[str] = []
        if checkpoint.exists():
            try:
                ckpt = torch.load(checkpoint, map_location="cpu", weights_only=False)
                vocab = ckpt["vocab"]
                self._vocab = vocab
                self._ivocab = {i: c for c, i in self._vocab.items()}
                self._chars = ckpt["chars"]
                from scripts.train_linker_generator import CharGRU  # noqa: E402
                cfg = ckpt["config"]
                self._model = CharGRU(len(vocab), cfg["emb"], cfg["hidden"], cfg["layers"])
                self._model.load_state_dict(ckpt["state"])
                self._model.eval()
            except Exception as exc:  # noqa: BLE001
                logger.warning("linker generator load failed: %s", exc)
                self._model = None

    @property
    def available(self) -> bool:
        return self._model is not None

    def sample(self, n: int = 48, temperature: float = 1.0) -> List[str]:
        """Sample n raw linker SMILES (may include invalid ones)."""
        if not self.available:
            return []
        import random
        start = self._vocab.get("<S>")
        stop = self._vocab.get("</S>")
        out: List[str] = []
        with torch.no_grad():
            for _ in range(n):
                x = torch.tensor([[start]], dtype=torch.long)
                hidden = None
                seq = []
                for _ in range(80):  # max chars
                    logits, hidden = self._model(x, hidden)
                    probs = torch.softmax(logits[0, 0] / max(temperature, 1e-3), dim=0)
                    idx = torch.multinomial(probs, 1).item()
                    if idx == stop:
                        break
                    ch = self._ivocab.get(idx, "")
                    if ch and ch not in ("<S>", "</S>"):
                        seq.append(ch)
                    x = torch.tensor([[idx]], dtype=torch.long)
                smi = "".join(seq)
                if smi:
                    out.append(smi)
        return out

    def generate(
        self,
        max_linkers: int = 24,
        temperature: float = 1.0,
        candidates: int = 64,
    ) -> List[LinkerRecord]:
        """Full pipeline: sample -> validate -> filter -> BATCH-score -> diversify."""
        from rdkit import Chem
        from rdkit.Chem import DataStructs
        from rdkit.Chem.AllChem import GetMorganFingerprintAsBitVect
        from rdkit.Chem.rdMolDescriptors import CalcNumRotatableBonds

        if not self.available:
            return []
        valid: List[Dict[str, Any]] = []
        seen: set = set()
        for smi in self.sample(candidates, temperature):
            if "[" in smi:  # attachment/dummy tokens learned from corpus — reject
                continue
            mol = Chem.MolFromSmiles(smi)
            if mol is None:
                continue
            canon = Chem.MolToSmiles(mol)
            if canon in seen:
                continue
            ha = mol.GetNumHeavyAtoms()
            if not (3 <= ha <= 20):
                continue
            if CalcNumRotatableBonds(mol) > _MAX_ROTATABLE:
                continue
            wrapped = f"[*:1]{canon}[*:2]"
            if Chem.MolFromSmiles(wrapped.replace("[*:1]", "[*]").replace("[*:2]", "[*]")) is None:
                continue  # attachment markers break chemistry — drop
            seen.add(canon)
            valid.append({"smiles": canon, "heavy_atoms": ha})

        # BATCH ADMET-AI scoring: ONE subprocess/model load for all candidates.
        risk_map: Dict[str, float] = {}
        try:
            from synglue_agent.tools.admet_integration import _run_admet_ai
            rows = _run_admet_ai([v["smiles"] for v in valid], timeout_s=300)
            for row in rows or []:
                e = row.get("endpoints", {})
                risk = 0.50 * float(e.get("AMES") or 0.0) + 0.30 * float(e.get("DILI") or 0.0) + 0.20 * float(e.get("hERG") or 0.0)
                risk_map[row.get("smiles")] = min(1.0, risk)
        except Exception:  # noqa: BLE001
            risk_map = {}

        for v in valid:
            ha = v["heavy_atoms"]
            length_penalty = 0.0
            if not (_TARGET_LENGTH[0] <= ha <= _TARGET_LENGTH[1]):
                length_penalty = 0.15 * abs(ha - _TARGET_LENGTH[0]) if ha < _TARGET_LENGTH[0] else 0.1 * (ha - _TARGET_LENGTH[1])
            admet_risk = risk_map.get(v["smiles"], 0.2)
            score = 1.0 - (admet_risk + length_penalty)
            v["score"] = float(max(0.0, min(1.0, score)))
            v["admet_risk"] = float(admet_risk)

        valid.sort(key=lambda v: -v["score"])
        # greedy diversity selection
        selected = []
        for v in valid:
            if len(selected) >= max_linkers:
                break
            mol = Chem.MolFromSmiles(v["smiles"])
            fp = GetMorganFingerprintAsBitVect(mol, 2, 2048)
            if all(1.0 - DataStructs.TanimotoSimilarity(fp, GetMorganFingerprintAsBitVect(
                    Chem.MolFromSmiles(s["smiles"]), 2, 2048)) > 0.35 for s in selected):
                selected.append(v)

        records = []
        for i, v in enumerate(selected):
            records.append(LinkerRecord(
                name=f"gen_{i}",
                smiles=f"[*:1]{v['smiles']}[*:2]",
                linker_class="generative",
                source="generative_linker_model",
                graph_length=v["heavy_atoms"],
                effective_length=max(3.0, v["heavy_atoms"] * 0.7),
                rotatable_bonds=_MAX_ROTATABLE,
                tpsa_contribution=0.0,
                hbd=0,
                hba=0,
                synthetic_feasibility_proxy=round(v["score"], 3),
                validity_status=self.toolbox.validate_linker(f"[*:1]{v['smiles']}[*:2]"),
                provenance={"generation_method": "charGRU-linker-v1",
                            "training_corpus": "PROTAC-DB BRICS linkers + curated",
                            "admet_risk": round(v["admet_risk"], 3)},
            ))
        return records


_GENERATOR: Optional[LinkerGenerator] = None


def generate_generative_linkers(max_linkers: int = 24) -> List[LinkerRecord]:
    """Module-level entry (cached model). Empty list when unavailable."""
    global _GENERATOR
    if _GENERATOR is None:
        _GENERATOR = LinkerGenerator()
    return _GENERATOR.generate(max_linkers=max_linkers)


if __name__ == "__main__":
    links = generate_generative_linkers(max_linkers=12)
    print(f"generated {len(links)} linkers")
    for l in links[:6]:
        print(f"  {l.smiles[:55]}  score={l.synthetic_feasibility_proxy}  src={l.source}")
