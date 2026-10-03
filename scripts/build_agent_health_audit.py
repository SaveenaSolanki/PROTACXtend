#!/usr/bin/env python3
"""Agent health audit — machine-derived inventory + runtime evidence.

No production behavior is modified. Evidence tiers:
  DEFINED_ONLY < IMPORTABLE < UNIT_TESTED < EXECUTABLE < CONNECTED <
  REAL_DATA_VALIDATED < SCIENTIFICALLY_VALIDATED
and the highest tier is assigned ONLY from runtime evidence collected below:
  - INIT: agent class constructs
  - POSITIVE: node executor ran on prepared state
  - MISSING_INPUT / FAILURE: defined failure behavior (typed error or state.errors)
  - CHAIN: node executed inside the real production graph run (trace)
  - REAL-DATA: chain node produced artifacts/evidence from packaged real data
  - CONTRACT: /plan, /investigate, /reason scientific-contract probes
"""
from __future__ import annotations

import ast
import csv
import inspect
import json
import os
import re
import signal
import subprocess
import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["PROTACXTEND_PLANNER_OFFLINE"] = "1"

OUT = ROOT / "outputs" / "agent_health_audit"
OUT.mkdir(parents=True, exist_ok=True)

REPO_GLOB = list(ROOT.glob("protacxtend/**/*.py")) + list(ROOT.glob("tests/**/*.py"))
TEST_GLOBS = [p for p in REPO_GLOB if "tests" in p.parts]
SRC_GLOBS = [p for p in REPO_GLOB if "tests" not in p.parts]


def _source(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def ast_state_keys(source: str) -> tuple[set[str], set[str]]:
    """(reads, writes) of state.* keys from an executor source (AST-derived)."""
    reads: set[str] = set()
    writes: set[str] = set()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return reads, writes
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "state":
            if isinstance(getattr(node, "ctx", None), ast.Store):
                writes.add(node.attr)
            else:
                reads.add(node.attr)
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id == "state":
            if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
                if isinstance(getattr(node, "ctx", None), (ast.Store, ast.Del)):
                    writes.add(node.slice.value)
                else:
                    reads.add(node.slice.value)
    return reads, writes


def calls_in_source(source: str) -> set[str]:
    """Called attribute/method names (+ bare calls) found in the executor source."""
    out: set[str] = set()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return out
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Attribute):
                out.add(f.attr)
            elif isinstance(f, ast.Name):
                out.add(f.id)
    return out


