"""PROTACpedia-style local accessors."""

from __future__ import annotations

from typing import Any

from synglue_agent.tools.protac_toolbox import ProtacDesignToolbox


_TOOLBOX = ProtacDesignToolbox()


def load_local_protacpedia() -> list[dict[str, Any]]:
    return _TOOLBOX.load_table("protacpedia_local.csv")


def search_by_target(target: str) -> list[dict[str, Any]]:
    return [row for row in load_local_protacpedia() if row.get("target", "").upper() == target.upper()]


def search_by_e3(e3_ligase: str) -> list[dict[str, Any]]:
    return [row for row in load_local_protacpedia() if row.get("e3_ligase", "").upper() == e3_ligase.upper()]
