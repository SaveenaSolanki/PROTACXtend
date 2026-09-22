"""Performance-harness tests (Sprint V6). Small N only; the full sweep is a CLI run."""

from __future__ import annotations

import json

from benchmarks import performance as P


def test_measure_size_small():
    row = P.measure_size(100, trials=3)
    assert row["n_events"] == 100
    assert row["total_memories"] > 0
    for field in ("encode", "fts_retrieval", "hybrid_retrieval", "context_assembly", "mcp_roundtrip"):
        summary = row[field]
        assert summary["n"] > 0
        assert summary["min_ms"] <= summary["median_ms"] <= summary["max_ms"]
        assert summary["p95_ms"] <= summary["max_ms"] + 1e-9
    assert row["db_size_bytes"] > 0
    assert row["consolidation_ms"] >= 0.0


def test_percentile_interpolation():
    values = [1.0, 2.0, 3.0, 4.0]
    assert P._percentile(values, 0) == 1.0
    assert P._percentile(values, 100) == 4.0
    assert P._percentile([], 50) == 0.0


def test_writers(tmp_path):
    results = P.run_all(sizes=[100], trials=2)
    paths = P.write_results(results, tmp_path)
    assert paths["json"].exists() and paths["csv"].exists() and paths["md"].exists()
    payload = json.loads(paths["json"].read_text())
    assert payload["results"][0]["n_events"] == 100
    assert "Performance Report" in paths["md"].read_text()
