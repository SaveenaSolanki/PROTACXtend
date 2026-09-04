"""Workflow-ready PROTAC component wrappers with honest provenance.

These helpers sit above the lower-level SynGlue lookup modules and normalize
their outputs for agent workflows. Network-backed services are never called
unless ``allow_network=True`` is passed explicitly by the caller.
"""

from __future__ import annotations

import csv
import hashlib
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from protacxtend.backend.config import DATA_DIR
from protacxtend.tools.chemistry_core import (
    analyze_protac_like_properties,
    compute_descriptors,
    detect_attachment_points,
    tanimoto_similarity,
    validate_smiles,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CURATED_TARGETS = DATA_DIR / "curated_targets.csv"
CURATED_E3_LIGANDS = DATA_DIR / "curated_e3_ligands.csv"
KNOWN_PROTACS = DATA_DIR / "known_protac_smiles.csv"
CURATED_EXIT_VECTOR_MAP = DATA_DIR / "curated_exit_vector_map.csv"

STATUS_EXECUTABLE_NOT_TESTED = "executable_not_tested"
STATUS_LOCAL_DEMO = "local_demo_data_only"
STATUS_NOT_RUN = "planned_integration"
STATUS_MISSING = "missing"


@dataclass
class ToolProvenance:
    score_name: str
    evidence_type: str
    tool_status: str
    source_tool_or_database: str
    source_file_or_url: str | None
    model_version: str | None = None
    run_timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    input_hash: str = ""
    limitations: str = ""
    confidence: float | None = None
    uncertainty: float | None = None
    applicability_domain: str | None = None
    claim_allowed: str = ""


def _hash_payload(payload: Any) -> str:
    return hashlib.sha256(repr(payload).encode("utf-8")).hexdigest()[:16]


def _read_csv(path: str | Path) -> list[dict[str, str]]:
    selected = Path(path)
    if not selected.exists():
        return []
    with selected.open("r", newline="", encoding="utf-8") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _provenance(
    *,
    score_name: str,
    evidence_type: str,
    tool_status: str,
    source_tool_or_database: str,
    source_file_or_url: str | Path | None,
    query: Any,
    limitations: str,
    confidence: float | None = None,
    claim_allowed: str = "",
    model_version: str | None = None,
    applicability_domain: str | None = None,
) -> dict[str, Any]:
    prov = ToolProvenance(
        score_name=score_name,
        evidence_type=evidence_type,
        tool_status=tool_status,
        source_tool_or_database=source_tool_or_database,
        source_file_or_url=str(source_file_or_url) if source_file_or_url is not None else None,
        model_version=model_version,
        input_hash=_hash_payload(query),
        limitations=limitations,
        confidence=confidence,
        uncertainty=None if confidence is None else round(1.0 - confidence, 4),
        applicability_domain=applicability_domain,
        claim_allowed=claim_allowed,
    )
    return asdict(prov)


def _normalize(value: Any) -> str:
    return str(value or "").strip().lower()


def _split_pipe(value: str | None) -> list[str]:
    return [item.strip() for item in str(value or "").split("|") if item.strip()]


def load_local_target_records(path: str | Path = CURATED_TARGETS) -> dict[str, Any]:
    rows = _read_csv(path)
    provenance = _provenance(
        score_name="target_resolution",
        evidence_type="local_database",
        tool_status=STATUS_LOCAL_DEMO,
        source_tool_or_database="SynGlue curated target table",
        source_file_or_url=path,
        query={"path": str(path)},
        limitations="Local curated target seed; not a live UniProt verification.",
        claim_allowed="May claim local curated target metadata only.",
    )
    return {"success": bool(rows), "records": rows, "provenance": provenance, "error": None if rows else "no_local_target_rows"}


def resolve_target_with_provenance(
    target_name: str,
    uniprot_id: str | None = None,
    *,
    allow_network: bool = False,
    local_path: str | Path = CURATED_TARGETS,
) -> dict[str, Any]:
    """Resolve target metadata with UniProt-first optional lookup and local fallback labeling."""

    query = {"target_name": target_name, "uniprot_id": uniprot_id, "allow_network": allow_network}
    if allow_network:
        try:
            from protacxtend.tools.uniprot_lookup import get_uniprot_record, search_uniprot

            result = get_uniprot_record(uniprot_id) if uniprot_id else search_uniprot(target_name, top_k=1)
            records = [result] if uniprot_id and result.get("success") else result.get("records", [])
            if records:
                record = records[0]
                provenance = _provenance(
                    score_name="target_resolution",
                    evidence_type="external_api",
                    tool_status=STATUS_EXECUTABLE_NOT_TESTED,
                    source_tool_or_database="UniProt REST",
                    source_file_or_url=record.get("source_url"),
                    query=query,
                    limitations="Live UniProt wrapper result; downstream biological tractability still requires independent evidence.",
                    confidence=0.9 if record.get("reviewed") else 0.75,
                    claim_allowed="May claim target metadata was retrieved from UniProt REST.",
                )
                return {"success": True, "record": record, "source": "uniprot_rest", "provenance": provenance, "warnings": []}
        except Exception as exc:
            network_warning = f"UniProt lookup failed and local fallback was attempted: {exc}"
        else:
            network_warning = "UniProt lookup returned no hit and local fallback was attempted."
    else:
        network_warning = "UniProt REST was not called; using local fallback only."

    target_l = _normalize(target_name)
    uniprot_l = _normalize(uniprot_id)
    for row in _read_csv(local_path):
        synonyms = [_normalize(item) for item in _split_pipe(row.get("synonyms"))]
        if target_l in {_normalize(row.get("target_name")), _normalize(row.get("gene_symbol")), *synonyms} or (
            uniprot_l and uniprot_l == _normalize(row.get("uniprot_id"))
        ):
            record = {
                "target_name": row.get("target_name"),
                "gene_symbol": row.get("gene_symbol"),
                "uniprot_id": row.get("uniprot_id") or None,
                "organism": row.get("organism"),
                "synonyms": _split_pipe(row.get("synonyms")),
                "structures": _split_pipe(row.get("structures")),
                "alphafold_id": row.get("alphafold_id") or None,
                "known_binder_count": int(float(row.get("known_binder_count") or 0)),
                "tractability_score": float(row.get("tractability_score") or 0.0),
                "source": "local_curated_seed",
            }
            provenance = _provenance(
                score_name="target_resolution",
                evidence_type="local_database",
                tool_status=STATUS_LOCAL_DEMO,
                source_tool_or_database="SynGlue curated target table",
                source_file_or_url=local_path,
                query=query,
                limitations="Local fallback metadata; UniProt REST was not verified for this result.",
                confidence=float(row.get("uniprot_confidence") or 0.0),
                claim_allowed="May claim local curated target fallback only.",
            )
            return {"success": True, "record": record, "source": "local_curated_seed", "provenance": provenance, "warnings": [network_warning]}

    provenance = _provenance(
        score_name="target_resolution",
        evidence_type="missing",
        tool_status=STATUS_MISSING,
        source_tool_or_database="UniProt REST / SynGlue curated target table",
        source_file_or_url=local_path,
        query=query,
        limitations="No target record was resolved.",
        claim_allowed="No target identity claim allowed.",
    )
    return {"success": False, "record": None, "source": "missing", "provenance": provenance, "warnings": [network_warning], "error": "target_not_found"}


def find_chembl_binders(
    target_query: str,
    *,
    target_chembl_id: str | None = None,
    allow_network: bool = False,
    top_k: int = 25,
) -> dict[str, Any]:
    query = {"target_query": target_query, "target_chembl_id": target_chembl_id, "top_k": top_k, "allow_network": allow_network}
    if not allow_network:
        return {
            "success": False,
            "records": [],
            "status": "not_run",
            "error": "ChEMBL REST was not called because allow_network=False.",
            "provenance": _provenance(
                score_name="binder_retrieval",
                evidence_type="not_run",
                tool_status=STATUS_NOT_RUN,
                source_tool_or_database="ChEMBL REST API",
                source_file_or_url="https://www.ebi.ac.uk/chembl/api/data",
                query=query,
                limitations="External ChEMBL lookup was available as a wrapper but not executed.",
                claim_allowed="No ChEMBL binder claim allowed.",
            ),
        }
    from protacxtend.tools.chembl_lookup import get_target_activities, rank_warhead_candidates, search_targets

    chembl_id = target_chembl_id
    source_url = None
    if not chembl_id:
        targets = search_targets(target_query, top_k=1)
        source_url = targets.get("source_url")
        if not targets.get("success"):
            return {**targets, "records": [], "provenance": _provenance(score_name="binder_retrieval", evidence_type="external_api", tool_status=STATUS_EXECUTABLE_NOT_TESTED, source_tool_or_database="ChEMBL REST API", source_file_or_url=source_url, query=query, limitations="ChEMBL target search did not return a usable target.", claim_allowed="No ChEMBL binder claim allowed.")}
        chembl_id = targets["records"][0]["target_id"]
    activities = get_target_activities(chembl_id, top_k=top_k)
    records = rank_warhead_candidates(activities.get("records", []))
    provenance = _provenance(
        score_name="binder_retrieval",
        evidence_type="external_api",
        tool_status=STATUS_EXECUTABLE_NOT_TESTED,
        source_tool_or_database="ChEMBL REST API",
        source_file_or_url=activities.get("source_url") or source_url,
        query=query,
        limitations="ChEMBL bioactivity records require assay/context review before selecting warheads.",
        confidence=0.75 if records else 0.0,
        claim_allowed="May claim ChEMBL binder retrieval only for returned records.",
    )
    return {"success": bool(records), "records": records, "status": "ok" if records else "no_hits", "error": None if records else "no_hits", "provenance": provenance}


def load_bindingdb_binders(target_query: str, *, path: str | Path | None = None, top_k: int = 100) -> dict[str, Any]:
    from protacxtend.tools.bindingdb_lookup import search_bindingdb_local

    result = search_bindingdb_local(target_query, top_k=top_k, path=path)
    selected_path = path or "BindingDB local TSV auto-discovery"
    result["provenance"] = _provenance(
        score_name="binder_retrieval",
        evidence_type="local_database" if result.get("success") else "missing",
        tool_status=STATUS_EXECUTABLE_NOT_TESTED if result.get("success") else STATUS_MISSING,
        source_tool_or_database="BindingDB local TSV",
        source_file_or_url=selected_path,
        query={"target_query": target_query, "path": str(path) if path else None, "top_k": top_k},
        limitations="BindingDB wrapper uses a local TSV export; no live BindingDB query is implied.",
        confidence=0.65 if result.get("success") else 0.0,
        claim_allowed="May claim local BindingDB TSV evidence only." if result.get("success") else "No BindingDB binder claim allowed.",
    )
    return result


def bindingdb_api_adapter(target_query: str, *, allow_network: bool = False) -> dict[str, Any]:
    query = {"target_query": target_query, "allow_network": allow_network}
    return {
        "success": False,
        "records": [],
        "status": "not_connected" if allow_network else "not_run",
        "error": "No live BindingDB API adapter is connected; use local TSV loader.",
        "provenance": _provenance(
            score_name="binder_retrieval",
            evidence_type="not_run",
            tool_status=STATUS_NOT_RUN,
            source_tool_or_database="BindingDB",
            source_file_or_url="https://www.bindingdb.org/",
            query=query,
            limitations="BindingDB live API was not implemented; local TSV loader is the supported backend.",
            claim_allowed="No live BindingDB API claim allowed.",
        ),
    }


def pubchem_compound_lookup(query_value: str | int, *, query_type: str = "name", allow_network: bool = False) -> dict[str, Any]:
    query = {"query_value": query_value, "query_type": query_type, "allow_network": allow_network}
    if not allow_network:
        return {
            "success": False,
            "records": [],
            "status": "not_run",
            "error": "PubChem PUG-REST was not called because allow_network=False.",
            "provenance": _provenance(score_name="compound_lookup", evidence_type="not_run", tool_status=STATUS_NOT_RUN, source_tool_or_database="PubChem PUG-REST", source_file_or_url="https://pubchem.ncbi.nlm.nih.gov/docs/pug-rest", query=query, limitations="External PubChem compound lookup was not executed.", claim_allowed="No PubChem compound claim allowed."),
        }
    from protacxtend.tools.pubchem_lookup import get_cid_from_smiles, get_compound_by_cid, search_compound_by_name

    if query_type == "cid":
        result = get_compound_by_cid(query_value)
    elif query_type == "smiles":
        result = get_cid_from_smiles(str(query_value))
    else:
        result = search_compound_by_name(str(query_value))
    result["provenance"] = _provenance(score_name="compound_lookup", evidence_type="external_api", tool_status=STATUS_EXECUTABLE_NOT_TESTED, source_tool_or_database="PubChem PUG-REST", source_file_or_url=result.get("source_url"), query=query, limitations="PubChem identity/similarity is not patent clearance or biological validation.", confidence=0.8 if result.get("success") else 0.0, claim_allowed="May claim PubChem compound lookup only for returned records.")
    return result


def pubchem_similarity_wrapper(smiles: str, *, threshold: int = 90, top_k: int = 20, allow_network: bool = False) -> dict[str, Any]:
    query = {"smiles": smiles, "threshold": threshold, "top_k": top_k, "allow_network": allow_network}
    if not allow_network:
        return {
            "success": False,
            "records": [],
            "status": "not_run",
            "error": "PubChem similarity search was not called because allow_network=False.",
            "provenance": _provenance(score_name="compound_similarity", evidence_type="not_run", tool_status=STATUS_NOT_RUN, source_tool_or_database="PubChem PUG-REST", source_file_or_url="https://pubchem.ncbi.nlm.nih.gov/docs/pug-rest", query=query, limitations="External PubChem similarity search was not executed.", claim_allowed="No PubChem similarity claim allowed."),
        }
    from protacxtend.tools.pubchem_lookup import pubchem_similarity_search

    result = pubchem_similarity_search(smiles, threshold=threshold, top_k=top_k)
    result["provenance"] = _provenance(score_name="compound_similarity", evidence_type="external_api", tool_status=STATUS_EXECUTABLE_NOT_TESTED, source_tool_or_database="PubChem PUG-REST", source_file_or_url=result.get("source_url"), query=query, limitations="PubChem 2D similarity is not novelty/IP clearance.", confidence=0.75 if result.get("success") else 0.0, claim_allowed="May claim PubChem similarity search only for returned records.")
    return result


def validate_e3_ligand_table(path: str | Path = CURATED_E3_LIGANDS) -> dict[str, Any]:
    required = {"name", "e3_ligase", "smiles", "ligand_class", "source", "exit_vector_confidence", "stereochemistry_valid", "source_confidence", "diversity_score"}
    rows = _read_csv(path)
    valid_records: list[dict[str, Any]] = []
    invalid_records: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=2):
        missing = sorted(required - set(row))
        validation = validate_smiles(row.get("smiles", ""))
        attachments = detect_attachment_points(row.get("smiles", ""))
        errors = missing + ([] if validation.valid else [validation.error or "invalid_smiles"])
        record = {**row, "row_number": index, "canonical_smiles": validation.canonical_smiles, "attachment_points": attachments}
        if errors:
            record["errors"] = errors
            invalid_records.append(record)
        else:
            valid_records.append(record)
    return {
        "success": bool(valid_records) and not invalid_records,
        "valid_records": valid_records,
        "invalid_records": invalid_records,
        "provenance": _provenance(score_name="e3_ligand_schema_validation", evidence_type="local_database", tool_status=STATUS_EXECUTABLE_NOT_TESTED, source_tool_or_database="SynGlue curated E3 ligand table", source_file_or_url=path, query={"path": str(path)}, limitations="Schema and RDKit validation only; does not prove cellular E3 expression or degradation compatibility.", confidence=1.0 if valid_records and not invalid_records else 0.5, claim_allowed="May claim local E3 ligand schema/SMILES validation only."),
    }


