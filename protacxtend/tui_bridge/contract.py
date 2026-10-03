"""Shared response contract for TUI/API/CLI terminal payloads.

Single source of truth for what counts as a scientific answer:

- ``ok``:      substantive result WITH evidence, OR an explicit evidence-gap
               conclusion (``evidence_gap_conclusion`` nonempty).
- ``hypothesis``: nonempty statement + rationale + discriminating test.
- ``plan``:    nonempty task list (plan_with_open_questions is still a plan).
- ``blocker``: a typed, actionable blocker (clarification question / status
               in {clarification_needed, blocked, unknown_symbol}) with no tasks.
- ``no_scientific_answer``: anything else. Resource-selection logs, progress
               events and the historical ``H ?`` placeholder are NEVER a
               scientific answer (they must not be rendered as one).

``annex`` computes the display annex (stage statuses + artifact paths) from a
terminal payload, and ``answer_text`` mirrors the Node TUI's visible lines so
that Python tests can assert what the user actually sees.
"""

from __future__ import annotations

import re
from typing import Any

LOG_ONLY_KEYS = {"resource_reason_summary", "progress", "chat_event", "tool_call", "tool_result"}
RESOURCE_LOG_MARKERS = re.compile(
    r"resource[- ]?reason|resource retrieval bounded|resource[- ]?selection"
)
H_QUESTION_GLYPH = "H ?"

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def strip_logs(text: str) -> str:
    """Remove ANSI, resource-selection log language and the H ? placeholder."""
    out = ANSI_RE.sub("", str(text))
    out = RESOURCE_LOG_MARKERS.sub("", out)
    out = out.replace(H_QUESTION_GLYPH, "")
    return out.strip()


def _clean(s: Any) -> str:
    return strip_logs(s)


def _typed_blocker(payload: dict[str, Any]) -> bool:
    q = str(payload.get("clarification_question") or payload.get("question") or "").strip()
    s = str(payload.get("status") or "")
    return bool(q) or s in ("clarification_needed", "blocked", "unknown_symbol")


def classify(payload: dict[str, Any]) -> dict[str, Any]:
    """Classify a terminal payload against the shared response contract."""
    ptype = payload.get("type")
    issues: list[str] = []
    kind = "no_scientific_answer"

    if ptype == "plan_answer":
        tasks = payload.get("tasks") or []
        if tasks:
            kind = "plan"
        elif _typed_blocker(payload):
            kind = "blocker"
        else:
            issues.append("plan_answer without tasks and without a typed blocker")
    elif ptype in ("research_answer", "investigate_answer"):
        findings = payload.get("findings")
        sf = payload.get("scientific_findings") or []
        gap = str(payload.get("evidence_gap_conclusion") or "").strip()
        if sf or findings or gap:
            kind = "ok"
        else:
            issues.append(
                "research/investigate answer without findings and without an "
                "explicit evidence-gap conclusion"
            )
    elif ptype == "run_answer":
        executed = payload.get("executed_stages") or []
        plan_id = payload.get("plan_id") or ""
        if executed and plan_id:
            kind = "execution"
        else:
            issues.append("run_answer without executed_stages+plan_id")
    elif ptype == "diagnosis_answer":
        sections = payload.get("sections") or []
        conclusion = payload.get("conclusion")
        if sections and conclusion:
            kind = "reasoning"
        else:
            hypotheses = payload.get("hypotheses") or []
            complete_hypotheses = []
            for h in hypotheses:
                statement = str(h.get("statement") or h.get("label") or h.get("title") or "").strip()
                rationale = str(h.get("rationale") or "").strip()
                tests = h.get("discriminating_tests") or []
                complete_hypotheses.append(bool(statement and rationale and tests))
            tests = payload.get("tests")
            answer_evidence = payload.get("scientific_direct_answer") or str(payload.get("evidence_gap_conclusion") or "").strip()
            if hypotheses and all(complete_hypotheses) and tests and answer_evidence:
                kind = "hypothesis"
            else:
                issues.append(
                    "diagnosis_answer missing sections+conclusion or hypothesis statement, "
                    "rationale, discriminating test, or direct evidence/evidence-gap conclusion"
                )
    else:
        issues.append(f"unhandled terminal payload type {ptype!r}")

    return {
        "kind": kind,
        "issues": issues,
        "type": ptype,
        "acceptable": kind != "no_scientific_answer",
    }


