"""Compatibility PubChem compound lookup helpers."""

from __future__ import annotations

from typing import Any, Dict

from synglue_agent.tools.protac_toolbox import ProtacDesignToolbox
from synglue_agent.tools.pubchem_lookup import (
    get_compound_by_cid,
    pubchem_similarity_search,
    pubchem_substructure_search,
    search_compound_by_name as pug_search_compound_by_name,
)


_TOOLBOX = ProtacDesignToolbox()


def lookup_pubchem_by_name(name: str, timeout: float = 10.0) -> dict[str, Any]:
    """Lookup PubChem CID and SMILES by compound name using PUG-REST."""

    return pug_search_compound_by_name(name, timeout=timeout)


def lookup_pubchem_by_cid(cid: int | str, timeout: float = 10.0) -> dict[str, Any]:
    """Lookup PubChem compound properties by CID using PUG-REST."""

    return get_compound_by_cid(cid, timeout=timeout)


def search_compound_by_name(name: str) -> list[dict[str, Any]]:
    rows = _TOOLBOX.load_curated_warheads() + _TOOLBOX.load_curated_e3_ligands()
    hits = []
    for row in rows:
        if name.lower() in row.get("name", "").lower():
            hit = dict(row)
            hit["source"] = row.get("source") or "local_seed"
            hit["execution_mode"] = "local_seed"
            hit["classification"] = "stub"
            hit["real_output_generated"] = False
            hits.append(hit)
    return hits


def get_compound_smiles(name: str) -> str | None:
    result = pug_search_compound_by_name(name)
    if result["success"]:
        return result.get("isomeric_smiles") or result.get("canonical_smiles")
    return None


def get_pubchem_compound_smiles(name: str):
    result = pug_search_compound_by_name(name)
    if not result["success"]:
        return None, [result["error"]]
    return result.get("isomeric_smiles") or result.get("canonical_smiles"), []


def get_compound_properties(smiles: str) -> Dict[str, Any]:
    return _TOOLBOX.compute_basic_properties(smiles)


def similarity_search(smiles: str, threshold: float = 0.5) -> list[dict[str, Any]]:
    result = pubchem_similarity_search(smiles, threshold=int(threshold * 100 if threshold <= 1 else threshold))
    return result.get("records", []) if result["success"] else []


def substructure_search(smarts: str) -> list[dict[str, Any]]:
    result = pubchem_substructure_search(smarts)
    return result.get("records", []) if result["success"] else []
