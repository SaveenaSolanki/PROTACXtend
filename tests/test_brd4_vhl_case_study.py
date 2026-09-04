"""Tests for the BRD4–VHL six-PROTAC PROSPECTIVE CASE STUDY.

Classification: prospective case study — the six molecules are never
benchmark ground truth; inputs are blinded (no outcome-derived ranking).
"""

import csv
from pathlib import Path

import pytest

from protacxtend.case_study.brd4_vhl_six import (
    DEFAULT_DATASETS,
    resolve_dataset,
    run_brd4_vhl_six_case_study,
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def bundled():
    path = ROOT / "examples" / "brd4_vhl_6.csv"
    assert path.is_file()
    return path


def test_dataset_ships_six_rows(bundled):
    with open(bundled, newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 6
    ids = {r["id"] for r in rows}
    assert ids == {f"mol{i}" for i in range(1, 7)}


def test_resolve_default_finds_bundled():
    ds = resolve_dataset(None)
    assert ds.is_file()
    assert any(ds.name == Path(d).name for d in DEFAULT_DATASETS)


def test_runner_shape_and_classification(bundled):
    out = run_brd4_vhl_six_case_study(str(bundled))
    res = out["result"]
    assert res["n_records"] == 6
    assert res["measured_present"] == 0
    assert res["measured_missing"] == 6
    assert res["classification"] == {"measured": 0, "retrieved": 6, "calculated": 12,
                                     "predicted": 6, "missing": 6}
    assert [s["phase"] for s in res["stages"]] == ["KNOW", "REASON", "DESIGN", "DISCOVER"]
    assert len(res["ranking"]) == 6
    # schema envelope has four honest evidence kinds
    kinds = {e["kind"] for e in out["schema"]["evidence"]}
    assert kinds == {"retrieved", "calculated", "predicted", "missing"}


def test_winner_is_computed_not_hardcoded(bundled, tmp_path):
    # baseline: mol1 wins
    base = run_brd4_vhl_six_case_study(str(bundled))["result"]
    assert base["winner"]["id"] == "mol1"

    # sabotage mol1's VHL ligand in a *copy* of the dataset -> winner must change
    patched = tmp_path / "brd4_vhl_6_patched.csv"
    with open(bundled, newline="") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        if r["id"] == "mol1":
            r["vhl_ligand_status"] = "modified"
    with open(patched, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    out = run_brd4_vhl_six_case_study(str(patched))["result"]
    assert out["winner"]["id"] != "mol1"


def test_deterministic(bundled):
    a = run_brd4_vhl_six_case_study(str(bundled))
    b = run_brd4_vhl_six_case_study(str(bundled))
    assert a == b


def test_input_is_blinded_and_not_ground_truth(bundled):
    with open(bundled, newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert "md_rank" not in rows[0]  # no outcome-derived ranking in inputs
    res = run_brd4_vhl_six_case_study(str(bundled))["result"]
    # ranking rows carry no outcome-derived field
    for row in res["ranking"]:
        assert "md_predicted_rank" not in row
    out = run_brd4_vhl_six_case_study(str(bundled))
    # case study never claims measured status
    assert out["result"]["measured_present"] == 0
    # lock statement documented
    notes = " ".join(st["note"] for st in res["stages"])
    assert "lock" in notes.lower()
    schema = out["schema"]
    assert schema["workflow"] == "case_study:brd4-vhl-six"
    assert any("ground truth" in w for w in schema["warnings"])
