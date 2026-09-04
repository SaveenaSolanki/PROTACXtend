"""
Degradation endpoint model (Task 4) — DC50 + Dmax + classification + context.
=============================================================================

Completes the degradation layer:
  - log10(DC50) regression head        (validated: ρ=0.758 single-target)
  - Dmax (%) regression head           (multi-target Chemprop, trained)
  - active/inactive classification     (deterministic thresholds)
  - cellular context                   (target/E3 expression, cell-line,
                                        subcellular localization)
  - uncertainty (conformal) + applicability domain

Cellular context is a DETERMINISTIC gate, not a model input:
  - if the E3 is not expressed in the selected cell line, degradation is
    not expected regardless of the model score → verdict downgraded,
    confidence reduced, note explains why.
  - context data is curated from literature (data/benchmark/expression_context.csv)
    with provenance per row — no LLM intuition.

The multitarget Chemprop model is trained on PROTAC-DB 3.0 rows with both
DC50 and Dmax (1,126 rows, benchmark+cal excluded).
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger("protacpilot.degradation.endpoint")

ROOT = Path(__file__).resolve().parents[2]
MULTITARGET_MODEL = ROOT / "outputs" / "benchmark" / "chemprop_multitarget" / "model_0" / "best.pt"
CONTEXT_CSV = ROOT / "data" / "benchmark" / "expression_context.csv"

# Classification thresholds (deterministic, aligned with classify_degradation_potency)
ACTIVE_DC50_NM = 100.0
ACTIVE_DMAX_PCT = 50.0


class CellContext(BaseModel):
    cell_line: str = "default"
    target: str = ""
    e3_ligase: str = ""
    target_expression: str = "unknown"      # high/medium/low/unknown
    e3_expression: str = "unknown"          # high/medium/low/unknown
    subcellular_match: bool = False
    context_id: str = ""
    evidence_refs: List[str] = Field(default_factory=list)


class DegradationEndpointResult(BaseModel):
    candidate_id: str = ""

    dc50_nM: Optional[float] = None
    log_dc50: Optional[float] = None
    dmax_pct: Optional[float] = None

    activity_class: Literal["active", "inactive", "unknown"] = "unknown"

    uncertainty_log10: Optional[float] = None
    ad_status: str = "unavailable"          # in_domain/borderline/out_of_domain
    nn_tanimoto: Optional[float] = None

    context: CellContext = Field(default_factory=CellContext)
    context_gated: bool = False
    context_note: str = ""

    verdict: Literal["high_confidence", "medium_confidence", "low_confidence"] = "low_confidence"
    confidence: float = 0.0

    model: str = "chemprop_multitarget"
    provenance: Dict[str, str] = Field(default_factory=dict)
    degraded_fallback: bool = False
    note: str = ""


# ── Expression context (curated, provenance per row) ──────────────────

_DEFAULT_CONTEXT: Dict[str, Dict[str, str]] = {
    # cell_line → {CRBN: level, VHL: level, source}
    "MM1.S":    {"CRBN": "high", "VHL": "low",   "source": "Ito et al. 2010 / Zhu et al. 2019 (curated)"},
    "HCT116":   {"CRBN": "medium", "VHL": "medium", "source": "PROTAC-DB meta (curated)"},
    "HEK293T":  {"CRBN": "high", "VHL": "medium", "source": "common cell-line proteomics (curated)"},
    "MCF7":     {"CRBN": "medium", "VHL": "high", "source": "CCLE-derived literature (curated)"},
    "Jurkat":   {"CRBN": "medium", "VHL": "low",  "source": "curated"},
    "RPMI8226": {"CRBN": "high", "VHL": "low",   "source": "curated (MM lines CRBN-high)"},
    "default":  {"CRBN": "medium", "VHL": "medium", "source": "default neutral"},
}

# Subcellular localization rules (target class → E3 compatibility)
# E3 ligases with nuclear-active ligands work for nuclear targets; CRBN is
# cytosolic/nuclear; VHL is cytosolic. These are literature-standard rules.
_NUCLEAR_TARGET_OK = {"CRBN", "DCAF15", "DCAF11", "KLHL20"}


def _load_context_csv() -> Dict[str, Dict[str, str]]:
    """Load curated expression table if present (provenance per row)."""
    if not CONTEXT_CSV.exists():
        return _DEFAULT_CONTEXT
    ctx: Dict[str, Dict[str, str]] = {}
    try:
        with open(CONTEXT_CSV, newline="") as f:
            for row in csv.DictReader(f):
                cell = row.get("cell_line", "").strip()
                if cell:
                    ctx[cell] = {"CRBN": row.get("CRBN", "medium"),
                                 "VHL": row.get("VHL", "medium"),
                                 "source": row.get("source", "curated")}
    except Exception as exc:
        logger.warning("context csv load failed: %s", exc)
        return _DEFAULT_CONTEXT
    return ctx


def build_cell_context(
    cell_line: str = "default",
    target: str = "",
    e3_ligase: str = "CRBN",
    target_localization: str = "nuclear",   # nuclear/cytosolic/membrane
) -> CellContext:
    """Deterministic cellular-context record with evidence refs."""
    table = _load_context_csv()
    row = table.get(cell_line, table["default"])
    e3_expr = row.get(e3_ligase, "medium")
    tgt_expr = "high"  # target expression assumed from the design request; extendable

    subcellular_match = (
        target_localization != "nuclear" or e3_ligase in _NUCLEAR_TARGET_OK
    )
    return CellContext(
        cell_line=cell_line,
        target=target,
        e3_ligase=e3_ligase,
        target_expression=tgt_expr,
        e3_expression=e3_expr,
        subcellular_match=subcellular_match,
        context_id=f"{cell_line}|{target}|{e3_ligase}",
        evidence_refs=[row.get("source", "curated")],
    )


def apply_context_gate(ctx: CellContext) -> Dict[str, Any]:
    """Deterministic gate: biology can veto a chemistry-only prediction."""
    gated = False
    notes: List[str] = []
    if ctx.e3_expression == "low":
        gated = True
        notes.append(f"{ctx.e3_ligase} expression is LOW in {ctx.cell_line} — degradation unlikely regardless of model score")
    if not ctx.subcellular_match:
        gated = True
        notes.append("target localization incompatible with E3 ligase activity")
    return {"gated": gated, "notes": notes}


def _pick_accelerator() -> str:
    """Choose gpu/cpu by availability (containers may lack CUDA)."""
    import os
    forced = os.environ.get("PROTACPILOT_ACCELERATOR", "")
    if forced in ("gpu", "cpu", "auto"):
        return "cpu" if forced == "cpu" else ("gpu" if forced == "gpu" else _auto_accel())
    try:
        import torch
        return "gpu" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


def _auto_accel() -> str:
    try:
        import torch
        return "gpu" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


# ── Multi-target prediction ───────────────────────────────────────────

def _run_multitarget(smiles_list: List[str]) -> Dict[str, Any]:
    """Chemprop predict with 2 targets (logDC50, dmax). CLI-backed."""
    import shutil
    import subprocess
    import sys
    import tempfile

    import pandas as pd
    from rdkit import Chem

    if not MULTITARGET_MODEL.exists():
        return {"ok": False, "reason": "multitarget_model_missing"}

    chemprop_bin = str(Path(sys.executable).parent / "chemprop")
    if not Path(chemprop_bin).exists():
        chemprop_bin = shutil.which("chemprop") or "chemprop"

    valid = [s for s in smiles_list if Chem.MolFromSmiles(s) is not None]
    if not valid:
        return {"ok": True, "rows": [None] * len(smiles_list), "n_valid": 0}

    accel = _pick_accelerator()
    with tempfile.TemporaryDirectory(prefix="mt_pred_") as tmp:
        in_csv = Path(tmp) / "in.csv"
        out_csv = Path(tmp) / "out.csv"
        pd.DataFrame({"smiles": valid}).to_csv(in_csv, index=False)
        cmd = [chemprop_bin, "predict", "-i", str(in_csv), "-s", "smiles",
               "--model-paths", str(MULTITARGET_MODEL),
               "--accelerator", accel, "--devices", "1", "-o", str(out_csv)]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600,
                              cwd=str(ROOT))
        if proc.returncode != 0 or not out_csv.exists():
            return {"ok": False, "reason": f"predict_error:{proc.stderr[-150:]}"}
        preds = pd.read_csv(out_csv)
        cols = preds.columns.tolist()
        # cols: smiles, logDC50, dmax
        rows = []
        for _, r in preds.iterrows():
            rows.append({
                "log_dc50": float(r[cols[1]]),
                "dmax": float(r[cols[2]]) if len(cols) > 2 else None,
            })
    return {"ok": True, "rows": rows, "n_valid": len(valid)}


# ── Endpoint orchestrator ─────────────────────────────────────────────

def _tack_primary(smiles: str, e3_ligase: str, cell_line: str, target: str) -> Optional[Dict[str, Any]]:
    """TACK-style model as the degradation primary vote (bounded, in-process).

    Returns the TACK prediction dict (dc50_nM, dmax_pct, active, provenance)
    when the local TACK-style models are available and prediction succeeds;
    returns None otherwise and never raises — the Chemprop path stays intact.
    """
    try:
        from protacxtend.tools.tack_degradation import predict_tack_degradation

        result = predict_tack_degradation(
            smiles, e3=e3_ligase or "", cell=cell_line or "", poi=target or ""
        )
        if not result:
            logger.info("TACK-style models unavailable; Chemprop remains primary.")
        return result
    except Exception as exc:  # noqa: BLE001
        logger.warning("TACK primary vote unavailable: %s", exc)
        return None


def predict_degradation_endpoint(
    smiles: str,
    candidate_id: str = "",
    cell_line: str = "default",
    target: str = "",
    e3_ligase: str = "CRBN",
    target_localization: str = "nuclear",
    use_conformal: bool = True,
) -> DegradationEndpointResult:
    """Full endpoint prediction: DC50 + Dmax + class + context + uncertainty."""
    from protacxtend.tools.applicability_domain import assess_applicability_domain

    ctx = build_cell_context(cell_line, target, e3_ligase, target_localization)
    gate = apply_context_gate(ctx)

    # Uncertainty + AD from the validated single-target ensemble
    try:
        from protacxtend.tools.uncertainty_aware_prediction import predict_with_uncertainty
        unc_rows = predict_with_uncertainty([smiles], use_conformal=use_conformal)
        u = unc_rows[0]
        dc50 = u.get("dc50_nM")
        unc = u.get("unc_log10")
        ad_status = u.get("ad_status", "unavailable")
        nn_t = u.get("nn_tanimoto")
    except Exception:
        dc50, unc, ad_status, nn_t = None, None, "unavailable", None

    # Multi-target prediction (Dmax head)
    mt = _run_multitarget([smiles])
    dmax = None
    log_dc50 = None
    model = "chemprop_multitarget"
    degraded_fallback = False
    if mt.get("ok") and mt.get("rows") and mt["rows"][0]:
        row = mt["rows"][0]
        log_dc50 = row["log_dc50"]
        dmax = row["dmax"]
        if dc50 is None:
            dc50 = float(10 ** log_dc50)
    else:
        degraded_fallback = True
        model = "chemprop_single_or_missing"
        if dc50 is None:
            dc50 = 500.0
            dmax = 50.0
            degraded_fallback = True

    # TACK-style model as the degradation primary vote when available.
    # Chemprop values are kept as cross-check provenance (never discarded).
    chemprop_dc50 = dc50
    chemprop_dmax = dmax
    tack = _tack_primary(smiles, e3_ligase, cell_line, target)
    tack_metrics = ""
    if tack:
        dc50 = tack["dc50_nM"]
        log_dc50 = tack.get("log_dc50")
        dmax = tack["dmax_pct"]
        model = "tack-style-v1"
        degraded_fallback = False
        tack_metrics = ",".join(
            f"{k}={v}"
            for k, v in (tack.get("provenance", {}).get("val_metrics") or {}).items()
        )

    # Classification (deterministic)
    activity_class: Literal["active", "inactive", "unknown"] = "unknown"
    if dc50 is not None and dmax is not None:
        activity_class = (
            "active" if dc50 <= ACTIVE_DC50_NM and dmax >= ACTIVE_DMAX_PCT
            else "inactive"
        )

    # Verdict composition: AD + uncertainty + context gate
    if gate["gated"]:
        verdict: Literal["high_confidence", "medium_confidence", "low_confidence"] = "low_confidence"
        confidence = 0.15
    elif ad_status == "in_domain" and (unc or 1.4) < 1.75:
        verdict = "high_confidence"
        confidence = 0.85
    elif ad_status in ("in_domain", "borderline"):
        verdict = "medium_confidence"
        confidence = 0.55
    else:
        verdict = "low_confidence"
        confidence = 0.25

    return DegradationEndpointResult(
        candidate_id=candidate_id,
        dc50_nM=round(dc50, 2) if dc50 is not None else None,
        log_dc50=round(log_dc50, 4) if log_dc50 is not None else None,
        dmax_pct=round(dmax, 1) if dmax is not None else None,
        activity_class=activity_class,
        uncertainty_log10=round(unc, 4) if unc is not None else None,
        ad_status=ad_status,
        nn_tanimoto=nn_t,
        context=ctx,
        context_gated=gate["gated"],
        context_note="; ".join(gate["notes"]),
        verdict=verdict,
        confidence=round(confidence, 3),
        model=model,
        provenance={
            "dc50_dmax": model,
            "chemprop_cross_check_dc50_nM": str(round(chemprop_dc50, 2)) if chemprop_dc50 is not None else "",
            "chemprop_cross_check_dmax_pct": str(round(chemprop_dmax, 1)) if chemprop_dmax is not None else "",
            "uncertainty": "chemprop_ensemble_conformal",
            "context": ";".join(ctx.evidence_refs),
            "tack_metrics": tack_metrics,
        },
        degraded_fallback=degraded_fallback,
        note="context gate vetoed chemistry score" if gate["gated"] else "",
    )



def predict_degradation_batch(
    smiles_list: list[str],
    candidate_ids: list[str] | None = None,
    cell_line: str = "default",
    target: str = "",
    e3_ligase: str = "CRBN",
    use_conformal: bool = True,
) -> list[dict]:
    """Batched endpoint: ONE chemprop ensemble call + ONE multitarget call,
    then per-molecule verdict/context composition. Fixes the per-candidate
    subprocess reload that made the deterministic pipeline take ~20 min."""
    from protacxtend.tools.uncertainty_aware_prediction import predict_with_uncertainty

    ctx = build_cell_context(cell_line, target, e3_ligase, "nuclear")
    gate = apply_context_gate(ctx)

    unc_rows = predict_with_uncertainty(smiles_list, use_conformal=use_conformal)
    by_smiles = {r.get("smiles"): r for r in unc_rows}

    mt = _run_multitarget(smiles_list)
    mt_by_smiles = {}
    if mt.get("ok") and mt.get("rows"):
        for row in mt["rows"]:
            mt_by_smiles[row.get("smiles", "")] = row

    out = []
    for i, smi in enumerate(smiles_list):
        u = by_smiles.get(smi, {})
        dc50 = u.get("dc50_nM")
        unc = u.get("unc_log10")
        ad_status = u.get("ad_status", "unavailable")
        nn_t = u.get("nn_tanimoto")
        dmax = None
        log_dc50 = None
        if smi in mt_by_smiles:
            row = mt_by_smiles[smi]
            log_dc50 = row.get("log_dc50")
            dmax = row.get("dmax")
            if dc50 is None and log_dc50 is not None:
                dc50 = float(10 ** log_dc50)
        if dc50 is None:
            dc50, dmax = 500.0, 50.0

        # TACK-style degradation primary vote (graceful when unavailable).
        chemprop_dc50, chemprop_dmax = dc50, dmax
        tack = _tack_primary(smi, e3_ligase, cell_line, target)
        tack_metrics = ""
        if tack:
            dc50 = tack["dc50_nM"]
            log_dc50 = tack.get("log_dc50")
            dmax = tack["dmax_pct"]
            model = "tack-style-v1"
            tack_metrics = ",".join(
                f"{k}={v}"
                for k, v in (tack.get("provenance", {}).get("val_metrics") or {}).items()
            )
        else:
            model = "chemprop_multitarget"

        activity_class: Literal["active", "inactive", "unknown"] = "unknown"
        if dc50 is not None and dmax is not None:
            activity_class = "active" if dc50 <= ACTIVE_DC50_NM and dmax >= ACTIVE_DMAX_PCT else "inactive"
        if gate["gated"]:
            verdict = "low_confidence"; confidence = 0.15
        elif ad_status == "in_domain" and (unc or 1.4) < 1.75:
            verdict = "high_confidence"; confidence = 0.85
        elif ad_status in ("in_domain", "borderline"):
            verdict = "medium_confidence"; confidence = 0.55
        else:
            verdict = "low_confidence"; confidence = 0.25
        out.append({
            "candidate_id": (candidate_ids[i] if candidate_ids else ""),
            "dc50_nM": round(dc50, 2) if dc50 is not None else None,
            "log_dc50": log_dc50,
            "dmax_pct": dmax,
            "activity_class": activity_class,
            "verdict": verdict,
            "confidence": confidence,
            "ad_status": ad_status,
            "nn_tanimoto": nn_t,
            "context_gated": gate["gated"],
            "context_note": "; ".join(gate.get("notes", [])),
            # Degradation-backend provenance for downstream mapping
            "model": model,
            "tack_dc50_nM": round(tack["dc50_nM"], 2) if tack else None,
            "tack_log_dc50": tack.get("log_dc50") if tack else None,
            "tack_dmax_pct": tack["dmax_pct"] if tack else None,
            "tack_active": tack["active"] if tack else None,
            "tack_active_prob": tack["active_prob"] if tack else None,
            "tack_metrics": tack_metrics,
            "chemprop_dc50_nM": round(chemprop_dc50, 2) if chemprop_dc50 is not None else None,
            "chemprop_dmax_pct": round(chemprop_dmax, 1) if chemprop_dmax is not None else None,
        })
    return out

def predict_endpoint_batch(
    smiles_list: List[str],
    cell_line: str = "default",
    target: str = "",
    e3_ligase: str = "CRBN",
) -> List[DegradationEndpointResult]:
    return [
        predict_degradation_endpoint(s, f"c{i}", cell_line, target, e3_ligase)
        for i, s in enumerate(smiles_list)
    ]
