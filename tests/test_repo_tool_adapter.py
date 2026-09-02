from synglue_agent.tools.repo_tool_adapter import (
    get_repo_tool,
    repo_tool_status,
    route_repo_tool_request,
    smoke_test_repo_tool,
)
from synglue_agent.tools.toolkit_router import route_tool_request


def test_linchemin_repo_tool_is_addressable():
    record = get_repo_tool("syngenta/linchemin")
    assert record is not None
    assert record["name"] == "linchemin"
    assert record["found_locally"] is True
    assert record["install_status"] == "installed_isolated"
    assert record["recommended_wrapper_type"] == "python_package_adapter"


def test_linchemin_status_exposes_executable_environment():
    status = repo_tool_status("linchemin")
    assert status["registered"] is True
    assert status["found_locally"] is True
    assert status["installed"] is True
    assert "python_executable" in status
    assert status["backend_status"] in {"installed_isolated", "installed_but_python_missing"}


def test_linchemin_safe_smoke_test_is_real_or_clearly_failed():
    result = smoke_test_repo_tool("linchemin")
    if result["success"]:
        assert result["status"] == "success"
        assert result["smoke_test"]["rdkit_parse_ok"] is True
        assert result["smoke_test"]["linchemin_version"]
    else:
        assert result["status"] == "failed"
        assert result["error"]


def test_legacy_synthesis_repos_are_not_claimed_executable():
    for name in ["step-wise-chemical-synthesis-prediction", "Deep-Synthesis"]:
        status = repo_tool_status(name)
        assert status["registered"] is True
        assert status["found_locally"] is True
        assert status["installed"] is False
        assert status["executable"] is False
        assert "manual" in status["recommended_wrapper_type"]


def test_protac_repo_records_resolve_without_execution_claims():
    status = repo_tool_status("TERNIFY")
    assert status["registered"] is True
    assert status["source"] == "protac_repos"
    assert "env_specs" in status
    assert status["status"] != "success"


def test_repo_router_recommends_synthesis_backends():
    routed = route_repo_tool_request("chemical synthesis prediction and retrosynthesis route")
    names = {tool["name"] for tool in routed["recommended_repo_tools"]}
    assert "linchemin" in names
    assert "step-wise-chemical-synthesis-prediction" in names
    assert "Deep-Synthesis" in names
    assert "env_specs alone are not treated as working tools" in routed["honest_execution_note"]


def test_general_tool_router_includes_repo_backed_tools():
    routed = route_tool_request("chemical synthesis prediction setup")
    names = {tool["name"] for tool in routed["repo_backed_tools"]}
    assert "linchemin" in names
    assert "step-wise-chemical-synthesis-prediction" in names
    assert "Deep-Synthesis" in names


def test_general_tool_router_exposes_protac_wrapper_dispatch():
    routed = route_tool_request("protac degradation tool setup")
    assert routed["repo_wrapper_capabilities"]
    assert all(
        item["callable_dispatch"] == "synglue_agent.tools.protac_repo_tool_wrappers.execute_protac_repo_tool"
        for item in routed["repo_wrapper_capabilities"]
    )
