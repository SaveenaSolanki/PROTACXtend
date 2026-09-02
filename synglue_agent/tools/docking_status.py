"""Docking backend detection utilities for Phase 11."""

from __future__ import annotations

import importlib.util
import shutil
from typing import Any


def detect_docking_backends() -> dict[str, Any]:
    executables = {
        "vina": "vina",
        "gnina": "gnina",
        "pymol": "pymol",
        "openbabel": "obabel",
        "haddock": "haddock3",
        "rfdiffusion": "rfdiffusion",
        "rosetta": "rosetta_scripts.default.linuxgccrelease",
    }
    backends: dict[str, Any] = {}
    for name, command in executables.items():
        path = shutil.which(command)
        backends[name] = {
            "registered": True,
            "available": path is not None,
            "executable": path is not None,
            "command": command,
            "path": path,
            "status": "executable" if path is not None else "registered_but_not_executable",
        }

    rdkit_available = importlib.util.find_spec("rdkit") is not None
    backends["rdkit"] = {
        "registered": True,
        "available": rdkit_available,
        "executable": rdkit_available,
        "command": "python_package:rdkit",
        "path": None,
        "status": "executable" if rdkit_available else "registered_but_not_executable",
    }
    return {
        "source": "local_detection",
        "success": True,
        "error": None,
        "backends": backends,
    }

