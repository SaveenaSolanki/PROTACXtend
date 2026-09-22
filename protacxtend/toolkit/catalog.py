"""Per-tool provisioning metadata.

The toolkit registry describes *what a tool is*. This module describes *how to
get it*: the pip/conda package, the exact command, the web portal, or the
reason a tool cannot be provisioned automatically (commercial licence, GPU
cluster, repo + trained weights required, …).

Classification is deterministic and derived from the registry row plus curated
overrides, so a new registry entry always gets a plan (never an exception).
"""

from __future__ import annotations

import shutil
from typing import Any

from protacxtend.toolkit.environments import PROXY_IMPORTS

# ── import name -> PyPI distribution ────────────────────────────────────
PIP_PACKAGES: dict[str, str] = {
    "nglview": "nglview",
    "meeko": "meeko",
    "pdbfixer": "pdbfixer",
    "openbabel": "openbabel-wheel",
    "rdkit": "rdkit",
    "chemprop": "chemprop",
    "deepchem": "deepchem",
    "tdc": "PyTDC",
    "rxnmapper": "rxnmapper",
    "rdchiral": "rdchiral",
    "rascore": "rascore",
    "scscore": "scscore",
    "aizynthfinder": "aizynthfinder",
    "crem": "crem",
    "mmpdb": "mmpdb",
    "guacamol": "guacamol",
    "moses": "moses",
    "scispacy": "scispacy",
    "chemdataextractor": "chemdataextractor",
    "delinker": "delinker",
    "reinvent": "reinvent",
    "esm": "fair-esm",
    "openmm": "openmm",
    "pyrosetta": "pyrosetta",
    "onmt": "OpenNMT-py",
    "cellprofiler": "cellprofiler",
    "DeepPurpose": "DeepPurpose",
    "Bio": "biopython",
    "propka": "propka",
    "pdb2pqr": "pdb2pqr",
    "opencv": "opencv-python-headless",
    "py3Dmol": "py3Dmol",
    "mdtraj": "mdtraj",
    "MDAnalysis": "MDAnalysis",
    "prody": "prody",
}

# ── tool name -> conda(-forge) package ──────────────────────────────────
CONDA_PACKAGES: dict[str, str] = {
    "OpenBabel": "openbabel",
    "CREST": "crest",
    "xTB": "xtb",
    "MOPAC": "mopac",
    "GROMACS": "gromacs",
    "NAMD": "namd",
    "AutoDock Vina": "vina",
    "Smina": "smina",
    "GNINA": "gnina",
    "AutoDock-GPU": "autodock-gpu",
    "rDock": "rdock",
    "DOCK6": "dock6",
    "LeDock": "ledock",
    "PLANTS": "plants",
    "HADDOCK3": "haddock3",
    "LightDock": "lightdock",
    "MEGADOCK": "megadock",
    "ZDOCK": "zdock",
    "PDB2PQR": "pdb2pqr",
    "PropKa": "propka",
    "Meeko": "meeko",
    "PDBFixer": "pdbfixer",
    "OpenMM": "openmm",
    "FragPipe": "fragpipe",
    "Perseus": "perseus",
    "KNIME": "knime",
    "Galaxy": "galaxy",
    "mmpdb": "mmpdb",
    "AiZynthFinder": "aizynthfinder",
}

# ── tool name -> web portal (not locally provisionable) ─────────────────
WEB_PORTALS: dict[str, str] = {
    "Mol*": "https://molstar.org/viewer/",
    "HADDOCK": "https://wenmr.science.uu.nl/haddock2.4",
    "ClusPro": "https://cluspro.bu.edu",
    "PatchDock": "https://bioinfo3d.cs.tau.ac.il/PatchDock",
    "SwissADME": "http://www.swissadme.ch",
    "ADMETlab 3.0": "https://admetlab3.scbdd.com",
    "pkCSM": "https://biosig.lab.uq.edu.au/pkcsm",
    "ProTox-II": "https://tox-new.charite.de/protox_II",
    "SureChEMBL": "https://www.surechembl.org",
    "Lens.org": "https://www.lens.org",
    "Google Patents": "https://patents.google.com",
    "PubTator": "https://www.ncbi.nlm.nih.gov/research/pubtator3/",
    "IBM RXN": "https://rxn.res.ibm.com",
    "ASKCOS": "https://askcos.mit.edu",
    "AlphaFold-Multimer": "https://colab.research.google.com/github/deepmind/alphafold",
}

