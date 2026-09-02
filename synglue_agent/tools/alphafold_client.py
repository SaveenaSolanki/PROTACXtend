"""AlphaFold DB structure availability stub."""

from __future__ import annotations

from synglue_agent.tools.target_resolver import resolve_target


def retrieve_alphafold_id(target_name: str) -> str | None:
    return resolve_target(target_name).alphafold_id


def retrieve_alphafold_confidence(target_name: str) -> float:
    record = resolve_target(target_name)
    return 0.75 if record.alphafold_id else 0.0
