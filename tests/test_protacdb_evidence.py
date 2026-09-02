from synglue_agent.databases.database_registry import get_database_entry
from synglue_agent.databases.database_router import route_database_request
from synglue_agent.backend.schemas import (
    ADMETPrediction,
    ApplicabilityDomainResult,
    CandidateRecord,
    CooperativityPrediction,
    DegradationPrediction,
    HookEffectPrediction,
    NoveltyResult,
)
from synglue_agent.tools.protacdb_client import (
    load_normalized_protacdb,
    search_protacdb_evidence,
    summarize_protacdb_diversity,
)
from synglue_agent.tools.protac_toolbox import ProtacDesignToolbox


def test_protacdb_registry_declares_rich_evidence_outputs():
    entry = get_database_entry("PROTAC-DB 3.0")

    assert entry is not None
    assert "data/benchmark/PROTAC-DB_3.0_protacs.xlsx" in entry["local_file_expected"]
    assert "ternary_complex_affinity" in entry["expected_outputs"]
    assert "PAMPA" in entry["expected_outputs"]
    assert "pharmacokinetic_parameters" in entry["expected_outputs"]


def test_normalized_protacdb_exposes_evidence_families():
    rows = load_normalized_protacdb(limit=25)

    assert rows
    assert all("evidence_families" in row for row in rows)
    assert any("physicochemical_properties" in row["evidence_families"] for row in rows)


def test_search_protacdb_ternary_affinity_for_brd9_vhl():
    rows = search_protacdb_evidence(
        target="BRD9",
        e3_ligase="VHL",
        required_families=["ternary_complex_affinity"],
        limit=5,
    )

    assert rows
    assert "ternary_complex_affinity" in rows[0]["evidence"]
    assert rows[0]["evidence_family_count"] >= 2


def test_protacdb_diversity_summary_counts_core_families():
    summary = summarize_protacdb_diversity()

    assert summary["records"] > 0
    assert summary["evidence_family_counts"]["degradation_capacity"] > 0
    assert summary["evidence_family_counts"]["cell_permeability"] >= 0


def test_router_recommends_protacdb_for_permeability_and_pk():
    permeability = route_database_request("find PROTAC permeability data")
    pk = route_database_request("find PROTAC pharmacokinetic parameters")

    assert "PROTAC-DB 3.0" in permeability["recommended_databases"]
    assert "PROTAC-DB 3.0" in pk["recommended_databases"]


def test_protacdb_prior_distinguishes_exact_from_neighborhood():
    toolbox = ProtacDesignToolbox()
    exact_record = search_protacdb_evidence(
        target="BRD9",
        e3_ligase="VHL",
        required_families=["ternary_complex_affinity"],
        limit=1,
    )[0]
    exact_candidate = CandidateRecord(
        candidate_id="exact",
        target=exact_record["target"],
        e3_ligase=exact_record["e3_ligase"],
        full_protac_smiles=exact_record["smiles"],
        synthetic_feasibility_score=0.7,
        provenance={"inchikey": exact_record["inchikey"]},
    )
    neighborhood_candidate = CandidateRecord(
        candidate_id="neighborhood",
        target="BRD9",
        e3_ligase="VHL",
        full_protac_smiles="CCOCCN",
        synthetic_feasibility_score=0.7,
    )

    exact_prior = toolbox.protacdb_evidence_prior(exact_candidate)
    neighborhood_prior = toolbox.protacdb_evidence_prior(neighborhood_candidate)

    assert exact_prior["source_scope"] == "exact_compound_match"
    assert exact_prior["influence"] == 1.0
    assert neighborhood_prior["source_scope"] == "target_e3_neighborhood"
    assert neighborhood_prior["influence"] < exact_prior["influence"]


def test_ranking_uses_protacdb_prior_as_capped_visible_signal():
    toolbox = ProtacDesignToolbox()
    record = search_protacdb_evidence(
        target="BRD9",
        e3_ligase="VHL",
        required_families=["ternary_complex_affinity"],
        limit=1,
    )[0]
    candidate = CandidateRecord(
        candidate_id="exact",
        target=record["target"],
        e3_ligase=record["e3_ligase"],
        full_protac_smiles=record["smiles"],
        synthetic_feasibility_score=0.7,
        provenance={"inchikey": record["inchikey"]},
    )

    ranking = toolbox.rank_candidates(
        [candidate],
        [DegradationPrediction(candidate_id="exact", predicted_dc50_nM=50, predicted_dmax_percent=80, model_confidence=0.7)],
        [ADMETPrediction(candidate_id="exact", overall_admet_penalty=0.2)],
        [NoveltyResult(candidate_id="exact", novelty_score=0.4)],
        [ApplicabilityDomainResult(candidate_id="exact", similarity_to_training_set=0.7, domain_status="inside")],
        cooperativity_results=[CooperativityPrediction(candidate_id="exact", cooperativity_score=0.7, confidence=0.7)],
        hook_results=[HookEffectPrediction(candidate_id="exact", therapeutic_window_score=0.6, hook_risk="low")],
    )

    prior = candidate.provenance["protacdb_evidence_prior"]
    assert prior["source_scope"] == "exact_compound_match"
    assert "PROTAC-DB prior" in ranking[0].reason_for_rank
    assert "protacdb_prior_is_target_e3_neighborhood_not_exact_compound" not in ranking[0].uncertainty_flags


def test_cooperativity_uses_protacdb_ternary_prior_without_claiming_measured_alpha():
    toolbox = ProtacDesignToolbox()
    record = search_protacdb_evidence(
        target="BRD9",
        e3_ligase="VHL",
        required_families=["ternary_complex_affinity"],
        limit=1,
    )[0]
    candidate = CandidateRecord(
        candidate_id="exact",
        target=record["target"],
        e3_ligase=record["e3_ligase"],
        full_protac_smiles=record["smiles"],
        synthetic_feasibility_score=0.7,
        rotatable_bonds=16,
        provenance={"inchikey": record["inchikey"]},
    )

    coop = toolbox.predict_cooperativity([candidate])[0]

    assert coop.model_version == "cooperativity-proxy-v0.1+protacdb-prior"
    assert "PROTAC-DB" in (coop.warning or "")
    assert "measured-alpha" not in coop.model_version
