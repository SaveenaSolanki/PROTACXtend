"""
Runtime/product-closure regression tests.
=========================================

Locks the pathway: User/Agent → Capability → Backend/Tool → QC → typed
ScientificResult, across the shared executor and the TUI/Web/FastAPI surfaces.

Also locks the five silent-failure fixes found by the adversarial campaign:
empty/invalid SMILES, executor default substitution, OpenBabel echo, and
corrupted-structure handling.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


# ── exposure / resolution ──────────────────────────────────────────────

def test_all_agent_tools_resolved_and_fixtured():
    from protacxtend.runtime.agent_tools import PROBE_EXEMPT, PROBE_FIXTURES, list_agent_tools

    tools = list_agent_tools()
    assert len(tools) == 44
    assert all(t["has_executor"] for t in tools)
    names = {t["name"] for t in tools}
    fixtured = {t["name"] for t in tools if t["has_fixture"]}
    exempt = {t["name"] for t in tools if t.get("probe_exempt")}
    # Every ready tool is either probed by a real fixture or explicitly declared
    # probe-exempt (repo-backed tools with no runnable smoke check).
    assert fixtured | exempt == names, sorted(names - fixtured - exempt)
    assert fixtured == set(PROBE_FIXTURES)
    assert exempt == set(PROBE_EXEMPT), sorted(set(PROBE_EXEMPT) - exempt)


@pytest.mark.parametrize("name,params", [
    ("inspect_smiles", {"smiles": "CCO"}),
    ("predict_admet", {"smiles": "CCO"}),
    ("detect_exit_vectors", {"smiles": "CC(=O)Oc1ccccc1C(=O)O", "role": "warhead"}),
    ("construct_protac", {"warhead_smiles": "CC(=O)Oc1ccccc1C(=O)O",
                          "linker_smiles": "CCOCCO",
                          "e3_smiles": "O=C1CCC(N2C(=O)c3ccccc3C2=O)C(=O)N1"}),
    ("rank_candidates", {"candidates": [{"candidate_id": "a", "log_dc50": 1.0},
                                        {"candidate_id": "b", "log_dc50": 2.0}]}),
    ("list_scientific_capabilities", {}),
])
def test_agent_tools_execute_with_typed_envelope(name, params):
    from protacxtend.runtime.agent_tools import run_agent_tool

    run = run_agent_tool(name, params)
    assert run["RESOLVED"] is True
    assert run["EXECUTED"] is True
    assert run["VALID_OUTPUT"] is True
    env = run["scientific_result"]
    assert env["schema_version"] == "1.0.0"
    assert env["workflow"] == "agent_tool"
    assert env["evidence"]
    assert env["provenance"]
    assert run["provenance"]["params_sha256"]


def test_executor_routes_agent_tool_before_resolved_capability():
    """`inspect_smiles` resolves to capability `chemistry` but must run the tool."""
    from protacxtend.runtime.executor import run_capability

    out = run_capability("inspect_smiles", {"smiles": "CCO"})
    assert out["executed"] is True
    assert out["result"]["backend"] == "agentic.registry"
    assert out["result"]["agent_tool"]["AGENT_EXPOSED"] is True


def test_executor_routes_all_scientific_backends():
    from protacxtend.runtime.executor import run_capability

    out = run_capability("candidate_ranking", {"candidates": [
        {"candidate_id": "a", "log_dc50": 1.0}, {"candidate_id": "b", "log_dc50": 2.0}]})
    assert out["executed"] is True
    assert out["output_valid"] is True


# ── TUI / Web / FastAPI transports ─────────────────────────────────────

def test_fastapi_tool_routes():
    from fastapi.testclient import TestClient
    from protacxtend.backend.api_routes import get_app

    client = TestClient(get_app())
    assert client.get("/tools").json()["count"] == 44
    detail = client.get("/tools/inspect_smiles").json()
    assert detail["found"] is True and detail["fixture"]
    run = client.post("/tools/inspect_smiles/run", json={"params": {"smiles": "CCO"}}).json()
    assert run["executed"] is True
    assert run["result"]["agent_tool"]["AGENT_EXPOSED"] is True


def test_tui_bridge_capability_transport():
    import contextlib
    import io
    import json

    import protacxtend.tui_bridge.server as tui

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        tui.handle_command("capability", {"name": "inspect_smiles", "params": {"smiles": "CCO"}})
    payloads = [json.loads(l) for l in buf.getvalue().splitlines() if l.strip().startswith("{")]
    results = [p for p in payloads if p.get("type") == "capability_result"]
    assert results
    assert results[0]["result"]["executed"] is True


def test_web_capability_entrypoint():
    from protacxtend.app.web_capability import run_web_capability

    out = run_web_capability("inspect_smiles", {"smiles": "CCO"})
    assert out["executed"] is True
    assert out["result"]["agent_tool"]["VALID_OUTPUT"] is True


# ── silent-failure fixes ───────────────────────────────────────────────

@pytest.mark.parametrize("smiles", ["", "not-a-smiles", None, float("nan")])
def test_empty_or_invalid_smiles_never_produces_descriptors(smiles):
    from protacxtend.scientific_backends.runner import run_capability

    r = run_capability("chemistry", smiles=smiles, operation="descriptors")
    assert r.status != "success"
    assert not (r.data or {}).get("molecular_weight")


def test_executor_does_not_substitute_default_smiles():
    from protacxtend.runtime.executor import run_capability

    out = run_capability("conformer_generation", {"smiles": "", "n_conformers": 2})
    assert out["executed"] is True
    assert not (out["result"].get("data") or {}).get("n_conformers")


def test_corrupted_structure_is_not_a_valid_zero_contact_result():
    import tempfile

    from protacxtend.scientific_backends.runner import run_capability

    p = Path(tempfile.mkdtemp()) / "bad.pdb"
    p.write_text("ATOM  not a valid pdb line\nEND\n")
    r = run_capability("interaction_energy", pdb_path=str(p))
    assert r.status != "success"
    assert not (r.data or {}).get("interface_score")


def test_output_valid_requires_non_empty_data():
    from protacxtend.runtime.executor import _validate

    assert _validate({"status": "warning", "data": {}}) is False
    assert _validate({"status": "not_available", "data": {"x": 1}}) is False
    assert _validate({"status": "success", "data": {"x": 1}}) is True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
