"""Invalid-run quarantine enforcement tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from protacxtend.run_quarantine import (
    assert_citeable,
    is_citeable,
    is_quarantined,
    iter_valid_run_dirs,
    quarantine_reason,
)

ROOT = Path(__file__).resolve().parents[1]


def test_marker_files_quarantine(tmp_path):
    for marker in ("INVALID_RUN.md", "INVALID_HISTORICAL"):
        run = tmp_path / f"run_{marker}"
        run.mkdir()
        (run / marker).write_text("withdrawn")
        assert is_quarantined(run) is True
        assert is_citeable(run) is False
        assert quarantine_reason(run)
        with pytest.raises(PermissionError):
            assert_citeable(run)


def test_clean_run_is_citeable(tmp_path):
    run = tmp_path / "run_ok"
    run.mkdir()
    (run / "run.json").write_text("{}")
    assert is_quarantined(run) is False
    assert is_citeable(run) is True


def test_iter_valid_run_dirs_excludes_quarantined(tmp_path):
    (tmp_path / "run_a").mkdir()
    bad = tmp_path / "run_b"
    bad.mkdir()
    (bad / "INVALID_HISTORICAL").write_text("x")
    names = {p.name for p in iter_valid_run_dirs(tmp_path)}
    assert names == {"run_a"}


def test_historical_invalid_run_is_quarantined():
    run = ROOT / "outputs" / "runs" / "run_e4e21ccd"
    if not run.exists():
        pytest.skip("invalid sample run not present")
    assert is_quarantined(run) is True


def test_cognitive_bridge_refuses_quarantined_run(tmp_path):
    from protacxtend.memory.cognitive_bridge import CognitiveMemoryBridge

    run = tmp_path / "run_bad"
    run.mkdir()
    (run / "INVALID_HISTORICAL").write_text("withdrawn")
    (run / "run.json").write_text('{"run_id": "run_bad", "candidates_generated": 128}')

    bridge = CognitiveMemoryBridge.__new__(CognitiveMemoryBridge)  # no DB needed for the guard
    result = bridge.ingest_run_dir(run)
    assert result["enabled"] is False
    assert result["quarantined"] is True
    assert result["n_predictions"] == 0


def test_run_search_skips_quarantined_run():
    from protacxtend.agentic.registry import _find_candidate_record

    # No candidate from the invalid historical run may be surfaced. Use a token
    # that only exists inside run_e4e21ccd.
    row = _find_candidate_record("SGA-1e468bb226c7")
    assert row == {} or row.get("run_id") != "run_e4e21ccd"


def test_tui_report_refuses_quarantined_run(monkeypatch):
    import protacxtend.tui_bridge.server as server

    run = ROOT / "outputs" / "runs" / "run_e4e21ccd"
    if not run.exists():
        pytest.skip("invalid sample run not present")
    captured: list[dict] = []
    monkeypatch.setattr(server, "emit", lambda payload: captured.append(payload))
    server.handle_report("run_e4e21ccd")
    assert captured[-1]["status"] == "invalid"
    assert "quarantined" in captured[-1]["error"]


def test_tui_report_serves_clean_run(monkeypatch):
    import protacxtend.tui_bridge.server as server

    run = ROOT / "outputs" / "runs" / "run_brd4_vhl_scientific_v1"
    if not run.exists():
        pytest.skip("scientific run not present")
    captured: list[dict] = []
    monkeypatch.setattr(server, "emit", lambda payload: captured.append(payload))
    server.handle_report("run_brd4_vhl_scientific_v1")
    assert captured[-1]["status"] == "ok"
    assert "PTAMRJLIOCHJMQ-PYNGZGNASA-N" in captured[-1]["report"]


# ---------------------------------------------------------------------------
# Comparison-only replays: visible on every surface; precise citation claims.
# ---------------------------------------------------------------------------

CORRECTED = ROOT / "outputs" / "runs" / "run_e4e21ccd_corrected_v1"


def _corrected_present():
    return CORRECTED.is_dir() and (CORRECTED / "manifest.json").exists()


def test_comparison_only_detected_from_manifest():
    if not _corrected_present():
        pytest.skip("corrected replay run not present")
    from protacxtend.run_quarantine import comparison_only_reason, run_status

    reason = comparison_only_reason(CORRECTED)
    assert reason is not None and "comparison_only" in reason
    assert run_status(CORRECTED) == "COMPARISON_ONLY"


def test_precise_citation_claim_replaces_broad_boolean():
    from protacxtend.run_quarantine import (
        CLAIM_CORRECTED_REPLAY, CLAIM_INVALID, CLAIM_MZ1_RECONSTRUCTION, CLAIM_OK,
        MZ1_RECONSTRUCTION_RUN, citation_claim, quarantine_manifest,
    )

    # MZ1 reference reconstruction label is reserved for the scientific run only.
    ok = CORRECTED.parent / "run_brd4_vhl_scientific_v1"
    if ok.is_dir() and ok.name == MZ1_RECONSTRUCTION_RUN:
        assert citation_claim(ok) == CLAIM_MZ1_RECONSTRUCTION
    # Invalid historical -> explicit invalid claim with reason.
    invalid = CORRECTED.parent / "run_e4e21ccd"
    if invalid.is_dir():
        claim = citation_claim(invalid)
        assert claim.startswith(CLAIM_INVALID)
    # Corrected replay -> malformed-input regression claim ONLY (never a
    # reconstruction, never candidate evidence).
    assert citation_claim(CORRECTED) == CLAIM_CORRECTED_REPLAY
    assert "reconstruction" not in citation_claim(CORRECTED)
    man = quarantine_manifest(CORRECTED)
    assert man["citation_claim"] == CLAIM_CORRECTED_REPLAY
    assert man["status"] == "COMPARISON_ONLY"
    assert man["comparison_only"] is True
    assert man["citeable"] is False  # legacy bool: not citeable as scientific evidence


def test_tui_marks_corrected_replay_comparison_only_against_record(monkeypatch):
    """TUI response must match the run record (manifest), not merely contain
    report.md text."""
    if not _corrected_present():
        pytest.skip("corrected replay run not present")
    import protacxtend.tui_bridge.server as server

    captured: list[dict] = []
    monkeypatch.setattr(server, "emit", lambda payload: captured.append(payload))
    server.handle_report("run_e4e21ccd_corrected_v1")
    payload = captured[-1]
    assert payload["status"] == "comparison_only"
    assert "COMPARISON-ONLY" in payload["report"]
    rec = payload["summary"].get("run_record") or {}
    # check the record itself, not free text
    assert rec.get("scientific_evidence") is False
    assert "comparison_only" in str(rec.get("role"))
    assert payload["summary"].get("citation_claim", "").startswith(
        "comparison-only malformed-input regression")


def test_api_marks_corrected_replay_comparison_only():
    if not _corrected_present():
        pytest.skip("corrected replay run not present")
    from fastapi.testclient import TestClient
    from protacxtend.backend.api_routes import app

    client = TestClient(app)
    resp = client.get("/runs/run_e4e21ccd_corrected_v1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "comparison_only"
    assert body["citation_claim"].startswith("comparison-only malformed-input regression")
    assert "reconstruction" not in body["citation_claim"]
    assert body["record"].get("role") == "corrected_replay_comparison_only"
    assert body["record"].get("scientific_evidence") is False


def test_scientific_search_excludes_invalid_and_comparison_only_by_default():
    """Neither invalid nor comparison-only runs may be selected as candidate
    evidence in scientific search (default)."""
    if not _corrected_present():
        pytest.skip("corrected replay run not present")
    from protacxtend.agentic.registry import _find_candidate_record

    # default: excluded
    row = _find_candidate_record("RLBP1")
    assert row == {} or (isinstance(row, dict) and row.get("run_id") != "run_e4e21ccd_corrected_v1")
    # explicit audit lookup: comparison-only may be retrieved, visibly flagged
    row2 = _find_candidate_record("RLBP1", include_comparison_only=True)
    if isinstance(row2, dict) and row2:
        assert row2.get("run_id") != "run_e4e21ccd"  # invalid remains excluded
        if row2.get("run_id") == "run_e4e21ccd_corrected_v1":
            assert row2.get("comparison_only") is True
            assert row2.get("citation_claim", "").startswith("comparison-only malformed-input regression")


def test_reports_surface_precise_claim(tmp_path):
    from protacxtend.run_quarantine import citation_claim

    claim = citation_claim(CORRECTED) if _corrected_present() else ""
    assert "no candidate or scientific result" in claim if _corrected_present() else True


def test_engram_refuses_or_flags_comparison_only():
    """ENGRAM (cognitive-memory gateway) must never ingest comparison-only
    replays as scientific memory."""
    if not _corrected_present():
        pytest.skip("corrected replay run not present")
    from protacxtend.memory.cognitive_bridge import CognitiveMemoryBridge

    bridge = CognitiveMemoryBridge.__new__(CognitiveMemoryBridge)  # guard only
    result = bridge.ingest_run_dir(CORRECTED)
    assert result["enabled"] is False
    assert result["comparison_only"] is True
    assert result["n_predictions"] == 0