def load_exit_vector_map(path: str | Path = CURATED_EXIT_VECTOR_MAP) -> dict[str, Any]:
    rows = _read_csv(path)
    required = {"component_type", "name", "smiles", "attachment_smarts", "confidence", "source"}
    invalid = []
    records = []
    for index, row in enumerate(rows, start=2):
        errors = sorted(required - set(row))
        validation = validate_smiles(row.get("smiles", ""))
        if not validation.valid:
            errors.append(validation.error or "invalid_smiles")
        item = {**row, "row_number": index, "canonical_smiles": validation.canonical_smiles}
        if errors:
            item["errors"] = errors
            invalid.append(item)
        else:
            records.append(item)
    return {
        "success": bool(records) and not invalid,
        "records": records,
        "invalid_records": invalid,
        "provenance": _provenance(score_name="exit_vector_map", evidence_type="local_database", tool_status=STATUS_EXECUTABLE_NOT_TESTED if rows else STATUS_MISSING, source_tool_or_database="SynGlue curated exit-vector map", source_file_or_url=path, query={"path": str(path)}, limitations="Curated attachment annotations only; no structural exit-vector modeling was run.", confidence=0.7 if records else 0.0, claim_allowed="May claim curated exit-vector annotation only."),
    }


def rdkit_assembly_validation_gate(
    warhead_smiles: str,
    linker_smiles: str,
    e3_smiles: str,
    assembled_smiles: str | None = None,
) -> dict[str, Any]:
    components = {"warhead": warhead_smiles, "linker": linker_smiles, "e3_ligand": e3_smiles}
    component_results = {}
    errors = []
    for role, smiles in components.items():
        validation = validate_smiles(smiles)
        attachment = detect_attachment_points(smiles)
        component_results[role] = {"validation": asdict(validation), "attachment_points": attachment}
        if not validation.valid:
            errors.append(f"{role}: {validation.error}")
        if role == "linker" and attachment["num_dummy_atoms"] < 2:
            errors.append("linker: expected at least two attachment points")
        if role != "linker" and attachment["num_dummy_atoms"] < 1:
            errors.append(f"{role}: expected at least one attachment point")
    assembled = None
    if assembled_smiles:
        analysis = analyze_protac_like_properties(assembled_smiles)
        assembled = asdict(analysis)
        if not analysis.valid:
            errors.append(f"assembled: {analysis.medicinal_chemistry_notes[0] if analysis.medicinal_chemistry_notes else 'invalid'}")
    return {
        "success": not errors,
        "status": "passed" if not errors else "failed",
        "component_results": component_results,
        "assembled_analysis": assembled,
        "errors": errors,
        "provenance": _provenance(score_name="assembly_validation", evidence_type="rdkit_descriptor", tool_status=STATUS_EXECUTABLE_NOT_TESTED, source_tool_or_database="RDKit via SynGlue chemistry_core", source_file_or_url="protacxtend/tools/chemistry_core.py", query={"components": components, "assembled_smiles": assembled_smiles}, limitations="RDKit validity/attachment gate only; no synthesis, docking, or ternary geometry validation.", confidence=1.0 if not errors else 0.0, claim_allowed="May claim RDKit assembly-input validation only."),
    }


