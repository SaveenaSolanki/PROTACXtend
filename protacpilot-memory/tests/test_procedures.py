"""Procedural-memory API and MCP-surface tests (Sprint V5)."""

from __future__ import annotations

import pytest
from protacpilot_memory.mcp.tools import CogToolRegistry

PROCEDURE_TOOLS = {
    "cog_procedure_save", "cog_procedure_search", "cog_procedure_get",
    "cog_procedure_record_run",
}


def _steps():
    return [
        "Prepare the target structure and remove waters",
        "Dock the warhead and E3 ligand",
        "Enumerate linkers and score ternary geometry",
        "Filter by permeability and degradation feasibility",
    ]


def test_procedure_tools_registered(mem):
    assert PROCEDURE_TOOLS <= set(CogToolRegistry(mem).names())


def test_save_and_get_procedure(mem, project):
    record = mem.procedure_save(
        name="ternary docking workflow",
        objective="Prioritise PROTAC candidates with productive ternary geometry",
        steps=_steps(),
        prerequisites="prepared receptor and ligand files",
        inputs=["target.pdb", "warhead.sdf"],
        outputs=["ranked_candidates.csv"],
        tool_dependencies=["haddock", "rdkit"],
        domain="structural",
        project_id=project,
        evidence=[{"evidence_type": "internal_experiment", "experiment_id": "PROC-1"}],
    )
    trace_id = record["trace_id"]
    assert trace_id and record["memory_type"] == "procedural"
    assert [s["order"] for s in record["steps_json"]] == [1, 2, 3, 4]
    assert (record["metadata_json"] or {})["objective"].startswith("Prioritise")
    assert (record["metadata_json"] or {})["version"] == 1
    assert record["evidence"], "evidence provenance should be linked"

    fetched = mem.procedure_get(trace_id)
    assert fetched["workflow_name"] == "ternary docking workflow"


def test_procedure_search_uses_hybrid_retrieval(mem, project):
    mem.procedure_save(
        name="permeability prioritisation",
        objective="Rank candidates by passive permeability",
        steps=["Compute cLogP", "Run PAMPA assay", "Rank"],
        tool_dependencies=["rdkit"], project_id=project, domain="adme",
    )
    mem.procedure_save(
        name="md validation workflow",
        objective="Validate ternary complex stability with molecular dynamics",
        steps=["Build system", "Run 100 ns MD", "Analyse RMSD"],
        tool_dependencies=["gromacs"], project_id=project, domain="structural",
    )
    result = mem.procedure_search("permeability ranking", project_id=project, limit=5)
    assert result["results"]
    assert result["results"][0]["name"] == "permeability prioritisation"
    assert result["results"][0]["why_retrieved"]

    by_domain = mem.procedure_search(None, project_id=project, domain="structural")
    assert [r["name"] for r in by_domain["results"]] == ["md validation workflow"]


def test_procedure_versioning_supersedes_old(mem, project):
    v1 = mem.procedure_save(
        name="candidate filtering", steps=["Step A", "Step B"],
        objective="filter v1", project_id=project,
    )["trace_id"]
    v2 = mem.procedure_save(
        name="candidate filtering", steps=["Step A", "Step B", "Step C"],
        objective="filter v2", project_id=project, replace=True,
    )["trace_id"]
    assert v2 != v1
    assert mem.store.get_trace(v1)["status"] == "superseded"
    assert mem.store.get_trace(v2)["status"] == "active"
    assert mem.procedure_get(v2)["metadata_json"]["version"] == 2
    # a superseded workflow must not surface in search
    hits = mem.procedure_search("candidate filtering", project_id=project)
    assert all(r["memory_id"] != v1 for r in hits["results"])


def test_record_run_statistics(mem, project):
    trace_id = mem.procedure_save(
        name="adme prioritisation", steps=["compute", "filter"], project_id=project,
    )["trace_id"]
    first = mem.procedure_record_run(trace_id, success=True)
    assert first["success_count"] == 1 and first["last_success_at"]
    second = mem.procedure_record_run(trace_id, success=False, note="assay failed")
    assert second["success_count"] == 1 and second["failure_count"] == 1
    record = mem.procedure_get(trace_id)
    assert record["success_count"] == 1 and record["failure_count"] == 1
    assert (record["metadata_json"] or {})["last_run_success"] is False


def test_procedure_save_requires_steps(mem, project):
    from protacpilot_memory.errors import ValidationError

    with pytest.raises(ValidationError):
        mem.procedure_save(name="empty", steps=[], project_id=project)


def test_procedure_mcp_round_trip(mem, project):
    registry = CogToolRegistry(mem)
    saved = registry.call("cog_procedure_save", {
        "name": "ternary docking workflow",
        "objective": "score ternary geometry",
        "steps": _steps(),
        "project_id": project,
    })
    memory_id = saved["trace_id"]
    got = registry.call("cog_procedure_get", {"memory_id": memory_id})
    assert got["workflow_name"] == "ternary docking workflow"
    search = registry.call("cog_procedure_search", {"query": "ternary geometry", "project_id": project})
    assert search["results"]
    run = registry.call("cog_procedure_record_run", {"memory_id": memory_id, "success": True})
    assert run["success_count"] == 1
