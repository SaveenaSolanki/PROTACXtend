from protacxtend.prediction_governance import (
    DomainStatus,
    ModelRecord,
    assess_prediction_domain,
    enforce_domain_policy,
    get_model_record,
    registry_rows,
)


def test_known_in_domain_prediction_allows_nomination():
    assessment = assess_prediction_domain(
        "tack_style_local",
        {
            "endpoint": "pDC50",
            "target": "BRD4",
            "e3": "CRBN",
            "chemical_similarity": 0.72,
            "linker_family": "PEG",
            "mw": 920,
            "assay_context": "cellular degradation",
        },
    )

    assert assessment.status == DomainStatus.IN_DOMAIN
    policy = enforce_domain_policy(assessment)
    assert policy["nomination_allowed"] is True
    assert policy["evidence_strength"] == "strong_model_evidence"


def test_chemical_out_of_domain_blocks_nomination():
    assessment = assess_prediction_domain(
        "tack_style_local",
        {"endpoint": "pDC50", "target": "BRD4", "e3": "CRBN", "chemical_similarity": 0.12},
    )

    assert assessment.status == DomainStatus.OUT_OF_DOMAIN
    assert assessment.dimensions["chemical_space_similarity"]["status"] == "OUT_OF_DOMAIN"
    assert enforce_domain_policy(assessment)["nomination_allowed"] is False


def test_target_out_of_domain_is_separate_from_chemical_space():
    assessment = assess_prediction_domain(
        "cooperativity_alpha_proxy",
        {"endpoint": "cooperativity_alpha", "target": "HMGB2", "e3": "VHL", "chemical_similarity": 0.8},
    )

    assert assessment.status == DomainStatus.OUT_OF_DOMAIN
    assert assessment.dimensions["target_coverage"]["status"] == "OUT_OF_DOMAIN"


def test_e3_out_of_domain_is_explicit():
    assessment = assess_prediction_domain(
        "cooperativity_alpha_proxy",
        {"endpoint": "cooperativity_alpha", "target": "BRD4", "e3": "DCAF15", "chemical_similarity": 0.8},
    )

    assert assessment.status == DomainStatus.OUT_OF_DOMAIN
    assert assessment.dimensions["E3_coverage"]["status"] == "OUT_OF_DOMAIN"


def test_endpoint_mismatch_is_out_of_domain():
    assessment = assess_prediction_domain(
        "tack_style_local",
        {"endpoint": "ternary_structure", "target": "BRD4", "e3": "CRBN", "chemical_similarity": 0.8},
    )

    assert assessment.status == DomainStatus.OUT_OF_DOMAIN
    assert assessment.dimensions["endpoint_coverage"]["status"] == "OUT_OF_DOMAIN"


def test_missing_model_metadata_is_unassessable():
    assessment = assess_prediction_domain(
        "unknown_model",
        {"endpoint": "pDC50", "target": "BRD4", "e3": "CRBN", "chemical_similarity": 0.8},
    )

    assert assessment.status == DomainStatus.UNASSESSABLE
    policy = enforce_domain_policy(assessment)
    assert policy["nomination_allowed"] is False
    assert policy["evidence_strength"] == "diagnostic_only"


def test_missing_applicability_method_is_unassessable():
    record = ModelRecord(
        model_id="metadata_gap",
        model_name="metadata gap",
        version="test",
        endpoint="pDC50",
        training_dataset="synthetic test",
        training_targets=("BRD4",),
        training_E3s=("CRBN",),
        n_training_records=10,
        feature_representation="descriptors",
        chemical_space="test",
        target_space=("BRD4",),
        E3_space=("CRBN",),
        assay_space=("cellular degradation",),
        uncertainty_method="none",
        applicability_method="",
        checkpoint="none",
        license="test",
    )

    assessment = assess_prediction_domain(
        record,
        {"endpoint": "pDC50", "target": "BRD4", "e3": "CRBN", "chemical_similarity": 0.8},
    )

    assert assessment.status == DomainStatus.UNASSESSABLE
    assert "missing applicability_method" in assessment.limitations


def test_near_domain_boundary_requires_warning_and_uncertainty():
    assessment = assess_prediction_domain(
        "tack_style_local",
        {"endpoint": "pDC50", "target": "BRD4", "e3": "CRBN", "chemical_similarity": 0.42},
    )

    assert assessment.status == DomainStatus.NEAR_DOMAIN_BOUNDARY
    policy = enforce_domain_policy(assessment)
    assert policy["nomination_allowed"] is True
    assert policy["uncertainty_required"] is True
    assert policy["warning"]


def test_registry_records_expose_required_fields():
    rows = registry_rows()
    assert rows
    required = {
        "model_id",
        "model_name",
        "version",
        "endpoint",
        "training_dataset",
        "training_targets",
        "training_E3s",
        "n_training_records",
        "feature_representation",
        "chemical_space",
        "target_space",
        "E3_space",
        "assay_space",
        "uncertainty_method",
        "applicability_method",
        "checkpoint",
        "license",
    }
    assert required.issubset(rows[0])
    assert get_model_record(rows[0]["model_id"]).model_id == rows[0]["model_id"]
