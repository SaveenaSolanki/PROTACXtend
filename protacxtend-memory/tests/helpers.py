"""Deterministic builders used across tests."""

from __future__ import annotations

from typing import Any

from protacpilot_memory.domain.protac import ProtacContext
from protacpilot_memory.domain.protac.evidence import EvidenceRef


def ctx(**kwargs: Any) -> ProtacContext:
    return ProtacContext(**kwargs)


def brd4_vhl(**overrides: Any) -> ProtacContext:
    base = dict(
        target_gene="BRD4",
        target_domain="BD2",
        e3_ligase="VHL",
        cell_line="HEK293",
        assay_type="degradation assay",
        linker_type="PEG",
    )
    base.update(overrides)
    return ProtacContext(**base)


def ev(experiment_id: str, kind: str = "internal_experiment", **kwargs: Any) -> EvidenceRef:
    return EvidenceRef(evidence_type=kind, experiment_id=experiment_id,
                       title=f"{kind} {experiment_id}", **kwargs)


def add_degradation_episode(mem, project_id: str, index: int, dmax: float, **overrides: Any) -> str:
    context = overrides.pop("context", brd4_vhl())
    evidence = overrides.pop("evidence", [ev(f"EXP-{index}")])
    decision_impact = overrides.pop("decision_impact", 0.8)
    return mem.save_episode(
        title=f"BRD4 VHL degradation experiment {index}",
        content=f"observed dmax={dmax} for PEG linker architecture",
        event_type="degradation_assay",
        project_id=project_id,
        context=context,
        observed={"dmax": dmax},
        interpretation="linker geometry affects productive ternary complex formation",
        evidence=evidence,
        decision_impact=decision_impact,
        **overrides,
    )["episode_id"]


def build_semantic(mem, project_id: str, n_support: int = 3, dmax: float = 0.2) -> str:
    for i in range(n_support):
        add_degradation_episode(mem, project_id, i, dmax)
    mem.consolidate(project_id)
    semantics = mem.store.semantics(project_id=project_id)
    assert semantics, "expected a semantic memory to be created"
    return semantics[0]["id"]
