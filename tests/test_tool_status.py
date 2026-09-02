from protacxtend.tools.tool_status import detect_all_tool_statuses, detect_tool_status
from protacxtend.tools.toolkit_registry import get_tool_by_name
from protacxtend.tools.toolkit_router import route_tool_request


def test_status_detection_never_crashes():
    statuses = detect_all_tool_statuses()
    assert isinstance(statuses, dict)
    assert len(statuses) > 0


def test_missing_binary_marked_honestly():
    fake_tool = {
        "tool_name": "Fake Missing Binary Tool",
        "executable_names": ["definitely_not_real_binary_xyz"],
        "python_imports": [],
        "api_required": False,
        "commercial": False,
        "web_service": False,
        "status": "registered_but_not_executable",
    }
    result = detect_tool_status(fake_tool)
    assert result["status"] in {"binary_missing", "registered_but_not_executable"}
    assert result["installed"] is False


def test_rdkit_detection():
    rdkit = get_tool_by_name("RDKit ETKDG")
    assert rdkit is not None
    result = detect_tool_status(rdkit)
    assert "rdkit" in rdkit["python_imports"]
    assert ("rdkit" in result["detected_python_imports"]) or ("rdkit" in result["missing_python_imports"])


def test_router_docking():
    routed = route_tool_request("run ligand docking")
    rec = set(routed["recommended_tools"])
    assert {"AutoDock Vina", "Smina", "GNINA"}.issubset(rec)


def test_router_admet():
    routed = route_tool_request("check ADMET toxicity")
    rec = set(routed["recommended_tools"])
    assert {"SwissADME", "ADMETlab 3.0", "pkCSM", "ProTox-II", "OpenADMET"}.issubset(rec)


def test_router_ternary_complex():
    routed = route_tool_request("ternary complex feasibility")
    rec = set(routed["recommended_tools"])
    assert "AlphaFold-Multimer" in rec
    assert "HADDOCK3" in rec
    assert "RosettaDock" in rec
    assert ("MEGADOCK" in rec) or ("ZDOCK" in rec)

