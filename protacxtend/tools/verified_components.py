"""Loader for source-backed, atom-mapped PROTAC components.

The registry is built by ``scripts/build_verified_components.py`` from real
PROTAC-DB entries (MZ1, dBET1, MT-802) and re-verified by RDKit ``molzip``
reassembly + InChIKey round-trip. Components carry the *real* conjugation atom
observed in the source, so a product assembled from them is a chemist-reviewable
candidate rather than a hypothetical-marker placeholder.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

_DATA = Path(__file__).resolve().parents[1] / "data" / "verified_components.json"


@lru_cache(maxsize=1)
def load_registry() -> dict[str, Any]:
    if not _DATA.exists():
        return {"components": [], "references": []}
    return json.loads(_DATA.read_text(encoding="utf-8"))


def components() -> list[dict[str, Any]]:
    return list(load_registry().get("components", []))


def warhead_for(target: str) -> dict[str, Any] | None:
    target_u = (target or "").strip().upper()
    for comp in components():
        if comp.get("role") == "warhead" and (comp.get("target") or "").upper() == target_u:
            return comp
    return None


def e3_ligand_for(e3_ligase: str, *, source_protac: str | None = None) -> dict[str, Any] | None:
    e3_u = (e3_ligase or "").strip().upper()
    candidates = [
        c for c in components()
        if c.get("role") == "e3_ligand" and (c.get("e3_ligase") or "").upper() == e3_u
    ]
    if source_protac:
        preferred = [c for c in candidates if c.get("source_protac") == source_protac]
        if preferred:
            return preferred[0]
    return candidates[0] if candidates else None


def linker_for(name_contains: str = "PEG3", *, source_protac: str | None = None) -> dict[str, Any] | None:
    candidates = [
        c for c in components()
        if c.get("role") == "linker" and name_contains.lower() in (c.get("name") or "").lower()
    ]
    if source_protac:
        preferred = [c for c in candidates if c.get("source_protac") == source_protac]
        if preferred:
            return preferred[0]
    return candidates[0] if candidates else None


def linker_for_protac(source_protac: str) -> dict[str, Any] | None:
    for comp in components():
        if comp.get("role") == "linker" and comp.get("source_protac") == source_protac:
            return comp
    return None


def reference_for(name: str) -> dict[str, Any] | None:
    for ref in load_registry().get("references", []):
        if (ref.get("name") or "").lower() == name.lower():
            return ref
    return None


def references() -> list[dict[str, Any]]:
    return list(load_registry().get("references", []))


def source_protac() -> dict[str, Any]:
    """Backwards-compatible alias for the MZ1 reference record."""
    return reference_for("MZ1") or {}


def has_verified_pair(target: str, e3_ligase: str) -> bool:
    return bool(warhead_for(target) and e3_ligand_for(e3_ligase))


def verified_paths() -> list[dict[str, str]]:
    """Distinct (target, E3) pairs with a full verified component set."""
    out: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for ref in references():
        target = (ref.get("role") or "").split("-")[0]
        e3 = (ref.get("role") or "").split("-")[-1]
        if target and e3 and (target, e3) not in seen:
            seen.add((target, e3))
            out.append({"target": target, "e3_ligase": e3, "source_protac": ref.get("name", "")})
    return out


def reference_components(target: str, e3_ligase: str) -> dict[str, Any] | None:
    """Return warhead/linker/E3-ligand from the *same* source PROTAC.

    Matching all three by source PROTAC prevents mixing a warhead from one
    structure with a linker/E3 ligand from another and calling it the reference.
    """
    target_u = (target or "").strip().upper()
    e3_u = (e3_ligase or "").strip().upper()
    for ref in references():
        role = ref.get("role") or ""
        parts = role.split("-")
        if len(parts) != 2:
            continue
        if parts[0].upper() != target_u or parts[1].upper() != e3_u:
            continue
        name = ref.get("name", "")
        warhead = next((c for c in components()
                        if c.get("role") == "warhead" and c.get("source_protac") == name), None)
        linker = next((c for c in components()
                       if c.get("role") == "linker" and c.get("source_protac") == name), None)
        e3 = next((c for c in components()
                   if c.get("role") == "e3_ligand" and c.get("source_protac") == name), None)
        if warhead and linker and e3:
            return {"reference": ref, "warhead": warhead, "linker": linker, "e3_ligand": e3}
    return None


__all__ = [
    "load_registry", "components", "warhead_for", "e3_ligand_for", "linker_for",
    "linker_for_protac", "reference_for", "reference_components", "references",
    "source_protac", "has_verified_pair", "verified_paths",
]
