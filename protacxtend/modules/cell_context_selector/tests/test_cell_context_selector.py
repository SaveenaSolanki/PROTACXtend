"""Module 5 tests — cleaning, mapping, features, grouped splits, artifact."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from protacxtend.modules.cell_context_selector import (
    build_curated,
    dataset_report,
    ensure_curated,
    omics,
    prepare,
)
from protacxtend.modules.cell_context_selector import dataset as ds
from protacxtend.modules.cell_context_selector import features as F
from protacxtend.modules.cell_context_selector import models as M


@pytest.fixture(scope="module")
def curated():
    df, rep = ds.build_curated()
    return df, rep


@pytest.fixture(scope="module")
def enriched(curated):
    return prepare.enrich(curated[0])


# ---------------------------------------------------------------- cleaning --
class TestCleaning:
    def test_unit_normalisation_pdc50_conversion(self, curated):
        df, rep = curated[0], curated[1]
        # DC50 asserted nM; pDC50 == -log10(M)
        row = df[df["has_dc50"] == 1].iloc[0]
        assert row["dc50_nM"] > 0
        assert abs(row["pdc50"] - (-np.log10(row["dc50_nM"] * 1e-9))) < 1e-9
        assert rep["dc50_unit_nM"] is True

    def test_dmax_bounds_and_masking(self, curated):
        df = curated[0]
        dm = df.loc[df["has_dmax"] == 1, "dmax_pct"]
        assert dm.between(0, 100).all()
        # endpoints independently masked; nothing fabricated
        assert df["has_dc50"].isin([0, 1]).all()
        assert df["has_dmax"].isin([0, 1]).all()

    def test_no_fabricated_labels(self, curated):
        df = curated[0]
        # derived label defined only where endpoints decide
        undef = df[df["derived_active_defined"] == 0]
        assert (undef["derived_active"].isna() | undef["derived_active"].isna()).all()
        assert int(df["label_is_derived"].sum()) == len(df)

    def test_viability_exclusion_count(self, curated):
        rep = curated[1]
        assert rep["viability_only_excluded"] > 0
        assert rep["curated_rows"] == len(curated[0])

    def test_derived_rule_matches_paper_semantics(self):
        assert ds.is_active_dc50_dmax(100.0, 100.0) is True   # pDC50 7, Dmax 1
        assert ds.is_active_dc50_dmax(10000.0, 100.0) is False  # pDC50 5 < 6
        assert ds.is_active_dc50_dmax(100.0, 50.0) is False     # Dmax 0.5 < 0.6
        assert np.isnan(ds.is_active_dc50_dmax(np.nan, 100.0))

    def test_target_to_gene_mapping(self):
        from protacxtend.modules.cell_context_selector.genemap import target_to_gene
        assert target_to_gene("BRD4") == "BRD4"
        assert target_to_gene("EGFR L858R/T790M") == "EGFR"
        assert target_to_gene("HiBiT-BRD9") == "BRD9"
        assert target_to_gene("BCL-xL") == "BCL2L1"
        assert target_to_gene("WT") is None


class TestCellLineMapping:
    def test_mapping_table(self, curated):
        from protacxtend.modules.cell_context_selector import cellline
        df = curated[0]
        names = sorted(df["cell_line_raw"].dropna().unique())
        mp = cellline.map_cell_lines(names)
        assert len(mp) == len(names)
        assert mp["mapping_status"].isin(
            ["mapped", "unmapped", "ambiguous"]).all()
        known = mp[mp["cell_line_raw"] == "MOLT-4"]
        assert len(known) == 1 and known.iloc[0]["mapping_status"] == "mapped"
        # no fabricated DepMap ids
        assert (mp.loc[mp["mapping_status"] != "mapped",
                       "depmap_id"].isna()).all()

    def test_row_context_coverage(self, enriched):
        assert int(enriched["has_expression"].sum()) > 0
        assert enriched["lineage"].notna().sum() > 0


class TestFeatures:
    def test_leg_dimensions_and_determinism(self, enriched):
        expr = omics.ensure_curated_expression()
        mc = F.MolCache()
        sub = enriched.head(20)
        for leg in "ABCD":
            enc = F.fit_encoders(sub, leg)
            X, names = F.build_row_features(
                sub, leg, mc, expr, enc_target=enc.get("enc_target"),
                enc_e3=enc.get("enc_e3"), enc_cell=enc.get("enc_cell"),
                lin_enc=enc.get("lin_enc"))
            X2, _ = F.build_row_features(
                sub, leg, mc, expr, enc_target=enc.get("enc_target"),
                enc_e3=enc.get("enc_e3"), enc_cell=enc.get("enc_cell"),
                lin_enc=enc.get("lin_enc"))
            assert np.allclose(X, X2, equal_nan=True)   # deterministic
            assert X.shape[1] == len(names)
            assert np.isfinite(X[:, :1032]).all()  # mol part finite
        # D > A in width
        Xa, _ = F.build_row_features(sub, "A", mc, expr)
        Xd, _ = F.build_row_features(
            sub, "D", mc, expr, enc_target=F.EntityEncoder().fit(
                sub["target"].fillna("unknown").astype(str).tolist()),
            enc_e3=F.EntityEncoder().fit(
                sub["e3"].fillna("unknown").astype(str).tolist()),
            enc_cell=F.EntityEncoder().fit(
                sub["cell_line_raw"].astype(str).tolist()),
            lin_enc=F.LineageEncoder().fit(sub["lineage"].tolist()))
        assert Xd.shape[1] > Xa.shape[1]

    def test_entity_oov_safe(self):
        enc = F.EntityEncoder().fit(["BRD4", "AR"])
        assert float(enc.transform(["BRD4"])[0]) == 0.0
        assert float(enc.transform(["NEWTARGET"])[0]) == 2.0  # OOV sentinel


class TestGroupedSplits:
    def test_folds_no_entity_overlap(self, enriched):
        sub = enriched[enriched["has_dc50"] == 1].head(400)
        folds = M.split_folds(sub, "unseen_target", 3)
        for tr, te in folds:
            tr_t = set(sub.iloc[tr]["target"])
            te_t = set(sub.iloc[te]["target"])
            assert not (tr_t & te_t)

    def test_unseen_protac_split(self, enriched):
        sub = enriched[enriched["has_dc50"] == 1].head(500)
        folds = M.split_folds(sub, "unseen_protac", 3)
        for tr, te in folds:
            assert not (set(sub.iloc[tr]["protac_smiles_canonical"])
                        & set(sub.iloc[te]["protac_smiles_canonical"]))

    def test_unseen_cell_line_split(self, enriched):
        sub = enriched[enriched["has_dc50"] == 1].head(500)
        folds = M.split_folds(sub, "unseen_cell_line", 3)
        for tr, te in folds:
            assert not (set(sub.iloc[tr]["cell_line_raw"])
                        & set(sub.iloc[te]["cell_line_raw"]))

    def test_evaluate_regime_returns_metrics(self, enriched):
        cfg = dict(n_estimators=20, n_jobs=1, n_splits=2)
        ev = M.Evaluator("pdc50", "B", cfg)
        m = ev.evaluate_regime(enriched, "ridge", "random")
        assert "r2" in m and "mae" in m and "n" in m and m["n"] > 0


class TestArtifactAndApi:
    def test_missing_artifact_raises(self):
        from protacxtend.modules.cell_context_selector.predict import (
            CellContextModelError,
            predict_cell_context,
        )
        with pytest.raises(CellContextModelError):
            predict_cell_context("CC(=O)Oc1ccccc1C(=O)O", cell_line="HeLa",
                                 model_path="/tmp/does-not-exist.joblib")

    def test_schema(self):
        from protacxtend.modules.cell_context_selector.schemas import (
            MODEL_VERSION,
            CellContextInput,
        )
        assert MODEL_VERSION.startswith("cell_context_degradation-v")
        inp = CellContextInput(protac="CC", cell_line="HeLa")
        assert inp.poi is None


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
