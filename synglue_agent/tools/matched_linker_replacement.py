"""Matched molecular pair-inspired linker replacement utilities."""

from __future__ import annotations

from synglue_agent.backend.schemas import LinkerRecord
from synglue_agent.tools.linker_generator import generate_linkers_for_pair


def propose_replacement_linkers(parent_linker: LinkerRecord, desired_class: str | None = None) -> list[LinkerRecord]:
    classes = [desired_class] if desired_class else [parent_linker.linker_class, "PEG", "alkyl", "triazole"]
    return [linker for linker in generate_linkers_for_pair(classes, max_linkers=16) if linker.name != parent_linker.name]