# ── tool name -> repo-backed method needing own weights ─────────────────
REPO_REQUIRED: dict[str, str] = {
    "DeepPROTACs": "github.com/FengleiShen/DeepPROTACs (checkpoint required)",
    "PROTAC-STAN": "PROTAC-STAN repo + trained weights",
    "DegradeMaster": "DegradeMaster repo + trained weights",
    "EquiDock": "github.com/octavian-ganea/equidock_public (+weights)",
    "DiffLinker": "github.com/igashov/DiffLinker (+checkpoint)",
    "SyntaLinker": "github.com/kyo-t/DeepLigBuilder (+checkpoint)",
    "MolDQN": "github.com/google-research/google-research/mol_dqn",
    "GROVER": "github.com/tencent-ailab/grover (+pretrained weights)",
    "ChemBERTa": "DeepChem/chemberta weights (HuggingFace)",
    "MolFormer": "IBM MolFormer weights (HuggingFace)",
    "Uni-Mol": "github.com/dptech-corp/Uni-Mol (+weights)",
    "ProtT5": "Rostlab/prot_t5_xl weights (seq2seq PLM)",
    "PRosettaC": "github.com/BCLCommons/PRosettaC + Rosetta licence",
    "AlphaFold-Multimer": "DeepMind AlphaFold params (~2.3 TB DB / weights on request)",
    # not on PyPI — source/GitHub only
    "DeLinker": "github.com/oxpig/DeLinker (+checkpoint; no PyPI distribution)",
    "REINVENT": "github.com/MolecularAI/REINVENT4 (no PyPI distribution)",
    "LinkInvent": "MolecularAI REINVENT4 LinkInvent (no PyPI distribution)",
    "RAscore": "github.com/reymond-group/RAscore (no PyPI distribution)",
    "SCScore": "github.com/connorcoley/scscore (no PyPI distribution)",
    "ChemDataExtractor": "DAWG build fails on py3.11; install via conda/py3.9 (github.com/cambridgeltl/chemdataextractor)",
    "DeepPurpose": "PyPI 0.1.5 pins numpy<2 — install in an isolated env (github.com/kexinhuang12345/DeepPurpose)",
}

# ── tool name -> pip install when only a generic framework import exists ─
# Some registry rows declare only a framework import but the *method* is pip
# installable under its own distribution; the catalog adds the real package.
METHOD_PIP: dict[str, str] = {
    "Molecular Transformer": "OpenNMT-py",
    "RXNMapper": "rxnmapper",
    "RDChiral": "rdchiral",
    "DeepPurpose": "DeepPurpose",
    "Therapeutics Data Commons": "PyTDC",
}

COMMERCIAL_TOOLS = {
    "GOLD", "Glide", "MOE Dock", "ICM-Pro", "Schrodinger LigPrep", "Epik",
    "OpenEye OMEGA", "Gaussian", "CHARMM", "Desmond", "NameRxn",
    "Pipeline Pilot", "Proteome Discoverer / MaxQuant",
}


def _is_proxy_only(tool: dict[str, Any]) -> bool:
    imports = set(tool.get("python_imports") or [])
    return bool(imports) and imports.issubset(PROXY_IMPORTS)


def _pip_package(tool: dict[str, Any], *, live: bool = True) -> str:
    name = tool.get("tool_name", "")
    if name in METHOD_PIP:
        return METHOD_PIP[name]
    for imp in tool.get("python_imports") or []:
        if imp in PIP_PACKAGES:
            return PIP_PACKAGES[imp]
    for imp in tool.get("python_imports") or []:
        if imp not in PROXY_IMPORTS:
            return imp
    return ""