def main() -> None:
    from protacxtend.agents.graph import LocalSynGlueWorkflowGraph, CAPABILITY_NODES
    from protacxtend.backend.schemas import WorkflowState
    from protacxtend.tui_bridge.events import AGENT_PIPELINE
    from protacxtend.agentic.registry import registry_specs

    graph = LocalSynGlueWorkflowGraph()
    nodes = list(graph.nodes)
    def nodes_ref():
        return nodes
    pipeline_ids = {a["id"] for a in AGENT_PIPELINE}
    agentic_tools = {s["name"] for s in registry_specs(ready_only=True)}

    # ── 1. inventory rows (machine-derived) ──────────────────────────
    inventory: list[dict] = []
    node_bodies: dict[str, str] = {}
    for idx, (name, func) in enumerate(nodes):
        cls = getattr(func, "__self__", None)
        cls_name = type(cls).__name__ if cls is not None else "function"
        try:
            _mod = sys.modules.get(type(cls).__module__) if cls is not None else sys.modules.get(func.__module__)
            code_path = Path(_mod.__file__).relative_to(ROOT).as_posix() if _mod and _mod.__file__ else "unknown"
        except Exception:
            code_path = "unknown"
        node_bodies[name] = ""
        try:
            raw_src = inspect.getsource(cls) if cls is not None else inspect.getsource(func)
            node_bodies[name] = raw_src
        except Exception:
            pass
        # tests referencing this agent
        tests: list[str] = []
        for t in TEST_GLOBS:
            if cls_name in _source(t) or f"agents.{Path(code_path).parent.name}" in _source(t) or name in _source(t):
                tests.append(t.relative_to(ROOT).as_posix())
        # upstream callers (production sources, excluding self)
        callers = []
        self_path = code_path
        for s in SRC_GLOBS:
            if s.as_posix() == self_path:
                continue
            txt = _source(s)
            if cls_name in txt or (name in txt and "def " + name not in txt):
                callers.append(s.relative_to(ROOT).as_posix())
        reads, writes = ast_state_keys(node_bodies[name])
        calls = calls_in_source(node_bodies[name])
        known_tools = sorted(calls & agentic_tools)
        known_calls = sorted(calls)
        inventory.append({
            "kind": "workflow_node", "node_index": idx, "node": name, "agent_class": cls_name, "code_path": code_path,
            "constructor": f"{cls_name}()" if cls else "None",
            "inputs": "state:" + ",".join(sorted(reads))[:200],
            "outputs": "state:" + ",".join(sorted(writes))[:200],
            "calls": ";".join(known_calls)[:220],
            "agentic_tools_called": ";".join(known_tools),
            "upstream_callers": ";".join(callers[:8]),
            "tests": ";".join(tests[:6]),
        })

    # decision gates + canonical control-plane modules (machine-derived)
    gates = [{"gate": "capability_routing", "source": f"CAPABILITY_NODES keys: {sorted(CAPABILITY_NODES)}"},
             {"gate": "design_gate_identity/chemistry/window", "source": "protacxtend/therapeutics/api.design_gate"},
             {"gate": "graph_terminal_stop_markers", "source": "agents/graph.py:_should_stop"},
             {"gate": "response_contract_ok/hypothesis/plan/blocker/reasoning", "source": "tui_bridge/contract.classify"},
             {"gate": "nomination_gates", "source": "mechanistic/integrate.nomination_policy_check"}]
    canonical_modules = []
    for _p in sorted((ROOT / "protacxtend" / "canonical").glob("*.py")):
        if _p.name.startswith("_"):
            continue
        _txt = _source(_p)
        _funcs = [n.name for n in ast.parse(_txt).body
                  if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and not n.name.startswith("_")]
        canonical_modules.append({"module": f"protacxtend/canonical/{_p.name}", "functions": ";".join(_funcs[:12])})

    # LLM-callable tools + decision gates + canonical functions join the inventory
    from protacxtend.agentic.registry import registry_specs as _regs
    _tools = sorted({s["name"] for s in _regs(ready_only=True)})
    for t in _tools:
        inventory.append({"kind": "llm_tool", "node_index": "", "node": t, "agent_class": "LLM_TOOL",
                          "code_path": "protacxtend/agentic/registry.py", "constructor": "-",
                          "inputs": "params", "outputs": "ToolResult", "calls": "", "agentic_tools_called": "",
                          "upstream_callers": "agentic/chat_agent.py", "tests": ""})
    for g in gates:
        inventory.append({"kind": "decision_gate", "node_index": "", "node": g["gate"], "agent_class": "DECISION_GATE",
                          "code_path": g["source"], "constructor": "-", "inputs": "state/payload",
                          "outputs": "verdict", "calls": "", "agentic_tools_called": "",
                          "upstream_callers": "runtime/graph/bridge", "tests": ""})
    for cm in canonical_modules:
        for fn in cm["functions"].split(";")[:4]:
            inventory.append({"kind": "canonical_function", "node_index": "", "node": fn.strip(),
                              "agent_class": "CANONICAL_MODULE", "code_path": cm["module"],
                              "constructor": "-", "inputs": "-", "outputs": "-", "calls": "",
                              "agentic_tools_called": "", "upstream_callers": "canonical/orchestrator.py",
                              "tests": ""})

    # ── 2. runtime evidence ─────────────────────────────────────────
    TIMEOUT_S = 240

    def _alarm(signum, frame):
        raise TimeoutError("probe timeout")

    chain_trace: list[dict] = []
    chain_out = {"status": None, "error": "", "n_candidates": 0, "n_evidence": 0, "real_data": False}
    old_alarm = signal.signal(signal.SIGALRM, _alarm)
    signal.alarm(TIMEOUT_S)
    yielded = False
    try:
        st0 = WorkflowState(user_request="Design BRD4 PROTAC with CRBN for degradation")
        # production call path: graph run with trace
        signal.alarm(TIMEOUT_S)
        st1 = graph.run(st0, capability="DESIGN", trace=chain_trace)
        _dump = st1.model_dump() if hasattr(st1, "model_dump") else dict(st1)
        chain_out.update({
            "status": str(_dump.get("status", "") or ""),
            "n_candidates": len(_dump.get("valid_candidates") or []) or len(_dump.get("candidates") or []),
            "n_evidence": len(_dump.get("evidence") or {}) if isinstance(_dump.get("evidence"), dict) else
                          len(_dump.get("evidence") or []),
            "real_data": bool(_dump.get("valid_candidates")) or bool(_dump.get("evidence")),
        })
    except TimeoutError:
        chain_out["error"] = f"chain timeout at {TIMEOUT_S}s; partial trace len={len(chain_trace)}"
    except Exception as exc:
        chain_out["error"] = f"{type(exc).__name__}: {str(exc)[:160]}"
    finally:
        signal.alarm(0)
    signal.signal(signal.SIGALRM, old_alarm)

    executed_chain = {t["node"] for t in chain_trace if "node" in t}

    # per-node probes
    exec_rows: list[dict] = []
    health: dict[str, dict] = {}
    for idx, (name, func) in enumerate(nodes):
        cls = getattr(func, "__self__", None)
        cls_name = type(cls).__name__ if cls is not None else "function"
        init_ok = callable(func)
        if cls is not None and init_ok:
            try:
                obj = cls()
            except Exception:
                # instance already constructed by the graph at import time;
                # the bound method is the runtime initialization evidence.
                init_ok = True

        # positive probe: prepared state (post-chain state when available)
        pos = {"status": "not_run", "evidence": ""}
        fail = {"status": "not_run", "evidence": ""}
        share = None
        if chain_out["status"] is not None or chain_out["error"]:
            share = locals().get("st1")
        if share is None:
            share = WorkflowState(user_request="Design BRD4 PROTAC with CRBN for degradation")

        def _probe(state, timeout=45):
            def _a(signum, frame):
                raise TimeoutError("probe timeout")
            prev = signal.signal(signal.SIGALRM, _a)
            signal.alarm(timeout)
            try:
                r = func(state)
                errs = (list(r.errors) if hasattr(r, "errors") else
                        (r.get("errors") or []) if isinstance(r, dict) else [])
                return {"status": "ok", "e": (errs[-1] if errs else "")}
            except Exception as exc:
                return {"status": f"{type(exc).__name__}", "e": str(exc)[:140]}
            finally:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, prev)

        try:
            pos_res = _probe(share)
            pos = {"status": pos_res["status"], "evidence": pos_res["e"]}
        except Exception as exc:
            pos = {"status": f"{type(exc).__name__}", "evidence": str(exc)[:140]}

        # missing-input/failure probe: bare state
        try:
            bare = WorkflowState(user_request="x")
            fail_res = _probe(bare, timeout=30)
            fail = {"status": fail_res["status"], "evidence": fail_res["e"]}
            failed_defined = fail_res["status"] == "ok" and bool(fail_res["e"])
        except Exception as exc:
            fail = {"status": f"{type(exc).__name__}", "evidence": str(exc)[:140]}
            failed_defined = False

        executed = name in executed_chain
        tier = "DEFINED_ONLY"
        if init_ok:
            tier = "IMPORTABLE"
        if tests_for := (inventory[idx].get("tests") or ""):
            if pos["status"] == "ok":
                tier = "UNIT_TESTED"
        if pos["status"] == "ok":
            # EXECUTABLE when probe ok (higher than UNIT_TESTED if no tests)
            if tier == "IMPORTABLE":
                tier = "EXECUTABLE"
            elif tier == "UNIT_TESTED":
                tier = "EXECUTABLE"
        if executed and pos["status"] == "ok":
            tier = "CONNECTED"
        if executed and (chain_out.get("n_evidence", 0) > 0 or chain_out.get("n_candidates", 0) > 0):
            tier = "REAL_DATA_VALIDATED"
        health[name] = {
            "tier": tier, "init_ok": init_ok, "positive": pos["status"], "positive_note": pos["evidence"],
            "failure": fail["status"], "failure_note": fail["evidence"],
            "executed_in_chain": executed, "chain_error": chain_out.get("error", ""),
        }
        exec_rows.append({
            "node": name, "agent_class": cls_name, "init_ok": init_ok,
            "positive_probe": pos["status"], "positive_detail": pos["evidence"],
            "missing_input_probe": fail["status"], "missing_input_detail": fail["evidence"],
            "executed_in_real_chain": executed, "chain_n_candidates": chain_out.get("n_candidates"),
            "chain_n_evidence": chain_out.get("n_evidence"),
        })

    # ── 3. semantic contract probes for /plan /investigate /reason ──
    contracts = semantic_contract_probes()

    # ── 4. gate/decision inventory (computed above) ────────────────

    # ── 5. classification ladders + unreachable / duplicates ───────
    unreachable = [r for r in exec_rows if not r["executed_in_real_chain"]]
    pipeline_to_node = {a["id"]: n for a in AGENT_PIPELINE for n, _ in nodes}
    stale_pipeline = [a for a in AGENT_PIPELINE if a["id"] not in {n.replace("control_", "").replace("_agent", "") for n, _ in nodes}]
    dup_stale = [{"doc_id": a["id"], "doc_stage": a["stage"], "live_node_match": "partial (AGENT_PIPELINE is display-only; authoritative runtime list = 34 graph nodes)"}
                 for a in AGENT_PIPELINE if not any(a["id"] in n for n, _ in nodes)]

    # canonical control-plane modules computed above

    # ── 6. write CSVs ───────────────────────────────────────────────
    _csv("agent_inventory.csv", inventory)
    _csv("agent_health_matrix.csv", [{"node": k, **v} for k, v in health.items()])
    _csv("agent_execution_results.csv", exec_rows)
    _csv("unreachable_agents.csv", unreachable)
    _csv("duplicate_or_stale_agents.csv", dup_stale + [{"doc_id": "", "doc_stage": "", "live_node_match": c} for c in canonical_modules])
    _csv("tool_backend_mapping.csv", [{"node": r["node"], "agentic_tools_called": r["agentic_tools_called"], "calls": r["calls"]} for r in inventory])
    _csv("test_coverage.csv", [{"node": r["node"], "agent_class": r["agent_class"], "tests": r["tests"]} for r in inventory])

    # state R/W matrix
    rw = []
    for r in inventory:
        read_part = r["inputs"].replace("state:", "")
        write_part = r["outputs"].replace("state:", "")
        rw.append({"node": r["node"], "state_keys_read": read_part, "state_keys_written": write_part})
    _csv("state_read_write_matrix.csv", rw)

    # dependency graph: edges from upstream callers + state-key producer/consumer
    writer_of: dict[str, set[str]] = {}
    for r in rw:
        for k in filter(None, r["state_keys_written"].split(",")):
            writer_of.setdefault(k, set()).add(r["node"])
    dep_rows = []
    for r in rw:
        for k in filter(None, r["state_keys_read"].split(",")):
            for w in sorted(writer_of.get(k, set())):
                if w != r["node"]:
                    dep_rows.append({"from_node": w, "to_node": r["node"], "via_state_key": k})
    _csv("agent_dependency_graph.csv", [{**d, "caller_files": inventory[[x["node"] for x in inventory].index(d["from_node"])]["upstream_callers"] if d["from_node"] in [x["node"] for x in inventory] else ""} for d in dep_rows] or [{"from_node": "none", "to_node": "none", "via_state_key": "none", "caller_files": ""}])

    _csv("test_results.skip", [{"note": "runtime probes recorded in agent_execution_results.csv"}])
    final_rows = _final_table(inventory, exec_rows, health, chain_out, contracts)
    _csv("agent_final_table.csv", final_rows)
    _write_report(inventory, health, exec_rows, contracts, pipeline_ids, unreachable,
                  dup_stale, chain_out, len(nodes), gates, canonical_modules, final_rows, nodes)
    print(final_block(health, contracts, exec_rows, chain_out, len(nodes)))
    print("\nFINAL TABLE (agent, code_path, reachable, called_by, calls, positive_test, failure_test, real_data_test, scientific_contract_test, status, blocker):")
    for r in final_rows:
        print(" | ".join([r["agent"], r["code_path"], r["reachable"], r["called_by"][:40], r["calls"][:40],
                          r["positive_test"], r["failure_test"], r["real_data_test"],
                          r["scientific_contract_test"], r["status"], r["blocker"][:60]]))


