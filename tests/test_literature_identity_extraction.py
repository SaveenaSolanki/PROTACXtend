import json
from pathlib import Path

from protacxtend.literature.chemical_identity import (
    extract_reviewed_corpus,
    write_reviewed_corpus_artifacts,
)


def test_reviewed_brd4_egfr_kras_identity_extraction_preserves_source_and_roles():
    out = extract_reviewed_corpus()
    accepted = out["accepted"]
    quarantine = out["quarantine"]

    targets = {r["target"] for r in accepted}
    assert {"BRD4", "EGFR", "KRAS"}.issubset(targets)
    assert accepted and all(r["manual_review_status"] == "reviewed" for r in accepted)
    assert all(r["source_ids"].get("pmid") or r["source_ids"].get("doi") for r in accepted)
    assert all(r.get("evidence_span") for r in accepted)
    assert all(r.get("canonical_smiles") for r in accepted if r.get("smiles"))

    labels_by_role = {(r["compound_label"].lower(), r["role"]) for r in accepted}
    assert ("jq1", "warhead_binder") in labels_by_role
    assert ("osimertinib", "warhead_binder") in labels_by_role
    assert ("adagrasib", "warhead_binder") in labels_by_role
    assert not any(r["compound_label"].lower() in {"mz1", "dbet1"} and r["role"] == "warhead_binder" for r in accepted)
    assert any(r["compound_label"] == "dBET1" and r["role"] == "whole_degrader" for r in accepted)
    assert any(q["compound_label"] == "dBET1" and q["reason"] == "whole_degrader_not_warhead" for q in quarantine)


def test_literature_identity_artifacts_include_metrics_and_quarantine(tmp_path):
    bundle = write_reviewed_corpus_artifacts(tmp_path)
    for key in ["accepted", "quarantine", "metrics", "report", "source_audit"]:
        assert Path(bundle[key]).exists()
    metrics = json.loads(Path(bundle["metrics"]).read_text())
    assert metrics["schema_version"] == "literature-identity-metrics.v1"
    assert metrics["accepted_records"] > 0
    assert metrics["quarantined_records"] > 0
    assert metrics["positive_score_claimed"] is False
    audit = json.loads(Path(bundle["source_audit"]).read_text())
    assert len(audit) == 8
    assert any(r["compound_label"] == "dBET1" and r["extracted_role"] == "whole_degrader" and r["audit_decision"] == "retain" for r in audit)
    assert any(r["compound_label"] == "dBET1" and r["extracted_role"] == "warhead_binder" and r["audit_decision"] == "quarantine" and r["source_record"].get("title") == "dBET1" for r in audit)
