# VALIDATION DEBT — where unit-green ≠ scientifically validated (2026-09-02)

Distinguish: **unit-test green** (code behaves deterministically) from
**scientifically validated** (predictions reproduce measured biology /
independent benchmarks). Debt list is ordered by scientific impact.

| # | Area | Unit green | Scientific validation status | Debt / needed work |
|---|---|---|---|---|
| V1 | Degradation chemprop pDC50/Dmax | yes (endpoint tests) | retrospective G6 reproduction (acc 81.6/AUC .900) + conformal calibration | no prospective set; no wet-lab pDC50/Dmax confirmation |
| V2 | M5 cell-context pDC50 | yes (16 tests) | grouped retrospective only | unseen-cell transfer negative (Δ−.076); proteomics absent → proteotype unclaimable |
| V3 | M6 E3 ranking | yes (17 tests) | retrospective retrieval of known usage | prospective novel-E3 discovery unvalidated; negatives = absence-of-record |
| V4 | M2 lysine feasibility | yes (8 tests, synthetic fixtures) | real-PDB benchmark **pending** (tracked) | curate real ternary/E2 structures with known ubiquitination outcomes |
| V5 | M3 cooperativity α | yes (harness tests) | **no curated experimental α dataset** → surrogate untrained | primary-literature SI curation (tracked) before any learned α |
| V6 | M4 pDC50 small-data | yes (9 tests, audit) | honest small baseline | supersession by M4-v2 (memo ready, gated on M5 audit) |
| V7 | Ternary proxy (pLDDT/stage) | yes (architecture tests) | proxy only; P4ward runs env-gated, not in CI | real ternary benchmark runs + coverage-cell truth tables (NULL-until-measured) |
| V8 | Linker generator + scorer | yes (15 linker tests) | internal rho .80 (style scorer); official Link-INVENT absent | parity with official package; potency correlation is a FINAL case study |
| V9 | ADMET-AI endpoints | yes (venv-gated) | endpoint-level only; no assay correlation | permeability/CYP/stability validation (GAP06/07) |
| V10 | Retrosynthesis | yes (14 tests, fallback) | verified-synthesis research briefs (history) | per-candidate route success rate on new design runs |
| V11 | Selectivity (restriction/neosubstrate) | yes (M6 axes) | restriction = lineage expression only | neosubstrate/off-target risk model (GAP05) |
| V12 | Hook effect / kinetics | M1 equilibrium validated (MC audit) | kinetics ≠ equilibrium; no measured kinetic params | experimental Kds/kon/koff needed for real kinetics |
| V13 | Deep research | yes (29 tests) | retrieval-grade evidence, claim grading | not a substitute for experimental validation |
| V14 | Config/claims sync | n/a | `config/scientific_status.yaml` stale (M6 PLANNED) | sync script (GAP02) |

**Overarching validation debt:** all *learned-prediction* claims (V1–V3, V8,
V9, V10) are retrospective or synthetic. Final case studies (matched-linker
potency, BRD4–VHL six-compound blind ranking, wet-lab) are the prospective
layer — deliberately OUT of current platform-building scope.
