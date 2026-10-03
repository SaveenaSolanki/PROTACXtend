"""TUI scientific command semantics repair — quality tests (§17).

Proves, on fresh bridge processes:
- PLAN: ordered stages, evidence requirements, gates, planned tools, persistence
- INVESTIGATE: evidence synthesis (not counts only), evidence-backed statements,
  limitations/gaps
- REASON: WHY_WORKS != WHY_FAILS routing; no generic failure-template leakage;
  evidence chain + explicit uncertainty
- CONTEXT: follow-up commands preserve target/E3; E3 replacement edits only E3;
  no leakage across conversations
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

os.environ.setdefault("PROTACXTEND_PLANNER_OFFLINE", "1")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HARNESS = r"""
import json, sys, warnings
warnings.filterwarnings("ignore")
import protacxtend.tui_bridge.server as server
caps = []
server.emit = lambda p: caps.append(p)
for msg in sys.stdin:
    if not msg.strip():
        continue
    m = json.loads(msg)
    server.handle_command(m.pop("type"), m)
print(json.dumps(caps, default=str))
"""


def bridge(seq: list[dict]) -> list[dict]:
    inp = "\n".join(json.dumps(m) for m in seq) + "\n"
    p = subprocess.run([sys.executable, "-c", HARNESS], input=inp, capture_output=True,
                       text=True, cwd=ROOT, env={**os.environ, "PROTACXTEND_PLANNER_OFFLINE": "1"},
                       timeout=600)
    assert p.returncode == 0, p.stderr[-800:]
    return json.loads(p.stdout.strip().splitlines()[-1])


def first(evs: list[dict], type_: str) -> dict:
    return next(e for e in evs if isinstance(e, dict) and e.get("type") == type_)


def plan_answers(evs: list[dict]) -> list[dict]:
    return [e for e in evs if isinstance(e, dict) and e.get("type") == "plan_answer"]


def query(cmd: str, request: str, conversation_id: str = "t") -> list[dict]:
    return bridge([{"type": cmd, "request": request, "conversation_id": conversation_id}])


# ────────────────────────────── PLAN ──────────────────────────────
class TestPlanDepth:
    def test_plan_has_ordered_scientific_stages(self):
        evs = query("plan", "EGFR protac with CRBN", "p1")
        p = first(evs, "plan_answer")
        secs = p.get("plan_sections") or {}
        stages = secs.get("workflow_stages") or []
        assert len(stages) >= 5, "plan must contain >= 5 ordered scientific stages"
        nums = [s["stage"].split(".")[0] for s in stages]
        assert nums == [str(i) for i in range(1, len(nums) + 1)], "stages must be ordered"

    def test_plan_contains_evidence_requirements(self):
        p = first(plan_answers(query("plan", "BRD4 protac with VHL", "p2")), "plan_answer")
        secs = p.get("plan_sections") or {}
        assert secs.get("evidence_required"), "evidence requirements required"
        assert any("binder" in str(e).lower() or "precedent" in str(e).lower()
                   for e in secs["evidence_required"])

    def test_plan_contains_gates(self):
        p = first(plan_answers(query("plan", "EGFR protac with CRBN", "p3")), "plan_answer")
        secs = p.get("plan_sections") or {}
        assert secs.get("decision_gates"), "decision gates required"
        assert all(any(g.get("gate") for s in secs["workflow_stages"] for g in [s]) for s in
                   secs["workflow_stages"] if s.get("tasks"))

    def test_plan_contains_tools_and_capabilities(self):
        p = first(plan_answers(query("plan", "BRD4 protac with VHL", "p4")), "plan_answer")
        secs = p.get("plan_sections") or {}
        assert secs.get("planned_tools"), "planned tools required"
        assert secs.get("planned_backend_capabilities"), "planned backend capabilities required"

    def test_plan_is_persisted(self):
        p = first(plan_answers(query("plan", "EGFR protac with CRBN", "p5")), "plan_answer")
        path = p.get("plan_object_path")
        assert path and os.path.exists(path), f"plan object not persisted: {path}"
        obj = json.load(open(path))
        for k in ("plan_id", "request_id", "objective", "entities", "stages", "dependencies",
                  "gates", "tools", "expected_outputs", "status"):
            assert k in obj, f"persisted plan missing {k}"


# ─────────────────────────── INVESTIGATE ───────────────────────────
class TestInvestigateSynthesis:
    def test_investigate_returns_findings_not_counts_only(self):
        evs = query("investigate", "why EGFR is a good target", "i1")
        p = first(evs, "research_answer")
        secs = p.get("sections") or []
        titles = [s.get("title") for s in secs]
        assert any("KNOWN DEGRADERS" in t for t in titles)
        assert any("BOTTOM" in t or "GAPS" in t for t in titles)
        all_text = " ".join(st.get("text", "") for s in secs for st in s.get("statements", []))
        assert "measured degradation row" in all_text  # synthesis wording, not just counts

    def test_investigate_evidence_backed_statements(self):
        evs = query("investigate", "BRD4 degradation landscape", "i2")
        p = first(evs, "research_answer")
        secs = p.get("sections") or []
        evidence = [e for s in secs for e in s.get("evidence", [])]
        assert evidence, "evidence rows required"
        assert any("verified" == e.get("tier") and e.get("source") for e in evidence)

    def test_investigate_returns_limitations_gaps(self):
        p = first(query("investigate", "HMGB2 for targeted degradation", "i3"), "research_answer")
        secs = p.get("sections") or []
        titles = " ".join(str(s.get("title")) for s in secs)
        assert "EVIDENCE GAPS" in titles
        limitation = any(st.get("tier") == "limitation" for s in secs for st in s.get("statements", []))
        assert limitation


# ────────────────────────────── REASON ─────────────────────────────
class TestReasonIntents:
    def test_why_works_vs_why_fails_routes(self):
        works = first(query("reason", "why BRD4 and CRBN works", "r1"), "diagnosis_answer")
        fails = first(query("reason", "why this degrader failed", "r2"), "diagnosis_answer")
        assert works.get("intent") == "WHY_WORKS"
        assert fails.get("intent") == "WHY_FAILS"
        w_titles = " ".join(s.get("title", "") for s in (works.get("sections") or []))
        f_titles = " ".join(s.get("title", "") for s in (fails.get("sections") or []))
        assert "HYPOTHESIS FAMILIES" not in w_titles
        assert "HYPOTHESIS FAMILIES" in f_titles

    def test_positive_query_no_generic_failure_hypotheses(self):
        evs = query("reason", "why BRD4 and CRBN works", "r3")
        p = first(evs, "diagnosis_answer")
        text = " ".join(st.get("text", "") for s in (p.get("sections") or [])
                        for st in s.get("statements", []))
        assert "formation is impaired" not in text.lower()
        assert "permeability / uptake" not in text.lower()
        assert p.get("case", "").upper().startswith("BRD4")

    def test_reasoning_includes_evidence_chain(self):
        p = first(query("reason", "why EGFR could be degraded", "r4"), "diagnosis_answer")
        secs = p.get("sections") or []
        assert len(secs) >= 4, "evidence chain requires >= 4 sections"
        assert p.get("conclusion"), "conclusion required"
        evidence = [e for s in secs for e in s.get("evidence", [])]
        assert evidence, "evidence rows required"

    def test_reasoning_uncertainty_explicit(self):
        p = first(query("reason", "why BRD4 and CRBN works", "r5"), "diagnosis_answer")
        titles = " ".join(s.get("title", "") for s in (p.get("sections") or []))
        assert "FALSIFIER" in titles.upper() or "UNCERTAINT" in titles.upper()


# ────────────────────────────── CONTEXT ─────────────────────────────
class TestContext:
    def test_followup_preserves_target_e3(self):
        seq = [
            {"type": "plan", "request": "EGFR protac with CRBN", "conversation_id": "c1"},
            {"type": "reason", "request": "why this E3 makes sense", "conversation_id": "c1"},
            {"type": "investigate", "request": "known degraders", "conversation_id": "c1"},
        ]
        evs = bridge(seq)
        reason = first(evs, "diagnosis_answer")
        assert reason.get("case", "").upper().startswith("EGFR")
        assert "(CRBN)" in reason.get("case", "")
        inv = first(evs, "research_answer")
        tgt = (inv.get("state") or {}).get("target") or {}
        assert tgt.get("symbol") == "EGFR"

    def test_e3_replacement_edits_only_e3(self):
        seq = [
            {"type": "plan", "request": "EGFR protac with CRBN", "conversation_id": "c2"},
            {"type": "context", "action": "set_e3", "e3": "VHL", "conversation_id": "c2"},
            {"type": "reason", "request": "why this E3 makes sense", "conversation_id": "c2"},
        ]
        evs = bridge(seq)
        ctx = first(evs, "context_answer")
        assert ctx.get("old_e3") == "CRBN" and ctx.get("new_e3") == "VHL"
        assert ctx.get("context", {}).get("target_symbol") == "EGFR"  # target untouched
        reason = first(evs, "diagnosis_answer")
        assert "(VHL)" in reason.get("case", "")

    def test_no_leakage_between_conversations(self):
        seq = [
            {"type": "plan", "request": "EGFR protac with CRBN", "conversation_id": "cA"},
            {"type": "plan", "request": "BRD4 protac with VHL", "conversation_id": "cB"},
            {"type": "reason", "request": "why this E3 makes sense", "conversation_id": "cA"},
        ]
        evs = bridge(seq)
        reason = first(evs, "diagnosis_answer")
        assert reason.get("case", "").upper().startswith("EGFR")
        assert "(CRBN)" in reason.get("case", "")


# ─────────────── generic template leakage audit (§12) ───────────────
class TestGenericTemplateAudit:
    def test_different_queries_produce_distinct_outputs(self):
        a = first(query("reason", "why BRD4 and CRBN works", "g1"), "diagnosis_answer")
        b = first(query("reason", "EGFR is a good target", "g2"), "diagnosis_answer")
        c = first(query("reason", "why candidate X failed", "g3"), "diagnosis_answer")
        texts = []
        for p in (a, b, c):
            texts.append(" ".join(st.get("text", "") for s in (p.get("sections") or [])
                                  for st in s.get("statements", [])))
        assert texts[0] != texts[1], "BRD4 and EGFR reasoning must differ"
        assert a.get("case", "").upper().startswith("BRD4")
        assert b.get("case", "").upper().startswith("EGFR")
        assert c.get("intent") == "WHY_FAILS"
        assert texts[2] != texts[0]
        # no query may emit the identical generic failure trio
        for t in texts:
            assert not ("formation is impaired" in t.lower()
                        and "permeability / uptake" in t.lower()
                        and "e3 recruitment" in t.lower()), "generic boilerplate trio leaked"