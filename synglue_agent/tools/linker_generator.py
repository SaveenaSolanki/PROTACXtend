"""Linker generation functions."""

from __future__ import annotations

from typing import Sequence

from synglue_agent.backend.schemas import LinkerRecord
from synglue_agent.tools.protac_toolbox import ProtacDesignToolbox


_TOOLBOX = ProtacDesignToolbox()


def generate_rule_based_linkers(linker_types: Sequence[str], max_linkers: int = 32) -> list[LinkerRecord]:
    return _TOOLBOX.generate_rule_based_linkers(linker_types, max_linkers)


def load_curated_linkers() -> list[dict[str, str]]:
    return _TOOLBOX.load_curated_linkers()


def generate_brics_recap_linkers(linker_types: Sequence[str] | None = None) -> list[LinkerRecord]:
    return _TOOLBOX.generate_linkers(linker_types or ["PEG", "alkyl", "amide"], max_linkers=24)


def generate_known_protac_linkers(linker_types: Sequence[str] | None = None) -> list[LinkerRecord]:
    return _TOOLBOX.generate_linkers(linker_types, max_linkers=24)


def generate_linkers_for_pair(linker_types: Sequence[str] | None = None, max_linkers: int = 64) -> list[LinkerRecord]:
    return _TOOLBOX.generate_linkers(linker_types, max_linkers=max_linkers)


def score_linker_properties(linker: LinkerRecord) -> float:
    return linker.synthetic_feasibility_proxy
