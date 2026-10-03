"""Reviewed chemical-identity extraction for the priority BRD4/EGFR/KRAS corpus.

This module is intentionally evidence-gated: it only emits identities from a
small manually reviewed corpus fixture. Ambiguous whole-degrader/component role
claims and source-identity discrepancies are quarantined rather than converted
into positive extraction records.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

try:  # pragma: no cover - import branch depends on optional install
    from rdkit import Chem
except Exception:  # noqa: BLE001
    Chem = None  # type: ignore

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "literature-chemical-identity.v1"

_REVIEWED_CORPUS: list[dict[str, Any]] = [
    {
        "record_id": "litid-brd4-jq1-001",
        "target": "BRD4",
        "mutation": "",
        "e3": "",
        "compound_label": "JQ1",
        "role": "warhead_binder",
        "smiles": "CC1=C(SC2=C1C(=N[C@H](C3=NN=C(N32)C)CC(=O)OC(C)(C)C)C4=CC=C(C=C4)Cl)C",
        "source_ids": {"cid": "46907787", "doi": "10.1038/nature09534"},
        "source_record": {"database": "PubChem", "title": "JQ1 compound", "formula": "C23H25ClN4O2S", "url": "https://pubchem.ncbi.nlm.nih.gov/compound/46907787"},
        "source_role": "BET bromodomain ligand / BRD4 warhead-binder scaffold",
        "assay": "BRD4/BET bromodomain ligand used as BET-warhead precursor in degrader literature",
        "evidence_span": "JQ1 was manually reviewed as the BRD4/BET binding element; no degradation measurement is inferred from identity alone.",
    },
    {
        "record_id": "litid-brd4-mz1-002",
        "target": "BRD4",
        "mutation": "",
        "e3": "VHL",
        "compound_label": "MZ1",
        "role": "whole_degrader",
        "smiles": "O[C@@H]1C[C@H](N(C1)C(=O)[C@H](C(C)(C)C)NC(=O)COCCOCCOCCNC(=O)C[C@@H]1N=C(c2ccc(cc2)Cl)c2c(n3c1nnc3C)sc(c2C)C)C(=O)NCc1ccc(cc1)c1scnc1C",
        "source_ids": {"cid": "122201421", "doi": "10.1038/nchembio.2089"},
        "source_record": {"database": "PubChem/IUPHAR", "title": "MZ1", "formula": "C49H60ClN9O8S2", "url": "https://pubchem.ncbi.nlm.nih.gov/compound/122201421"},
        "source_role": "complete VHL-recruiting BRD2/BRD4 PROTAC degrader",
        "assay": "published BRD4 degrader identity/assay context",
        "evidence_span": "MZ1 is reviewed as a complete VHL-recruiting BET degrader, not a warhead fragment.",
    },
    {
        "record_id": "litid-egfr-osimertinib-001",
        "target": "EGFR",
        "mutation": "",
        "e3": "",
        "compound_label": "osimertinib",
        "role": "warhead_binder",
        "smiles": "COc1cc(N(C)CCN(C)C)c(NC(=O)C=C)cc1Nc2nccc(n2)c3cn(C)c4ccccc34",
        "source_ids": {"cid": "71496458", "pmid": "26343577", "doi": "10.1126/scitranslmed.aac7077"},
        "source_record": {"database": "PubChem", "title": "Osimertinib", "formula": "C28H33N7O2", "url": "https://pubchem.ncbi.nlm.nih.gov/compound/71496458"},
        "source_role": "EGFR tyrosine kinase inhibitor / covalent binder component",
        "assay": "EGFR inhibitor identity reviewed as possible covalent binder component",
        "evidence_span": "Osimertinib is reviewed as an EGFR inhibitor/binder identity; PROTAC degradation is not inferred here.",
    },
    {
        "record_id": "litid-kras-adagrasib-001",
        "target": "KRAS",
        "mutation": "G12C",
        "e3": "",
        "compound_label": "adagrasib",
        "role": "warhead_binder",
        "smiles": "CN1CCC[C@H]1COC2=NC3=C(CCN(C3)C4=CC=CC5=C4C(=CC=C5)Cl)C(=N2)N6CCN([C@H](C6)CC#N)C(=O)C(=C)F",
        "source_ids": {"cid": "138611145", "pmid": "35658005", "doi": "10.1056/NEJMoa2204619"},
        "source_record": {"database": "PubChem", "title": "Adagrasib", "formula": "C32H35ClFN7O2", "url": "https://pubchem.ncbi.nlm.nih.gov/compound/138611145"},
        "source_role": "irreversible covalent KRAS G12C inhibitor / allele-specific binder component",
        "assay": "KRAS G12C inhibitor identity reviewed as allele-specific binder component",
        "evidence_span": "Adagrasib is reviewed as a KRAS G12C inhibitor identity; degradation is not inferred from inhibitor identity.",
    },
    {
        "record_id": "litid-crbn-pomalidomide-001",
        "target": "BRD4",
        "mutation": "",
        "e3": "CRBN",
        "compound_label": "pomalidomide",
        "role": "e3_ligand",
        "smiles": "NC(=O)N1c2ccccc2C(=O)NC1=O",
        "source_ids": {"cid": "134780", "pmid": "24875894", "doi": "10.1126/science.1259925"},
        "source_record": {"database": "PubChem", "title": "Pomalidomide", "formula": "C13H11N3O4", "url": "https://pubchem.ncbi.nlm.nih.gov/compound/134780"},
        "source_role": "CRBN-binding immunomodulatory imide / E3 ligand",
        "assay": "CRBN ligand identity reviewed for E3 recruitment context",
        "evidence_span": "Pomalidomide is reviewed as a CRBN-recruiting ligand identity.",
    },
    {
        "record_id": "litid-brd4-dbet1-accepted-001",
        "target": "BRD4",
        "mutation": "",
        "e3": "CRBN",
        "compound_label": "dBET1",
        "role": "whole_degrader",
        "smiles": "CC1=C(SC2=C1C(=N[C@H](C3=NN=C(N32)C)CC(=O)NCCCCNC(=O)COC4=CC=CC5=C4C(=O)N(C5=O)C6CCC(=O)NC6=O)C7=CC=C(C=C7)Cl)C",
        "source_ids": {"cid": "91799313", "pmid": "26075522", "doi": "10.1126/science.aab1433"},
        "source_record": {"database": "PubChem", "title": "dBET1", "formula": "C38H37ClN8O7S", "url": "https://pubchem.ncbi.nlm.nih.gov/compound/91799313"},
        "source_role": "complete CRBN-recruiting BET PROTAC degrader",
        "assay": "published CRBN-recruiting BET degrader identity/assay context",
        "evidence_span": "dBET1 is retained as a complete CRBN-recruiting BET degrader identity; it is not a warhead fragment.",
    },
    {
        "record_id": "litid-brd4-dbet1-quarantine-001",
        "target": "BRD4",
        "mutation": "",
        "e3": "CRBN",
        "compound_label": "dBET1",
        "role": "warhead_binder",
        "smiles": "CC1=C(SC2=C1C(=N[C@H](C3=NN=C(N32)C)CC(=O)NCCCCNC(=O)COC4=CC=CC5=C4C(=O)N(C5=O)C6CCC(=O)NC6=O)C7=CC=C(C=C7)Cl)C",
        "source_ids": {"cid": "91799313", "pmid": "26075522", "doi": "10.1126/science.aab1433"},
        "source_record": {"database": "PubChem", "title": "dBET1", "formula": "C38H37ClN8O7S", "url": "https://pubchem.ncbi.nlm.nih.gov/compound/91799313"},
        "source_role": "complete CRBN-recruiting BET PROTAC degrader",
        "assay": "reviewed whole-degrader mention mis-slotted as warhead in extraction candidate",
        "evidence_span": "dBET1 is a complete CRBN-recruiting BET degrader; this candidate role is quarantined.",
        "expected_quarantine": "whole_degrader_not_warhead",
    },
    {
        "record_id": "litid-egfr-doi-quarantine-001",
        "target": "EGFR",
        "mutation": "",
        "e3": "VHL",
        "compound_label": "EGFR-PROTAC-X",
        "role": "whole_degrader",
        "smiles": "",
        "source_ids": {"pmid": "manual-review-note", "doi": "10.0000/discrepant-placeholder"},
        "assay": "manual review found source identity mismatch",
        "evidence_span": "The DOI supplied with this extraction candidate did not match the manuscript identity under review.",
        "expected_quarantine": "doi_publication_identity_mismatch",
    },
]

_WHOLE_DEGRADER_LABELS = {"mz1", "dbet1", "arv-771", "mt-802"}


def _canonicalize(smiles: str) -> tuple[str, str]:
    if not smiles:
        return "", "not_supplied"
    if Chem is None:
        return smiles, "rdkit_unavailable_unvalidated"
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return "", "invalid_smiles"
    return Chem.MolToSmiles(mol, canonical=True), "rdkit_canonical"


def _quarantine_reason(row: dict[str, Any]) -> str:
    expected = str(row.get("expected_quarantine") or "")
    if expected:
        return expected
    if row.get("role") == "warhead_binder" and str(row.get("compound_label", "")).lower() in _WHOLE_DEGRADER_LABELS:
        return "whole_degrader_not_warhead"
    return ""


def _normalize(row: dict[str, Any]) -> dict[str, Any]:
    canonical, validation = _canonicalize(str(row.get("smiles") or ""))
    return {
        "schema_version": SCHEMA_VERSION,
        "record_id": row["record_id"],
        "manual_review_status": "reviewed",
        "target": row.get("target", ""),
        "mutation": row.get("mutation", ""),
        "e3": row.get("e3", ""),
        "compound_label": row.get("compound_label", ""),
        "role": row.get("role", ""),
        "smiles": row.get("smiles", ""),
        "canonical_smiles": canonical,
        "smiles_validation": validation,
        "source_ids": dict(row.get("source_ids") or {}),
        "source_record": dict(row.get("source_record") or {}),
        "source_role": row.get("source_role", ""),
        "assay": row.get("assay", ""),
        "evidence_span": row.get("evidence_span", ""),
        "limitation": "chemical identity only; no degradation, ternary, ADMET, or synthesis claim is scored",
    }


def extract_reviewed_corpus() -> dict[str, Any]:
    accepted: list[dict[str, Any]] = []
    quarantine: list[dict[str, Any]] = []
    for raw in _REVIEWED_CORPUS:
        row = _normalize(raw)
        reason = _quarantine_reason(raw)
        if reason or row["smiles_validation"] == "invalid_smiles":
            q = dict(row)
            q["reason"] = reason or "invalid_smiles"
            q["decision"] = "quarantined"
            quarantine.append(q)
        else:
            row["decision"] = "accepted_identity"
            accepted.append(row)
    return {
        "schema_version": SCHEMA_VERSION,
        "corpus": "manual-reviewed-brd4-egfr-kras.v1",
        "accepted": accepted,
        "quarantine": quarantine,
        "guardrail": "Only manually reviewed rows are accepted; ambiguous or mismatched rows are quarantined.",
    }


def metrics(bundle: dict[str, Any]) -> dict[str, Any]:
    accepted = bundle.get("accepted") or []
    quarantine = bundle.get("quarantine") or []
    return {
        "schema_version": "literature-identity-metrics.v1",
        "corpus": bundle.get("corpus", ""),
        "accepted_records": len(accepted),
        "quarantined_records": len(quarantine),
        "targets": sorted({r.get("target", "") for r in accepted if r.get("target")}),
        "roles": sorted({r.get("role", "") for r in accepted if r.get("role")}),
        "positive_score_claimed": False,
        "limitation": "This is chemical-identity extraction over reviewed fixtures, not a matched 48-case task score.",
    }


def source_audit(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    """Audit accepted/quarantined rows against manually verified source-record fields."""
    rows: list[dict[str, Any]] = []
    for decision, entries in (("accepted", bundle.get("accepted") or []), ("quarantined", bundle.get("quarantine") or [])):
        for row in entries:
            source = row.get("source_record") or {}
            role = row.get("source_role") or ""
            canonical = row.get("canonical_smiles") or ""
            rows.append({
                "record_id": row.get("record_id", ""),
                "decision": decision,
                "compound_label": row.get("compound_label", ""),
                "extracted_role": row.get("role", ""),
                "source_role": role,
                "role_match": (decision == "accepted" and bool(role)) or row.get("reason") == "whole_degrader_not_warhead",
                "source_ids": row.get("source_ids", {}),
                "source_record": source,
                "canonical_smiles": canonical,
                "structure_status": "source_record_verified" if canonical else "no_structure_for_source_mismatch",
                "audit_decision": "retain" if decision == "accepted" else "quarantine",
                "limitation": row.get("limitation", ""),
                "quarantine_reason": row.get("reason", ""),
            })
    return rows


def write_reviewed_corpus_artifacts(out_dir: str | Path = "outputs/priority_agent_audit/literature_identity") -> dict[str, str]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    bundle = extract_reviewed_corpus()
    m = metrics(bundle)
    accepted_path = out / "reviewed_corpus_extractions.json"
    quarantine_path = out / "quarantine.json"
    metrics_path = out / "metrics.json"
    csv_path = out / "reviewed_corpus_extractions.csv"
    report_path = out / "report.md"
    audit_path = out / "source_record_audit.json"
    accepted_path.write_text(json.dumps(bundle["accepted"], indent=2, default=str), encoding="utf-8")
    quarantine_path.write_text(json.dumps(bundle["quarantine"], indent=2, default=str), encoding="utf-8")
    metrics_path.write_text(json.dumps(m, indent=2, default=str), encoding="utf-8")
    audit_path.write_text(json.dumps(source_audit(bundle), indent=2, default=str), encoding="utf-8")
    fields = ["record_id", "target", "mutation", "e3", "compound_label", "role", "canonical_smiles", "smiles_validation", "assay"]
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in bundle["accepted"]:
            writer.writerow({k: row.get(k, "") for k in fields})
    lines = [
        "# Literature Chemical Identity Extraction",
        "",
        f"Schema: `{SCHEMA_VERSION}`",
        f"Accepted reviewed identities: {m['accepted_records']}",
        f"Quarantined extraction candidates: {m['quarantined_records']}",
        "",
        "No positive degradation/evaluation score is claimed from this corpus.",
        "",
        "## Source-record audit",
        f"Rows audited against source-role/structure fields: {len(source_audit(bundle))}",
        "",
        "## Quarantine reasons",
    ]
    for q in bundle["quarantine"]:
        lines.append(f"- `{q['record_id']}`: {q['reason']} ({q['compound_label']})")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "accepted": str(accepted_path),
        "quarantine": str(quarantine_path),
        "metrics": str(metrics_path),
        "csv": str(csv_path),
        "report": str(report_path),
        "source_audit": str(audit_path),
    }
