"""Online target and ligand mining fallbacks.

These tools are optional network fallbacks used when a target is not present in
the local curated tables. They never fabricate activity values or SMILES. If an
external source is unavailable, they return warnings and let the workflow fail
transparently or request user-provided chemistry.
"""

from __future__ import annotations

import csv
import json
import math
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from protacxtend.backend.config import DATA_DIR
from protacxtend.backend.schemas import BinderRecord, TargetRecord


CHEMBL_BASE = "https://www.ebi.ac.uk/chembl/api/data"
PUBCHEM_BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
GPROFILER_GOST_URL = "https://biit.cs.ut.ee/gprofiler/api/gost/profile/"


def _get_json(url: str, params: Optional[Dict[str, Any]] = None, timeout: float = 8.0) -> Dict[str, Any]:
    query = urllib.parse.urlencode({key: value for key, value in (params or {}).items() if value not in (None, "")})
    full_url = f"{url}?{query}" if query else url
    request = urllib.request.Request(full_url, headers={"User-Agent": "PROTACXtend/0.1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _post_json(url: str, payload: Dict[str, Any], timeout: float = 8.0) -> Dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "User-Agent": "PROTACXtend/0.1"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except Exception:
        return None


def _p_activity(activity_nM: Optional[float]) -> Optional[float]:
    if activity_nM is None or activity_nM <= 0:
        return None
    return -math.log10(activity_nM * 1e-9)


def classify_activity_mode(assay_description: str = "", mechanism: str = "") -> str:
    text = f"{assay_description} {mechanism}".lower()
    if any(term in text for term in ["activator", "activation", "agonist", "stimulator"]):
        return "activator"
    if any(term in text for term in ["inhibitor", "inhibition", "antagonist", "blocker"]):
        return "inhibitor"
    return "bioactive"


def search_chembl_targets(target_name: str, limit: int = 5) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    try:
        payload = _get_json(f"{CHEMBL_BASE}/target/search.json", {"q": target_name, "limit": limit})
        return payload.get("targets", [])[:limit], warnings
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        warnings.append(f"ChEMBL target search failed: {exc}")
        return [], warnings


def resolve_target_from_chembl(target_name: str) -> tuple[Optional[TargetRecord], list[str]]:
    targets, warnings = search_chembl_targets(target_name)
    if not targets:
        return None, warnings
    preferred = None
    query = target_name.upper()
    for target in targets:
        if target.get("organism", "").lower() == "homo sapiens" and (
            target.get("pref_name", "").upper() == query
            or query in {component.get("accession", "").upper() for component in target.get("target_components", [])}
        ):
            preferred = target
            break
    preferred = preferred or targets[0]
    components = preferred.get("target_components", []) or []
    uniprot = None
    synonyms = []
    for component in components:
        if component.get("accession"):
            uniprot = component.get("accession")
        for synonym in component.get("target_component_synonyms", []) or []:
            value = synonym.get("component_synonym")
            if value:
                synonyms.append(value)
    chembl_id = preferred.get("target_chembl_id")
    record = TargetRecord(
        target_name=preferred.get("pref_name") or target_name,
        gene_symbol=target_name.upper(),
        uniprot_id=uniprot,
        organism=preferred.get("organism", "unknown"),
        synonyms=sorted(set(synonyms))[:30],
        structures=[],
        alphafold_id=f"AF-{uniprot}-F1" if uniprot else None,
        uniprot_confidence=0.72 if uniprot else 0.45,
        known_binder_count=0,
        tractability_score=0.42,
        source="ChEMBL online target search",
        external_ids={"chembl_target_id": chembl_id} if chembl_id else {},
        warnings=["Target was not found locally; resolved from ChEMBL online fallback."],
    )
    return record, warnings


def fetch_chembl_molecule_smiles(molecule_chembl_id: str) -> Optional[str]:
    try:
        payload = _get_json(f"{CHEMBL_BASE}/molecule/{urllib.parse.quote(molecule_chembl_id)}.json")
    except Exception:
        return None
    structures = payload.get("molecule_structures") or {}
    return structures.get("canonical_smiles") or payload.get("canonical_smiles")


def retrieve_chembl_bioactive_ligands(
    target_record: TargetRecord,
    limit: int = 80,
    potency_threshold_nM: float = 10_000.0,
) -> tuple[list[BinderRecord], list[str]]:
    warnings: list[str] = []
    target_chembl_id = target_record.external_ids.get("chembl_target_id") if target_record.external_ids else None
    if not target_chembl_id:
        return [], ["No ChEMBL target ID available for online ligand mining."]
    try:
        payload = _get_json(
            f"{CHEMBL_BASE}/activity.json",
            {
                "target_chembl_id": target_chembl_id,
                "standard_units": "nM",
                "limit": limit,
            },
            timeout=10.0,
        )
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return [], [f"ChEMBL activity retrieval failed: {exc}"]

    allowed_types = {"IC50", "Ki", "Kd", "EC50", "AC50"}
    binders: list[BinderRecord] = []
    seen: set[str] = set()
    for item in payload.get("activities", []):
        activity_type = item.get("standard_type") or ""
        activity_value = _safe_float(item.get("standard_value"))
        if activity_type not in allowed_types or activity_value is None or activity_value > potency_threshold_nM:
            continue
        smiles = item.get("canonical_smiles")
        molecule_id = item.get("molecule_chembl_id")
        if not smiles and molecule_id:
            smiles = fetch_chembl_molecule_smiles(molecule_id)
        if not smiles and item.get("molecule_pref_name"):
            smiles, pubchem_warnings = pubchem_name_to_smiles(item.get("molecule_pref_name", ""))
            warnings.extend(pubchem_warnings)
        if not smiles:
            continue
        key = smiles
        if key in seen:
            continue
        seen.add(key)
        mode = classify_activity_mode(item.get("assay_description", ""), item.get("mechanism_of_action", ""))
        binders.append(
            BinderRecord(
                name=item.get("molecule_pref_name") or molecule_id or f"ChEMBL ligand {len(binders) + 1}",
                target=target_record.gene_symbol or target_record.target_name,
                smiles=smiles,
                activity_type=activity_type,
                activity_nM=activity_value,
                p_activity=_p_activity(activity_value),
                assay_confidence=0.58,
                source="ChEMBL online activity mining",
                year=None,
                metadata={
                    "molecule_chembl_id": molecule_id,
                    "target_chembl_id": target_chembl_id,
                    "activity_mode": mode,
                    "assay_description": item.get("assay_description"),
                    "needs_exit_vector_hypothesis": True,
                },
            )
        )
    binders.sort(key=lambda item: item.activity_nM if item.activity_nM is not None else 999999.0)
    if not binders:
        warnings.append("ChEMBL target was found but no qualifying inhibitor/activator/bioactive SMILES passed filters.")
    return binders, warnings


def pubchem_name_to_smiles(name: str) -> tuple[Optional[str], list[str]]:
    try:
        from protacxtend.tools.pubchem_lookup import search_compound_by_name
    except Exception as exc:
        return None, [f"PubChem executable wrapper unavailable for {name}: {exc}"]
    result = search_compound_by_name(name)
    if not result["success"]:
        return None, [f"PubChem PUG-REST lookup failed for {name}: {result['error']}"]
    smiles = result.get("isomeric_smiles") or result.get("canonical_smiles")
    if not smiles:
        return None, [f"PubChem PUG-REST returned no SMILES for {name}."]
    return smiles, []


def load_local_drugbank_binders(target_record: TargetRecord, drugbank_path: Path | None = None) -> tuple[list[BinderRecord], list[str]]:
    path = drugbank_path or DATA_DIR / "drugbank_local.csv"
    if not path.exists():
        return [], ["DrugBank fallback skipped: add licensed export to protacxtend/data/drugbank_local.csv."]
    target_values = {target_record.target_name.upper(), target_record.gene_symbol.upper(), (target_record.uniprot_id or "").upper()}
    binders: list[BinderRecord] = []
    with path.open("r", newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            row_values = {
                row.get("target_name", "").upper(),
                row.get("gene_symbol", "").upper(),
                row.get("uniprot_id", "").upper(),
            }
            if not target_values & row_values or not row.get("smiles"):
                continue
            activity = _safe_float(row.get("activity_nM"))
            binders.append(
                BinderRecord(
                    name=row.get("drug_name") or row.get("name", "DrugBank ligand"),
                    target=target_record.gene_symbol or target_record.target_name,
                    smiles=row.get("smiles", ""),
                    activity_type=row.get("activity_type", "DrugBank action"),
                    activity_nM=activity,
                    p_activity=_p_activity(activity),
                    assay_confidence=0.64,
                    source="DrugBank licensed local export",
                    metadata={
                        "drugbank_id": row.get("drugbank_id"),
                        "activity_mode": row.get("action_type", "drugbank_action"),
                        "needs_exit_vector_hypothesis": True,
                    },
                )
            )
    return binders, []


def retrieve_gcoupler_biology_context(target_name: str, organism: str = "hsapiens") -> tuple[dict[str, Any], list[str]]:
    """Return g:Profiler/g:GOSt style biology context for a target.

    This supports biology perspective and report context only. It cannot produce
    a final PROTAC SMILES without a chemical ligand source.
    """

    warnings: list[str] = []
    try:
        payload = _post_json(
            GPROFILER_GOST_URL,
            {
                "organism": organism,
                "query": [target_name],
                "sources": ["GO:BP", "REAC", "KEGG", "WP"],
            },
            timeout=10.0,
        )
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {}, [f"g:Profiler/g:Coupler biology fallback failed: {exc}"]
    terms = []
    for row in payload.get("result", [])[:15]:
        terms.append(
            {
                "source": row.get("source"),
                "term_id": row.get("native"),
                "name": row.get("name"),
                "p_value": row.get("p_value"),
                "parents": row.get("parents", []),
            }
        )
    if not terms:
        warnings.append("g:Profiler/g:Coupler returned no enriched biology context for the target.")
    return {"organism": organism, "terms": terms, "source": "g:Profiler/g:GOSt API"}, warnings


def mine_online_target_and_ligands(target_name: str) -> tuple[Optional[TargetRecord], list[BinderRecord], list[str]]:
    warnings: list[str] = []
    target_record, target_warnings = resolve_target_from_chembl(target_name)
    warnings.extend(target_warnings)
    if target_record is None:
        biology, biology_warnings = retrieve_gcoupler_biology_context(target_name)
        warnings.extend(biology_warnings)
        if biology:
            target_record = TargetRecord(
                target_name=target_name,
                gene_symbol=target_name.upper(),
                organism="human",
                uniprot_confidence=0.0,
                known_binder_count=0,
                tractability_score=0.12,
                source="biology context fallback",
                biology_context=biology,
                warnings=[
                    "Target was not resolved to a chemical design target. Biology context is available, but no ligand-derived warhead can be built."
                ],
            )
        return target_record, [], warnings

    drugbank_binders, drugbank_warnings = load_local_drugbank_binders(target_record)
    warnings.extend(drugbank_warnings)
    chembl_binders, chembl_warnings = retrieve_chembl_bioactive_ligands(target_record)
    warnings.extend(chembl_warnings)
    binders = drugbank_binders + chembl_binders
    if not binders:
        biology, biology_warnings = retrieve_gcoupler_biology_context(target_record.gene_symbol or target_name)
        warnings.extend(biology_warnings)
        target_record.biology_context = biology
    target_record.known_binder_count = len(binders)
    if binders:
        target_record.tractability_score = max(target_record.tractability_score, min(0.72, 0.35 + 0.02 * len(binders)))
    return target_record, binders, warnings
