#!/usr/bin/env python3
"""
B5 — Retrospective benchmark: SynGlue degradation predictor vs PROTAC-DB 3.0.
=============================================================================

Data: PROTAC-DB 3.0 (cadd.zju.edu.cn/protacdb) — 15,502 PROTACs, 2,275 with DC50.
       Downloaded 2026-08-02 → data/benchmark/PROTAC-DB_3.0_protacs.xlsx

Method (mirrors SynGlue's own inference design from its generation pipeline):
  - full PROTAC SMILES → GROVER 4800-dim embedding (real extraction)
  - E3 embedding: pre-computed GROVER vector matched to E3 family
      CRBN → pomalidomide, VHL → VH032 (both in data/synglue/data/grover_e3.csv)
  - warhead embedding: constant vector (SynGlue's generation pipeline uses
    iloc[0] of grover_warhead.csv — the model was trained that way)
  - tensor (3, 4800) → MultiTaskProtacModel → predicted DC50 / Dmax

Metrics:
  - Spearman rho + Kendall tau on log10(DC50) predicted vs published
  - Hit rate at <100 nM and <1000 nM thresholds
  - MAE on log10 nM
  - Dmax rank correlation (subset with Dmax)

Honest caveats (recorded in report):
  - Assay heterogeneity: PROTAC-DB merges multiple cell lines/assays per row
  - The model was trained on SynGlue's own data (not PROTAC-DB), and the
    constant-warhead simplification discards warhead identity
  - GROVER embeddings for full PROTACs are the real learned representations

Usage:
  python scripts/benchmark_degradation.py [--sample N] [--gpu/--cpu]
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("benchmark")

from protacxtend.tools.synglue_degradation import (
    extract_grover_embedding,
    lookup_precomputed_embedding,
    _build_transformer,
    MODEL_PATHS,
    _grover_available,
)

DATA = ROOT / "data" / "benchmark" / "PROTAC-DB_3.0_protacs.xlsx"
OUT = ROOT / "outputs" / "benchmark"


# ── E3 family → pre-computed embedding (by canonical SMILES in e3_ligand.csv) ──
POMALIDOMIDE = "Nc1cccc2c1C(=O)N(C1CCC(=O)NC1=O)C2=O"
THALIDOMIDE = "O=C1CCC(N2C(=O)c3ccccc3C2=O)C(=O)N1"
# VH032 canonical SMILES as stored in SynGlue e3_ligand.csv (must match exactly)
VH032 = "CC(=O)N[C@H](C(=O)N1C[C@H](O)C[C@H]1C(=O)NCC1=CC=C(C2=C(C)N=CS2)C=C1)C(C)(C)C"


def get_e3_embedding(e3_family: str):
    """Return (embedding, name) for an E3 family using pre-computed GROVER."""
    if "VHL" in e3_family.upper():
        smi, name = VH032, "VH032"
    else:
        smi, name = POMALIDOMIDE, "pomalidomide"
    emb = lookup_precomputed_embedding(
        smi, MODEL_PATHS["grover_e3_csv"], MODEL_PATHS["e3_ligand_csv"]
    )
    return emb, name


def build_benchmark_set(df: pd.DataFrame, sample_size: int) -> pd.DataFrame:
    """Filter + stratify by log10(DC50) quantiles."""
    df = df.copy()
    df["DC50 (nM)"] = pd.to_numeric(df["DC50 (nM)"], errors="coerce")
    df["Dmax (%)"] = pd.to_numeric(df["Dmax (%)"], errors="coerce")
    df = df[df["DC50 (nM)"].notna()]
    df = df[df["DC50 (nM)"] > 0]  # log-scale requires positive values
    df = df[df["E3 ligase"].isin(["CRBN", "VHL"])]
    df = df[df["Smiles"].notna()]

    # Deduplicate identical SMILES (keep min DC50)
    df = df.sort_values("DC50 (nM)").drop_duplicates(subset="Smiles", keep="first")

    # Stratified sampling across log10(DC50) bins
    df["log_dc50"] = np.log10(df["DC50 (nM)"])
    try:
        df["bin"] = pd.qcut(df["log_dc50"], q=8, duplicates="drop")
    except Exception:
        df["bin"] = pd.cut(df["log_dc50"], bins=8)

    per_bin = max(1, sample_size // 8)
    sampled = df.groupby("bin", observed=True).apply(
        lambda g: g.sample(min(per_bin, len(g)), random_state=42)
    ).reset_index(drop=True)
    return sampled


def predict_one(protac_smiles: str, e3_family: str, model) -> dict:
    """Predict DC50/Dmax for one PROTAC (SynGlue inference design)."""
    import torch

    protac_emb = extract_grover_embedding(protac_smiles)
    if protac_emb is None:
        return {"ok": False, "reason": "grover_failed"}

    e3_emb, e3_name = get_e3_embedding(e3_family)
    if e3_emb is None:
        return {"ok": False, "reason": "no_e3_embedding"}

    # Constant warhead vector (SynGlue generation-pipeline design)
    import pandas as _pd
    wh_df = _pd.read_csv(MODEL_PATHS["grover_warhead_csv"], low_memory=False)
    w_cols = [c for c in wh_df.columns if c.startswith("Grover_")]
    warhead_emb = wh_df[w_cols].iloc[0].values.astype(np.float32)

    X = np.stack([warhead_emb, protac_emb, e3_emb])[np.newaxis, :, :].astype(np.float32)
    X_t = torch.tensor(X)

    with torch.no_grad():
        dc50_head, dmax_head, attn = model(X_t)

    return {
        "ok": True,
        "pred_dc50_nM": float(10 ** dc50_head.item()),
        "pred_dmax_pct": float(dmax_head.item()),
        "attn_warhead": float(attn[0, 0, 0]),
        "attn_protac": float(attn[0, 1, 0]),
        "attn_e3": float(attn[0, 2, 0]),
        "e3_embedding": e3_name,
    }


def spearman_rho(x: np.ndarray, y: np.ndarray) -> float:
    from scipy.stats import spearmanr, kendalltau
    rho, p = spearmanr(x, y)
    return float(rho), float(p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=64)
    ap.add_argument("--max-extract-seconds", type=int, default=120)
    args = ap.parse_args()

    if not DATA.exists():
        logger.error("PROTAC-DB xlsx not found: %s (download from cadd.zju.edu.cn/protacdb)", DATA)
        sys.exit(1)

    logger.info("GROVER available: %s", _grover_available())
    if not _grover_available():
        logger.warning("GROVER unavailable — embeddings would be proxies. Aborting honest run.")
        sys.exit(2)

    df = pd.read_excel(DATA)
    bench = build_benchmark_set(df, args.sample)
    logger.info("Benchmark set: %d PROTACs (CRBN/VHL, DC50 available)", len(bench))

    model = _build_transformer()
    model.eval()

    rows = []
    t_start = time.time()
    for i, (_, row) in enumerate(bench.iterrows()):
        smi = row["Smiles"]
        e3_fam = row["E3 ligase"]
        published_dc50 = float(row["DC50 (nM)"])
        published_dmax = float(row["Dmax (%)"]) if pd.notna(row["Dmax (%)"]) else None

        logger.info("[%d/%d] %s (%s) DC50=%.2f", i + 1, len(bench),
                    str(row.get("Name", ""))[:30], e3_fam, published_dc50)
        pred = predict_one(smi, e3_fam, model)
        if not pred["ok"]:
            logger.warning("  skip: %s", pred["reason"])
            continue

        rows.append({
            "name": row.get("Name", ""),
            "target": row.get("Target", ""),
            "e3": e3_fam,
            "smiles": smi,
            "published_dc50_nM": published_dc50,
            "published_dmax_pct": published_dmax,
            "pred_dc50_nM": pred["pred_dc50_nM"],
            "pred_dmax_pct": pred["pred_dmax_pct"],
            "attn_warhead": pred["attn_warhead"],
            "attn_protac": pred["attn_protac"],
            "attn_e3": pred["attn_e3"],
            "e3_embedding": pred["e3_embedding"],
        })
        if time.time() - t_start > args.max_extract_seconds * 60:
            logger.warning("time budget reached at %d molecules", len(rows))
            break

    if len(rows) < 10:
        logger.error("Too few predictions (%d) — cannot report correlations.", len(rows))
        sys.exit(3)

    res = pd.DataFrame(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    res.to_csv(OUT / "benchmark_predictions.csv", index=False)

    # ── Metrics ──
    x = np.log10(res["published_dc50_nM"].values)
    y = np.log10(res["pred_dc50_nM"].values)
    rho, p_rho = spearman_rho(x, y)
    from scipy.stats import kendalltau
    tau, p_tau = kendalltau(x, y)

    hit_100 = ((res["published_dc50_nM"] < 100) == (res["pred_dc50_nM"] < 100)).mean()
    hit_1000 = ((res["published_dc50_nM"] < 1000) == (res["pred_dc50_nM"] < 1000)).mean()
    mae_log = np.abs(x - y).mean()

    dmax_rows = res[res["published_dmax_pct"].notna()]
    rho_dmax = None
    if len(dmax_rows) >= 10:
        rho_dmax, _ = spearman_rho(
            dmax_rows["published_dmax_pct"].values, dmax_rows["pred_dmax_pct"].values
        )

    metrics = {
        "n_predictions": len(res),
        "n_published_dc50": len(res),
        "n_with_dmax": len(dmax_rows),
        "spearman_rho_logdc50": round(rho, 4),
        "spearman_p": round(p_rho, 6),
        "kendall_tau_logdc50": round(tau, 4),
        "kendall_p": round(p_tau, 6),
        "hit_rate_100nM": round(float(hit_100), 4),
        "hit_rate_1000nM": round(float(hit_1000), 4),
        "mae_log10_dc50": round(float(mae_log), 4),
        "spearman_rho_dmax": round(float(rho_dmax), 4) if rho_dmax is not None else None,
        "median_published_dc50": float(np.median(res["published_dc50_nM"])),
        "median_predicted_dc50": float(np.median(res["pred_dc50_nM"])),
        "pct_grover_protac": 100.0,  # all used real GROVER embeddings
        "sample_size_requested": args.sample,
        "method": "SynGlue MultiTaskProtacModel, full-PROTAC GROVER embedding + family E3 embedding + constant warhead (SynGlue inference design)",
        "data": "PROTAC-DB 3.0 (cadd.zju.edu.cn/protacdb), DC50-available CRBN/VHL PROTACs",
    }

    with open(OUT / "benchmark_metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)

    print("\n" + "=" * 60)
    print("RETROSPECTIVE BENCHMARK — PROTAC-DB 3.0 vs SynGlue predictor")
    print("=" * 60)
    for k, v in metrics.items():
        print(f"  {k}: {v}")

    # Report markdown
    report = OUT / "benchmark_report.md"
    lines = [
        "# Retrospective Benchmark Report (B5)",
        "",
        f"_Generated 2026-08-02 · n={len(res)} predictions · data: PROTAC-DB 3.0_",
        "",
        "## Metrics",
        "",
        "| Metric | Value |",
        "|---|---|",
    ]
    for k, v in metrics.items():
        lines.append(f"| {k} | {v} |")
    lines += ["", "## Top/bottom predictions", "", "| Name | Target | E3 | Published DC50 (nM) | Predicted DC50 (nM) |",
              "|---|---|---|---|---|"]
    top = res.sort_values("published_dc50_nM").head(8)
    for _, r in top.iterrows():
        lines.append(f"| {str(r['name'])[:25]} | {r['target']} | {r['e3']} | {r['published_dc50_nM']:.2f} | {r['pred_dc50_nM']:.2f} |")
    lines += ["", "## Honest caveats",
              "",
              "- Assay heterogeneity: PROTAC-DB merges values across cell lines/assays; row-level DC50 has multi-fold noise.",
              "- The constant-warhead simplification (SynGlue's own inference design) discards warhead identity.",
              "- The model was trained on SynGlue's data, not PROTAC-DB; this is out-of-distribution testing for the model.",
              "- GROVER embeddings are the real learned representations (no RDKit proxy used).",
              "- Spearman rho on log10 DC50 is the primary readout; threshold hit rates depend on assay-matched cutoffs."]
    report.write_text("\n".join(lines))
    print(f"\nReport: {report}")
    print(f"Predictions: {OUT / 'benchmark_predictions.csv'}")


if __name__ == "__main__":
    main()
