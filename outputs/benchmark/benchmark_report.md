# Retrospective Benchmark Report (B5)

_Generated 2026-08-02 · n=64 predictions · data: PROTAC-DB 3.0_

## Metrics

| Metric | Value |
|---|---|
| n_predictions | 64 |
| n_published_dc50 | 64 |
| n_with_dmax | 32 |
| spearman_rho_logdc50 | 0.2433 |
| spearman_p | 0.052673 |
| kendall_tau_logdc50 | 0.1672 |
| kendall_p | 0.050881 |
| hit_rate_100nM | 0.5312 |
| hit_rate_1000nM | 0.7812 |
| mae_log10_dc50 | 1.2098 |
| spearman_rho_dmax | 0.1956 |
| median_published_dc50 | 22.0 |
| median_predicted_dc50 | 173.0510726467407 |
| pct_grover_protac | 100.0 |
| sample_size_requested | 64 |
| method | SynGlue MultiTaskProtacModel, full-PROTAC GROVER embedding + family E3 embedding + constant warhead (SynGlue inference design) |
| data | PROTAC-DB 3.0 (cadd.zju.edu.cn/protacdb), DC50-available CRBN/VHL PROTACs |

## Top/bottom predictions

| Name | Target | E3 | Published DC50 (nM) | Predicted DC50 (nM) |
|---|---|---|---|---|
| PROTAC(H-PGDS)-7 | HPGDS | CRBN | 0.02 | 305.25 |
| PROTAC(H-PGDS)-5-TFC-007 | HPGDS | CRBN | 0.03 | 307.36 |
| nan | ERalpha | CRBN | 0.14 | 6.57 |
| BD-7162 | BRD2 | CRBN | 0.20 | 275.97 |
| nan | ERalpha | CRBN | 0.34 | 7.42 |
| nan | BTK | CRBN | 0.39 | 50.47 |
| nan | BTK | CRBN | 0.73 | 81.07 |
| nan | SMARCA2 | VHL | 0.76 | 1543.88 |

## Honest caveats

- Assay heterogeneity: PROTAC-DB merges values across cell lines/assays; row-level DC50 has multi-fold noise.
- The constant-warhead simplification (SynGlue's own inference design) discards warhead identity.
- The model was trained on SynGlue's data, not PROTAC-DB; this is out-of-distribution testing for the model.
- GROVER embeddings are the real learned representations (no RDKit proxy used).
- Spearman rho on log10 DC50 is the primary readout; threshold hit rates depend on assay-matched cutoffs.
## Interpretation (2026-08-02)

- **Weak but nonzero rank signal**: Spearman ρ = 0.243 (p = 0.053) on log10
  DC50 across 64 stratified PROTAC-DB 3.0 PROTACs. The predictor separates
  sub-µM from super-µM degraders at 78% agreement, but cannot rank
  sub-100 nM degraders (53% vs 50% chance).
- **Systematic bias**: predicted DC50 median 173 nM vs published 22 nM —
  the model overestimates DC50 (predicts weaker potency). MAE = 1.21 log10
  units. Any use of absolute DC50 values from this model is unreliable;
  only coarse binning (potent/weak) has signal.
- **Why performance is limited (expected)**: (1) out-of-distribution —
  model trained on SynGlue's private data, tested on PROTAC-DB;
  (2) constant-warhead inference design discards warhead identity;
  (3) assay heterogeneity in PROTAC-DB (multi-cell-line, multi-assay rows);
  (4) n=64 is small; ρ's CI is wide.
- **Baseline established**: this is the measured baseline any improved model
  (Chemprop D-MPNN trained on PROTAC-DB, B1) must beat on the same 64-molecule
  stratified set. Benchmark is reproducible: `scripts/benchmark_degradation.py`.