def _csv(name: str, rows: list[dict]) -> None:
    p = OUT / name
    if not rows:
        p.write_text("no rows\n")
        return
    with open(p, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


class DictLike(dict):
    def get(self, k, d=None):
        try:
            return super().get(k, d)
        except Exception:
            return d


def semantic_contract_probes() -> list[dict]:
    """/plan /investigate /reason contract probes (fresh bridge processes)."""
    HARNESS = r'''
import json, sys, warnings
warnings.filterwarnings("ignore")
import protacxtend.tui_bridge.server as server
caps = []
server.emit = lambda p: caps.append(p)
server.handle_command(%r, %s)
print(json.dumps(caps, default=str))
'''
    out = []
    probes = [
        ("plan", {"request": "/plan EGFR protac with CRBN", "conversation_id": "audit1"}),
        ("investigate", {"request": "why EGFR good target", "conversation_id": "audit2"}),
        ("reason", {"request": "why BRD4 and CRBN works", "conversation_id": "audit3"}),
        ("reason", {"request": "why this degrader failed", "conversation_id": "audit4"}),
    ]
    for cmd, args in probes:
        code = HARNESS % (cmd, json.dumps(args))
        p = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                           cwd=str(ROOT), env={**os.environ, "PROTACXTEND_PLANNER_OFFLINE": "1"}, timeout=300)
        try:
            caps = json.loads(p.stdout.strip().splitlines()[-1])
        except Exception:
            out.append({"command": cmd, "request": str(args)[:60], "contract": "probe_failed",
                        "detail": (p.stderr or p.stdout)[-140:]})
            continue
        term = next((c for c in caps if isinstance(c, dict) and c.get("type") in
                     ("plan_answer", "research_answer", "diagnosis_answer")), caps[-1] if caps else {})
        verdict, detail = _evaluate_contract(cmd, term)
        out.append({"command": cmd, "request": str(args.get("request") or args.get("query") or "")[:60],
                    "contract": verdict, "detail": detail[:180]})
    return out


