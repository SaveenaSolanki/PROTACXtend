"""Paper artifacts: architecture, lifecycle, engram, tidy tables (brief §1–§3, §11)."""

from __future__ import annotations

import xml.dom.minidom as minidom

from paper import architecture, engram, lifecycle, tables


def test_architecture_metadata_is_machine_readable():
    meta = architecture.architecture_metadata()
    assert meta["subsystem"] == "protacpilot-memory"
    assert meta["cognitive_memory"]["direction"] == "bidirectional"
    assert "redesign" in [s.lower() for s in meta["pipeline"]]
    assert "target" in meta["cognitive_memory"]["interacts_with"]
    assert "explanation" in meta["cognitive_memory"]["interacts_with"]
    assert meta["context_fingerprint_coordinates"]
    assert meta["invariants"]
    assert meta["claim_scope"].startswith("computational engram")


def test_architecture_svg_is_valid_xml():
    minidom.parseString(architecture.render_architecture_svg())


def test_lifecycle_metadata_and_svg():
    meta = lifecycle.lifecycle_metadata()
    assert "Reconsolidation" in meta["stages"]
    for outcome in ("STRENGTHEN", "REFINE_SCOPE", "BRANCH", "WEAKEN", "SUPERSEDE"):
        assert outcome in meta["reconsolidation_outcomes"]
    # The brief's five terms map onto the canonical vocabulary.
    assert meta["reconsolidation_mapping"]["modify"] == "REFINE_SCOPE"
    assert set(meta["reconsolidation_outcomes_brief"]) == {
        "strengthen", "modify", "branch", "weaken", "supersede",
    }
    minidom.parseString(lifecycle.render_lifecycle_svg())


def test_engram_example_separates_observation_interpretation_claim():
    example = engram.build_engram_example()
    for field in engram.FIELDS:
        assert field in example, field
    assert example["observation"], "observation must be populated"
    assert example["interpretation"], "interpretation must be populated"
    assert example["claim"] is not None, "consolidation should produce a claim"
    assert example["claim"]["text"] != example["interpretation"]
    assert example["context_fingerprint"]["hash"]
    assert example["context_fingerprint"]["coordinates"]["target"] == "brd4"
    assert example["evidence_stance"]
    assert example["prediction_id"] and example["outcome_id"]


def test_engram_markdown_renders():
    markdown = engram.render_engram_markdown(engram.build_engram_example())
    assert "Observation / interpretation / claim" in markdown
    assert "Context fingerprint" in markdown


def _fake_h_results():
    return {
        "conditions": {
            "cognitive_memory": {
                "questions": [{
                    "qid": "Q1", "query": "q", "expected_memory": ["E1"],
                    "retrieved_ids": ["M1", "M2"], "retrieved_sources": [["E1"], ["E2"]],
                    "retrieval_latency_ms": 2.0, "tokens_injected": 10,
                    "query_context": {}, "retrieved_contexts": [], "answer_correct": 1.0,
                }],
            },
            "rag_memory": {
                "questions": [{
                    "qid": "Q1", "query": "q", "expected_memory": ["E1"],
                    "retrieved_ids": ["M2", "M1"], "retrieved_sources": [["E2"], ["E1"]],
                    "retrieval_latency_ms": 1.0, "tokens_injected": 12,
                    "query_context": {}, "retrieved_contexts": [], "answer_correct": 1.0,
                }],
            },
        }
    }


def test_tidy_summary_and_statistics(tmp_path):
    rows = tables.tidy_from_benchmark_h(_fake_h_results())
    assert len(rows) == 2
    assert rows[0]["rank"] == 1
    summary = tables.summary_table(rows)
    assert {row["memory_config"] for row in summary} == {"cognitive_memory", "rag_memory"}
    stats = tables.statistical_comparisons(rows)
    assert stats and stats[0]["reference"] == "cognitive_memory"

    paths = tables.write_tidy(rows, tmp_path)
    assert paths["csv"].exists()
    summary_paths = tables.write_summary_and_stats(rows, tmp_path)
    assert summary_paths["summary_csv"].exists() and summary_paths["stats_csv"].exists()


def test_tidy_parquet_written_when_pyarrow_available(tmp_path):
    import pytest

    pytest.importorskip("pyarrow")
    rows = tables.tidy_from_benchmark_h(_fake_h_results())
    paths = tables.write_tidy(rows, tmp_path)
    assert "parquet" in paths and paths["parquet"].exists()
