"""Explicit tool provenance for the canonical stack.

Every module result must name the tool that produced it *and* the tool's
version, backend and citation. Without that, a result is not reproducible and
the :class:`~protacxtend.canonical.critics.ReproducibilityCritic` fails the
run closed.

This registry is the single source of truth for those identities. It is a
dependency leaf: it imports only the schema base class and the package
version, so both modules and critics can use it.
"""

from __future__ import annotations

from typing import Any

from protacxtend import __version__
from protacxtend.backend.schemas import BaseModel, Field

#: Fallback version when a tool is not explicitly registered. The package
#: version is always included so a released build is identifiable.
DEFAULT_TOOL_VERSION = f"protacxtend-{__version__}"


class ToolProvenance(BaseModel):
    """Identity of a scientific tool: name, version, backend, citation."""

    tool: str = ""
    tool_version: str = ""
    backend: str = ""
    modality: str = ""
    citation: str = ""
    deterministic: bool = True
    registry_source: str = "canonical"


#: Registered tool identities used by the nine canonical modules and the
#: executor. Versions are bumped when behaviour changes in a way that would
#: invalidate a benchmark result.
TOOL_PROVENANCE: dict[str, ToolProvenance] = {
    "deterministic_engine.target_resolution": ToolProvenance(
        tool="deterministic_engine.target_resolution",
        tool_version="1.1.0",
        backend="curated_targets + uniprot",
        modality="target_identity",
        citation="protacxtend/data/curated_targets.csv; UniProt REST",
    ),
    "deterministic_engine.binder_retrieval": ToolProvenance(
        tool="deterministic_engine.binder_retrieval",
        tool_version="1.0.0",
        backend="chembl + bindingdb",
        modality="ligand_retrieval",
        citation="ChEMBL; BindingDB",
    ),
    "deterministic_engine.e3_selection": ToolProvenance(
        tool="deterministic_engine.e3_selection",
        tool_version="1.1.0",
        backend="curated_e3_ligands + cell_context",
        modality="e3_selection",
        citation="protacxtend E3 context engine",
    ),
    "deterministic_engine.construction_validation": ToolProvenance(
        tool="deterministic_engine.construction_validation",
        tool_version="1.0.0",
        backend="rdkit",
        modality="chemistry",
        citation="RDKit; linker generator",
    ),
    "deterministic_engine.ternary": ToolProvenance(
        tool="deterministic_engine.ternary",
        tool_version="1.0.0",
        backend="ternary_feasibility",
        modality="structure",
        citation="protacxtend ternary feasibility model",
    ),
    "deterministic_engine.degradation": ToolProvenance(
        tool="deterministic_engine.degradation",
        tool_version="1.0.0",
        backend="chemprop/heuristic",
        modality="degradation",
        citation="Chemprop degradation model; heuristic fallback flagged",
    ),
    "deterministic_engine.admet": ToolProvenance(
        tool="deterministic_engine.admet",
        tool_version="1.0.0",
        backend="admet predictors",
        modality="adme",
        citation="protacxtend ADMET predictors",
    ),
    "resistance_mechanisms.predict_resistance": ToolProvenance(
        tool="resistance_mechanisms.predict_resistance",
        tool_version="1.1.0",
        backend="curated resistance catalogue",
        modality="resistance",
        citation="protacxtend resistance catalogue",
    ),
    "scientific_contract.experiment_design": ToolProvenance(
        tool="scientific_contract.experiment_design",
        tool_version="1.0.0",
        backend="scientific_contract",
        modality="experimental_design",
        citation="protacxtend scientific contract",
    ),
    "scientific_engine": ToolProvenance(
        tool="scientific_engine",
        tool_version="1.0.0",
        backend="deterministic|adaptive",
        modality="orchestration",
        citation="protacxtend canonical control plane",
    ),
    "resistance_profile": ToolProvenance(
        tool="resistance_profile",
        tool_version="1.1.0",
        backend="curated resistance catalogue",
        modality="resistance",
        citation="protacxtend resistance catalogue",
    ),
}


def resolve_tool_provenance(tool: str, *, module_id: str = "") -> ToolProvenance:
    """Return explicit provenance for ``tool``; unregistered tools get a
    clearly-marked inferred identity (never an empty version)."""
    if not tool:
        tool = f"unregistered:{module_id or 'unknown'}"
    registered = TOOL_PROVENANCE.get(tool)
    if registered is not None:
        return registered
    return ToolProvenance(
        tool=tool,
        tool_version=DEFAULT_TOOL_VERSION,
        backend="unregistered",
        modality="unknown",
        citation="",
        registry_source="inferred",
    )


def provenance_payload(tool: str, *, module_id: str = "", **extra: Any) -> dict[str, Any]:
    """Flat provenance dict for ``ModuleResult.provenance``."""
    record = resolve_tool_provenance(tool, module_id=module_id)
    payload = record.model_dump()
    payload["package_version"] = __version__
    payload.update(extra)
    return payload


def provenance_is_explicit(provenance: dict[str, Any] | None) -> bool:
    """True when a provenance record names a version and a tool."""
    if not provenance:
        return False
    return bool(provenance.get("tool")) and bool(provenance.get("tool_version"))


def registered_tools() -> list[str]:
    return sorted(TOOL_PROVENANCE)


__all__ = [
    "DEFAULT_TOOL_VERSION",
    "TOOL_PROVENANCE",
    "ToolProvenance",
    "provenance_is_explicit",
    "provenance_payload",
    "registered_tools",
    "resolve_tool_provenance",
]
