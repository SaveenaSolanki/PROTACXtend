# Limitations — Module 5 (cell-context degradation model)

Honest limits; nothing below is hidden.

## Dataset
- Clean core with *both* DC50 and Dmax measured: 479 rows (pre-dedup audit
  number 522). Regression tasks are trained per endpoint on 1,181 (DC50) and
  761 (Dmax) measured rows — many rows lack one endpoint.
- 231 source DOIs → inter-lab assay heterogeneity (different protocols,
  treatment times 1–72 h, WB vs HiBiT quantitation) is absorbed as label
  noise, not modelled.
- Cell-line imbalance: a few lines dominate (VCaP, HEK293T, HeLa …); 30 of 98
  cell lines have ≥5 (DC50&Dmax) rows.
- Target/E3 imbalance: 8 canonical E3 ligases (CRBN/VHL dominate); 121 target
  strings with many mutant variants mapped to 91 genes.

## Labels
- **Binary "activity" is threshold-derived** (`pDC50>=6.0 AND Dmax>=60`), the
  documented rule of the source paper (arXiv 2406.02637). It is not an
  independently measured degradation-outcome label. Shipped `Active` column
  disagrees with the rule on 157/857 QA rows → never used; ours is recomputed.
- No DC50/Dmax/probability value is fabricated; missing endpoints stay missing
  (endpoint masks).

## Cell context
- DepMap 24Q4 covers 130/180 cell-line names (unmapped 41 incl. 7 qualitative
  descriptions; lines absent from DepMap such as HEK293T, SRD15, TMD8, WI38).
- **Proteomics: not available** → proteotype-awareness is NOT claimed.
- Transcriptomic features are TPM-log1p as shipped (batch-corrected
  alternative not used); a subset of genes (TCEB1/TCEB2/BIRC4/UBE2R1) is
  absent from the matrix and imputed (train-median) in leg-D models.
- Unmapped cell lines at query time → imputed context + cell-OOD flag +
  applicability CAUTION (documented in predict.py).

## Mechanistic (Modules 1–3) features
Only 22/1,913 rows reference a ternary PDB structure; Module 1 (hook) requires
measured binding parameters that this database does not carry. Modules 1–3
features are therefore **not included at dataset scale** — ablation leg F is
reported as a census, not a model comparison. Wiring exists to add them for
structure-paired series later.

## Methods
- Split metrics on hardest grouped regimes are modest (often negative R² on
  unseen-E3/unseen-target for linear models) — reported in full, never
  cherry-picked. "Random" splits are an optimistic ceiling (same compound can
  appear in train and test).
- Conformal-style intervals use training residuals (not calibrated);
  uncertainty also reports RF tree-spread.
- OOD uses kNN distances in molecular/expression space + entity vocabulary
  membership — a heuristic, not calibrated density.

## Claims policy
`cell_context_aware` is set True **only** when the best cell-information leg
beats PROTAC+target+E3 on held-out grouped regimes (evidence recorded in the
artifact). `proteotype_aware` stays False. Selectivity is never claimed from
cell-line identity codes alone.
