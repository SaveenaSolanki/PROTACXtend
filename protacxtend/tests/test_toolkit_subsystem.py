"""Tests for the toolkit provisioning/detection/truth subsystem.

Offline-only: no network calls, no installs. Tests skip gracefully when an
optional tool is not present in any registered environment.
"""

from __future__ import annotations

import pytest

from protacxtend.toolkit import catalog
from protacxtend.toolkit.environments import (
    PROXY_IMPORTS,
    find_module,
    toolkit_envs,
)
from protacxtend.toolkit.truth import build_truth


def test_plan_covers_every_registered_tool():
    from protacxtend.tools.toolkit_registry import get_toolkit_registry

    registry = get_toolkit_registry()
    plans = catalog.plan_all_tools()
    assert len(plans) == len(registry) >= 100
    for plan in plans:
        assert plan["method"] in {
            "pip", "conda", "repo", "web", "api", "commercial", "metadata", "binary",
        }
        assert plan["reason"]
        if plan["auto_installable"]:
            assert plan["command"]


def test_commercial_and_web_classification():
    from protacxtend.tools.toolkit_registry import get_tool_by_name

    for name in ("Glide", "GOLD", "Schrodinger LigPrep"):
        plan = catalog.provision_plan(get_tool_by_name(name))
        assert plan["method"] == "commercial"
        assert not plan["auto_installable"]

    for name in ("SwissADME", "ClusPro", "ADMETlab 3.0"):
        plan = catalog.provision_plan(get_tool_by_name(name))
        assert plan["method"] == "web"
        assert plan["portal"]


def test_proxy_framework_tools_are_repo_required():
    """torch/transformers alone must not count as an installed method."""
    from protacxtend.tools.toolkit_registry import get_tool_by_name

    for name in ("DeepPROTACs", "GROVER", "Uni-Mol"):
        row = get_tool_by_name(name)
        assert set(row["python_imports"]) <= PROXY_IMPORTS
        assert catalog.provision_method(row) == "repo"


def test_environments_are_registered():
    envs = toolkit_envs()
    assert envs, "at least the current interpreter must be registered"
    assert any(e.kind == "current" for e in envs)


def test_cross_env_version_detection_finds_rdkit():
    found = find_module("rdkit")
    assert found is not None
    env, version = found
    assert version
    assert env.python


def test_tool_status_has_callable_and_version_fields():
    from protacxtend.tools.tool_status import detect_all_tool_statuses

    statuses = detect_all_tool_statuses()
    assert len(statuses) >= 100
    for status in statuses.values():
        for key in ("status", "installed", "callable", "verified", "version",
                    "provider_env", "provision_method"):
            assert key in status


def test_truth_workbook_schema_without_hashing():
    sheets = build_truth(compute_hash=False)
    for name in ("Summary", "Tools", "Tool_Versions", "Agent_Tools", "Datasets",
                 "Dependencies", "Capabilities", "Distribution_Matrix"):
        assert name in sheets
    assert len(sheets["Tools"]) == 115
    metrics = {row["metric"]: row["value"] for row in sheets["Summary"]}
    assert metrics["toolkit_tools"] == 115
    assert metrics["agent_tools"] == metrics["agent_tools_ready"] >= 32
    assert metrics["datasets"] >= 40


def test_all_agent_tools_are_ready_and_have_executors():
    from protacxtend.agentic.registry import TOOL_SPECS
    from protacxtend.agentic import registry as registry_mod

    assert TOOL_SPECS
    assert all(spec["readiness"] == "ready" for spec in TOOL_SPECS)
    # every advertised tool must have a dispatch entry (no fabricated readiness)
    for spec in TOOL_SPECS:
        assert spec["name"] in registry_mod._EXECUTORS, spec["name"]


def test_bridge_local_call():
    from protacxtend.toolkit.bridge import call_first_available

    python = pytest.importorskip("rdkit")  # noqa: F841
    outcome = call_first_available(
        "protacxtend.tools.chemistry_core", "validate_smiles",
        args=["CCO"], prefer_env=None)
    assert outcome["ok"], outcome.get("error")
