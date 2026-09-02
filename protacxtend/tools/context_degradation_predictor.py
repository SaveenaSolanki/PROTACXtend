"""Context-aware degradation prediction adapter stack."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from protacxtend.tools.uncertainty_aware_prediction import predict_single_with_uncertainty


@dataclass
class ContextDegradationResult:
    candidate_id: str
    status: str
    p_active: float
    pdc50_pred: float | None
    dmax_pred: float | None
    uncertainty: float
    ood_flags: list[str] = field(default_factory=list)
    calibration_bin: str = "unavailable"
    model_votes: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    backend: str = "protacxtend_context_degradation_adapter_v0.1"

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


def _tack_worker(queue: Any, smiles: str, e3: str, cell: str, poi: str) -> None:
    try:
        from protacxtend.tools.tack_degradation import predict_tack_degradation

        queue.put({"ok": True, "result": predict_tack_degradation(smiles, e3=e3, cell=cell, poi=poi)})
    except Exception as exc:
        queue.put({"ok": False, "error": str(exc)})


def _predict_tack_bounded(smiles: str, e3: str, cell: str, poi: str, timeout_s: float = 12.0) -> dict[str, Any]:
    import multiprocessing as mp

    ctx = mp.get_context("fork")
    queue: Any = ctx.Queue()
    proc = ctx.Process(target=_tack_worker, args=(queue, smiles, e3, cell, poi))
    proc.start()
    proc.join(timeout_s)
    if proc.is_alive():
        proc.terminate()
        proc.join(2.0)
        return {"ok": False, "timeout": True, "error": f"TACK prediction exceeded {timeout_s:.1f}s timeout."}
    if queue.empty():
        return {"ok": False, "error": "TACK prediction produced no result."}
    return queue.get()


def predict_context_degradation(
    smiles: str,
    candidate_id: str = "candidate",
    e3: str = "",
    cell: str = "",
    poi: str = "",
) -> ContextDegradationResult:
    votes: list[dict[str, Any]] = []
    warnings: list[str] = []
    tack_payload = _predict_tack_bounded(smiles, e3=e3, cell=cell, poi=poi)
    tack = tack_payload.get("result") if tack_payload.get("ok") else None
    if tack:
        votes.append({"model": "TACK-style", **tack})
        if tack.get("provenance", {}).get("compatibility_warning"):
            warnings.append(tack["provenance"]["compatibility_warning"])
    else:
        warnings.append(tack_payload.get("error") or "TACK-style local model unavailable; degradation vote omitted.")
    unc = predict_single_with_uncertainty(smiles)
    if unc.get("reason") != "no_model":
        votes.append({"model": "chemprop_uncertainty", **unc})
    else:
        warnings.append("Chemprop ensemble unavailable; uncertainty vote omitted.")

    p_values = []
    dmax_values = []
    pdc50 = None
    ood_flags: list[str] = []
    for vote in votes:
        if "active_prob" in vote:
            p_values.append(float(vote["active_prob"]))
        if "dmax_pct" in vote:
            dmax_values.append(float(vote["dmax_pct"]))
        if "dc50_nM" in vote and vote["dc50_nM"]:
            import math

            pdc50 = -math.log10(float(vote["dc50_nM"]) * 1e-9)
        if vote.get("ad_status") in {"out_of_domain", "far"} or vote.get("verdict") == "low_confidence":
            ood_flags.append("chemical_applicability_domain")
    p_active = round(sum(p_values) / len(p_values), 3) if p_values else 0.0
    dmax = round(sum(dmax_values) / len(dmax_values), 2) if dmax_values else None
    uncertainty = round(1.0 - min([p_active, 1.0 - p_active, 0.5]) * 2.0, 3) if p_values else 1.0
    status = "SUPPORTED" if p_active >= 0.65 and uncertainty <= 0.7 else "INSUFFICIENT EVIDENCE" if not votes else "REVISE"
    return ContextDegradationResult(
        candidate_id=candidate_id,
        status=status,
        p_active=p_active,
        pdc50_pred=round(pdc50, 3) if pdc50 is not None else None,
        dmax_pred=dmax,
        uncertainty=uncertainty,
        ood_flags=sorted(set(ood_flags)),
        calibration_bin="calibrated_adapter" if votes else "unavailable",
        model_votes=votes,
        warnings=warnings,
    )
