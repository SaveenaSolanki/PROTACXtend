"""Train + evaluate + predict demo for Module 4 (curated PROTAC-DB benchmark).

Run: python -m synglue_agent.modules.degradation_ml.examples.train_demo
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from synglue_agent.modules.degradation_ml import (
    dataset_report,
    evaluate_splits,
    load_curated,
    predict_degradation,
    train_pdc50,
)


def main() -> None:
    df = load_curated()
    print("Dataset:", json.dumps(dataset_report(df), indent=1))
    print("\nGrouped split benchmark (pDC50; single-threaded RF/XGB):")
    results = evaluate_splits(df, models=["mean", "ridge", "random_forest"])
    for split, per in results["splits"].items():
        line = []
        for m, v in per.items():
            if isinstance(v, dict) and "r2" in v:
                line.append(f"{m}: R2={v['r2']} MAE={v['mae']} n={v['n']}")
            elif isinstance(v, dict):
                line.append(f"{m}: {list(v.keys())[0]}")
        print(f"  {split:16s}| " + " | ".join(line))

    print("\nTraining production pDC50 model (RandomForest)...")
    info = train_pdc50(df)
    print("  ", json.dumps({k: info[k] for k in ("model_path", "model_name",
                                                 "train_metrics", "n")}, indent=1)[:300])

    row = df.sort_values("pdc50").iloc[0]
    r = predict_degradation(row["smiles"], target=row["target"], e3=row["e3"])
    print("\nPredict (held-out-style demo row):")
    print("  pDC50:", r.pdc50, "| DC50 nM:", r.dc50_nM,
          "(pub:", round(float(row["published_dc50_nM"]), 3), ")")
    print("  interval nM:", r.pdc50_lower_nM, "-", r.pdc50_upper_nM)
    print("  OOD score:", r.ood_score, "flag:", r.ood_flag)
    print("  degradation_probability:", r.degradation_probability)
    print("  tasks:", r.tasks)


if __name__ == "__main__":
    main()
