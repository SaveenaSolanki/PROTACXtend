# CLAIMS REGISTRY — PROTACpilot / SynGlue Agent (2026-09-02 audit)

Aggregated, evidence-gated claim registry. Rules: no claim may exceed its
validation evidence; per-module claim registers remain authoritative for their
scope (Module 6 → `modules/e3_opportunity/docs/CLAIMS.md`); platform-level
claims below consolidate all modules + tools. Distinguish *retrospective
benchmark success* from *prospective scientific validation*.

Grading: SUPPORTED (benchmark + independent reproduction), PROMISING (strong
signal, limited validation), EXPLORATORY (plausible, insufficient),
NOT SUPPORTED (no or negative evidence).

| # | Capability | Grade | Evidence (repo file / test / benchmark) |
|---|---|---|---|
| 1 | pDC50 / Dmax degradation prediction (chemprop ensemble) | SUPPORTED (retrospective only) | chemprop degradation endpoint; G6 reproduction acc 81.6%/AUC .900 vs paper 80.8/.865 (arXiv 2406.02637); conformal calibration `outputs/benchmark/chemprop_cal_*` |
| 2 | pDC50 ML small-data (M4) | SUPPORTED (as honest small-data baseline) | `modules/degradation_ml`; 9 tests; audit-approved; grouped modest, in-sample RF ~0.95 labelled train-fit |
| 3 | Cell-context-aware pDC50 (M5, transcriptomics) | SUPPORTED (retrospective) | `modules/cell_context_selector`; leg D > B unseen-PROTAC R² .605 vs .513; 16 tests |
| 4 | Unseen-cell-line transcriptomic generalization | NOT SUPPORTED | M5: D < B on unseen-cell-line (RF .161 vs .269; Δ−.076); claim gate false in artifact |
| 5 | Proteotype-aware prediction | NOT SUPPORTED | no proteomics coverage (DepMap 24Q4); M5 proteotype_aware=False |
| 6 | E3 retrieval of known/tractable choices | SUPPORTED (retrospective) | M6 grouped benchmark RF AUROC .98 easy / .93 unseen-E3; recruiter ablation −.52 |
| 7 | Novel-E3 prospective discovery | NOT SUPPORTED | M6 CLAIMS.md; absence-of-record negatives only |
| 8 | Unseen-E3 generalization | NOT SUPPORTED (PROMISING signals) | M6 unseen-E3 AP .69 vs .94 easy; XGB below chance |
| 9 | E3 recommendation by expression alone | NOT SUPPORTED (explicitly forbidden) | M6 benchmark expression-only AUROC .49; hard rule + tests |
| 10 | Lysine ubiquitination feasibility (static geometry) | PROMISING (surrogate) | M2 8 tests; synthetic-fixture only; real-PDB benchmark pending |
| 11 | Cooperativity (α) prediction | EXPLORATORY (data-gated surrogate only) | M3: no curated experimental α dataset; surrogate labelled untrained |
| 12 | Hook effect / occupancy (equilibrium) | SUPPORTED (CALCULATED analytic) | M1 24 tests + MC audit; equilibrium only, no kinetics |
| 13 | Ternary-complex feasibility | EXPLORATORY (proxy) / WRAPPER (P4ward) | ternary_stage pLDDT/proxy gates; P4ward docker env-gated; M6 returns None w/o ternary data |
| 14 | Permeability / intracellular exposure | EXPLORATORY | only 2D rule descriptors (`admet_integration` druglikeness); no 3D PSA/IMHB/exposure model |
| 15 | Metabolic stability / CYP / PK-PD | NOT SUPPORTED | no such endpoints; no PK/PBPK models |
| 16 | Selectivity / neosubstrate risk | NOT SUPPORTED | only lineage-restriction heuristic (M6) + seed-prior `proteome_selectivity` v0.1 |
| 17 | Generative linker + Link-INVENT-style scoring | SUPPORTED (as internal structure/ML tool) | trained char-GRU; 15 linker tests; internal re-implementation rho .80 — NOT the official Link-INVENT package |
| 18 | Retrosynthesis / synthesis feasibility | EXPLORATORY (backend-dependent) | ASKCOS HTTP + optional AiZynth; offline fallback path default; verified-synthesis research briefs (history) |
| 19 | Deep-research evidence retrieval & grading | SUPPORTED (as retrieval/reporting tool) | research/ reporting; 29 tests; publication-quality reports; claims graded Strong/Moderate/Weak |
| 20 | Degradation probability (binary "Active") | NOT SUPPORTED as experimental | both M4 (disabled) and M5 (threshold-derived, explicitly documented) |

Software status ("v0.3 core release") is **separate** from scientific
validation (config/scientific_status.yaml). This registry is the consolidated
view; keep in sync with `config/scientific_status.yaml` (currently stale:
novel_e3_engine listed PLANNED while M6 is implemented).
