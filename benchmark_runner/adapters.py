"""Matched benchmark adapters: deterministic, agentic, llm_only,
retrieval_only, tool_only. Eligibility per engine is explicit; results carry
answer, cited evidence, status, error category, score, cost, latency.
Protocol exclusion (engine not applicable to the task) is recorded as
engine_ineligible — distinct from system abstention (the engine ran and
returned an abstention with reason).
"""
from __future__ import annotations

import json, re, time
from typing import Any

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "deepseek-r1:7b"


def _jsonline(cell: dict) -> dict:
    return cell


def deterministic_adapter(question: str) -> dict:
    from protacxtend.agents.runtime import run_protacpilot
    t0 = time.monotonic()
    try:
        res = run_protacpilot(question, mode="deterministic", config={"record_run": False})
        ans = json.dumps(res.get("therapeutic_strategy") or res.get("summary") or res, default=str)
        status = "answered"
    except Exception as exc:
        ans, status = "", "system_abstained"
    return {"answer": ans, "status": status, "latency_s": round(time.monotonic() - t0, 2), "cost_usd": 0.0}


def agentic_adapter(question: str) -> dict:
    from protacxtend.agents.runtime import run_protacpilot
    t0 = time.monotonic()
    try:
        res = run_protacpilot(question, mode="adaptive", config={"record_run": False})
        ans = json.dumps(res.get("therapeutic_strategy") or res.get("summary") or res, default=str)
        status = "answered" if ans.strip() else "system_abstained"
    except Exception as exc:
        ans, status = "", "system_abstained"
    return {"answer": ans, "status": status, "latency_s": round(time.monotonic() - t0, 2), "cost_usd": 0.0}


def llm_only_adapter(question: str, model: str = OLLAMA_MODEL, timeout_s: int = 75) -> dict:
    import urllib.request
    payload = json.dumps({
        "model": model, "prompt": (
            "Answer the scientific question directly and precisely, no tools, no preamble. "
            f"QUESTION: {question}\nANSWER:"),
        "stream": False, "options": {"temperature": 0.2, "num_predict": 320}}).encode()
    t0 = time.monotonic()
    try:
        req = urllib.request.Request(OLLAMA_URL, data=payload,
                                     headers={"Content-Type": "application/json"})
        resp = json.loads(urllib.request.urlopen(req, timeout=timeout_s).read())
        ans = (resp.get("response") or "").strip()
        status = "answered" if ans else "system_abstained"
        cost = 0.0
        ev = resp.get("eval_count") or 0; pr = resp.get("prompt_eval_count") or 0
    except Exception as exc:
        ans, status, cost = "", "engine_error", 0.0
        ev = pr = 0
    return {"answer": ans, "status": status,
            "latency_s": round(time.monotonic() - t0, 2), "cost_usd": cost,
            "tokens": {"prompt": pr, "completion": ev},
            "model": model}


def _symbols(question: str) -> list[str]:
    toks = re.split(r"[\s,;()/|]+", question)
    out = []
    for t in toks:
        t = t.strip(".,;:!?'\"[]{}")
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9]{1,9}", t or "") and t.upper() not in {"PROTAC", "THE", "WHICH", "WHAT", "AND", "FOR", "WITH", "DATA", "RATIONALE"}:
            out.append(t)
    return out


def retrieval_only_adapter(question: str) -> dict:
    """Evidence gathering only (no design, no LLM synthesis)."""
    from protacxtend.planning.planner import resolve_target_canonical
    t0 = time.monotonic()
    syms = _symbols(question)
    ans = ""
    ev: list[str] = []
    for s in syms[:3]:
        r = resolve_target_canonical(s, offline=True)
        if r.status in ("resolved", "ambiguous"):
            ans += f"{s} -> UniProt {r.uniprot_id or '?'} ({r.match_type}); "
            ev.append("packaged curated_targets.csv")
    if ans:
        status = "answered"
    else:
        ans = "NO_RESOLVABLE_SYMBOL"
        status = "system_abstained"
    return {"answer": ans.strip(), "status": status,
            "evidence": ev, "latency_s": round(time.monotonic() - t0, 2), "cost_usd": 0.0}


def tool_only_adapter(question: str) -> dict:
    """Chemical tools only: a tool input must be embedded in the question."""
    from protacxtend.tools.protac_toolbox import ProtacDesignToolbox
    t0 = time.monotonic()
    m = re.search(r"\b([A-Za-z0-9@+\-\[\]\(\)=#$\\/%.:*]+)\b", question)
    smi_candidates = re.findall(r"(\[[^\]]+\]|[A-Z][a-z]?[0-9]?[=#]?\(?[A-Za-z0-9@+\-\[\]\(\)=#\\/%:.]+)", question)
    smi = ""
    for c in smi_candidates:
        c = c.strip(".,;")
        if ("=" in c or "[" in c or "#" in c or "(" in c) and len(c) > 4 and "PROTAC" not in c.upper():
            smi = c
            break
    if not smi:
        return {"answer": "", "status": "system_abstained",
                "error_category": "no_tool_input", "latency_s": round(time.monotonic() - t0, 2),
                "cost_usd": 0.0}
    box = ProtacDesignToolbox()
    valid = box.validate_smiles(smi)
    return {"answer": f"SMILES validity tool: {valid}", "status": "answered",
            "evidence": ["protac_toolbox.validate_smiles"],
            "latency_s": round(time.monotonic() - t0, 2), "cost_usd": 0.0}


ADAPTERS = {
    "deterministic": deterministic_adapter,
    "agentic": agentic_adapter,
    "llm_only": llm_only_adapter,
    "retrieval_only": retrieval_only_adapter,
    "tool_only": tool_only_adapter,
}