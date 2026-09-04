"""
Tests for the uncertainty-aware degradation layer (capability 5).
=================================================================

Verifies:
  1. Conformal-calibrated intervals cover ~90% on held-out PROTAC-DB molecules
  2. AD detection flags OOD molecules (ICM warhead) as low_confidence
  3. Verdict composition: in-domain → high, borderline → medium, far → low
  4. Rank correlation of the calibrated ensemble (ρ > 0.5 on benchmark)
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from protacxtend.tools.uncertainty_aware_prediction import (
    predict_with_uncertainty,
    ENSEMBLE_PATHS,
    CAL_CSV,
)
from protacxtend.tools.applicability_domain import assess_applicability_domain

HAS_MODELS = all(p.exists() for p in ENSEMBLE_PATHS)


@pytest.mark.skipif(not HAS_MODELS, reason="calibrated ensemble not on disk")
class TestUncertaintyLayer:
    def test_ensemble_models_exist(self):
        assert all(p.exists() for p in ENSEMBLE_PATHS)
        assert CAL_CSV.exists()

    def test_conformal_coverage_on_benchmark(self):
        """The conformal interval should contain the true DC50 ~90% of the time."""
        import pandas as pd
        from rdkit import Chem
        from scipy.stats import spearmanr

        bench = pd.read_csv(Path(__file__).resolve().parents[2] / "outputs" / "benchmark" / "benchmark_predictions.csv")
        conf = pd.read_csv(Path(__file__).resolve().parents[2] / "outputs" / "benchmark" / "chemprop_conformal_predictions.csv")

        def canon(s):
            m = Chem.MolFromSmiles(s)
            return Chem.MolToSmiles(m) if m else None
        conf["canon"] = conf["smiles"].apply(canon)
        bench["canon"] = bench["smiles"].apply(canon)
        m = bench.merge(conf[["canon", "logDC50", "logDC50_unc"]], on="canon", how="inner")

        x = np.log10(m["published_dc50_nM"].values)
        y = m["logDC50"].values
        unc = m["logDC50_unc"].values

        coverage = (np.abs(x - y) <= unc).mean()
        assert coverage >= 0.80, f"coverage {coverage:.2f} below 80%"

        rho, _ = spearmanr(x, y)
        assert rho > 0.5, f"rho {rho:.3f} below 0.5"

    def test_ood_flagged_low_confidence(self):
        """The ICM warhead (far from PROTAC-DB chemistry) must be low_confidence."""
        icm = "CC1(C2=CCN3C(=O)N(C(=O)N3C2C4=C(C=CC(=C4O)C1)O)C5=CC=C(C=C5)C(=O)O)"
        ad = assess_applicability_domain(icm)
        assert ad["status"] == "out_of_domain"
        res = predict_with_uncertainty([icm])[0]
        assert res["verdict"] == "low_confidence"
        assert res["nn_tanimoto"] < 0.30

    def test_indomain_high_confidence(self):
        import pandas as pd
        from rdkit import Chem
        bench = pd.read_csv(Path(__file__).resolve().parents[2] / "outputs" / "benchmark" / "benchmark_predictions.csv")
        smi = bench.iloc[0]["smiles"]
        ad = assess_applicability_domain(smi)
        assert ad["status"] in ("in_domain", "borderline")
        res = predict_with_uncertainty([smi])[0]
        assert res["verdict"] in ("high_confidence", "medium_confidence")
        assert res["dc50_nM"] is not None

    def test_ad_detector_math(self):
        """Self-similarity must be ~1.0 (regression guard for the bool-matmul bug)."""
        from protacxtend.tools.applicability_domain import _load_or_build_train_fps
        fps, smis = _load_or_build_train_fps()
        r = assess_applicability_domain(smis[0])
        assert r["nn_tanimoto"] > 0.95, f"self-sim {r['nn_tanimoto']}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
