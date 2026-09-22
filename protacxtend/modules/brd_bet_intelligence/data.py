"""BRD/BET domain-aware knowledge — data layer.

Loads the curated, provenance-carrying BRD/BET ligand + domain-selectivity
evidence table built by ``scripts/gap_completion/curate_brd_bet.py``.

Every row is a single measured affinity (or a pair split into BD1/BD2 with the
domain ordering flagged ``inferred_pair_order``). Nothing is imputed. The
``evidence_level`` column distinguishes measured values from any future
inferred/proxy value.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

MODULE_DIR = Path(__file__).resolve().parent
DATA_DIR = MODULE_DIR / "data"
EVIDENCE_CSV = DATA_DIR / "brd_bet_ligand_evidence.csv"
PAIRS_CSV = DATA_DIR / "brd_bet_bd1_bd2_pairs.csv"
SUMMARY_CSV = DATA_DIR / "brd_bet_domain_summary.csv"
PROVENANCE_JSON = DATA_DIR / "brd_bet_provenance.json"

# canonical BET bromodomain genes targeted by the intelligence layer
BET_GENES = ("BRD2", "BRD3", "BRD4", "BRDT")

_cache: dict[str, pd.DataFrame] = {}


def load_evidence() -> pd.DataFrame:
    if "evidence" not in _cache:
        _cache["evidence"] = (pd.read_csv(EVIDENCE_CSV)
                              if EVIDENCE_CSV.exists() else pd.DataFrame())
    return _cache["evidence"].copy()


def load_pairs() -> pd.DataFrame:
    if "pairs" not in _cache:
        _cache["pairs"] = (pd.read_csv(PAIRS_CSV)
                           if PAIRS_CSV.exists() else pd.DataFrame())
    return _cache["pairs"].copy()


def load_summary() -> pd.DataFrame:
    if "summary" not in _cache:
        _cache["summary"] = (pd.read_csv(SUMMARY_CSV)
                             if SUMMARY_CSV.exists() else pd.DataFrame())
    return _cache["summary"].copy()


def provenance() -> dict[str, Any]:
    if PROVENANCE_JSON.exists():
        return json.loads(PROVENANCE_JSON.read_text())
    return {}


def is_bet_target(gene: str | None) -> bool:
    return bool(gene) and str(gene).strip().upper() in BET_GENES


def canonical_gene(gene: str | None) -> str | None:
    if not gene:
        return None
    g = str(gene).strip().upper()
    aliases = {"BRD4": "BRD4", "BRD2": "BRD2", "BRD3": "BRD3", "BRDT": "BRDT",
               "BRD4-S": "BRD4", "BRD4-L": "BRD4", "BROMODOMAIN": None}
    return aliases.get(g, g if g in BET_GENES else None)
