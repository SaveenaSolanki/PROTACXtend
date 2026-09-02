# Validation — Module 6 (E3 opportunity engine)

`pytest synglue_agent/modules/e3_opportunity/tests/` → 17 passed (deterministic;
challenge tests 1–7 + integrity rules). Full benchmark JSON under
`artifacts/benchmark_results.json` (reproducible; grouped CV, n_splits=4,
seed 42).

## Dataset & evidence resources
- Retrospective positives: 270 unique (poi, cell, E3) measured pairs
  (1,114 benchmark instances incl. sampled never-used negatives) from 1,913
  curated PROTAC-Degradation-DB rows; E3 labels mapped to the 30-gene catalog.
- Recruiters: DOI-cited ligand library (107 rows; demo rows excluded).
- Localization: 78 UniProt-reviewed annotations cached offline.
- Context: DepMap 24Q4 percentiles (catalog E3 + adaptors + POI genes).

## Model vs baselines — AUROC / AUPRC / MRR (retrieval of known-working E3)

| regime | expression-only | recruiter-only | precedent-freq | logistic | RF (full) | XGBoost |
|---|---|---|---|---|---|---|
| random | .49/.24/.79 | .73/.37/.89 | .50/.24/.85 | .78/.43/.90 | **.98/.94/1.00** | .47/.23/.85 |
| unseen-target | .49/.24/.48 | .73/.37/.91 | .50/.24/.88 | .79/.43/.73 | **.98/.95/.98** | .50/.24/.88 |
| unseen-pair | .49/.24/.79 | .73/.37/.89 | .50/.24/.85 | .78/.43/.90 | **.98/.94/1.00** | .47/.23/.85 |
| unseen-cell | .49/.24/.48 | .73/.37/.91 | .85/.78/.99 | .95/.91/.94 | **.99/.98/.99** | .86/.81/.99 |
| unseen-E3 | .49/.24/.84 | .73/.37/.95 | .50/.24/.92 | .58/.30/.85 | **.93/.69/.96** | .19/.19/.91 |
| family-LOO | .49/.24/.85 | .73/.37/.93 | .50/.24/.92 | .61/.30/.83 | **.93/.69/.97** | .18/.20/.92 |

RandomForest is the best model and is used for claim gating. XGBoost is
unstable on leave-one-E3/family regimes (below chance) — reported, not hidden.

## Claims gating (evidence-based)
| claim | verdict | evidence |
|---|---|---|
| expression alone ranks E3s | **False** | AUROC 0.49 (chance) on every regime → hard rule enforced (never recommend from expression alone) |
| combined evidence model beats expression-only & recruiter-only | True | unseen-target RF .98 vs .49/.73; unseen-E3 .93 vs .49/.73 |
| recruiter availability is the dominant axis for never-seen E3s | True | −recruiter ablation on unseen-E3: AUROC −0.52 |
| precedent transfers across cell lines but not across targets/E3s | True | unseen-cell precedent .85/.78; unseen-target .50 |
| context/localization/selectivity add small incremental signal | True | −context −0.010 (unseen-target); −localization −0.002; −selectivity −0.003 |
| structure/lysine axes improve ranking on this dataset | **not testable** | 0 POI structures in retrospective rows → coverage census; validated only via unit tests on user-supplied structures |

## Ablation deltas (full RF minus dropped feature group; AUROC)
| drop | unseen-target | unseen-pair | unseen-E3 |
|---|---|---|---|
| −context | −0.010 | −0.006 | +0.013 |
| −localization | −0.002 | −0.000 | +0.015 |
| −recruiter | −0.102 | −0.127 | **−0.517** |
| −precedent | +0.002 | +0.003 | +0.035 |
| −selectivity | −0.003 | −0.001 | +0.037 |

## Product behaviour checks
- BRD4/K562 → VHL + CRBN **SUPPORTED** (direct precedent 44/33 rows) ranked
  above recruiter-only PROMISING novel E3s; expression-only novel E3s are
  EXPLORATORY (never suitable-by-expression).
- Unknown POI → graceful INSUFFICIENT EVIDENCE (empty candidate list).
- Missing cell context → context axis None + uncertainty flags; no fabricated
  score. Structural feasibility is None for every candidate without ternary
  data; lysine axis needs a supplied POI structure.
