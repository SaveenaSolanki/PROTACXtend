"""Local PROTAC-DB / PROTACpedia style accessors."""

from __future__ import annotations

from typing import Any

from synglue_agent.tools.protac_toolbox import ProtacDesignToolbox


_TOOLBOX = ProtacDesignToolbox()


def load_local_protacdb() -> list[dict[str, Any]]:
    return _TOOLBOX.load_table("protacdb_local.csv")


def search_by_target(target: str) -> list[dict[str, Any]]:
    target_u = target.upper()
    return [row for row in load_local_protacdb() if row.get("target", "").upper() == target_u]


def search_by_e3(e3_ligase: str) -> list[dict[str, Any]]:
    e3_u = e3_ligase.upper()
    return [row for row in load_local_protacdb() if row.get("e3_ligase", "").upper() == e3_u]


def extract_warheads(target: str | None = None) -> list[dict[str, Any]]:
    rows = _TOOLBOX.load_curated_warheads()
    return [row for row in rows if target is None or row.get("target", "").upper() == target.upper()]


def extract_linkers(linker_class: str | None = None) -> list[dict[str, Any]]:
    rows = _TOOLBOX.load_curated_linkers()
    return [row for row in rows if linker_class is None or row.get("linker_class", "").upper() == linker_class.upper()]


def extract_e3_ligands(e3_ligase: str | None = None) -> list[dict[str, Any]]:
    rows = _TOOLBOX.load_curated_e3_ligands()
    return [row for row in rows if e3_ligase is None or row.get("e3_ligase", "").upper() == e3_ligase.upper()]


def get_known_protac_smiles() -> list[str]:
    return [row.get("smiles", "") for row in _TOOLBOX.load_known_protacs() if row.get("smiles")]
