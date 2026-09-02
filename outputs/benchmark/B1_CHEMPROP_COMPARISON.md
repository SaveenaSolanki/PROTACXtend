# B1 — Chemprop D-MPNN trained on PROTAC-DB 3.0: benchmark comparison

_Generated 2026-08-02_

## Setup

- **Training data**: PROTAC-DB 3.0 (2,275 rows with DC50 → 1,762 usable after
  DC50>0 + dedup by canonical SMILES → 1,698 after excluding the 64 benchmark
  molecules). Target: `log10(DC50 nM)`.
- **Model**: Chemprop 2.3.0 D-MPNN (`MolAtomBondMPNN`), regression, scaffold-balanced
  split 80/10/10, 60 epochs, GPU (RTX 5000).
- **Internal test (scaffold split)**: RMSE = 0.875 log10, **R² = 0.517**.
- **Evaluation**: the same 64-molecule stratified PROTAC-DB benchmark set used
  for the SynGlue baseline (B5) — excluded from training.

## Head-to-head on the same 64 molecules

| Metric | SynGlue transformer (B5 baseline) | Chemprop D-MPNN (B1) |
|---|---|---|
| Spearman ρ (log10 DC50) | 0.243 (p=0.053) | **0.758 (p<0.001)** |
| Kendall τ | 0.167 | **0.559** |
| Hit rate <100 nM | 53.1% | **76.6%** |
| Hit rate <1000 nM | 78.1% | **93.8%** |
| MAE (log10 nM) | 1.21 | **0.641** |
| Median predicted DC50 | 173 nM (published 22 nM) | — |

## Interpretation

1. **Training on domain data is decisive.** The SynGlue model (trained on a
   different private corpus, tested out-of-distribution) has weak signal
   (ρ=0.24). A Chemprop D-MPNN trained on PROTAC-DB's own labels reaches
   ρ=0.76 on the same held-out molecules — a ~3× improvement in rank
   correlation and near-2× in MAE.
2. **The benchmark molecules were excluded from training** (1,698 training rows
   vs 64 held out), and the internal scaffold-split R²=0.52 confirms the model
   generalizes beyond memorization.
3. **Remaining honest limits**: single-target regression (no Dmax head yet);
   PROTAC-DB assay heterogeneity remains; the benchmark is n=64; absolute DC50
   still has ~0.64 log10 error (~4.4×), so absolute values need caution — but
   *ranking* is now usable (ρ=0.76).

## Artifacts

- Trained model: `outputs/benchmark/chemprop_model/model_0/best.pt`
- Train CSV: `data/benchmark/chemprop_train.csv`
- Benchmark predictions (SynGlue): `outputs/benchmark/benchmark_predictions.csv`
- Benchmark predictions (Chemprop): `outputs/benchmark/chemprop_predictions.csv`
- Repro: `scripts/benchmark_degradation.py` (SynGlue path);
  Chemprop train/predict commands in this report:

```bash
chemprop train -i data/benchmark/chemprop_train.csv -s smiles \
  --target-columns logDC50 --task-type regression --metrics rmse r2 \
  --split SCAFFOLD_BALANCED --split-sizes 0.8 0.1 0.1 \
  --epochs 60 --accelerator gpu --devices 1 \
  -o outputs/benchmark/chemprop_model --ensemble-size 1

chemprop predict -i data/benchmark/chemprop_benchmark_clean.csv -s smiles \
  --model-paths outputs/benchmark/chemprop_model/model_0/best.pt \
  --accelerator gpu --devices 1 \
  -o outputs/benchmark/chemprop_predictions.csv
```

## Next steps

- Add Dmax head (multi-target training) — extends to efficacy ranking.
- Ensemble of 3-5 Chemprop models with different seeds (error bars on ρ).
- Wire the trained model into `protac_toolbox` / `synglue_degradation` as a
  `chemprop` backend so the agentic pipeline can use it (see B1 wrapper).
