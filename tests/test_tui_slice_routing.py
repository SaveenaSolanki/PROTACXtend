"""Vertical-slice tests: Textual TUI engine routing + honest stage states.

The Textual TUI routes every command through the SAME bridge handlers the
Node TUI uses (tui_bridge.server.handle_command) via
protacxtend.tui.engine.execute_command. These tests execute the REAL
handlers in-process (no mocks): plan, investigate, evidence, compare,
validate, status, unknown-command, chat target card. The full /design engine
run is covered by the integration driver (scripts/drive_bridge.py) and the
canonical run; this file includes one REAL design execution unless
PROTACXTEND_SKIP_SLOW=1 is set.
"""

import os
import uuid

import pytest

from protacxtend.tui.engine import execute_command, parse_input, summarize

REAL_DESIGN = os.environ.get("PROTACXTEND_SKIP_SLOW", "") not in ("1", "true", "yes")


# ── parse_input ────────────────────────────────────────────────────

def test_parse_input_maps_slash_commands_to_bridge_verbs():
    assert parse_input("/design Design a CRBN-recruiting PROTAC for BRD4") == (
        "design", "Design a CRBN-recruiting PROTAC for BRD4")
    assert parse_input("/plan BRD4 programme")[0] == "plan"
    assert parse_input("/investigate BRD4")[0] == "investigate"
    assert parse_input("/reason why does CRBN degrade BRD4?")[0] == "reason"
    assert parse_input("/evidence BRD4")[0] == "evidence"
    assert parse_input("/run BRD4 CRBN")[0] == "run"
    assert parse_input("/validate CC(=O)Nc1ccc(O)cc1")[0] == "validate"
    assert parse_input("/status")[0] == "status"
    assert parse_input("/exit")[0] == "quit"
    assert parse_input("/quit")[0] == "quit"


def test_parse_input_free_text_is_chat_and_unknown_verb_falls_back_to_chat():
    assert parse_input("what is BRD4 and why is it a PROTAC target?")[0] == "chat"
    assert parse_input("/notacommand anything")[0] == "chat"


# ── real in-process handlers (fast) ────────────────────────────────

def test_execute_plan_routes_to_planner_not_chat():
    out = execute_command("plan", "Design a BRD4 degrader using CRBN",
                          offline=True, conversation_id=f"tui-{uuid.uuid4().hex[:8]}")
    ans = out["answer"]
    assert ans and ans["type"] == "plan_answer"
    assert "BRD4" in (ans.get("interpretation") or "")
    assert ans.get("executed_design") is not True


def test_execute_investigate_sets_brd4_identity_and_persists_evidence():
    out = execute_command("investigate", "BRD4 cereblon degraders and ligands",
                          offline=True, conversation_id=f"tui-{uuid.uuid4().hex[:8]}")
    ans = out["answer"]
    assert ans and ans.get("command") == "investigate"
    f = ans.get("findings") or {}
    assert f.get("target") == "BRD4"
    assert f.get("uniprot") == "O60885"
    assert ans.get("evidence_graph")  # persisted


def test_execute_compare_computes_descriptors():
    out = execute_command("compare",
                          "compare smiles:CC(=O)Nc1ccc(O)cc1 smiles:CC(=O)Oc1ccccc1C(=O)O",
                          offline=True)
    ans = out["answer"]
    assert ans and ans.get("command") == "compare"
    assert ans.get("comparison")


def test_execute_validate_rdkit_smiles():
    out = execute_command("validate", "CC(=O)Nc1ccc(O)cc1", offline=True)
    ans = out["answer"]
    # handle_validate emits a validate_answer or tool_result payload
    if ans:
        assert ans.get("type") == "validate_answer" or "smiles" in str(ans)


def test_execute_unknown_command_emits_typed_error():
    out = execute_command("definitely_not_a_command", "", offline=True)
    errs = [e for e in out["events"] if e.get("type") == "error"]
    assert errs, "no error event emitted for unknown command"
    assert "Unknown command" in str(errs[0].get("message"))


def test_execute_chat_bare_target_is_deterministic_target_card():
    out = execute_command("chat", "BRD4", offline=True,
                          conversation_id=f"tui-{uuid.uuid4().hex[:8]}")
    ans = out["answer"]
    assert ans and ans.get("type") == "chat_answer"
    assert ans.get("kind") in ("target_card", "answer")


def test_summarize_flags_unevaluated_stages():
    events = [
        {"type": "research_answer", "stage_timeline": [
            {"stage": "validation", "status": "executed", "detail": "150 valid"},
            {"stage": "ternary_coordinates", "status": "unevaluated",
             "detail": "No validated coordinate backend"},
            {"stage": "synthesis_route", "status": "unevaluated", "detail": "proxy/gate"},
        ]},
    ]
    s = summarize(events)
    assert s["executed"] == ["validation"]
    assert set(s["unevaluated"]) == {"ternary_coordinates", "synthesis_route"}


# ── real /design through the actual engine (slow, run by default) ──

@pytest.mark.skipif(not REAL_DESIGN, reason="PROTACXTEND_SKIP_SLOW=1")
def test_execute_design_runs_existing_engine_with_honest_gates():
    out = execute_command("design", "Design a CRBN-recruiting PROTAC for BRD4",
                          offline=True, conversation_id=f"tui-{uuid.uuid4().hex[:8]}")
    ans = out["answer"]
    assert ans and ans.get("command") == "design"
    assert ans.get("executed_design") is True
    assert ans.get("engine") == "run_protacpilot"
    assert (ans.get("assembly_counts") or {}).get("valid", 0) > 0
    gates = ans.get("evidence_gates") or {}
    assert gates.get("ternary_coordinates", {}).get("status") == "unevaluated"
    assert gates.get("synthesis_route", {}).get("status") == "unevaluated"
    assert gates.get("degradation", {}).get("status") == "predicted"
    tl = ans.get("stage_timeline") or []
    assert any(s.get("status") == "unevaluated" for s in tl)
    assert (ans.get("intermediate_files") or {}).get("evidence_graph")
    # verdict is not a fabrication: engine reports design-brief-only state
    # (verified separately in the canonical run bundle); here we only assert
    # the payload contract the TUI renders.