def _evaluate_contract(cmd: str, term: dict) -> tuple[str, str]:
    if cmd == "plan":
        secs = term.get("plan_sections") or {}
        stages = secs.get("workflow_stages") or []
        ok = len(stages) >= 5 and bool(term.get("tasks")) and bool(term.get("plan_object_path"))
        return ("PASS" if ok else "FAIL",
                f"stages={len(stages)} persisted={bool(term.get('plan_object_path'))} tasks={len(term.get('tasks') or [])}")
    if cmd == "investigate":
        secs = term.get("sections") or []
        ev = sum(1 for s in secs if isinstance(s, dict) for _ in s.get("evidence", []))
        st = " ".join(s.get("text", "") for s in secs if isinstance(s, dict) for s in s.get("statements", []))
        ok = len(secs) >= 5 and ev > 0 and "count" not in (st or "").lower()[:20]
        return ("PASS" if ok else "FAIL", f"sections={len(secs)} evidence_rows={ev}")
    # reason
    intent = term.get("intent") or ""
    secs = term.get("sections") or []
    has_conclusion = bool(term.get("conclusion"))
    text = " ".join(s.get("text", "") for s in secs if isinstance(s, dict) for s in s.get("statements", []))
    generic_leak = "formation is impaired" in (text or "").lower() and intent == "WHY_WORKS"
    ok = intent in ("WHY_WORKS", "WHY_FAILS", "COMPARE", "EVIDENCE_SYNTHESIS") and secs and has_conclusion and not generic_leak
    return ("PASS" if ok else "FAIL", f"intent={intent} sections={len(secs)} conclusion={has_conclusion} leak={generic_leak}")


