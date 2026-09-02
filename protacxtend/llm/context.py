"""
Context control (A6 / guidance #5).
===================================

Never send all ChEMBL/literature records to the model. Retrieve only
relevant evidence, summarize completed steps into structured state, and
cap what the LLM sees at ~16-32K effective context.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

MAX_EVIDENCE_CHARS = 6000          # cap per evidence payload to the LLM
MAX_RECORDS_PER_SOURCE = 5         # never dump full lists


def summarize_evidence(evidence: Dict[str, Any], max_chars: int = MAX_EVIDENCE_CHARS) -> str:
    """Serialize evidence to a compact structured summary for the LLM.

    - numeric/verdict fields kept as-is
    - big lists truncated to MAX_RECORDS_PER_SOURCE with counts
    - SMILES lists truncated (the model never needs 100 SMILES)
    """
    if not evidence:
        return "{}"

    out: Dict[str, Any] = {}
    for key, value in evidence.items():
        if isinstance(value, list):
            out[key] = {
                "count": len(value),
                "preview": value[:MAX_RECORDS_PER_SOURCE],
            }
        elif isinstance(value, dict):
            # keep shallow numeric/string fields; truncate nested lists
            shallow = {k: v for k, v in value.items() if not isinstance(v, (list, dict))}
            out[key] = shallow
        else:
            out[key] = value

    text = json.dumps(out, default=str, sort_keys=True)
    if len(text) > max_chars:
        text = text[:max_chars] + "...[truncated]"
    return text


def retrieve_relevant_evidence(
    evidence: Dict[str, Any],
    keys: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Return only the requested evidence keys (default: all, but truncated)."""
    if keys is None:
        return evidence
    return {k: evidence[k] for k in keys if k in evidence}


def compact_state_for_llm(state: Dict[str, Any]) -> str:
    """Summarize completed workflow steps into structured state for the LLM.

    Includes: status, retry counts, decision log summary (count + last few
    entries), prediction verdicts — not raw records.
    """
    decision_log = state.get("decision_log", [])
    log_summary = {
        "count": len(decision_log),
        "last_3": [
            {
                "node": d.get("node") if isinstance(d, dict) else getattr(d, "node", None),
                "decision_type": d.get("decision_type") if isinstance(d, dict) else getattr(d, "decision_type", None),
                "next": d.get("next_proposed_node") if isinstance(d, dict) else getattr(d, "next_proposed_node", None),
            }
            for d in decision_log[-3:]
        ],
    }
    compact = {
        "status": state.get("status"),
        "pipeline_status": state.get("pipeline_status"),
        "retry_counts": state.get("retry_counts", {}),
        "n_candidates": len(state.get("valid_candidates", [])),
        "degradation_verdicts": [
            {k: p.get(k) for k in ("candidate_id", "verdict", "dc50_nM") if k in p}
            for p in state.get("degradation_predictions", [])[:5]
        ],
        "decision_log": log_summary,
        "warnings": state.get("warnings", [])[:5],
    }
    return json.dumps(compact, default=str, sort_keys=True)[:MAX_EVIDENCE_CHARS]