def basic_novelty_check(
    smiles: str,
    *,
    reference_path: str | Path = KNOWN_PROTACS,
    similarity_threshold: float = 0.85,
) -> dict[str, Any]:
    validation = validate_smiles(smiles)
    if not validation.valid:
        return {"success": False, "status": "failed", "error": validation.error, "provenance": _provenance(score_name="novelty", evidence_type="missing", tool_status=STATUS_MISSING, source_tool_or_database="RDKit / local known PROTAC table", source_file_or_url=reference_path, query={"smiles": smiles}, limitations="Input SMILES is invalid.", claim_allowed="No novelty claim allowed.")}
    canonical = validation.canonical_smiles
    best: dict[str, Any] | None = None
    exact = None
    for row in _read_csv(reference_path):
        ref_smiles = row.get("smiles") or ""
        ref_validation = validate_smiles(ref_smiles)
        if not ref_validation.valid:
            continue
        sim = tanimoto_similarity(canonical or smiles, ref_validation.canonical_smiles or ref_smiles)
        score = float(sim["similarity"] or 0.0) if sim["status"] == "success" else 0.0
        item = {**row, "canonical_smiles": ref_validation.canonical_smiles, "similarity": score}
        if canonical == ref_validation.canonical_smiles:
            exact = item
        if best is None or score > best["similarity"]:
            best = item
    duplicate = bool(exact) or bool(best and best["similarity"] >= similarity_threshold)
    return {
        "success": True,
        "status": "ok",
        "input_canonical_smiles": canonical,
        "exact_match": exact,
        "nearest_match": best,
        "max_tanimoto_similarity": best["similarity"] if best else None,
        "duplicate_or_near_duplicate": duplicate,
        "similarity_threshold": similarity_threshold,
        "provenance": _provenance(score_name="novelty", evidence_type="local_database", tool_status=STATUS_EXECUTABLE_NOT_TESTED, source_tool_or_database="SynGlue local known PROTAC table + RDKit Morgan similarity", source_file_or_url=reference_path, query={"smiles": smiles, "similarity_threshold": similarity_threshold}, limitations="Basic exact/similarity screen against local references only; not patent-safe and not an exhaustive novelty/IP search.", confidence=0.65, claim_allowed="May claim local exact/similarity novelty screen only; never patent-safe."),
    }


