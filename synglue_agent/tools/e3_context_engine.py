"""
E3-context engine (Task 5) — deterministic, evidence-based E3 selection.
========================================================================

Selects CRBN vs VHL (vs other E3s) from retrieved/curated evidence, NOT LLM
intuition. Every score component carries an evidence reference.

Components (all 0-1, higher = better for that E3 in this context):
  - expression_score       tissue/cell-line E3 expression
  - colocalization_score   target subcellular localization vs E3 activity
  - ligand_availability    usable E3 ligand for PROTAC chemistry
  - structural_support     PDB/crystal structures for ternary modelling
  - resistance_risk        known resistance mechanisms (inverted: higher=safer)

total_context_score = weighted mean. Explanation is generated from the
component scores (deterministic templates), not free text.

Evidence sources (curated, provenance per row):
  - cell-line expression: literature/CCLE-derived table (data/benchmark/e3_expression_evidence.csv)
  - ligand availability: curated E3 ligand registry (e3_ligand.csv)
  - structural support: PDB availability for CRBN-DDB1 / VHL-elonginBC complexes
  - resistance: known CRBN-mutant/VHL-loss resistance literature
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger("protacpilot.e3context")

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_CSV = ROOT / "data" / "benchmark" / "e3_expression_evidence.csv"
PACKAGE_EVIDENCE_CSV = ROOT / "synglue_agent" / "data" / "e3_expression_evidence.csv"

# Weights (deterministic, documented)
WEIGHTS = {
    "expression_score": 0.30,
    "colocalization_score": 0.20,
    "ligand_availability_score": 0.20,
    "structural_support_score": 0.20,
    "resistance_risk": 0.10,
}

# Curated expression evidence (cell_line → E3 → level + source)
_DEFAULT_EXPRESSION: Dict[str, Dict[str, Dict[str, str]]] = {
    "MM1.S": {
        "CRBN": {"level": "high", "source": "Ito et al. 2010; Zhu et al. 2019 (curated)"},
        "VHL": {"level": "low", "source": "Zhu et al. 2019 (curated)"},
        "cIAP1": {"level": "medium", "source": "curated"},
        "MDM2": {"level": "medium", "source": "curated"},
    },
    "HCT116": {
        "CRBN": {"level": "medium", "source": "PROTAC-DB meta (curated)"},
        "VHL": {"level": "medium", "source": "PROTAC-DB meta (curated)"},
        "cIAP1": {"level": "high", "source": "curated"},
        "MDM2": {"level": "medium", "source": "curated"},
    },
    "HEK293T": {
        "CRBN": {"level": "high", "source": "common proteomics (curated)"},
        "VHL": {"level": "medium", "source": "common proteomics (curated)"},
        "cIAP1": {"level": "medium", "source": "curated"},
        "MDM2": {"level": "medium", "source": "curated"},
    },
    "MCF7": {
        "CRBN": {"level": "medium", "source": "CCLE-derived (curated)"},
        "VHL": {"level": "high", "source": "CCLE-derived (curated)"},
        "cIAP1": {"level": "low", "source": "curated"},
        "MDM2": {"level": "high", "source": "curated (p53 wt)"},
    },
    "default": {
        "CRBN": {"level": "medium", "source": "default neutral"},
        "VHL": {"level": "medium", "source": "default neutral"},
        "cIAP1": {"level": "medium", "source": "default neutral"},
        "MDM2": {"level": "medium", "source": "default neutral"},
    },
}

# E3 ligands (name, SMILES source) — ligand availability
_LIGAND_AVAILABILITY = {
    "CRBN": {"ligand": "pomalidomide/thalidomide", "score": 1.0},
    "VHL": {"ligand": "VH032/VH298", "score": 1.0},
    "cIAP1": {"ligand": "bestatin/LCL161", "score": 0.8},
    "MDM2": {"ligand": "nutlin-3", "score": 0.7},
}

# Structural support (PDB complexes for ternary modelling)
_STRUCTURAL_SUPPORT = {
    "CRBN": {"pdb": "4CI2 (CRBN-DDB1), 6BN7 (BRD4-CRBN)", "score": 0.9},
    "VHL": {"pdb": "4W9O (VHL-ElonginBC), 5T35 (BRD4-VHL)", "score": 1.0},
    "cIAP1": {"pdb": "limited", "score": 0.4},
    "MDM2": {"pdb": "4HG7 (MDM2-p53)", "score": 0.5},
}

# Resistance evidence (inverted: higher score = safer)
_RESISTANCE_RISK = {
    "CRBN": {"note": "CRBN mutations/thalidomide resistance documented", "risk": 0.7},
    "VHL": {"note": "VHL loss-of-function in ccRCC", "risk": 0.5},
    "cIAP1": {"note": "IAP overexpression in many cancers", "risk": 0.6},
    "MDM2": {"note": "MDM2 amplification common", "risk": 0.6},
}

# Nuclear-compatible E3s (subcellular colocalization rule)
_NUCLEAR_E3S = {"CRBN", "DCAF15", "DCAF11", "KLHL20"}


class E3ContextResult(BaseModel):
    e3_ligase: str
    context_id: str = ""

    expression_score: float = 0.0
    colocalization_score: float = 0.0
    ligand_availability_score: float = 0.0
    structural_support_score: float = 0.0
    resistance_risk: float = 0.0

    total_context_score: float = 0.0
    evidence_refs: List[str] = Field(default_factory=list)
    contraindications: List[str] = Field(default_factory=list)
    confidence: float = 0.0
    explanation: str = ""


def _level_to_score(level: str) -> float:
    return {"high": 1.0, "medium": 0.6, "low": 0.2, "unknown": 0.4}.get(level, 0.4)


def _canonical_cell(value: str) -> str:
    return value.strip().upper().replace("_", "").replace("-", "").replace(" ", "")


def _canonical_e3(value: str) -> str:
    aliases = {
        "CEREBLON": "CRBN",
        "CRBN": "CRBN",
        "VHL": "VHL",
        "PVHL": "VHL",
        "CIAP1": "cIAP1",
        "BIRC2": "cIAP1",
        "CIAP2": "cIAP2",
        "BIRC3": "cIAP2",
        "MDM2": "MDM2",
        "DCAF15": "DCAF15",
        "DCAF16": "DCAF16",
    }
    token = value.strip().upper()
    return aliases.get(token, value.strip())


def _expression_score(row: dict[str, str]) -> float:
    explicit = row.get("expression_score", "")
    if explicit not in ("", None):
        try:
            return max(0.0, min(1.0, float(explicit)))
        except Exception:
            pass
    return _level_to_score(row.get("level", "unknown"))


def _load_expression_table() -> Dict[str, Any]:
    evidence_path = EVIDENCE_CSV if EVIDENCE_CSV.exists() else PACKAGE_EVIDENCE_CSV
    if not evidence_path.exists():
        return _DEFAULT_EXPRESSION
    table: Dict[str, Dict[str, Dict[str, str]]] = {}
    try:
        with open(evidence_path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                cell = row.get("cell_line", "").strip()
                e3 = _canonical_e3(row.get("e3", "").strip())
                if cell and e3:
                    record = {
                        "level": row.get("level", "medium"),
                        "source": row.get("source", "curated"),
                        "expression_score": str(_expression_score(row)),
                        "evidence_type": row.get("evidence_type", "curated_expression"),
                        "source_url": row.get("source_url", ""),
                        "confidence": row.get("confidence", "0.7"),
                    }
                    table.setdefault(cell, {})[e3] = record
                    table.setdefault(_canonical_cell(cell), {})[e3] = record
    except Exception as exc:
        logger.warning("e3 evidence csv failed: %s", exc)
        return _DEFAULT_EXPRESSION
    for cell, values in _DEFAULT_EXPRESSION.items():
        table.setdefault(cell, values)
        table.setdefault(_canonical_cell(cell), values)
    return table or _DEFAULT_EXPRESSION


def score_e3(
    e3_ligase: str,
    cell_line: str = "default",
    target_localization: str = "nuclear",
    target: str = "",
) -> E3ContextResult:
    """Score one E3 in a context. Deterministic, evidence-referenced."""
    table = _load_expression_table()
    e3_ligase = _canonical_e3(e3_ligase)
    context_key = cell_line if cell_line in table else _canonical_cell(cell_line)
    expr = table.get(context_key, table["default"]).get(
        e3_ligase,
        table["default"].get(e3_ligase, {"level": "medium", "source": "default", "expression_score": "0.6", "confidence": "0.5"}),
    )
    expression_score = _expression_score(expr)

    colocalization_score = 1.0 if (target_localization != "nuclear" or e3_ligase in _NUCLEAR_E3S) else 0.3

    ligand = _LIGAND_AVAILABILITY.get(e3_ligase, {"ligand": "none", "score": 0.1})
    structural = _STRUCTURAL_SUPPORT.get(e3_ligase, {"pdb": "none", "score": 0.1})
    resistance = _RESISTANCE_RISK.get(e3_ligase, {"note": "unknown", "risk": 0.5})

    # resistance_risk is inverted for scoring (higher = safer)
    resistance_safety = 1.0 - resistance["risk"]

    total = (
        WEIGHTS["expression_score"] * expression_score
        + WEIGHTS["colocalization_score"] * colocalization_score
        + WEIGHTS["ligand_availability_score"] * ligand["score"]
        + WEIGHTS["structural_support_score"] * structural["score"]
        + WEIGHTS["resistance_risk"] * resistance_safety
    )

    evidence_refs = [
        f"expression:{expr.get('source', 'curated')}",
        f"ligand:{ligand['ligand']}",
        f"structure:{structural['pdb']}",
        f"resistance:{resistance['note']}",
    ]
    if expr.get("source_url"):
        evidence_refs.append(f"expression_url:{expr['source_url']}")
    contraindications: List[str] = []
    if expr["level"] == "low":
        contraindications.append(f"{e3_ligase} expression LOW in {cell_line}")
    if colocalization_score < 0.5:
        contraindications.append(f"{e3_ligase} incompatible with {target_localization} target localization")
    if resistance["risk"] >= 0.7:
        contraindications.append(f"known resistance: {resistance['note']}")

    explanation = (
        f"{e3_ligase} scores {total:.2f} in {cell_line}: expression {expr['level']} "
        f"({expression_score:.2f}), colocalization {'compatible' if colocalization_score > 0.5 else 'incompatible'} "
        f"({colocalization_score:.2f}), ligand {ligand['ligand']} ({ligand['score']:.2f}), "
        f"structural support ({structural['score']:.2f}), resistance safety ({resistance_safety:.2f})."
    )

    return E3ContextResult(
        e3_ligase=e3_ligase,
        context_id=f"{cell_line}|{target}|{e3_ligase}",
        expression_score=round(expression_score, 3),
        colocalization_score=round(colocalization_score, 3),
        ligand_availability_score=round(ligand["score"], 3),
        structural_support_score=round(structural["score"], 3),
        resistance_risk=round(resistance["risk"], 3),
        total_context_score=round(total, 4),
        evidence_refs=evidence_refs,
        contraindications=contraindications,
        confidence=round(min(0.95, max(0.45, float(expr.get("confidence", 0.5))) + 0.2 * expression_score), 3),
        explanation=explanation,
    )


def select_best_e3(
    candidates: List[str],
    cell_line: str = "default",
    target_localization: str = "nuclear",
    target: str = "",
) -> Dict[str, Any]:
    """Score all candidates and return the best with a comparison explanation.

    The explanation is derived from component scores, not LLM intuition:
    e.g. 'CRBN preferred over VHL because CRBN has higher expression in MM1.S
    (1.0 vs 0.2) and stronger contextual support (0.85 vs 0.72), despite VHL
    having better structural availability (1.0 vs 0.9).'
    """
    results = [score_e3(e, cell_line, target_localization, target) for e in candidates]
    if not results:
        return {"best": None, "results": [], "explanation": ""}
    results.sort(key=lambda r: -r.total_context_score)
    best = results[0]
    second = results[1] if len(results) > 1 else None

    parts = [f"{best.e3_ligase} preferred over "
             + (second.e3_ligase if second else "alternatives")
             + f" because {best.e3_ligase} has "
             + _comparison_phrase(best, second, "expression_score", "expression")
             + f" and stronger contextual support ({best.total_context_score:.2f} vs "
             + (f"{second.total_context_score:.2f}" if second else "—")
             + ")"]
    if second and best.structural_support_score < second.structural_support_score:
        parts.append(
            f"despite {second.e3_ligase} having better structural availability "
            f"({second.structural_support_score:.2f} vs {best.structural_support_score:.2f})"
        )
    return {
        "best": best,
        "results": results,
        "explanation": " ".join(parts),
    }


def _comparison_phrase(best, second, attr: str, noun: str) -> str:
    if second is None:
        return f"the strongest {noun} evidence ({getattr(best, attr):.2f})"
    b = getattr(best, attr)
    s = getattr(second, attr)
    if b > s:
        return f"higher {noun} ({b:.2f} vs {s:.2f})"
    if b < s:
        return f"comparable {noun} despite lower score ({b:.2f} vs {s:.2f})"
    return f"equal {noun} ({b:.2f})"
