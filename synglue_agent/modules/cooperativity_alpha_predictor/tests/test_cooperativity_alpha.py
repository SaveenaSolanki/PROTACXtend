"""Module 3 tests — Cooperativity alpha definitions, surrogate, data & models."""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from synglue_agent.modules.cooperativity_alpha_predictor import (
    CooperativityEvidenceError,
    alpha_to_log,
    audit_records,
    class_from_log,
    cooperativity_class,
    cooperativity_class_thermodynamic,
    load_records,
    log_to_alpha,
    predict_cooperativity,
    run_benchmarks,
)
from synglue_agent.modules.cooperativity_alpha_predictor.data import (
    grouped_kfold,
    grouped_train_test_indices,
)
from synglue_agent.modules.cooperativity_alpha_predictor.features import (
    molecular_features,
)
from synglue_agent.modules.cooperativity_alpha_predictor.surrogate import (
    surrogate_from_structures,
)

# ── synthetic two-chain pose builder (deterministic geometry) ───────────────

def _pose(path: Path, poi_chain: str = "A", e3_chain: str = "B", sep: float = 3.6) -> Path:
    rows = [
        (poi_chain, "ALA", 10, "CA", 0.0, 0.0, 0.0),
        (poi_chain, "LEU", 11, "CA", 3.0, 0.0, 0.0),
        (poi_chain, "LEU", 11, "CB", 4.0, 1.4, 0.0),
        (poi_chain, "ARG", 12, "CZ", 0.0, 5.0, 0.0),
        (e3_chain, "GLU", 40, "CD", 0.0, sep, 0.0),
        (e3_chain, "GLU", 40, "OE1", 0.0, sep + 1.24, 0.0),
        (e3_chain, "LEU", 41, "CB", 3.0, sep, 0.0),
        (e3_chain, "CYS", 42, "SG", 6.0, sep, 0.0),
    ]
    lines, serial = [], 1
    for chain, res, rseq, name, x, y, z in rows:
        elem = name[0]
        lines.append(f"ATOM  {serial:5d} {name:>4s} {res:>3s} {chain}{rseq:4d}    "
                     f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00 20.00          {elem:>2s}")
        serial += 1
    lines.append("END")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


# ── alpha definition / conversions / classes ────────────────────────────────

class TestAlphaDefinition:
    def test_conversion_roundtrip(self):
        for a in (0.1, 0.8, 1.0, 1.25, 30.0):
            assert log_to_alpha(alpha_to_log(a)) == pytest.approx(a, rel=1e-12)

    def test_alpha_zero_maps_to_neg_inf(self):
        assert alpha_to_log(0.0) == -math.inf
        assert log_to_alpha(-math.inf) == 0.0

    def test_negative_alpha_rejected(self):
        with pytest.raises(ValueError):
            alpha_to_log(-1.0)

    def test_practical_class_bands_non_overlapping(self):
        assert cooperativity_class(30.0) == "positive"
        assert cooperativity_class(0.5) == "negative"
        assert cooperativity_class(1.0) == "approximately_neutral"
        assert cooperativity_class(0.8) == "approximately_neutral"   # low edge inclusive
        assert cooperativity_class(1.25) == "approximately_neutral"  # high edge inclusive
        assert cooperativity_class(0.7999) == "negative"
        assert cooperativity_class(1.2501) == "positive"
        assert cooperativity_class(None) == "not_assessed"

    def test_thermodynamic_class_exact_sign(self):
        assert cooperativity_class_thermodynamic(1.5) == "positive"
        assert cooperativity_class_thermodynamic(1.0) == "non_cooperative"
        assert cooperativity_class_thermodynamic(0.9999999999) == "non_cooperative"
        assert cooperativity_class_thermodynamic(0.5) == "negative"
        assert cooperativity_class_thermodynamic(None) == "not_assessed"

    def test_thermo_vs_reporting_documented_separation(self):
        # 1.05 is thermodynamically positive but practically approximately neutral
        assert cooperativity_class_thermodynamic(1.05) == "positive"
        assert cooperativity_class(1.05) == "approximately_neutral"

    def test_class_from_log(self):
        assert class_from_log(math.log(5.0)) == "positive"
        assert class_from_log(None) == "not_assessed"


# ── feature extraction & surrogate ──────────────────────────────────────────

class TestFeaturesAndSurrogate:
    def test_interface_features_deterministic_and_reproducible(self, tmp_path):
        p = _pose(tmp_path / "a.pdb")
        s1, _ = surrogate_from_structures([str(p)], "A", "B")
        s2, _ = surrogate_from_structures([str(p)], "A", "B")
        assert s1.cooperativity_feasibility_score == s2.cooperativity_feasibility_score
        f = s1.interface
        assert f.intermolecular_contacts > 0          # chains A/B interact at sep=3.6
        assert f.buried_surface_area_angstrom2 >= 0.0
        assert 0.0 <= s1.cooperativity_feasibility_score <= 1.0

    def test_missing_chain_raises(self, tmp_path):
        p = _pose(tmp_path / "b.pdb")
        with pytest.raises(CooperativityEvidenceError):
            predict_cooperativity(ternary_structure=str(p), poi_chain="A")  # no e3_chain

    def test_malformed_structure_raises(self, tmp_path):
        bad = tmp_path / "bad.pdb"
        bad.write_text("not a pdb\nEND\n")
        with pytest.raises(CooperativityEvidenceError, match="no heavy atoms"):
            predict_cooperativity(ternary_structure=str(bad), poi_chain="A", e3_chain="B")

    def test_molecular_features(self):
        ok = molecular_features("CC(=O)Oc1ccccc1C(=O)O")
        assert ok.available is True and ok.mol_wt > 0
        assert molecular_features(None).available is False
        assert molecular_features("definitely-not-a-smiles").available is False


# ── predict API ─────────────────────────────────────────────────────────────

class TestPredictApi:
    def test_no_evidence_is_explicit_failure(self):
        with pytest.raises(CooperativityEvidenceError, match="No evidence"):
            predict_cooperativity(protac="x", poi="BRD4", e3="VHL")

    def test_surrogate_path_never_claims_alpha(self, tmp_path):
        p = _pose(tmp_path / "c.pdb")
        r = predict_cooperativity(protac="MZ1", poi="BRD4", e3="VHL",
                                  ternary_structure=str(p), poi_chain="A", e3_chain="B")
        assert r.model_kind == "structural_surrogate"
        assert r.predicted_alpha is None
        assert r.predicted_log_alpha is None
        assert r.cooperativity_class == "not_assessed"
        assert r.structure_available is True
        assert r.uncertainty["kind"] == "surrogate_heuristic"
        assert any("NOT an experimental alpha" in lim for lim in r.limitations)
        assert any("UNTRAINED" in lim for lim in r.limitations)
        assert 0.0 <= r.feature_evidence.cooperativity_feasibility_score <= 1.0
        assert r.model.startswith("cooperativity_alpha_predictor-v")

    def test_feasibility_score_can_never_populate_alpha(self, tmp_path):
        """Invariant: a high heuristic score must still keep predicted_alpha None."""
        p = _pose(tmp_path / "c2.pdb")
        r = predict_cooperativity(ternary_structure=str(p), poi_chain="A", e3_chain="B")
        score = r.feature_evidence.cooperativity_feasibility_score
        assert score > 0.0 or r.feature_evidence.interface.intermolecular_contacts >= 0
        assert r.predicted_alpha is None and r.predicted_log_alpha is None
        assert r.feature_evidence.cooperativity_feasibility_score != r.predicted_alpha

    def test_missing_model_artifact_degrades_to_surrogate(self, tmp_path):
        p = _pose(tmp_path / "d.pdb")
        r = predict_cooperativity(ternary_structure=str(p), poi_chain="A", e3_chain="B",
                                  model_path=str(tmp_path / "does_not_exist.joblib"))
        assert r.model_kind == "structural_surrogate"
        assert any("not found" in lim for lim in r.limitations)

    def test_reproducible_calls(self, tmp_path):
        p = _pose(tmp_path / "e.pdb")
        a = predict_cooperativity(ternary_structure=str(p), poi_chain="A", e3_chain="B")
        b = predict_cooperativity(ternary_structure=str(p), poi_chain="A", e3_chain="B")
        assert a.model_dump() == b.model_dump()


# ── data audit & leakage ────────────────────────────────────────────────────

class TestDataAudit:
    def test_empty_curated_template_stops_supervised_path(self):
        audit = audit_records(load_records())
        assert audit["records"] == 0
        assert "NO MACHINE-READABLE" in audit["conclusion"]

    def test_benchmark_on_empty_data_never_trains(self):
        out = run_benchmarks(pd.DataFrame(), feature_cols=["x"])
        assert out.get("dataset_empty") is True
        assert "no supervised" in out.get("note", "")

    def test_leakage_safe_splits(self):
        groups = ["s1", "s1", "s2", "s3", "s4"]
        tr, te = grouped_train_test_indices(groups, "s2")
        assert not ({groups[i] for i in tr} & {groups[i] for i in te})
        folds = list(grouped_kfold(groups, n_splits=4))
        assert len(folds) >= 2
        for tr_i, te_i in folds:
            assert not ({groups[i] for i in tr_i} & {groups[i] for i in te_i})

    def test_audit_reports_conflicts(self):
        df = pd.DataFrame([
            {"protac_id": "p1", "poi": "BRD4", "e3": "VHL", "doi": "10.1/x",
             "alpha": 2.0, "log_alpha": math.log(2.0), "assay": "ITC"},
            {"protac_id": "p1", "poi": "BRD4", "e3": "VHL", "doi": "10.1/x",
             "alpha": 3.0, "log_alpha": math.log(3.0), "assay": "ITC"},
        ])
        audit = audit_records(df)
        assert audit["records"] == 2
        assert audit["unique_protacs"] == 1
        assert len(audit["duplicates"]) >= 1


class TestSyntheticBenchmarkPipeline:
    def test_grouped_benchmark_runs_on_synthetic_data(self):
        """Synthetic sanity check of the benchmark harness ONLY (clearly not
        real curation): grouped folds, metrics present."""
        rng = pd.DataFrame({
            "protac_id": [f"p{i // 3}" for i in range(12)],
            "log_alpha": [0.3 * ((i % 3) - 1) + 0.1 * (i % 4) for i in range(12)],
            "feat1": [float(i % 5) for i in range(12)],
            "feat2": [float((i * 7) % 11) for i in range(12)],
        })
        out = run_benchmarks(rng, feature_cols=["feat1", "feat2"], gaussian_process=False)
        assert "dataset_empty" not in out
        assert "leakage_policy" in out
        models = out["models"]
        assert "mean" in models and "ridge" in models
        assert models["mean"]["pooled"]["n"] >= 4
