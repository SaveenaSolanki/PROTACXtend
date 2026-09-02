"""Retrospective benchmark + baselines + ablations (Module 6).

Task: retrieve the E3(s) actually used for a POI (measured PROTAC rows) among
catalog candidates, given the cell context. Labels: 1 = E3 used for this POI
(measured DC50 row); 0 = catalog E3 never used for this POI (absence of
record = absence of evidence — documented). All grouped CV regimes prevent
leakage: random (grouped by target-E3 pair), unseen-target, unseen-E3,
unseen-pair, unseen-cell, leave-one-E3-family-out.

Metrics: pooled AUROC/AP; per-query retrieval Hit@3 / MRR over the candidate
subset present in the test fold. Baselines: expression-only,
recruiter-availability-only, precedent-frequency (train-fold counts),
logistic regression, RandomForest, XGBoost. Ablations drop feature groups;
structure/lysine axes have no numeric instances in this dataset and are
reported as a coverage census, not a model comparison.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold

from protacxtend.modules.e3_opportunity import context as ctx_mod
from protacxtend.modules.e3_opportunity import dataset as ds
from protacxtend.modules.e3_opportunity import features as F
from protacxtend.modules.e3_opportunity import localization as loc_mod
from protacxtend.modules.e3_opportunity import recruiters as rec_mod
from protacxtend.modules.e3_opportunity.e3_catalog import load_catalog

logger = logging.getLogger("protacxtend.e3_benchmark")


def _auroc(y, s):
    from sklearn.metrics import average_precision_score, roc_auc_score
    y = np.asarray(y, int)
    s = np.asarray(s, float)
    m = np.isfinite(s) & (y >= 0)
    y, s = y[m], s[m]
    if len(np.unique(y)) < 2 or len(y) < 5:
        return None, None
    try:
        return (float(roc_auc_score(y, s)), float(average_precision_score(y, s)))
    except Exception:
        return None, None


def _group(inst: pd.DataFrame, regime: str) -> np.ndarray:
    if regime == "random":
        return (inst["poi_gene"] + "|" + inst["e3_gene"]).to_numpy()
    if regime == "unseen_target":
        return inst["poi_gene"].to_numpy()
    if regime == "unseen_e3":
        return inst["e3_gene"].to_numpy()
    if regime == "unseen_cell":
        return inst["cell_line"].to_numpy()
    if regime == "unseen_pair":
        return (inst["poi_gene"] + "|" + inst["e3_gene"]).to_numpy()
    if regime == "family_loo":
        return inst["e3_family"].to_numpy()
    raise ValueError(regime)


class Benchmark:
    def __init__(self, seed: int = 42) -> None:
        self.seed = seed
        self.cat = load_catalog()
        self.pairs = ds.load_benchmark_pairs()
        self.inst = self._build_instances()

    # ------------------------------------------------------------------ data
    def _build_instances(self) -> pd.DataFrame:
        pairs = self.pairs
        pos = pairs[pairs["has_dc50"] == 1]
        used_by_poi = {p: set(g["e3_gene"]) for p, g in
                       pos.groupby("poi_gene")}
        candidates = sorted(self.cat["e3_gene"])
        never = {p: [e for e in candidates if e not in e3s]
                 for p, e3s in used_by_poi.items()}
        n_ok = 0
        rows = []
        rng = np.random.RandomState(self.seed)
        pos_uniq = pos.drop_duplicates(["poi_gene", "cell_line", "e3_gene"])
        for (poi, cell), g in pos_uniq.groupby(["poi_gene", "cell_line"]):
            for _, r in g.iterrows():
                if self._ctx(poi, cell, r["e3_gene"]) is None:
                    continue
                n_ok += 1
                rows.append(self._inst(poi, cell, r["e3_gene"], 1))
            negs = [e for e in never.get(poi, [])
                    if self._ctx(poi, cell, e) is not None]
            rng.shuffle(negs)
            for e3 in negs[:4]:
                rows.append(self._inst(poi, cell, e3, 0))
        self._n_pos_context = n_ok
        return pd.DataFrame(rows)

    def _ctx(self, poi, cell, e3):
        cache = self._cs()
        if (poi, cell, e3) not in cache:
            cache[(poi, cell, e3)] = ctx_mod.context_scores(poi, cell, None, e3)
        d = cache[(poi, cell, e3)]
        return d if d.get("score") is not None else None

    _cache: dict = {}

    def _cs(self) -> dict:
        if "cs" not in self._cache:
            cache = {}
            pos = self.pairs[self.pairs["has_dc50"] == 1]
            for (poi, cell, e3), _ in pos.groupby(
                    ["poi_gene", "cell_line", "e3_gene"]):
                cache[(poi, cell, e3)] = ctx_mod.context_scores(
                    poi, cell, None, e3)
            self._cache["cs"] = cache
        return self._cache["cs"]

    def _inst(self, poi, cell, e3, label) -> dict:
        cs = self._cs().get((poi, cell, e3)) or {}
        loc = loc_mod.compatibility(poi, e3) or {}
        rec = rec_mod.recruiter_info(e3) or {}
        bd = ctx_mod.expression_breadth(e3) or {}
        fam = self.cat[self.cat["e3_gene"] == e3]["e3_family"]
        return {
            "poi_gene": poi, "cell_line": cell, "e3_gene": e3,
            "e3_family": str(fam.iloc[0]) if len(fam) else "?",
            "label": label,
            "e3_expr_pct": cs.get("e3_expression_percentile"),
            "adaptor_expr_pct": cs.get("adaptor_expression_percentile"),
            "poi_expr_pct": cs.get("poi_expression_percentile"),
            "loc_score": loc.get("score"),
            "recruiter_avail": int(bool(rec.get("available"))),
            "recruiter_conf": rec.get("confidence"),
            "log_aff_best": (None if not rec.get("best_affinity_nM")
                             else float(np.log10(rec["best_affinity_nM"]))),
            "expr_breadth": bd.get("score"),
        }

    # ------------------------------------------------------------ precedent
    def _precedent_col(self, train_idx: np.ndarray) -> pd.Series:
        tr = self.inst.iloc[train_idx]
        counts = tr[tr["label"] == 1].groupby(
            ["poi_gene", "e3_gene"]).size()
        return self.inst.apply(
            lambda r: int(counts.get((r["poi_gene"], r["e3_gene"]), 0)),
            axis=1)

    # ------------------------------------------------------------- scores
    def scores(self, Xtr, ytr, Xte, model: str, precedent_tr=None,
               precedent_te=None) -> np.ndarray:
        if model == "expression_only":
            return np.nan_to_num(Xte[:, 0], nan=0.5)
        if model == "recruiter_only":
            # recruiter availability column index 4
            return Xte[:, 4]
        if model == "precedent_freq":
            return np.log1p(np.asarray(precedent_te, float))
        from sklearn.impute import SimpleImputer
        imp = SimpleImputer(strategy="median").fit(Xtr)
        Xtr, Xte = imp.transform(Xtr), imp.transform(Xte)
        if model == "logistic":
            clf = LogisticRegression(C=1.0, max_iter=3000, solver="liblinear")
        elif model == "random_forest":
            clf = RandomForestClassifier(n_estimators=200, random_state=42,
                                         n_jobs=2, min_samples_leaf=2)
        elif model == "xgboost":
            try:
                from xgboost import XGBClassifier
                clf = XGBClassifier(n_estimators=200, max_depth=4,
                                    learning_rate=0.05, random_state=42,
                                    n_jobs=2, verbosity=0)
            except Exception:
                clf = RandomForestClassifier(n_estimators=200, random_state=42,
                                             n_jobs=2, min_samples_leaf=2)
        else:
            raise ValueError(model)
        clf.fit(Xtr, ytr)
        if hasattr(clf, "predict_proba"):
            return clf.predict_proba(Xte)[:, 1]
        return clf.decision_function(Xte)

    # ------------------------------------------------------------ evaluate
    def evaluate(self, regime: str, model: str, n_splits: int = 5,
                 drop_groups: Sequence[str] | None = None
                 ) -> dict[str, Any]:
        inst = self.inst
        groups = _group(inst, regime)
        gkf = GroupKFold(n_splits=min(n_splits, len(set(groups))))
        y_all, s_all, folds = [], [], 0
        hit3, mrr, nq = [], [], 0
        for tr, te in gkf.split(inst, groups=groups):
            ytr = inst["label"].to_numpy()[tr]
            yte = inst["label"].to_numpy()[te]
            prec_tr = self._precedent_col(tr)
            prec_te = prec_tr.iloc[te].to_numpy()
            instf = inst.copy()
            instf["precedent_n"] = prec_tr   # train-derived counts (leak-safe)
            Xtr, _ = F.matrix(instf.iloc[tr], drop_groups)
            Xte, _ = F.matrix(instf.iloc[te], drop_groups)
            if model == "precedent_freq":
                s = self.scores(Xtr, ytr, Xte, model, None, prec_te)
            else:
                s = self.scores(Xtr, ytr, Xte, model)
            y_all.extend(yte.tolist())
            s_all.extend(s.tolist())
            folds += 1
            # retrieval per test query (poi, cell): candidates in test fold
            te_df = inst.iloc[te].copy()
            te_df["score"] = s
            for _, q in te_df.groupby(["poi_gene", "cell_line"]):
                pos_set = set(q[q["label"] == 1]["e3_gene"])
                if not pos_set:
                    continue
                # deterministic tie-break: shuffle candidate order before the
                # ranking so all-zero scores give honest (not artifact) ranks
                q = q.sample(frac=1.0, random_state=7)
                ranked = q.sort_values("score", ascending=False)["e3_gene"]
                r3 = list(ranked.head(3))
                hit3.append(1.0 if pos_set & set(r3) else 0.0)
                for rank, e3 in enumerate(ranked, start=1):
                    if e3 in pos_set:
                        mrr.append(1.0 / rank)
                        break
                else:
                    mrr.append(0.0)
                nq += 1
        auc, ap = _auroc(np.array(y_all), np.array(s_all))
        return {"regime": regime, "model": model, "folds": folds,
                "auroc": (None if auc is None else round(auc, 4)),
                "auprc": (None if ap is None else round(ap, 4)),
                "n_instances": int(len(inst)), "n_pos": int(sum(y_all)),
                "n_test": int(len(y_all)),
                "hit_at_3": (round(float(np.mean(hit3)), 4) if hit3 else None),
                "mrr": (round(float(np.mean(mrr)), 4) if mrr else None),
                "n_queries": nq}

    # ------------------------------------------------------------ ablations
    def ablation(self, regimes=("unseen_target", "unseen_pair"),
                 full_model="random_forest",
                 drop_groups=("context", "localization", "recruiter",
                              "precedent", "selectivity")) -> dict[str, Any]:
        out = {"full": {}, "ablations": {}}
        for reg in regimes:
            out["full"][reg] = self.evaluate(reg, full_model)
        for g in drop_groups:
            key = f"-{g}"
            out["ablations"][key] = {}
            for reg in regimes:
                m = self.evaluate(reg, full_model, drop_groups=[g])
                out["ablations"][key][reg] = m
                base = out["full"][reg].get("auroc")
                ab = m.get("auroc")
                if base is not None and ab is not None:
                    out["ablations"][key][reg + "_delta"] = round(ab - base, 4)
        return out

    def structure_coverage(self) -> dict[str, Any]:
        """Coverage census for structure/lysine axes (no numeric instances)."""
        from protacxtend.modules.e3_opportunity.structure import (
            e3_structural_evidence,
        )
        e3s = sorted(set(self.inst["e3_gene"]))
        with_complex = [e for e in e3s
                        if e3_structural_evidence(e).get("has_curated_complex")]
        return {"instances": int(len(self.inst)),
                "e3_candidates_seen": len(e3s),
                "e3_with_curated_complex_pdb": with_complex,
                "poi_structures_available": 0,
                "note": "no POI structures in the retrospective set; "
                        "structure/lysine axes evaluated via unit tests on "
                        "user-supplied structures only"}