def annex(payload: dict[str, Any]) -> dict[str, Any]:
    """Display annex: stage statuses and persisted artifact paths."""
    stage_status: dict[str, str] = {}
    for s in payload.get("stage_timeline") or []:
        if isinstance(s, dict) and s.get("stage"):
            stage_status[str(s["stage"])] = str(s.get("status") or "unknown")
    for s in payload.get("stages") or []:
        if isinstance(s, dict) and s.get("stage"):
            stage_status[str(s["stage"])] = str(s.get("status") or "unknown")
    # research/investigate payloads: derive stage status from state + findings
    st = payload.get("state")
    if isinstance(st, dict):
        t = st.get("target")
        if isinstance(t, dict) and t.get("symbol"):
            stage_status["target_resolution"] = str(t.get("status") or "resolved")
        if st.get("clarification_pending"):
            stage_status["clarification"] = "pending"
    f = payload.get("findings")
    if isinstance(f, dict):
        if f.get("measured_precedent_rows") is not None:
            stage_status["evidence_retrieval"] = (
                f"completed ({f['measured_precedent_rows']} packaged precedent rows)")
        elif f.get("missing"):
            stage_status["evidence_retrieval"] = "missing: " + ", ".join(map(str, f["missing"]))
    # diagnosis payloads: row-level evidence stage
    direct = payload.get("scientific_direct_answer") or []
    if direct:
        stage_status["evidence_retrieval"] = f"completed ({len(direct)} evidence lines)"
    elif payload.get("evidence_gap_conclusion"):
        stage_status["evidence_retrieval"] = "completed (0 rows; explicit evidence-gap conclusion)"

    artifacts: list[str] = []
    ap = payload.get("artifact_paths")
    if isinstance(ap, dict):
        artifacts = [str(v) for v in ap.values() if v]
    files = payload.get("intermediate_files")
    if isinstance(files, dict):
        for v in files.values():
            v = str(v)
            if v and v not in artifacts:
                artifacts.append(v)
    if payload.get("evidence_graph"):
        eg = str(payload["evidence_graph"])
        if eg not in artifacts:
            artifacts.append(eg)
    return {"stage_status": stage_status, "artifacts": artifacts[:10]}


def answer_text(payload: dict[str, Any]) -> list[str]:
    """Visible scientific lines for a terminal payload (mirror of the Node TUI).

    Only scientific content; resource-selection/progress logs and the ``H ?``
    placeholder never appear.
    """
    ptype = payload.get("type")
    lines: list[str] = []
    if ptype == "plan_answer":
        interp = str(payload.get("interpretation") or "").strip()
        if interp:
            lines.append(interp)
        for t in (payload.get("tasks") or [])[:12]:
            tid = str(t.get("id") or t.get("task_id") or "?")
            title = str(t.get("title") or "").strip()
            ex = str(t.get("executor") or "").strip()
            suffix = f" (executor: {ex})" if ex else ""
            lines.append(f"TASK {tid} — {title}{suffix}")
        for q in (payload.get("open_questions") or [])[:4]:
            lines.append(f"OPEN {q}")
        if payload.get("execution_contract"):
            lines.append(f"CONTRACT {payload['execution_contract']}")
    elif ptype in ("research_answer", "investigate_answer"):
        for f in (payload.get("scientific_findings") or [])[:8]:
            lines.append(f"· {f}")
        gap = str(payload.get("evidence_gap_conclusion") or "").strip()
        if gap:
            lines.append(f"GAP {gap}")
        if not lines:
            lines.append("No substantive scientific result; evidence-gap conclusion required.")
    elif ptype == "diagnosis_answer":
        for d in (payload.get("scientific_direct_answer") or [])[:6]:
            lines.append(f"· {d}")
        gap = str(payload.get("evidence_gap_conclusion") or "").strip()
        if gap:
            lines.append(f"GAP {gap}")
        lines.append(f"CASE {str(payload.get('case') or '')}")
        for h in (payload.get("hypotheses") or [])[:6]:
            lines.append(f"H {str(h.get('label') or h.get('title') or '').strip()}")
        for t in (payload.get("tests") or [])[:3]:
            lines.append(f"TEST {str(t.get('test') or '').strip()}")
        if payload.get("recommended_action"):
            lines.append(f"ACTION {payload['recommended_action']}")
        if payload.get("gated"):
            lines.append(f"GATED {', '.join(str(g) for g in payload['gated'])}")
    return [l for l in lines if _clean(l)]


def describe(payload: dict[str, Any]) -> dict[str, Any]:
    """Convenience: classify + annex + answer_text in one dict."""
    cl = classify(payload)
    return {
        "contract": cl,
        "annex": annex(payload),
        "answer_text": answer_text(payload),
    }