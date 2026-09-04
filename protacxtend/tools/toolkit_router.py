"""Natural-language router from task descriptions to toolkit tools."""

from __future__ import annotations

from typing import Any

from protacxtend.tools.protac_repo_tool_wrappers import get_protac_repo_wrapper_status
from protacxtend.tools.repo_tool_adapter import route_repo_tool_request
from protacxtend.tools.tool_status import detect_all_tool_statuses
from protacxtend.tools.toolkit_registry import get_tool_by_name


TASK_RULES: list[tuple[list[str], list[str]]] = [
    (
        ["prepare", "ligand", "vina", "docking"],
        ["Meeko", "OpenBabel", "RDKit ETKDG", "MGLTools"],
    ),
    (
        ["run", "ligand", "docking"],
        ["AutoDock Vina", "Smina", "GNINA", "Glide", "GOLD", "DOCK6"],
    ),
    (
        ["ternary", "complex", "feasibility"],
        ["AlphaFold-Multimer", "ColabFold", "HADDOCK3", "RosettaDock", "MEGADOCK", "ZDOCK", "LightDock"],
    ),
    (
        ["run", "md", "refinement"],
        ["GROMACS", "OpenMM", "AMBER / AmberTools", "NAMD", "CHARMM", "Desmond"],
    ),
    (
        ["binding", "energy"],
        ["gmx_MMPBSA", "MMPBSA.py", "Rosetta InterfaceAnalyzer"],
    ),
    (
        ["design", "linker"],
        ["LinkInvent", "DeLinker", "DiffLinker", "SyntaLinker", "CReM", "BRICS", "RECAP"],
    ),
    (
        ["check", "admet"],
        ["SwissADME", "ADMETlab 3.0", "pkCSM", "ProTox-II", "OpenADMET"],
    ),
    (
        ["predict", "degradation"],
        ["DeepPROTACs", "PROTAC-STAN", "DegradeMaster"],
    ),
    (
        ["retrosynth"],
        ["AiZynthFinder", "ASKCOS", "ASKCOS Tree Builder", "Molecular Transformer", "RDKit + OpenNMT workflow", "RAscore", "SCScore", "RDChiral"],
    ),
    (
        ["synthes", "route"],
        ["AiZynthFinder", "ASKCOS", "ASKCOS Tree Builder", "Molecular Transformer", "RDKit + OpenNMT workflow", "RAscore", "SCScore"],
    ),
    (
        ["reaction", "predict", "forward"],
        ["IBM RXN", "RXNMapper", "Molecular Transformer", "RDChiral"],
    ),
    (
        ["accessibility", "score"],
        ["RAscore", "SCScore"],
    ),
    (
        ["search", "patent"],
        ["SureChEMBL", "Lens.org", "Google Patents"],
    ),
    (
        ["extract", "chemistry", "text"],
        ["OPSIN", "ChemDataExtractor", "SciSpacy", "PubTator"],
    ),
]


def route_tool_request(task_description: str) -> dict[str, Any]:
    task = (task_description or "").strip()
    task_l = task.lower()
    recommended: list[str] = []
    for keys, tools in TASK_RULES:
        if all(k in task_l for k in keys):
            recommended = tools
            break

    if not recommended:
        if "docking" in task_l:
            recommended = ["AutoDock Vina", "Smina", "GNINA"]
        elif "admet" in task_l or "tox" in task_l:
            recommended = ["SwissADME", "ADMETlab 3.0", "pkCSM", "ProTox-II", "OpenADMET"]
        elif "ternary" in task_l:
            recommended = ["AlphaFold-Multimer", "HADDOCK3", "RosettaDock", "MEGADOCK", "ZDOCK"]

    statuses = detect_all_tool_statuses()
    repo_route = route_repo_tool_request(task)
    repo_wrapper_capabilities = [
        {
            "name": item["name"],
            "safe_capabilities": get_protac_repo_wrapper_status(item["name"]).get("safe_capabilities", []),
            "callable_dispatch": "protacxtend.tools.protac_repo_tool_wrappers.execute_protac_repo_tool",
        }
        for item in repo_route["recommended_repo_tools"]
        if item.get("source") == "protac_repos"
    ]
    available_tools: list[str] = []
    missing_tools: list[str] = []
    web_or_api_tools: list[str] = []
    commercial_tools: list[str] = []
    for name in recommended:
        status = statuses.get(name, {"status": "missing"})
        meta = get_tool_by_name(name) or {}
        if status["status"] in {"installed", "available"}:
            available_tools.append(name)
        else:
            missing_tools.append(name)
        if meta.get("web_service") or meta.get("api_required"):
            web_or_api_tools.append(name)
        if meta.get("commercial"):
            commercial_tools.append(name)

    note = (
        "Recommendations are registry-driven. Tools listed as missing/web_only/api_key_required/"
        "commercial_not_available are not treated as executable until actually detected."
    )
    return {
        "task": task,
        "recommended_tools": recommended,
        "available_tools": available_tools,
        "missing_tools": missing_tools,
        "web_or_api_tools": web_or_api_tools,
        "commercial_tools": commercial_tools,
        "repo_backed_tools": repo_route["recommended_repo_tools"],
        "repo_wrapper_capabilities": repo_wrapper_capabilities,
        "repo_backed_honest_execution_note": repo_route["honest_execution_note"],
        "honest_execution_note": note,
    }
