from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from synglue_agent.backend.mode_router import run_mode
from synglue_agent.learning.design_test_learn import lock_predictions, recommend_next_batch
from synglue_agent.tools.cooperativity_potential import score_cooperativity_potential
from synglue_agent.tools.dose_response_simulator import simulate_ternary_dose_response
from synglue_agent.tools.proteome_selectivity import score_proteome_context
from synglue_agent.tools.ubiquitination_geometry import score_ubiquitination_geometry


def _pdb_line(serial: int, name: str, res: str, chain: str, resid: int, x: float, y: float, z: float, element: str) -> str:
    return (
        f"ATOM  {serial:5d} {name:<4s} {res:>3s} {chain:1s}{resid:4d}    "
        f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00 20.00          {element:>2s}"
    )


def _write_pose(path: Path) -> Path:
    lines = [
        _pdb_line(1, "CA", "ALA", "A", 1, 0.0, 0.0, 0.0, "C"),
        _pdb_line(2, "NZ", "LYS", "A", 2, 12.0, 0.0, 0.0, "N"),
        _pdb_line(3, "CA", "LYS", "A", 2, 11.5, 0.5, 0.0, "C"),
        _pdb_line(4, "CA", "GLY", "B", 10, 30.0, 0.0, 0.0, "C"),
        _pdb_line(5, "O", "GLY", "B", 10, 30.5, 0.0, 0.0, "O"),
        _pdb_line(6, "N", "SER", "B", 11, 31.5, 1.0, 0.0, "N"),
        "END",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_ubiquitination_geometry_scores_pose(tmp_path: Path):
    pose = _write_pose(tmp_path / "pose.pdb")
    result = score_ubiquitination_geometry("cand1", pose, target_chain="A", e3_chain="B")
    assert result.status in {"SUPPORTED", "REVISE"}
    assert result.features["nearest_lysine"] == "LYS2:A"
    assert result.features["productive_lysine_count"] >= 1
    assert result.score > 0


def test_cooperativity_potential_scores_pose(tmp_path: Path):
    pose = _write_pose(tmp_path / "pose.pdb")
    result = score_cooperativity_potential("cand1", pose, smiles="CCO", target_chain="A", e3_chain="B")
    assert result.status in {"SUPPORTED", "REVISE"}
    assert result.predicted_alpha > 0
    assert "interface_quality_score" in result.features


def test_dose_response_simulator_detects_curve():
    result = simulate_ternary_dose_response(alpha=5.0)
    assert result.status in {"SUPPORTED", "REVISE"}
    assert result.dmax_pred_percent > 0
    assert result.ternary_peak_concentration_nM > 0
    assert result.curve


def test_proteome_context_uses_seed_atlas():
    result = score_proteome_context("BRD4", "CRBN", "MM1.S")
    assert result.status == "SUPPORTED"
    assert result.selectivity_score > 0.6
    assert result.evidence_rows


def test_design_test_learn_locks_and_recommends(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("synglue_agent.learning.design_test_learn.REGISTRY_DIR", tmp_path)
    locked = lock_predictions([{"candidate_id": "A", "score": 0.7}], run_id="unit")
    assert locked["success"]
    assert Path(locked["path"]).exists()
    decision = recommend_next_batch(
        [
            {"candidate_id": "A", "score": 0.7, "uncertainty": 0.4, "diversity_score": 0.2},
            {"candidate_id": "B", "score": 0.6, "uncertainty": 0.9, "diversity_score": 0.8},
        ],
        batch_size=1,
    )
    assert decision.next_batch == ["B"]


def test_mode_router_stepwise_modes(tmp_path: Path):
    pose = _write_pose(tmp_path / "pose.pdb")
    structure = run_mode({"mode": "structure", "pose": str(pose), "target_chain": "A", "e3_chain": "B"})
    assert structure["ubiquitination_geometry"]["features"]["productive_lysine_count"] >= 1
    assert run_mode({"mode": "dose", "alpha": 2.0})["dose_response"]["curve"]
    assert run_mode({"mode": "proteome", "target": "BRD4", "e3": "CRBN", "cell": "MM1.S"})["proteome_context"]["status"] == "SUPPORTED"
    assert run_mode({"mode": "external", "action": "status"})["success"]
    learn = run_mode({"mode": "learn", "candidates": json.dumps([{"candidate_id": "A", "uncertainty": 0.8}])})
    assert learn["decision"]["next_batch"] == ["A"]


def test_cli_stepwise_commands(tmp_path: Path):
    pose = _write_pose(tmp_path / "pose.pdb")
    root = Path(__file__).resolve().parents[1]
    commands = [
        ["./protacxtend", "dose", "--alpha", "2"],
        ["./protacxtend", "proteome", "--target", "BRD4", "--e3", "CRBN", "--cell", "MM1.S"],
        ["./protacxtend", "structure", "--pose", str(pose), "--target-chain", "A", "--e3-chain", "B"],
    ]
    for command in commands:
        completed = subprocess.run(command, cwd=root, check=False, capture_output=True, text=True, timeout=45)
        assert completed.returncode == 0, completed.stderr
        assert json.loads(completed.stdout)
