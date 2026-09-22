"""Honest external executors for escalated capabilities.

An executor is only ever called when the chosen external tool is actually
installed. It must either return a real result or an explicit
``status="not_available"`` payload — it must never fabricate data.
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
from typing import Any, Callable, Dict, Optional

from protacxtend.escalation.contracts import ExternalToolCandidate


def _not_available(tool: str, reason: str) -> dict[str, Any]:
    return {"status": "not_available", "evidence_type": "NOT AVAILABLE", "tool": tool, "reason": reason}


def _has_module(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


# ── cheminformatics: OpenBabel canonicalisation ────────────────────────
def execute_cheminformatics(inputs: dict[str, Any], candidate: ExternalToolCandidate) -> dict[str, Any]:
    smiles = inputs.get("smiles") or inputs.get("input") or ""
    if not smiles:
        return _not_available(candidate.tool_name, "no SMILES input supplied")
    # OpenBabel python bindings
    if _has_module("openbabel"):
        try:
            from openbabel import pybel  # type: ignore

            mol = pybel.readstring("smi", smiles)
            return {
                "status": "ok",
                "evidence_type": "CALCULATED",
                "tool": candidate.tool_name,
                "canonical_smiles": mol.write("can").strip(),
                "formula": mol.formula,
                "version": candidate.version,
            }
        except Exception as exc:
            return _not_available(candidate.tool_name, f"openbabel error: {exc}")
    if shutil.which("obabel"):
        try:
            proc = subprocess.run(
                ["obabel", "-:" + smiles, "-ocan"], capture_output=True, text=True, timeout=30
            )
            if proc.returncode == 0 and proc.stdout.strip():
                return {
                    "status": "ok",
                    "evidence_type": "CALCULATED",
                    "tool": candidate.tool_name,
                    "canonical_smiles": proc.stdout.strip().split()[0],
                    "version": candidate.version,
                }
        except Exception as exc:
            return _not_available(candidate.tool_name, f"obabel error: {exc}")
    return _not_available(candidate.tool_name, "openbabel bindings/CLI not found")


# ── retrosynthesis: AiZynthFinder / ASKCOS ─────────────────────────────
def execute_retrosynthesis(inputs: dict[str, Any], candidate: ExternalToolCandidate) -> dict[str, Any]:
    smiles = inputs.get("smiles") or inputs.get("input") or ""
    if not smiles:
        return _not_available(candidate.tool_name, "no SMILES input supplied")
    try:
        from protacxtend.tools import retrosynthesis_engines as re

        if candidate.tool_name == "AiZynthFinder" and hasattr(re, "run_aizynth_engine"):
            result = re.run_aizynth_engine(smiles)
            return {"status": "ok", "evidence_type": "CALCULATED", "tool": candidate.tool_name,
                    "result": result, "version": candidate.version}
        if candidate.tool_name.startswith("ASKCOS") and hasattr(re, "AskcosClient"):
            client = re.AskcosClient()
            result = client.one_step(smiles) if hasattr(client, "one_step") else None
            if result is not None:
                return {"status": "ok", "evidence_type": "CALCULATED", "tool": candidate.tool_name,
                        "result": result, "version": candidate.version}
    except Exception as exc:
        return _not_available(candidate.tool_name, f"retrosynthesis adapter error: {exc}")
    return _not_available(candidate.tool_name, "retrosynthesis adapter not wired for this engine")


# ── ADMET: TDC / DeepPurpose readiness ─────────────────────────────────
def execute_admet(inputs: dict[str, Any], candidate: ExternalToolCandidate) -> dict[str, Any]:
    smiles = inputs.get("smiles") or inputs.get("input") or ""
    if not smiles:
        return _not_available(candidate.tool_name, "no SMILES input supplied")
    if _has_module("tdc"):
        return {
            "status": "ready",
            "evidence_type": "ML PREDICTION",
            "tool": candidate.tool_name,
            "note": "TDC installed; endpoint model selection required before inference. "
                    "No prediction fabricated.",
            "version": candidate.version,
        }
    if _has_module("DeepPurpose"):
        return {
            "status": "ready",
            "evidence_type": "ML PREDICTION",
            "tool": candidate.tool_name,
            "note": "DeepPurpose installed; model weights required before inference.",
            "version": candidate.version,
        }
    return _not_available(candidate.tool_name, "no ADMET model backend importable")


# ── degradation: Chemprop / external baseline readiness ────────────────
def execute_degradation(inputs: dict[str, Any], candidate: ExternalToolCandidate) -> dict[str, Any]:
    smiles = inputs.get("smiles") or inputs.get("input") or ""
    if not smiles:
        return _not_available(candidate.tool_name, "no SMILES input supplied")
    if _has_module("chemprop"):
        return {
            "status": "ready",
            "evidence_type": "ML PREDICTION",
            "tool": candidate.tool_name,
            "note": "Chemprop installed; trained degradation checkpoint required for inference.",
            "version": candidate.version,
        }
    return _not_available(candidate.tool_name, "chemprop not importable")


# ── docking: binary presence (full run needs receptor prep) ────────────
def execute_docking(inputs: dict[str, Any], candidate: ExternalToolCandidate) -> dict[str, Any]:
    for exe in candidate.executable_names:
        if shutil.which(exe):
            return {
                "status": "ready",
                "evidence_type": "STRUCTURAL SURROGATE",
                "tool": candidate.tool_name,
                "note": "docking engine present; receptor/ligand preparation required to run a pose search",
                "executable": exe,
                "version": candidate.version,
            }
    return _not_available(candidate.tool_name, "docking executable not on PATH")


def _generic(inputs: dict[str, Any], candidate: ExternalToolCandidate) -> dict[str, Any]:
    return {
        "status": "registered",
        "evidence_type": "NOT AVAILABLE",
        "tool": candidate.tool_name,
        "note": "no capability-specific executor; tool is installed and registered for reuse",
        "version": candidate.version,
    }


EXTERNAL_EXECUTORS: dict[str, Callable[[dict[str, Any], ExternalToolCandidate], dict[str, Any]]] = {
    "smiles_validation": execute_cheminformatics,
    "cheminformatics": execute_cheminformatics,
    "conformer_generation": _generic,
    "ligand_docking": execute_docking,
    "protein_protein_docking": execute_docking,
    "ternary_complex_modeling": _generic,
    "retrosynthesis": execute_retrosynthesis,
    "reaction_prediction": execute_retrosynthesis,
    "admet_toxicity": execute_admet,
    "degradation_prediction": execute_degradation,
    "molecular_ml": execute_degradation,
}


def run_external(
    capability: str,
    candidate: ExternalToolCandidate,
    inputs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    executor = EXTERNAL_EXECUTORS.get(capability, _generic)
    try:
        return executor(inputs or {}, candidate)
    except Exception as exc:  # pragma: no cover - defensive
        return _not_available(candidate.tool_name, f"executor raised: {exc}")
