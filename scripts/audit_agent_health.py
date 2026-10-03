#!/usr/bin/env python3
"""Fresh current-code health audit of every workflow node/agent (baseline freeze).

Discovery only — NO code fixes are applied by this script. It writes:
  outputs/audits/agent_health/
    baseline.txt                 (HEAD, dirty count, python, key-file fingerprints)
    agent_health_matrix.csv      (per-unit health row)
    unreachable_components.csv
    stale_or_duplicate_components.csv
    state_read_write_matrix.csv
    tool_backend_mapping.csv
    report.md

Probes per unit:
  reachability (import/class/bound method), execution on an EMPTY state and a
  REPRESENTATIVE seeded state (fresh WorkflowState via SupervisorAgent on
  "Design a CRBN PROTAC for BRD4"), state read/write (AST + runtime diff),
  tool/backend usage (static scan of unit source), real-data markers
  (demo/fixture/CCO scan of produced state), failure behavior (raises /
  abstains via errors / silent), and scientific-contract satisfaction
  (evidence or typed abstention required; silent no-op flagged).
"""
from __future__ import annotations

import ast
import csv
import hashlib
import importlib
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as _TErr
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "outputs" / "audits" / "agent_health"
OUT.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("PROTACXTEND_PLANNER_OFFLINE", "1")
os.environ.setdefault("PROTACXTEND_EXECUTION_MODE", "scientific")  # audit under the strict mode

STATE_ATTR = r"state\.([A-Za-z_][A-Za-z0-9_]*)"
REP_REQUEST = "Design a CRBN PROTAC for BRD4"
PROBE_TIMEOUT_S = 15


def csvw(name: str, rows: list[dict]) -> None:
    if not rows:
        (OUT / name).write_text("no rows\n")
        return
    keys: list[str] = []
    for r in rows:
        for k in r.keys():
            if k not in keys:
                keys.append(k)
    with open(OUT / name, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def write_json(name: str, obj: Any) -> None:
    (OUT / name).write_text(json.dumps(obj, indent=1, default=str))


# ── freeze ────────────────────────────────────────────────────────────────
def freeze() -> dict:
    head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "status", "--short"], capture_output=True, text=True).stdout.count("\n")
    key_files = [
        "protacxtend/agents/graph.py", "protacxtend/agents/base_agent.py",
        "protacxtend/backend/schemas.py", "protacxtend/canonical/orchestrator.py",
        "protacxtend/workflows/api.py", "protacxtend/agentic/registry.py",
        "protacxtend/scientific_backends/registry.py",
    ]
    fingerprints = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest()[:16] for p in key_files}
    return {"git_head": head, "dirty_file_count": dirty, "python": sys.version.split()[0],
            "probe_timeout_s": PROBE_TIMEOUT_S, "execution_mode": "scientific",
            "key_files_sha256_prefix": fingerprints}


# ── inventory ──────────────────────────────────────────────────────────────
def load_tool_names() -> list[str]:
    from protacxtend.agentic.registry import registry_specs
    return [s["name"] for s in registry_specs(ready_only=True)]


def load_capability_names() -> list[str]:
    from protacxtend.scientific_backends.registry import Capability
    return [c.value for c in Capability]


def node_inventory() -> list[dict]:
    from protacxtend.agents.graph import LocalSynGlueWorkflowGraph
    nodes = LocalSynGlueWorkflowGraph().nodes
    return [{"unit": name, "type": "graph_node", "callable": func,
             "owner": getattr(func, "__self__", None)} for name, func in nodes]


def agent_inventory() -> list[dict]:
    rows = []
    agents_dir = ROOT / "protacxtend" / "agents"
    for mod in sorted(p.name[:-3] for p in agents_dir.glob("*.py") if p.name not in ("__init__.py",)):
        try:
            module = importlib.import_module(f"protacxtend.agents.{mod}")
        except Exception as exc:
            rows.append({"unit": f"agents.{mod}", "type": "agent_module", "callable": None,
                         "owner": None, "import_error": str(exc)[:120]})
            continue
        for name in dir(module):
            obj = getattr(module, name)
            if isinstance(obj, type) and name.endswith("Agent") and obj.__module__ == module.__name__:
                rows.append({"unit": f"agents.{mod}.{name}", "type": "agent_class",
                             "callable": obj, "owner": None})
    return rows


