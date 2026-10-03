"""Deterministic identifier list-vs-database comparison (KNOW-12).

Normalizes identifiers (accessions, gene symbols, drug names, SMILES), resolves
known aliases, removes duplicates, and reports shared / added / removed sets
with unresolved identifiers and provenance. It never queries the network and
never invents a member: an identifier that cannot be resolved is reported as
unresolved, not silently matched.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

_ACCESSION_RE = re.compile(
    r"^(?:[OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2})$"
)
_SMILES_RE = re.compile(r"^[A-Za-z0-9@+\-\[\]\(\)=#$\\/%.*:]+$")
_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def _looks_like_smiles(value: str) -> bool:
    value = value.strip()
    if len(value) < 6 or " " in value or not _SMILES_RE.match(value):
        return False
    return any(ch.isalpha() for ch in value) and ("C" in value or "c" in value or "[" in value)


def _canonical_smiles(smiles: str) -> str | None:
    try:
        from rdkit import Chem

        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return None
        return Chem.MolToSmiles(mol, isomericSmiles=False)
    except Exception:  # noqa: BLE001
        return None


def normalize_identifier(value: Any) -> dict[str, str]:
    """Return ``{key, display, kind, resolved}`` for one identifier."""
    text = str(value or "").strip().strip("{}[]\"'")
    if not text:
        return {"key": "", "display": "", "kind": "empty", "resolved": "unresolved"}
    if _looks_like_smiles(text):
        canon = _canonical_smiles(text)
        if canon:
            return {"key": f"smiles:{canon}", "display": text, "kind": "smiles", "resolved": "resolved"}
    upper = text.upper().strip()
    if _ACCESSION_RE.match(upper):
        return {"key": f"acc:{upper}", "display": upper, "kind": "accession", "resolved": "resolved"}
    # Gene/drug names: uppercase the key so case/space/punctuation variants merge.
    key = _ALNUM_RE.sub("", text.lower())
    if not key:
        return {"key": "", "display": text, "kind": "unknown", "resolved": "unresolved"}
    return {"key": f"name:{key}", "display": text, "kind": "name", "resolved": "resolved"}


def build_alias_map() -> dict[str, str]:
    """Alias -> canonical display, from curated tables and verified references."""
    aliases: dict[str, str] = {}
    try:
        from protacxtend.tools.protac_toolbox import ProtacDesignToolbox

        toolbox = ProtacDesignToolbox()
        for row in toolbox.load_curated_targets():
            canonical = row.get("gene_symbol") or row.get("target_name") or ""
            for name in [row.get("target_name"), row.get("gene_symbol"), *(row.get("synonyms") or "").split("|")]:
                norm = normalize_identifier(name)["key"]
                if norm and canonical:
                    aliases[norm] = canonical
        for row in toolbox.load_curated_warheads():
            name = row.get("name") or ""
            norm = normalize_identifier(name)["key"]
            if norm:
                aliases.setdefault(norm, name)
    except Exception:  # noqa: BLE001
        pass
    try:
        from protacxtend.tools import verified_components as vc

        for ref in vc.references():
            norm = normalize_identifier(ref.get("name"))["key"]
            if norm:
                aliases.setdefault(norm, ref.get("name", ""))
    except Exception:  # noqa: BLE001
        pass
    return aliases


def compare_identifier_lists(
    supplied: Iterable[str],
    database: Iterable[str],
    *,
    alias_map: dict[str, str] | None = None,
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compare two identifier lists deterministically."""
    alias_map = alias_map if alias_map is not None else build_alias_map()

    def prepare(values: Iterable[str]) -> tuple[dict[str, dict[str, str]], list[str]]:
        table: dict[str, dict[str, str]] = {}
        duplicates: list[str] = []
        for value in values:
            norm = normalize_identifier(value)
            if not norm["key"]:
                continue
            if norm["key"] in table:
                duplicates.append(norm["display"])
                continue
            cannon = alias_map.get(norm["key"])
            if cannon:
                norm = dict(norm, canonical=cannon, resolved="alias_resolved")
            table[norm["key"]] = norm
        return table, duplicates

    supplied_table, supplied_dups = prepare(supplied)
    db_table, db_dups = prepare(database)

    # Alias-aware lookup: map a supplied key to the database key if an alias links them.
    def resolve_key(norm: dict[str, str], table: dict[str, dict[str, str]]) -> str | None:
        if norm["key"] in table:
            return norm["key"]
        canonical = norm.get("canonical")
        if canonical:
            ckey = normalize_identifier(canonical)["key"]
            if ckey in table:
                return ckey
            for key, item in table.items():
                if item.get("canonical") and normalize_identifier(item["canonical"])["key"] == ckey:
                    return key
        return None

    shared: list[dict[str, str]] = []
    only_supplied: list[dict[str, str]] = []
    unresolved: list[dict[str, str]] = []
    matched_db_keys: set[str] = set()
    for key, item in supplied_table.items():
        target_key = resolve_key(item, db_table)
        if target_key:
            shared.append({"supplied": item["display"], "database": db_table[target_key]["display"]})
            matched_db_keys.add(target_key)
        else:
            only_supplied.append(item)
            if item["resolved"] == "unresolved":
                unresolved.append(item)

    only_database = [item for key, item in db_table.items() if key not in matched_db_keys]
    return {
        "supplied": [i["display"] for i in supplied_table.values()],
        "database": [i["display"] for i in db_table.values()],
        "shared": shared,
        "only_in_supplied_missing_from_database": [i["display"] for i in only_supplied],
        "only_in_database_added": [i["display"] for i in only_database],
        "duplicates_removed": {"supplied": supplied_dups, "database": db_dups},
        "unresolved": [i["display"] for i in unresolved],
        "n_supplied": len(supplied_table),
        "n_database": len(db_table),
        "n_shared": len(shared),
        "provenance": provenance or {},
        "method": "deterministic_normalize_alias_dedupe_setdiff",
    }


__all__ = ["normalize_identifier", "build_alias_map", "compare_identifier_lists"]