def _conda_package(tool: dict[str, Any]) -> str:
    name = tool.get("tool_name", "")
    if name in CONDA_PACKAGES:
        return CONDA_PACKAGES[name]
    for imp in tool.get("python_imports") or []:
        if imp in CONDA_PACKAGES.values():
            return imp
    return (name or "").lower().replace(" ", "-")


def provision_method(tool: dict[str, Any]) -> str:
    """Canonical provisioning class for a registry row.

    One of: ``installed``, ``pip``, ``conda``, ``repo``, ``web``, ``api``,
    ``commercial``, ``metadata``, ``binary``.
    """
    name = tool.get("tool_name", "")
    if name in COMMERCIAL_TOOLS or tool.get("commercial"):
        return "commercial"
    if _is_proxy_only(tool) or name in REPO_REQUIRED:
        return "repo"
    if tool.get("python_imports"):
        return "pip"
    if tool.get("executable_names"):
        # A bare executable may come from a conda package or a source build.
        return "conda" if name in CONDA_PACKAGES else "binary"
    if tool.get("api_required"):
        return "api"
    if tool.get("web_service") or name in WEB_PORTALS:
        return "web"
    if (tool.get("executable_type") or "") == "metadata" or tool.get("reliability_level") == "metadata_only":
        return "metadata"
    return "metadata"


def provision_plan(tool: dict[str, Any], *, python: str = "python") -> dict[str, Any]:
    """Actionable plan for one toolkit row (never raises)."""
    name = tool.get("tool_name", "")
    method = provision_method(tool)
    package = ""
    command = ""
    portal = WEB_PORTALS.get(name, "")
    reason = ""
    auto_installable = False

    if method == "pip":
        package = _pip_package(tool)
        command = f"{python} -m pip install {package}" if package else ""
        auto_installable = bool(package)
        reason = "pip-installable Python package"
    elif method == "conda":
        package = _conda_package(tool)
        command = f"conda install -y -c conda-forge {package}" if package else ""
        auto_installable = bool(package)
        reason = "conda-forge / bioconda package"
    elif method == "binary":
        command = ""
        reason = "source/apt binary — provide on PATH or install into a conda env"
    elif method == "repo":
        reason = REPO_REQUIRED.get(name, "method repository + trained weights required")
    elif method == "web":
        reason = f"web-only service{f' — {portal}' if portal else ''}"
    elif method == "api":
        reason = "remote API — credentials required, no local install"
    elif method == "commercial":
        reason = "commercial/licensed — manual provisioning and licence required"
    else:
        reason = "metadata/planning entry — nothing to install"

    conda_available = bool(shutil.which("conda"))
    return {
        "tool_name": name,
        "category": tool.get("category", ""),
        "method": method,
        "pip_package": package if method == "pip" else "",
        "conda_package": package if method == "conda" else "",
        "command": command,
        "portal": portal,
        "auto_installable": auto_installable,
        "conda_available": conda_available,
        "reason": reason,
        "install_hint": tool.get("install_hint", ""),
        "commercial": bool(tool.get("commercial") or name in COMMERCIAL_TOOLS),
        "web_service": bool(tool.get("web_service")),
        "python_imports": list(tool.get("python_imports") or []),
        "executable_names": list(tool.get("executable_names") or []),
    }


def plan_all_tools(*, python: str = "python") -> list[dict[str, Any]]:
    from protacxtend.tools.toolkit_registry import get_toolkit_registry

    return [provision_plan(t, python=python) for t in get_toolkit_registry()]


def summarize_plans(plans: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for plan in plans:
        counts[plan["method"]] = counts.get(plan["method"], 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: -kv[1]))


__all__ = [
    "PIP_PACKAGES",
    "CONDA_PACKAGES",
    "WEB_PORTALS",
    "REPO_REQUIRED",
    "COMMERCIAL_TOOLS",
    "provision_method",
    "provision_plan",
    "plan_all_tools",
    "summarize_plans",
]