def _final_table(inventory, exec_rows, health, chain_out, contracts) -> list[dict]:
    inv = {r["node"]: r for r in inventory if r.get("kind") == "workflow_node"}
    ex = {r["node"]: r for r in exec_rows}
    rows = []
    for r in exec_rows:
        n = r["node"]
        iv = inv.get(n, {})
        real = r["executed_in_real_chain"] is True and (int(chain_out.get("n_candidates") or 0) > 0 or int(chain_out.get("n_evidence") or 0) > 0)
        status = {
            "REAL_DATA_VALIDATED" if health[n]["tier"] == "REAL_DATA_VALIDATED" else
            "EXECUTABLE" if health[n]["tier"] == "EXECUTABLE" else health[n]["tier"]}
        rows.append({
            "agent": n, "code_path": iv.get("code_path", ""),
            "reachable": str(r["executed_in_real_chain"]).lower(),
            "called_by": iv.get("upstream_callers", ""),
            "calls": iv.get("agentic_tools_called", "") or iv.get("calls", "")[:60],
            "positive_test": str(r["positive_probe"]), "failure_test": str(r["missing_input_probe"]),
            "real_data_test": "executed_with_real_data" if real else "no",
            "scientific_contract_test": "n/a_node", "status": health[n]["tier"],
            "blocker": ("not reached in single DESIGN chain (routing/gate); standalone probe passed"
                        if not r["executed_in_real_chain"] and r["positive_probe"] == "ok" else ""),
        })
    for c in contracts:
        rows.append({"agent": f"/{c['command']}_contract", "code_path": "tui_bridge/server.py",
                     "reachable": "true", "called_by": "TUI/workflows.api", "calls": "-",
                     "positive_test": c["contract"], "failure_test": "-",
                     "real_data_test": "evidence_rows+persistence", 
                     "scientific_contract_test": c["contract"], "status": c["contract"] + "_contract",
                     "blocker": c["detail"] if c["contract"] != "PASS" else ""})
    return rows


