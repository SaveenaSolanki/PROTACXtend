"""
Unified degradation-model interface (Task 1 — one interface, many backends).
============================================================================

Backends (auto-selected, provenance always returned):
  1. chemprop      — trained D-MPNN ensemble + conformal + AD (DEFAULT when
                     the model exists; ρ=0.758 benchmark, 92% coverage)
  2. synglue       — SynGlue transformer (GROVER embeddings)
  3. heuristic     — MW-threshold fallback (explicitly labelled)

The interface returns one uniform dict; callers never know the backend.
The old entry points (tools/degradation_predictor.py, synglue_degradation.py)
remain as marked-legacy modules; this is the canonical path.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("protacpilot.degradation.interface")

DEFAULT_BACKEND_ORDER = ["chemprop", "synglue", "heuristic"]


def _chemprop_backend(smiles_list: List[str]) -> Optional[List[Dict[str, Any]]]:
    try:
        from protacxtend.tools.uncertainty_aware_prediction import predict_with_uncertainty
        return predict_with_uncertainty(smiles_list, use_conformal=True)
    except Exception as exc:
        logger.warning("chemprop backend failed: %s", exc)
        return None


def _synglue_backend(smiles_list: List[str]) -> Optional[List[Dict[str, Any]]]:
    try:
        from protacxtend.tools.synglue_degradation import predict_degradation_batch
        candidates = [{"candidate_id": f"c{i}", "full_protac_smiles": s} for i, s in enumerate(smiles_list)]
        results = predict_degradation_batch(candidates)
        return [
            {
                "dc50_nM": r.get("dc50_nM"),
                "dmax_pct": r.get("dmax_pct"),
                "verdict": "medium_confidence",
                "confidence": 0.5,
                "model": r.get("model", "synglue"),
            }
            for r in results
        ]
    except Exception as exc:
        logger.warning("synglue backend failed: %s", exc)
        return None


def _heuristic_backend(smiles_list: List[str]) -> List[Dict[str, Any]]:
    from protacxtend.tools.synglue_degradation import _heuristic_single
    results = []
    for s in smiles_list:
        r = _heuristic_single(s)
        results.append({
            "dc50_nM": r.get("dc50_nM"),
            "dmax_pct": r.get("dmax_pct"),
            "verdict": "low_confidence",
            "confidence": 0.2,
            "model": "heuristic",
        })
    return results


def predict_degradation(
    smiles_list: List[str],
    backend: str = "auto",
    require_ad: bool = True,
) -> Dict[str, Any]:
    """Unified degradation prediction.

    backend: "auto" | "chemprop" | "synglue" | "heuristic"
    Returns {predictions: [...], backend_used, provenance: {tool_version},
             degraded_fallback: bool}
    """
    order = {
        "auto": DEFAULT_BACKEND_ORDER,
        "chemprop": ["chemprop"],
        "synglue": ["synglue"],
        "heuristic": ["heuristic"],
    }.get(backend, DEFAULT_BACKEND_ORDER)

    for name in order:
        fn = {
            "chemprop": _chemprop_backend,
            "synglue": _synglue_backend,
            "heuristic": _heuristic_backend,
        }[name]
        if name == "heuristic":
            results = fn(smiles_list)
        else:
            results = fn(smiles_list)
        if results is not None:
            return {
                "predictions": results,
                "backend_used": name,
                "degraded_fallback": name == "heuristic",
                "provenance": {"tool": f"degradation:{name}", "version": "v1"},
            }

    return {
        "predictions": [],
        "backend_used": "none",
        "degraded_fallback": True,
        "provenance": {"tool": "degradation:none", "version": "v1"},
    }


def degradation_backend_status() -> Dict[str, Any]:
    """Which backends are available (for UI + provenance)."""
    import os
    from protacxtend.tools.chemprop_degradation import chemprop_available
    from protacxtend.tools.synglue_degradation import check_models_available as _sg

    chemprop = chemprop_available()
    synglue_models = _sg()
    return {
        "chemprop": {"available": chemprop, "note": "trained D-MPNN ensemble + conformal + AD (preferred)"},
        "synglue": {"available": synglue_models.get("multitask_transformer", False),
                     "note": "SynGlue transformer (GROVER)"},
        "heuristic": {"available": True, "note": "MW-threshold fallback — clearly labelled"},
        "preferred": "chemprop" if chemprop else ("synglue" if synglue_models.get("multitask_transformer") else "heuristic"),
    }
