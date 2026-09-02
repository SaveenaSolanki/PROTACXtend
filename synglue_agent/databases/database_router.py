"""Router for mapping natural-language database tasks to candidate sources."""

from __future__ import annotations

from typing import Any

from synglue_agent.databases.database_status import check_all_database_statuses
from synglue_agent.databases.database_registry import get_database_registry


RULES: list[tuple[list[str], list[str]]] = [
    (["find", "ligands"], ["ChEMBL", "BindingDB", "PubChem", "IUPHAR/BPS Guide to Pharmacology"]),
    (["find", "protacs"], ["PROTAC-DB 3.0", "PROTACpedia", "PROTAC-8K"]),
    (["protac", "permeability"], ["PROTAC-DB 3.0"]),
    (["protac", "pharmacokinetic"], ["PROTAC-DB 3.0"]),
    (["protac", "ternary", "affinity"], ["PROTAC-DB 3.0", "RCSB PDB"]),
    (["protac", "binding", "affinity"], ["PROTAC-DB 3.0", "ChEMBL", "BindingDB"]),
    (["ternary", "structures"], ["RCSB PDB", "PROTAC-DB 3.0", "AlphaFold DB"]),
    (["target", "disease"], ["Open Targets", "DisGeNET", "OMIM", "cBioPortal"]),
    (["cancer", "dependency"], ["DepMap", "cBioPortal", "TCGA / GDC"]),
    (["normal", "tissue", "expression"], ["GTEx", "Human Protein Atlas", "ProteomicsDB"]),
    (["e3", "substrate", "biology"], ["UbiBrowser", "UbiNet", "BioGRID", "IntAct", "STRING"]),
    (["search", "patents"], ["Lens.org", "SureChEMBL"]),
    (["search", "literature"], ["PubMed", "Europe PMC", "Semantic Scholar", "OpenAlex"]),
    (["purchasable", "analogs"], ["ZINC", "Enamine REAL", "MolPort", "eMolecules"]),
]


def _pick_databases(task: str) -> list[str]:
    task_l = task.lower()
    for keys, dbs in RULES:
        if all(k in task_l for k in keys):
            return dbs
    if "protac" in task_l:
        return ["PROTAC-DB 3.0", "PROTACpedia", "PROTAC-8K"]
    if "patent" in task_l:
        return ["Lens.org", "SureChEMBL"]
    if "literature" in task_l:
        return ["PubMed", "Europe PMC", "Semantic Scholar", "OpenAlex"]
    return []


def route_database_request(task_description: str) -> dict[str, Any]:
    task = (task_description or "").strip()
    recommended = _pick_databases(task)
    statuses = check_all_database_statuses()
    registry_by_name = {d["name"]: d for d in get_database_registry()}
    available = []
    unavailable = []
    restricted = []
    for name in recommended:
        st = statuses.get(name, {})
        entry = registry_by_name.get(name, {})
        if st.get("status") in {"api_live", "download_local", "api_and_download"}:
            available.append(name)
        else:
            unavailable.append(name)
        if entry.get("access_mode", "").startswith("restricted") or st.get("status", "").startswith("restricted"):
            restricted.append(name)
    return {
        "task": task,
        "recommended_databases": recommended,
        "available_databases": available,
        "unavailable_databases": unavailable,
        "restricted_databases": restricted,
        "honest_execution_note": (
            "Databases are recommendation-only until API/local checks succeed. "
            "No fake API output, no fake local availability."
        ),
    }