def rdkit_adme_descriptor_output(smiles: str) -> dict[str, Any]:
    descriptors = compute_descriptors(smiles)
    if descriptors.descriptor_status != "success":
        return {"success": False, "status": "failed", "error": descriptors.descriptor_status, "descriptors": {}, "claim_language": "No ADME/Tox claim allowed because RDKit descriptor calculation failed.", "provenance": _provenance(score_name="adme_descriptor", evidence_type="missing", tool_status=STATUS_MISSING, source_tool_or_database="RDKit", source_file_or_url="protacxtend/tools/chemistry_core.py", query={"smiles": smiles}, limitations="Descriptor calculation failed.", claim_allowed="No ADME/Tox claim allowed.")}
    descriptor_map = asdict(descriptors)
    return {
        "success": True,
        "status": "ok",
        "descriptors": descriptor_map,
        "claim_language": "RDKit molecular descriptors only; not ML/API-predicted ADME/Tox endpoints.",
        "provenance": _provenance(score_name="adme_descriptor", evidence_type="rdkit_descriptor", tool_status=STATUS_EXECUTABLE_NOT_TESTED, source_tool_or_database="RDKit via SynGlue chemistry_core", source_file_or_url="protacxtend/tools/chemistry_core.py", query={"smiles": smiles}, limitations="Descriptors support ADME triage language only; hERG/AMES/DILI/solubility are not claimed as ML/API predictions.", confidence=1.0, applicability_domain="Valid RDKit-parsed small molecule/PROTAC-like SMILES.", claim_allowed="May claim RDKit descriptor values only."),
    }


def require_provenance_fields(records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    required = set(ToolProvenance.__dataclass_fields__)
    missing = []
    for index, record in enumerate(records):
        provenance = record.get("provenance") or {}
        absent = sorted(required - set(provenance))
        if absent:
            missing.append({"index": index, "missing_fields": absent})
    return {"success": not missing, "missing": missing, "required_fields": sorted(required)}

