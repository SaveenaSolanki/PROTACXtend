"""Module 5 demo: run the full grouped benchmark, train the production
artifact, print claims + a demo prediction.

Run: python -m protacxtend.modules.cell_context_selector.examples.train_demo
     [--quick]  (tiny estimators, few folds — for CI/tests)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from protacxtend.modules.cell_context_selector import (
    cellline,
    dataset,
    omics,
    prepare,
)
from protacxtend.modules.cell_context_selector.predict import (
    predict_cell_context,
)
from protacxtend.modules.cell_context_selector.train import (
    compute_claims,
    run_benchmark,
    train_production,
)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--benchmark-only", action="store_true")
    args = ap.parse_args()

    if args.quick:
        cfg = dict(n_estimators=40, n_jobs=1, n_splits=3, seed=7)
    else:
        cfg = dict(n_estimators=250, n_jobs=4, n_splits=5, seed=42)

    df, rep = dataset.build_curated()
    print("== curated dataset ==")
    print(json.dumps({k: rep[k] for k in (
        "raw_rows", "viability_only_excluded", "curated_rows",
        "measured_dc50", "measured_dmax", "measured_both",
        "derived_active_defined", "cell_lines_raw", "targets", "e3_ligases",
        "dois")}, indent=1))
    print("QA vs shipped Active:", rep["qa_vs_shipped_active"])

    print("\n== cell-line mapping / omics coverage ==")
    enr = prepare.enrich(df)
    expr = omics.ensure_curated_expression()
    names = sorted(df["cell_line_raw"].dropna().unique())
    mp = cellline.map_cell_lines(names)
    cov = {
        "raw_names": len(names),
        "mapped": int((mp["mapping_status"] == "mapped").sum()),
        "unmapped": int((mp["mapping_status"] == "unmapped").sum()),
        "ambiguous": int((mp["mapping_status"] == "ambiguous").sum()),
        "rows_with_expression": int(enr["has_expression"].sum()),
        "expression_models": int(len(expr)),
        "genes_curated": int(len(expr.columns)),
        "proteomics_available": False,
    }
    print(json.dumps(cov, indent=1))

    print("\n== grouped benchmark (this takes a while) ==")
    results = run_benchmark(df, cfg)
    (Path(__file__).resolve().parent.parent / "data" /
     "benchmark_results.json").write_text(
        json.dumps(results, indent=1, default=str))
    claims = compute_claims(results)
    print(json.dumps(claims, indent=1))

    if args.benchmark_only:
        return

    print("\n== training production artifact ==")
    info = train_production(df, results, cfg)
    print(json.dumps({k: info[k] for k in ("model_path", "claims",
                                            "endpoint_legs",
                                            "endpoint_models", "n_rows")},
                     indent=1, default=str))

    print("\n== demo prediction ==")
    row = enr.sort_values("pdc50").dropna(subset=["pdc50"]).iloc[0]
    out = predict_cell_context(row["protac_smiles_canonical"],
                               poi=row["target"], e3=row["e3"],
                               cell_line=row["cell_line_raw"])
    out.pop("limitations", None)
    print(json.dumps(out, indent=1, default=str))
    print("\npublished DC50 nM:", round(float(row["dc50_nM"]), 3),
          "| published Dmax:", row["dmax_pct"])


if __name__ == "__main__":
    main()