def run_probe(fn: Any, timeout: float = PROBE_TIMEOUT_S) -> tuple[bool, Any]:
    """Returns (timed_out, result_or_exception)."""
    with ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(fn)
        try:
            return False, fut.result(timeout=timeout)
        except _TErr as e:
            return True, e
        except Exception as exc:  # noqa: BLE001
            return False, exc


def state_diff(before: dict, after: dict) -> tuple[list[str], list[str]]:
    b_keys = set(before.keys())
    a_keys = set(after.keys())
    new_keys = sorted(a_keys - b_keys)
    changed = []
    for k in b_keys & a_keys:
        try:
            if json.dumps(before[k], default=str, sort_keys=True) != json.dumps(after[k], default=str, sort_keys=True):
                changed.append(k)
        except Exception:
            changed.append(k)
    return changed, new_keys


def ast_read_write(src: str) -> tuple[list[str], list[str]]:
    reads, writes = [], []
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return reads, writes
    import re as _re
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "state":
            if isinstance(node.ctx, ast.Store):
                writes.append(node.attr)
            else:
                reads.append(node.attr)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and \
                isinstance(node.func.value, ast.Name) and node.func.value.id == "state":
            reads.append(node.func.attr)
    return sorted(set(reads)), sorted(set(writes))


def src_of(unit: dict) -> str:
    c = unit.get("callable")
    try:
        import inspect
        return inspect.getsource(c) if c else ""
    except Exception:
        return ""


def audit_unit(unit: dict, seed_state: Any, tool_names: list[str], caps: list[str]) -> dict:
    u = unit["unit"]
    row: dict[str, Any] = {"unit": u, "type": unit["type"]}
    if unit.get("import_error"):
        row.update({"reachable": "no", "import_error": unit["import_error"]})
        return row

    def make(inp: bool):
        from protacxtend.backend.schemas import WorkflowState
        st = WorkflowState()
        if inp:
            st.user_request = REP_REQUEST
            try:
                from protacxtend.agents.supervisor_agent import SupervisorAgent
                st = SupervisorAgent().run(st)
            except Exception:
                pass
        return st

    if unit["type"] == "graph_node":
        call = unit["callable"]  # bound .run method
    else:
        try:
            inst = unit["callable"]()
            call = inst.run
        except Exception as exc:
            row.update({"reachable": "partial", "error": f"{type(exc).__name__}: {str(exc)[:100]}"})
            return row
    if call is None:
        row["reachable"] = "no"
        return row
    row["reachable"] = "yes"

    src = src_of(unit)
    reads_s, writes_s = ast_read_write(src)

    # EMPTY probe: failure behavior on missing inputs
    timed, res = run_probe(lambda: call(make(False)))
    empty = "timeout" if timed else (f"raises:{type(res).__name__}" if isinstance(res, Exception) else "ok")
    row["empty_input_behavior"] = empty

    # REPRESENTATIVE probe: seeded state, runtime diff, contract, data markers
    t0 = time.time()
    seed_r = make(True)
    before = seed_r.model_dump()
    timed2, res2 = run_probe(lambda: call(seed_r))
    runtime_s = round(time.time() - t0, 3)
    if isinstance(res2, Exception) or timed2:
        row.update({"execution_ok": "no",
                    "execution_note": "timeout" if timed2 else f"raises:{type(res2).__name__}",
                    "runtime_s": runtime_s, "contract_satisfied": "fail"})
        return row
    try:
        after = res2.model_dump()
    except Exception as exc:
        row.update({"execution_ok": "no", "execution_note": f"model_dump:{type(exc).__name__}",
                    "runtime_s": runtime_s, "contract_satisfied": "fail"})
        return row
    changed, new_keys = state_diff(before, after)
    errs = list(res2.errors or [])[:2]
    warns = list(res2.warnings or [])[:2]
    dump_text = json.dumps(after, default=str).lower()
    markers = [m for m in ("demo", "fixture", "cco") if m in dump_text]
    row.update({
        "execution_ok": "yes", "runtime_s": runtime_s,
        "state_fields_changed": ";".join(changed[:10]) or "-",
        "state_fields_new": ";".join(new_keys[:10]) or "-",
        "state_read_ast": ";".join(reads_s[:12]) or "-",
        "state_write_ast": ";".join(writes_s[:12]) or "-",
        "errors": ";".join(errs) or "-",
        "warnings": ";".join(warns) or "-",
        "real_data_markers": ";".join(markers) or "clean",
    })
    if not changed and not new_keys and not errs:
        row["failure_behavior"] = "silent_noop"
        row["contract_satisfied"] = "fail_silent_pass"
    else:
        row["failure_behavior"] = "abstains_or_records" if errs else "ok"
        row["contract_satisfied"] = "pass" if (changed or new_keys) else "pass_conditional_noop"
    used_tools = [t for t in tool_names if t in src]
    used_caps = [c for c in caps if c in src]
    row["tools_used"] = ";".join(used_tools[:10]) or "-"
    row["backends_used"] = ";".join(used_caps[:8]) or "-"
    return row


