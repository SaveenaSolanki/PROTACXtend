"""predict_cell_context — public Module 5 API + production artifact.

Artifact (default models/cell_context_model.joblib) is produced by
examples/train_demo.py after the benchmark chooses the best feature leg and
model per endpoint under strict grouped validation (see models.py). The
artifact stores per-endpoint fitted pipelines, entity/lineage encoders,
expression imputation, OOD references, and the claim-gating record.

Query-time behaviour is honest by construction:
* If the requested cell line has no mapped DepMap/expression profile, the
  transcriptomic features are marked ABSENT and imputed with training medians;
  the cell-context OOD flag is raised and the output carries an applicability
  warning (no fabricated context).
* degradation_probability is always the derived-threshold view (never called
  an experimental probability).
* Unknown target / E3 / cell names map to out-of-vocabulary codes and raise
  the corresponding OOD flag.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import joblib
import numpy as np
import pandas as pd

from synglue_agent.modules.cell_context_selector.features import MolCache
from synglue_agent.modules.cell_context_selector.schemas import MODEL_VERSION
from synglue_agent.modules.degradation_ml.features import murcko_group

logger = logging.getLogger("protacxtend.cell_context_predict")

MODULE_DIR = Path(__file__).resolve().parent
DEFAULT_MODEL_PATH = MODULE_DIR / "models" / "cell_context_model.joblib"


class CellContextModelError(ValueError):
    """Raised when required trained evidence/artifacts are missing."""


def _load(path):
    p = Path(path) if path else DEFAULT_MODEL_PATH
    if not p.exists():
        raise CellContextModelError(
            f"no trained cell-context model at {p} — run "
            "python -m synglue_agent.modules.cell_context_selector.examples."
            "train_demo to train on the curated cell-context dataset")
    return joblib.load(p)


def _knn_distance(x: np.ndarray, ref: np.ndarray, k: int = 5) -> float | None:
    if ref is None or len(ref) == 0:
        return None
    from sklearn.neighbors import NearestNeighbors
    nn = NearestNeighbors(n_neighbors=min(k, len(ref)), n_jobs=1)
    nn.fit(np.asarray(ref, float))
    d, _ = nn.kneighbors(np.asarray(x, float).reshape(1, -1))
    return float(np.mean(d[0]))


def predict_cell_context(protac: str, poi: str | None = None, e3: str | None = None,
                         cell_line: str = "", model_path=None,
                         resolve_name: bool = True) -> dict[str, Any]:
    """Predict per-cell-line degradation for a PROTAC.

    Returns a dict matching the spec (PredictionResult-compatible).
    """
    art = _load(model_path)
    cfg = art.get("config", {})
    leg = cfg.get("leg", "D")

    from synglue_agent.modules.cell_context_selector import omics, prepare
    from synglue_agent.modules.cell_context_selector.genemap import target_to_gene

    expr = omics.ensure_curated_expression()
    # --- resolve cell line ------------------------------------------------
    mapping = art.get("cell_line_table")
    mrow = None
    if mapping is not None:
        hit = mapping[mapping["cell_line_raw"].astype(str).str.lower()
                      == str(cell_line).strip().lower()]
        mrow = hit.iloc[0] if len(hit) else None
    depmap_id = mrow["depmap_id"] if mrow is not None else None
    lineage = mrow["lineage"] if mrow is not None else None
    has_expr = depmap_id in expr.index if depmap_id else False

    # --- molecular ---------------------------------------------------------
    mol = MolCache().get(protac)
    if float(np.abs(mol).sum()) == 0.0:
        raise CellContextModelError(f"RDKit could not parse SMILES {protac!r}")
    vocab = set(expr.columns)
    gene = target_to_gene(poi, vocab) if poi else None

    # --- assemble a one-row frame in the training schema -------------------
    row = pd.DataFrame([{
        "protac_smiles_canonical": protac, "target": poi or "",
        "e3": e3 or "unknown", "cell_line_raw": cell_line,
        "depmap_id": depmap_id if has_expr else None,
        "lineage": lineage, "target_gene": gene,
        "has_expression": int(has_expr),
    }])
    from synglue_agent.modules.cell_context_selector import features as F
    enc = art.get("encoders", {})
    lin = enc.get("lin_enc")
    X, names = F.build_row_features(
        row, leg, MolCache(), expr,
        enc_target=enc.get("enc_target"), enc_e3=enc.get("enc_e3"),
        enc_cell=enc.get("enc_cell"), lin_enc=lin)
    X = np.asarray(X, float)
    if leg == "D":
        imp = art.get("imputer")
        if imp is not None:
            X = imp.transform(X)
    has_expr_vec = X[:, -1] if leg == "D" else np.zeros(1)

    out: dict[str, Any] = {"model": MODEL_VERSION,
                           "model_path": str(art.get("model_path",
                                                     DEFAULT_MODEL_PATH))}
    # --- per-endpoint predictions ------------------------------------------
    ood: dict[str, Any] = {}
    for endp in ("pdc50", "dmax", "derived_active"):
        e = art.get(endp)
        if e is None:
            continue
        sc = e.get("scaler")
        Xe = sc.transform(X) if sc is not None else X
        est = e["estimator"]
        if endp == "derived_active":
            p = float(np.asarray(est.predict_proba(Xe))[0, 1])
            out["degradation_probability"] = round(p, 4)
        else:
            p = float(np.asarray(est.predict(Xe)).ravel()[0])
            if endp == "pdc50":
                out["predicted_pdc50"] = round(p, 4)
                out["predicted_DC50_nM"] = round(float(10.0 ** (-p) * 1e9), 3)
                rq = e.get("residual_quantiles", {})
                if rq:
                    lo = 10.0 ** (-(p + rq.get("p95", 0.5))) * 1e9
                    hi = 10.0 ** (-(p + rq.get("p5", -0.5))) * 1e9
                    out.setdefault("uncertainty", {})["dc50_interval_nM"] = [
                        round(min(lo, hi), 3), round(max(lo, hi), 3)]
            else:
                out["predicted_Dmax_pct"] = round(float(np.clip(p, 0, 100)), 3)
            std = None
            if hasattr(est, "estimators_"):
                import sklearn.ensemble  # noqa
                leaf_pred = np.asarray([t.predict(Xe) for t in est.estimators_])
                std = float(np.std(leaf_pred, axis=0)[0])
            out.setdefault("uncertainty", {})[f"{endp}_model_spread"] = (
                round(std, 4) if std is not None else None)
    # --- OOD axes -----------------------------------------------------------
    mol_ref = art.get("mol_ref")
    mdist = _knn_distance(mol, mol_ref) if mol_ref is not None else None
    mean_mol = art.get("mean_mol_distance")
    protac_ood = bool(mdist is not None and mean_mol and mdist > 3 * mean_mol)
    scaff = murcko_group(protac)
    scaff_known = scaff in art.get("scaffolds", set())
    cell_ood = (not has_expr) or bool(
        mrow is not None and depmap_id not in art.get("train_cells", set()))
    if mrow is None:
        cell_ood = True
    ent = art.get("encoders", {})
    tgt_ood = bool(ent.get("enc_target") and
                   (poi or "").strip().lower() not in
                   ent["enc_target"].vocab)
    e3_ood = bool(ent.get("enc_e3") and
                  (e3 or "unknown").strip().lower() not in
                  ent["enc_e3"].vocab)
    ood = {"protac_molecular": bool(protac_ood),
           "protac_scaffold_unseen": bool(not scaff_known),
           "target_unseen": bool(tgt_ood),
           "e3_unseen": bool(e3_ood),
           "cell_line_unseen_or_no_context": bool(cell_ood)}
    out["ood_flags"] = ood
    flags_on = [k for k, v in ood.items() if v]
    # --- applicability -------------------------------------------------------
    out["applicability"] = {
        "overall": "CAUTION" if flags_on else "SUPPORTED",
        "flags": flags_on,
        "cell_line_mapped": bool(mrow is not None),
        "expression_context_present": bool(has_expr),
        "leg": leg,
    }
    out["cell_context_features_used"] = (
        ["lineage", "expression_panel", "poi_expression"] if leg == "D" else
        ["cell_identity_code"] if leg == "C" else [])
    out["mechanistic_features_used"] = (
        art.get("mechanistic_features_used", []))
    out["claims"] = art.get("claims", {})
    out["limitations"] = art.get("limitations", [])
    out["status"] = "SUPPORTED"
    return out
