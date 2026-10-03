from __future__ import annotations

import json
from pathlib import Path

from protacxtend.reporting.landscape_scoring import (
    build_scored_record,
    coordinates_from_record,
    score_run_artifacts,
)


def test_missing_evidence_never_scores_positive() -> None:
    record = build_scored_record(None)

    assert len(record["dimensions"]) == 12
    assert all(dim["score"] is None for dim in record["dimensions"])
    assert record["summary"]["normalized_depth_0_10"] == 0


def test_positive_scores_require_supporting_artifact_ids(tmp_path: Path) -> None:
    run_dir = tmp_path / "run_x"
    run_dir.mkdir()
    (run_dir / "run.json").write_text(json.dumps({"run_id": "run_x"}))

    record = build_scored_record(run_dir)

    for dim in record["dimensions"]:
        if dim["score"] is not None:
            assert dim["supporting_artifact_ids"], dim["dimension_id"]


def test_scored_record_and_coordinates_are_deterministic(tmp_path: Path) -> None:
    run_dir = tmp_path / "run_mz1"
    out_dir = tmp_path / "landscape"
    run_dir.mkdir()
    (run_dir / "run.json").write_text(json.dumps({
        "run_id": "run_mz1",
        "target": {"record_id": "rec_target", "gene_symbol": "BRD4"},
        "predictions": [
            {"record_id": "rec_dc50", "endpoint": "DC50", "value": 8.0, "available": True, "kind": "measured"},
            {"record_id": "rec_dmax", "endpoint": "Dmax", "value": 98.0, "available": True, "kind": "measured"},
        ],
    }, sort_keys=True))

    first, paths = score_run_artifacts(run_dir, out_dir)
    second, _ = score_run_artifacts(run_dir, out_dir)

    assert first["determinism_hash"] == second["determinism_hash"]
    assert coordinates_from_record(first) == coordinates_from_record(second)
    assert Path(paths["record"]).exists()
    assert Path(paths["csv"]).exists()
    assert Path(paths["markdown"]).exists()
    assert Path(paths["coordinates"]).exists()
    assert next(d for d in first["dimensions"] if d["dimension_id"] == "M9")["score"] == 3