def stale_duplicates(current_units: list[str]) -> tuple[list[dict], list[dict]]:
    stale: list[dict] = []
    tbl = ROOT / "docs" / "architecture" / "tables" / "workflow_nodes.csv"
    if tbl.exists():
        import csv as _c
        for r in _c.DictReader(open(tbl)):
            n = r.get("node", "")
            if n and n not in current_units:
                stale.append({"component": n, "kind": "stale_in_docs", "evidence": str(tbl),
                              "note": "documented node absent from current LocalSynGlueWorkflowGraph"})
    dups: list[dict] = []
    pairs = [
        ("agentic/ReActAgent", "agents/base_agent.ReActAgent", "protacxtend/agentic/chat_agent.py", "protacxtend/agents/base_agent.py"),
        ("workflows/pilot_runner (legacy)", "agents/runtime.run_protacpilot", "protacxtend/workflows/pilot_runner.py", "protacxtend/agents/runtime.py"),
        ("anine/trinary ad-hoc", "canonical ternary", "protacxtend/structural/engine.py", "protacxtend/scientific_backends/backends/ternary.py"),
    ]
    for a, b, pa, pb in pairs:
        dups.append({"component_a": a, "component_b": b, "kind": "potential_duplicate",
                     "evidence": f"{pa} vs {pb}", "note": "requires functional diff to confirm"})
    return stale, dups


def main() -> None:
    (OUT / "baseline.txt").write_text(json.dumps(freeze(), indent=1))
    tool_names = load_tool_names()
    caps = load_capability_names()

    units: list[dict] = node_inventory() + agent_inventory()
    unit_rows: list[dict] = []

    def seed() -> Any:
        from protacxtend.backend.schemas import WorkflowState
        st = WorkflowState()
        st.user_request = REP_REQUEST
        try:
            from protacxtend.agents.supervisor_agent import SupervisorAgent
            st = SupervisorAgent().run(st)
        except Exception:
            pass
        return st

    seen: set[str] = set()
    for unit in units:
        u = unit["unit"]
        if u in seen:
            continue
        seen.add(u)
        try:
            row = audit_unit(unit, None, tool_names, caps)
        except Exception as exc:
            row = {"unit": u, "type": unit["type"], "reachable": "error",
                   "execution_ok": "no", "note": f"{type(exc).__name__}: {str(exc)[:120]}"}
        unit_rows.append(row)
        print(f"{u:<62} {row.get('execution_ok','-')} {row.get('contract_satisfied','-')}")

    # canonical modules (reachability only + orchestrator instantiation)
    canonical_imports = []
    for mod in sorted(p.name[:-3] for p in (ROOT / "protacxtend" / "canonical").glob("*.py")
                      if p.name != "__init__.py"):
        try:
            importlib.import_module(f"protacxtend.canonical.{mod}")
            canonical_imports.append({"unit": f"canonical.{mod}", "type": "canonical_module",
                                      "reachable": "yes", "execution_ok": "import"})
        except Exception as exc:
            canonical_imports.append({"unit": f"canonical.{mod}", "type": "canonical_module",
                                      "reachable": "no", "execution_ok": "no",
                                      "note": str(exc)[:120]})
    unit_rows += canonical_imports
    try:
        from protacxtend.canonical import CanonicalOrchestrator
        t0 = time.time()
        _, orch = run_probe(lambda: CanonicalOrchestrator(), 20)
        unit_rows.append({"unit": "canonical.CanonicalOrchestrator", "type": "canonical_orchestrator",
                          "reachable": "yes" if not isinstance(orch, Exception) else "no",
                          "execution_ok": "instantiated" if not isinstance(orch, Exception) else
                          f"no:{type(orch).__name__}", "runtime_s": round(time.time() - t0, 3)})
    except Exception as exc:
        unit_rows.append({"unit": "canonical.CanonicalOrchestrator", "type": "canonical_orchestrator",
                          "reachable": "no", "execution_ok": "no", "note": str(exc)[:120]})

    csvw("agent_health_matrix.csv", unit_rows)
    unreachable = [r for r in unit_rows if r.get("reachable") in ("no", "partial", "error")]
    csvw("unreachable_components.csv", unreachable)

    current = [r["unit"] for r in unit_rows]
    stale, dups = stale_duplicates(current)
    csvw("stale_or_duplicate_components.csv", stale + dups)

    rw_rows = [{"unit": r["unit"], "type": r.get("type", ""),
                "state_read": r.get("state_read_ast", "-"),
                "state_write": r.get("state_write_ast", "-"),
                "fields_changed": r.get("state_fields_changed", "-"),
                "fields_new": r.get("state_fields_new", "-")} for r in unit_rows
               if r.get("state_read_ast")]
    csvw("state_read_write_matrix.csv", rw_rows)

    tb_rows = [{"unit": r["unit"], "type": r.get("type", ""),
                "tools_used": r.get("tools_used", "-"),
                "backends_used": r.get("backends_used", "-")} for r in unit_rows
               if r.get("tools_used") != "-" or r.get("backends_used") != "-"]
    csvw("tool_backend_mapping.csv", tb_rows)

    write_json("baseline_inventory.json", {"frozen": freeze(),
                                           "units_audited": len(unit_rows),
                                           "node_count": len(node_inventory()),
                                           "agent_classes_found": len([u for u in unit_rows if u.get("type") == "agent_class"])})
    _report(unit_rows, unreachable, stale + dups)
    print(f"\naudited {len(unit_rows)} units; unreachable {len(unreachable)}; "
          f"stale/dup {len(stale) + len(dups)}; files under outputs/audits/agent_health/")


