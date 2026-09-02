# Module 6 — Novel E3 Ligase Opportunity Engine: specification

`rank_e3_ligases(poi, cell_line=None, tissue=None, disease=None, warhead=None,
poi_structure=None, top_k=10)` — Module 6 of PROTACpilot.

## 1. Objective
Given a POI (gene symbol or name) and optional cell line / tissue / disease /
warhead / POI structure, rank candidate E3 ligases for PROTAC development and
return per-candidate evidence with a decision verdict:
**SUPPORTED | PROMISING | EXPLORATORY | INSUFFICIENT EVIDENCE**.

## 2. Scientific constraint (hard rule)
**A novel E3 is never recommended because it is highly expressed.** Expression
alone has no retrieval power in our benchmark (AUROC ≈ 0.49, at chance), so
every candidate needs ≥2 corroborating evidence axes and a chemical handle or
usage signal before it can be PROMISING; SUPPORTED additionally requires
direct measured precedent for that POI in the curated dataset.

## 3. Evidence axes (all data-gated; missing = UNKNOWN, never guessed)
| Axis | Data | Module |
|---|---|---|
| cell-context expression (E3 + adaptors + POI) | DepMap 24Q4 TPM-log1p percentiles | 5 infra + context.py |
| subcellular compatibility | UniProt (reviewed, cached offline) | localization.py |
| recruiter tractability | DOI-cited E3-ligand library (demo rows excluded) | recruiters.py |
| biological precedent | curated PROTAC-Degradation-DB rows | dataset.py/rank.py |
| structural availability / ternary feasibility | curated complex PDB facts; UNKNOWN otherwise | structure.py |
| lysine opportunity | provided POI structure only (Module-2 SASA) | lysines.py |
| selectivity opportunity | real lineage-expression restriction + curated paralog families | selectivity.py |
| uncertainty/OOD | per-axis flags, evidence gaps, warhead Tanimoto | uncertainty.py |

## 4. API surface
- `rank_e3_ligases(...)` → response with ranked `candidates` (each carrying
  the output columns of the spec: rank, e3_gene, e3_family, per-axis scores
  and confidences, recruiter availability, structural feasibility (None unless
  ternary data), lysine opportunity, selectivity, precedent, resistance risk,
  overall score/confidence, verdict, supporting_evidence, limitations,
  recommended_next_test).
- schemas: `E3OpportunityInput`, `RankResponse`, `CandidateResult`.
- agent tool: `run_e3_opportunity`.

## 5. Benchmark (retrospective known POI-E3 pairs)
Instances = real measured PROTAC rows (poi, cell, E3) as positives; negatives
= catalog E3s never used for that POI (absence-of-evidence, documented).
Regimes (all grouped, no leakage): random (pair-grouped), unseen-target,
unseen-E3, unseen-target-E3-pair, unseen-cell, leave-one-family-out.
Baselines: expression-only, recruiter-only, precedent-frequency, logistic,
RandomForest, XGBoost. Ablations drop context/localization/recruiter/
precedent/selectivity groups. Structure/lysine axes have no numeric instances
in this dataset → coverage census, not model comparison.
Claims gated by benchmark evidence (see VALIDATION.md).

## 6. Honesty rules encoded in tests
1 same POI, different cell lines → distinct context scores
2 same POI, VHL vs CRBN → both returned with real evidence
3 low-expression E3 → verdict capped, never SUPPORTED
4 missing cell context → uncertainty, not fabrication
5 no structure → no mechanistic/ternary claim (feasibility None)
6 absent recruiter → explicitly reported (None + limitation)
7 unknown POI → graceful INSUFFICIENT EVIDENCE
plus determinism and no-invented-value checks.
