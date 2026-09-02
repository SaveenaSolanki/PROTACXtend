"""Feature builders for Module 5 ablation legs (A-F).

Legs (each documented; molecular features reused from Module 4 so the two
modules share a featurizer):
  A  PROTAC molecular only          (8 RDKit descriptors + ECFP4-1024)
  B  A + target code + E3 code      (entity encoders fit on train folds only)
  C  B + cell-line identity code    (explicitly NOT a selectivity claim)
  D  B + transcriptomic cell-state  (lineage one-hot + DepMap 24Q4 TPM panel
                                     + row POI expression + expression flag)
  E  + proteomics                   -> NOT AVAILABLE (no DepMap proteomics
                                     matrix; reported, never fabricated)
  F  + mechanistic Modules 1-3      -> structure/parameter-limited (22 rows
                                     reference a ternary PDB; Module 1 needs
                                     measured Kds); reported as a census, not
                                     used in dataset-scale ablations.

Molecular features for a given canonical SMILES are computed once and cached.
Entity/lineage vocabularies and any imputation/scaling are fit on the training
fold only (no leakage).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd

from synglue_agent.modules.degradation_ml.features import (
    EntityEncoder,
    featurize_molecule,
    murcko_group,
)

MOL_DIM = 8 + 1024
LEGS = ("A", "B", "C", "D")

# lineage vocabulary used for the D leg one-hot (fit on train; capped)
MAX_LINEAGES = 14


class MolCache:
    """Deterministic per-SMILES molecular feature cache."""

    def __init__(self) -> None:
        self._cache: dict[str, np.ndarray] = {}

    def get(self, smiles: str) -> np.ndarray:
        v = self._cache.get(smiles)
        if v is None:
            v, ok = featurize_molecule(smiles)
            v = v if ok else np.zeros(MOL_DIM, dtype=float)
            self._cache[smiles] = v
        return v

    def matrix(self, smiles_list: Iterable[str]) -> np.ndarray:
        return np.vstack([self.get(s) for s in smiles_list])


class LineageEncoder:
    """One-hot for the top lineages; fit on train, OOV-safe (all-zero)."""

    def __init__(self, max_lineages: int = MAX_LINEAGES) -> None:
        self.max_lineages = max_lineages
        self.vocab: list[str] = []

    def fit(self, lineages: Iterable[str]) -> LineageEncoder:
        counts = pd.Series([str(x) if x is not None and x == x else "unknown"
                            for x in lineages]).value_counts()
        known = [x for x in counts.index if x != "unknown"]
        self.vocab = known[: self.max_lineages]
        return self

    def transform(self, lineages: Iterable[str]) -> np.ndarray:
        rows = []
        for x in lineages:
            lab = str(x) if x is not None and x == x else "unknown"
            row = np.zeros(len(self.vocab), dtype=float)
            if lab in self.vocab:
                row[self.vocab.index(lab)] = 1.0
            rows.append(row)
        return np.vstack(rows)


def _expr_for_row(expr: pd.DataFrame, depmap_id, gene: str | None) -> float:
    if gene is None or depmap_id is None or gene not in expr.columns:
        return np.nan
    try:
        return float(expr.at[depmap_id, gene])
    except Exception:
        return np.nan


def context_columns(expr: pd.DataFrame) -> list[str]:
    return [c for c in expr.columns]


def build_row_features(rows: pd.DataFrame, leg: str, mol_cache: MolCache,
                       expr: pd.DataFrame,
                       enc_target: EntityEncoder | None = None,
                       enc_e3: EntityEncoder | None = None,
                       enc_cell: EntityEncoder | None = None,
                       lin_enc: LineageEncoder | None = None,
                       ) -> tuple[np.ndarray, list[str]]:
    """Assemble the design matrix for the given rows (single fold).

    rows must carry: protac_smiles_canonical, target, e3, cell_line_raw,
    depmap_id, lineage (+ target_gene for the D leg).
    """
    mol = mol_cache.matrix(rows["protac_smiles_canonical"].tolist())
    parts = [mol]
    names: list[str] = []
    for i in range(MOL_DIM):
        names.append(f"mol_{i}")
    if leg in ("B", "C", "D"):
        if enc_target is None or enc_e3 is None:
            raise ValueError(f"leg {leg} requires target/e3 encoders")
        parts.append(enc_target.transform(rows["target"].fillna("unknown")
                                          .astype(str).tolist()).reshape(-1, 1))
        names += ["code_target"]
        parts.append(enc_e3.transform(rows["e3"].fillna("unknown")
                                      .astype(str).tolist()).reshape(-1, 1))
        names += ["code_e3"]
    if leg in ("C", "D"):
        if enc_cell is None:
            raise ValueError(f"leg {leg} requires a cell-line encoder")
        parts.append(enc_cell.transform(
            rows["cell_line_raw"].astype(str).tolist()).reshape(-1, 1))
        names += ["code_cell"]
    if leg == "D":
        if lin_enc is None:
            raise ValueError("leg D requires a lineage encoder")
        lin = lin_enc.transform(rows["lineage"].tolist())
        parts.append(lin)
        names += [f"lineage_{c}" for c in lin_enc.vocab]
        # fixed machinery panel + POI expression
        expr_cols = context_columns(expr)
        exprs = np.full((len(rows), len(expr_cols) + 2), np.nan)
        has_tg = "target_gene" in rows.columns
        for i, (_, r) in enumerate(rows.iterrows()):
            did = r.get("depmap_id")
            tg = r.get("target_gene") if has_tg else None
            if did is not None and did in expr.index:
                exprs[i, : len(expr_cols)] = expr.loc[did, expr_cols].to_numpy(
                    dtype=float)
                if isinstance(tg, str) and tg in expr.columns:
                    exprs[i, len(expr_cols)] = float(expr.at[did, tg])
                exprs[i, len(expr_cols) + 1] = 1.0  # context present
        parts.append(exprs)
        names += [f"expr_{c}" for c in expr_cols]
        names += ["expr_target_poi", "has_expression"]
    X = np.hstack(parts).astype(float)
    return X, names


def fit_encoders(rows: pd.DataFrame, leg: str) -> dict[str, Any]:
    """Fit the per-fold entity/lineage encoders on TRAIN rows only."""
    out: dict[str, Any] = {}
    if leg in ("B", "C", "D"):
        out["enc_target"] = (EntityEncoder().fit(
            rows["target"].fillna("unknown").astype(str).tolist()))
        out["enc_e3"] = EntityEncoder().fit(
            rows["e3"].fillna("unknown").astype(str).tolist())
    if leg in ("C", "D"):
        out["enc_cell"] = EntityEncoder().fit(
            rows["cell_line_raw"].astype(str).tolist())
    if leg == "D":
        out["lin_enc"] = LineageEncoder().fit(rows["lineage"].tolist())
    return out
