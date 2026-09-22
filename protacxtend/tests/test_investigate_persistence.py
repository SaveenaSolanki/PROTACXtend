"""DEV/mock regression tests: /investigate run persistence (single fix scope).

Proves the ACTIVE /investigate execution path now runs through the existing
production runtime (protacxtend/agents/runtime.run_protacpilot) so one
canonical run id produces the normal outputs/runs/<run_id>/ artifact bundle
and workflow memory, with no state reuse between independent runs and no
false “results saved” claim.

NOT touching: frozen 48-task benchmark, ground truth, scoring rubric,
benchmark schemas, scientific modules.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from uuid import uuid4

import pytest


def _rid() -> str:
    return f"run_itest_{uuid4().hex[:8]}"


def _make_state(request: str, target: str, n_candidates: int = 1) -> "object":
    """A small, realistic completed WorkflowState (mocks the scientific graph
    output AND the graph's MemoryUpdateAgent final node)."""
    from protacxtend.backend.config import WORKFLOW_LOG_DIR
    from protacxtend.backend.schemas import (
        AgentTrace,
        BinderRecord,
        CandidateRecord,
        TargetRecord,
        WorkflowState,
    )
    from protacxtend.tools.memory_manager import write_workflow_memory

    WORKFLOW_LOG_DIR.mkdir(parents=True, exist_ok=True)
    candidates = [
        CandidateRecord(
            candidate_id=f"{target}-c{i}",
            target=target,
            e3_ligase="VHL",
            e3_ligand_name="VH032",
            linker_name="PEG2",
            full_protac_smiles=f"CC(=O)Nc1ccc(O)cc1{i}",
            validity_status="valid",
            composite_score=0.9 - i * 0.1,
        )
        for i in range(n_candidates)
    ]
    state = WorkflowState(
        user_request=request,
        target_record=TargetRecord(
            target_name=target,
            gene_symbol=target,
            uniprot_id=f"UP_{target}",
            organism="Homo sapiens",
        ),
        retrieved_binders=[
            BinderRecord(name=f"{target} binder 1", target=target,
                         source="mockdb", activity_nM=12.0, p_activity=7.92)
        ],
        valid_candidates=list(candidates),
        final_ranked_candidates=list(candidates),
        report=f"# {target} mock investigation\n\ncompleted KNOW \u2192 REASON \u2192 DISCOVER.",
        workflow_log=[
            AgentTrace(agent="SupervisorAgent", thought="parse",
                       action="resolve", observation="target known",
                       processing_time_s=0.01),
            AgentTrace(agent="MemoryUpdateAgent", thought="persist",
                       action="update_memory", observation="memory written",
                       processing_time_s=0.0),
        ],
    )
    state.parsed_objective.target_name = target
    # Mimic the graph's final `update_memory` node so the workflow-memory log
    # is produced with the canonical runtime run id.
    update = write_workflow_memory(state)
    state.memory_updates.append(update)
    return state


def _artifact_paths(run_dir: Path):
    return {
        name: run_dir / name
        for name in ("run.json", "summary.json", "trace.jsonl",
                     "decisions.jsonl", "evidence.jsonl",
                     "candidates.parquet", "report.md")
    }


def _cleanup(rid: str) -> None:
    from protacxtend.backend.config import WORKFLOW_LOG_DIR
    from protacxtend.run_records import OUTPUT_ROOT
    shutil.rmtree(OUTPUT_ROOT / rid, ignore_errors=True)
    try:
        (WORKFLOW_LOG_DIR / f"{rid}.json").unlink(missing_ok=True)
    except Exception:
        pass


class TestInvestigatePersistence:
    """/investigate produces outputs/runs/<run_id>/ with one canonical id."""

    def test_runtime_writes_canonical_bundle_deterministic(self, monkeypatch):
        """Mocked /investigate → outputs/runs/<run_id>/ full bundle; memory and
        run.json share the canonical id."""
        from protacxtend.agents.runtime import run_protacpilot
        from protacxtend.backend.config import WORKFLOW_LOG_DIR
        from protacxtend.run_records import OUTPUT_ROOT

        rid = _rid()
        calls: list[str] = []

        def fake_graph(request: str):
            calls.append(request)
            return _make_state(request, "BRD4", n_candidates=2)

        monkeypatch.setattr("protacxtend.agents.graph.run_syn_glue_workflow", fake_graph)
        try:
            result = run_protacpilot(
                "Investigate: BRD4 and VHL", mode="deterministic",
                config={"run_id": rid, "record_run": True})
            assert result["status"] == "ok"
            assert calls == ["Investigate: BRD4 and VHL"]

            run_record = result.get("run_record") or {}
            assert run_record.get("run_id") == rid
            run_dir = OUTPUT_ROOT / rid
            assert Path(run_record["dir"]) == run_dir

            # 1) every artifact exists
            artifacts = _artifact_paths(run_dir)
            for name, path in artifacts.items():
                assert path.exists(), f"missing {name}"

            # 2) run.json carries the canonical id and the objective
            run_json = json.loads((run_dir / "run.json").read_text())
            assert run_json["run_id"] == rid
            assert run_json["user_objective"] == "Investigate: BRD4 and VHL"

            # 3) trace summary.json carries the same canonical id
            summary = json.loads((run_dir / "summary.json").read_text())
            assert summary["run_id"] == rid

            # 3b) trace.jsonl events carry the canonical id
            trace_lines = [json.loads(l) for l in (run_dir / "trace.jsonl").read_text().splitlines() if l.strip()]
            assert trace_lines and trace_lines[0]["event"] == "run_start"
            assert trace_lines[0]["run_id"] == rid

            # 4) conversational-memory record uses the SAME canonical id
            mem_file = WORKFLOW_LOG_DIR / f"{rid}.json"
            assert mem_file.exists(), "workflow-memory record missing"
            mem = json.loads(mem_file.read_text())
            assert mem["run_id"] == rid

            # 5) report content present
            assert "mock investigation" in (run_dir / "report.md").read_text()
        finally:
            _cleanup(rid)

    def test_two_consecutive_investigations_isolated(self, monkeypatch):
        """BRD4 then BCL2 → two distinct run ids; second run holds no BRD4 state."""
        import json as _json
        from protacxtend.agents.runtime import run_protacpilot
        from protacxtend.backend.config import WORKFLOW_LOG_DIR
        from protacxtend.run_records import OUTPUT_ROOT

        rid1, rid2 = _rid(), _rid()

        def fake_graph(request: str):
            target = "BRD4" if "BRD4" in request else "BCL2"
            return _make_state(request, target, n_candidates=1)

        monkeypatch.setattr("protacxtend.agents.graph.run_syn_glue_workflow", fake_graph)
        try:
            r1 = run_protacpilot("Investigate: BRD4 and VHL", mode="deterministic",
                                 config={"run_id": rid1, "record_run": True})
            r2 = run_protacpilot("Investigate: BCL2 in lymphoma", mode="deterministic",
                                 config={"run_id": rid2, "record_run": True})
            assert rid1 != rid2
            assert r1["state"] is not r2["state"]

            # second run contains no BRD4 residue from the first
            s2_dump = _json.dumps(r2["state"].model_dump(), default=str)
            assert "BRD4" not in s2_dump
            assert r2["state"].target_record.target_name == "BCL2"
            assert r2["state"].parsed_objective.target_name == "BCL2"

            # distinct run dirs + distinct memory files
            assert (OUTPUT_ROOT / rid1).exists() and (OUTPUT_ROOT / rid2).exists()
            assert (WORKFLOW_LOG_DIR / f"{rid1}.json").exists()
            assert (WORKFLOW_LOG_DIR / f"{rid2}.json").exists()
            run2 = json.loads((OUTPUT_ROOT / rid2 / "run.json").read_text())
            assert run2["run_id"] == rid2
        finally:
            _cleanup(rid1)
            _cleanup(rid2)


class TestBridgePersistence:
    """handle_run (the active /investigate bridge) routes through runtime once
    per request, emits the exact saved dir, and never claims “saved” on
    failure."""

    def _run_bridge(self, capsys, request_text: str):
        import protacxtend.tui_bridge.server as server
        server.handle_run(request_text)
        out = capsys.readouterr().out
        return [json.loads(line) for line in out.splitlines() if line.strip()]

    def test_bridge_routes_each_request_once_with_exact_dir(self, monkeypatch, capsys):
        from protacxtend.agents.runtime import run_protacpilot as _real  # noqa: F401
        from protacxtend.run_records import OUTPUT_ROOT

        calls: list[tuple[str, dict]] = []

        def fake_runtime(request: str, mode: str = "deterministic",
                         config: dict | None = None):
            calls.append((request, dict(config or {})))
            rid = (config or {}).get("run_id", "")
            target = "BRD4" if "BRD4" in request else "BCL2"
            return {"status": "ok", "state": _make_state(request, target, n_candidates=1),
                    "run_record": {"run_id": rid, "dir": str(OUTPUT_ROOT / rid)}}

        monkeypatch.setattr("protacxtend.agents.runtime.run_protacpilot", fake_runtime)
        try:
            ev1 = self._run_bridge(capsys, "Investigate: BRD4 and VHL")
            ev2 = self._run_bridge(capsys, "Investigate: BCL2 in lymphoma")

            def by_type(events, t):
                return [e for e in events if e.get("type") == t]

            start1 = by_type(ev1, "run_start")[0]
            start2 = by_type(ev2, "run_start")[0]
            rid1, rid2 = start1["run_id"], start2["run_id"]
            assert rid1 != rid2

            # every run executed the runtime exactly once (no cached-state reuse)
            assert [c[0] for c in calls] == ["Investigate: BRD4 and VHL",
                                             "Investigate: BCL2 in lymphoma"]
            assert [c[1].get("run_id") for c in calls] == [rid1, rid2]
            assert all(c[1].get("record_run") is True for c in calls)

            # results event exposes the EXACT persisted directory
            res1 = by_type(ev1, "results")[0]
            assert res1["run_id"] == rid1
            assert res1["persisted"] is True
            assert res1["saved_dir"] == str(OUTPUT_ROOT / rid1)

            # scientific_result + run_complete share the same canonical id
            sch1 = by_type(ev1, "scientific_result")[0]["result"]
            assert sch1["task_id"] == rid1 and sch1["result"]["run_id"] == rid1
            comp1 = by_type(ev1, "run_complete")[0]
            assert comp1["run_id"] == rid1 and comp1["status"] == "ok"
            assert comp1["summary"]["persisted"] is True

            # streaming UX preserved: agent_start stream present
            assert by_type(ev1, "agent_start")
            # second run targets BCL2 (proves no BRD4 cache survives)
            res2 = by_type(ev2, "results")[0]
            assert res2["run_id"] == rid2
        finally:
            pass

    def test_persistence_failure_never_claims_saved(self, monkeypatch, capsys):
        """Runtime returns ok but no run_record → results event persisted=False
        (the Node UI prints a warning, not “results saved”)."""
        def fake_runtime(request: str, mode: str = "deterministic",
                         config: dict | None = None):
            rid = (config or {}).get("run_id", "")
            return {"status": "ok", "state": _make_state(request, "BRD4"),
                    "run_record": None}  # write failed inside runtime

        monkeypatch.setattr("protacxtend.agents.runtime.run_protacpilot", fake_runtime)
        ev = self._run_bridge(capsys, "Investigate: BRD4 and VHL")
        res = [e for e in ev if e.get("type") == "results"][0]
        assert res["persisted"] is False
        assert res["saved_dir"] == ""
        comp = [e for e in ev if e.get("type") == "run_complete"][0]
        assert comp["summary"]["persisted"] is False

    def test_runtime_exception_reports_error_without_results(self, monkeypatch, capsys):
        def boom(request: str, mode: str = "deterministic", config: dict | None = None):
            raise RuntimeError("simulated backend failure")

        monkeypatch.setattr("protacxtend.agents.runtime.run_protacpilot", boom)
        ev = self._run_bridge(capsys, "Investigate: BRD4 and VHL")
        types = {e.get("type") for e in ev}
        assert "results" not in types          # nothing to claim “saved”
        assert "scientific_result" not in types
        comp = [e for e in ev if e.get("type") == "run_complete"][0]
        assert comp["status"] == "error"
        assert "simulated backend failure" in comp["summary"]["error"]

    def test_run_record_write_failure_yields_no_record(self, monkeypatch):
        """A disk-write failure inside the production runtime must not surface
        a run_record (and therefore never prints “saved”)."""
        from protacxtend.agents.runtime import run_protacpilot
        from protacxtend.run_records import OUTPUT_ROOT

        rid = _rid()

        def fake_graph(request: str):
            return _make_state(request, "BRD4", n_candidates=1)

        def boom(*_args, **_kwargs):
            raise OSError("disk full (simulated)")

        monkeypatch.setattr("protacxtend.agents.graph.run_syn_glue_workflow", fake_graph)
        monkeypatch.setattr("protacxtend.run_records.write_run_record", boom)
        try:
            result = run_protacpilot("Investigate: BRD4 and VHL", mode="deterministic",
                                     config={"run_id": rid, "record_run": True})
            assert (result.get("run_record") or {}) == {}  # never claimed
            assert not (OUTPUT_ROOT / rid / "run.json").exists()
        finally:
            _cleanup(rid)