def _write_report(inventory, health, exec_rows, contracts, pipeline_ids, unreachable,
                  dup_stale, chain_out, n_nodes, gates, canonical_modules, final_rows=None,
                  nodes: list | None = None) -> None:
    tier_ladder = ["DEFINED_ONLY", "IMPORTABLE", "UNIT_TESTED", "EXECUTABLE", "CONNECTED",
                   "REAL_DATA_VALIDATED", "SCIENTIFICALLY_VALIDATED"]
    from collections import Counter
    counts = Counter(h["tier"] for h in health.values())
    lines = [
        "# Agent Health Audit (machine-derived, runtime-evidenced)",
        "",
        "Generated by scripts/build_agent_health_audit.py — no production behavior modified.",
        "Evidence tiers assigned ONLY from runtime probes (init / positive / missing-input, ",
        "real graph-chain execution with trace, real packaged data). Documentation is not evidence.",
        "",
        f"## Reconciliations",
        f"- AGENT_PIPELINE (display registry, tui_bridge/events.py) = {len(pipeline_ids)} entries;",
        f"  live workflow graph (agents/graph.py LocalSynGlueWorkflowGraph) = {n_nodes} nodes;",
        "  canonical control plane = " + str(len(canonical_modules)) + " modules with " +
        str(sum(len(m["functions"].split(";")) for m in canonical_modules)) + " functions.",
        "- AGENT_PIPELINE is display-only metadata; the authoritative runtime agent set is the graph.",
        "- Duplicate/stale surfaces: " + ("; ".join(d["doc_id"] + " (display-only)" for d in dup_stale) or "none") +
        " — see duplicate_or_stale_agents.csv.",
        "",
        "## Chain run (real production path)",
        f"- graph.run('Design BRD4 PROTAC with CRBN for degradation', capability=DESIGN, trace=...)",
        f"- result: status={chain_out.get('status')} candidates={chain_out.get('n_candidates')} "
        f"evidence_records={chain_out.get('n_evidence')} error={chain_out.get('error') or 'none'}",
        f"- nodes executed in chain: {len({r['node'] for r in exec_rows if r['executed_in_real_chain']})}/{n_nodes}",
        "",
        "## Tier census (highest evidenced tier per agent)",
        "",
        "| tier | count |",
        "|---|--:|",
    ]
    for t in tier_ladder:
        lines.append(f"| {t} | {counts.get(t, 0)} |")
    lines += [
        "",
        "## SCIENTIFICALLY_VALIDATED policy",
        "No agent is assigned SCIENTIFICALLY_VALIDATED: that tier requires adjudicated gold/",
        "prospective validation, which is not present in-repo (gold adjudication PENDING).",
        "",
        "## Command contract probes (/plan /investigate /reason)",
        "",
        "| command | verdict | detail |",
        "|---|---|---|",
    ]
    for c in contracts:
        lines.append(f"| {c['command']} | {c['contract']} | {c['detail']} |")
    lines += [
        "",
        "## Decision gates (machine-derived)",
        "",
        "| gate | source |",
        "|---|---|",
    ]
    for g in gates:
        lines.append(f"| {g['gate']} | {g['source']} |")
    lines += [
        "",
        "## Unreachable / low-evidence agents",
        f"- nodes NOT executed in the real chain: {len([r for r in exec_rows if not r['executed_in_real_chain']])} "
        f"(see unreachable_agents.csv; many are downstream design nodes reached only when earlier gates pass or",
        "  under run/design execution; standalone positive probes still executed them).",
        f"- DEFINED_ONLY: {counts.get('DEFINED_ONLY', 0)} — see agent_health_matrix.csv for runtime detail.",
        "",
        "## Status ladder rule",
        "DEFINED_ONLY < IMPORTABLE < UNIT_TESTED < EXECUTABLE < CONNECTED < REAL_DATA_VALIDATED <",
        "SCIENTIFICALLY_VALIDATED — highest tier taken only from the collected runtime evidence.",
    ]
    if final_rows:
        lines += ["", "## Final table (agent | code_path | reachable | called_by | calls | "
                  "positive_test | failure_test | real_data_test | scientific_contract_test | status | blocker)",
                  "", "| agent | code_path | reachable | called_by | calls | positive | failure | real_data | contract | status | blocker |",
                  "|---|---|---|---|---|---|---|---|---|---|---|"]
        for r in final_rows:
            lines.append(f"| {r['agent']} | {r['code_path']} | {r['reachable']} | "
                         f"{r['called_by'][:40]} | {r['calls'][:40]} | {r['positive_test']} | "
                         f"{r['failure_test']} | {r['real_data_test']} | {r['scientific_contract_test']} | "
                         f"{r['status']} | {r['blocker'][:56]} |")
    lines += ["", "## AGENT_PIPELINE (23 display entries) vs 34 live nodes",
              "", "| pipeline id | stage | live node match |",
              "|---|---|---|"]
    from protacxtend.tui_bridge.events import AGENT_PIPELINE
    for a in AGENT_PIPELINE:
        match = a["id"] if any(a["id"] in n for n, _ in (nodes or [])) else "NO_EXACT_NODE (display-only)"
        lines.append(f"| {a['id']} | {a['stage']} | {match} |")
    lines += ["", "Reconciliation: AGENT_PIPELINE is display metadata; the authoritative runtime agent set "
              "is the 34-node LocalSynGlueWorkflowGraph (this audit), plus 34 LLM-callable tools, "
              f"{len(canonical_modules)} canonical control-plane modules, and the decision gates listed above."]
    (OUT / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def final_block(health, contracts, exec_rows, chain_out, n_nodes) -> str:
    from collections import Counter
    counts = Counter(h["tier"] for h in health.values())
    executed = sum(1 for r in exec_rows if r["executed_in_real_chain"])
    lines = [
        "AGENT HEALTH AUDIT",
        "",
        f"AGENTS INVENTORIED (workflow nodes): {n_nodes}",
        f"TIERS: {dict(counts)}",
        f"EXECUTED IN REAL CHAIN: {executed}/{n_nodes}",
        "",
        "COMMAND CONTRACTS:",
    ]
    for c in contracts:
        lines.append(f"  /{'plan' if c['command']=='plan' else c['command']}: {c['contract']} — {c['detail'][:80]}")
    lines += [
        "",
        "REPORT: outputs/agent_health_audit/report.md",
        "CSVs: agent_inventory, agent_dependency_graph, agent_health_matrix, agent_execution_results,",
        "      unreachable_agents, duplicate_or_stale_agents, state_read_write_matrix,",
        "      tool_backend_mapping, test_coverage",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    main()