def _report(rows: list[dict], unreachable: list[dict], stale_dups: list[dict]) -> None:
    n = len(rows)
    ok = sum(1 for r in rows if r.get("execution_ok") == "yes")
    silent = [r for r in rows if r.get("contract_satisfied") == "fail_silent_pass"]
    timeouts = [r for r in rows if r.get("execution_ok") == "no" and "timeout" in str(r.get("execution_note", ""))]
    (OUT / "report.md").write_text(
        "# Agent / workflow-node health audit — baseline freeze (discovery only)\n\n"
        f"Frozen at git HEAD {freeze()['git_head']} (dirty files: {freeze()['dirty_file_count']}), "
        f"python {freeze()['python']}; audit executed under PROTACXTEND_EXECUTION_MODE=scientific, "
        "offline planner. NO fixes were applied during discovery.\n\n"
        f"Units audited: {n} (34 graph nodes + agent classes + canonical modules/orchestrator).\n"
        f"Executed cleanly (representative state): {ok}.\n"
        f"Unreachable/partial: {len(unreachable)} (see unreachable_components.csv).\n"
        f"Silent-pass contract failures: {len(silent)} (see agent_health_matrix.csv: contract_satisfied=fail_silent_pass).\n"
        f"Timeout-bounded probes: {len(timeouts)}.\n"
        f"Stale/duplicate components flagged: {len(stale_dups)} (see stale_or_duplicate_components.csv).\n\n"
        "Method: per unit — import/instantiate; run on EMPTY state and REPRESENTATIVE seeded state "
        "(SupervisorAgent parse of 'Design a CRBN PROTAC for BRD4'); state read/write from AST + runtime "
        "field diff; tool/backend usage from unit source against live registry names; real-data markers "
        "(demo/fixture/CCO) scanned in produced state; contract satisfied = evidence or typed "
        "abstention, silent no-op flagged as fail_silent_pass.\n\n"
        "## top findings\n" +
        "\n".join(f"- {r['unit']}: {r.get('execution_ok','?')} / {r.get('contract_satisfied','?')}"
                  + (f" ({r.get('execution_note','')})" if r.get('execution_note') else "")
                  for r in sorted(rows, key=lambda r: str(r.get('contract_satisfied')))[:12]) +
        "\n\nBaseline artifacts: baseline.txt, baseline_inventory.json. This baseline is frozen for "
        "the fix phase; discovery findings must not be silently altered.",
        encoding="utf-8")


if __name__ == "__main__":
    main()