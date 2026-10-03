# Matched-case adjudication — closed BRD4 × CRBN vertical slice

Date: 2026-09-25 · Script: `tui_dev/scripts/adjudicate_slice.py` (reproducible)
· Raw data: `adjudication.json`, `answers.jsonl`

## Status
- **Gold remains PENDING_HUMAN_ADJUDICATION.** Every score below is a
  **provisional machinery overlay** (LLM-free grader, frozen ground truth);
  no case is claimed signed or expert-approved. Rubric cases are additionally
  marked `requires_expert_review` by the grader itself.
- Protocol: frozen B1 protocol — abstentions excluded from means; machines
  never score abstained cases; ranked-floor pathology checked (empty-answer
  baselines are all 0.0 here, so no ranked floor inflates the result).

## Matched set and outcome

| Case | Capability | Slice surface (real execution) | Status | Machine score | What the engine actually produced |
|---|---|---|---|---|---|
| KNOW-01 | KNOW | `/investigate BRD4` + target card | attempted | **0.5** (checklist) | O60885 ✓; BD1/BD2 architecture NOT emitted → half |
| KNOW-07 | KNOW | target card (`chat BRD4`) | attempted | **0.0** | Card lists 5T35 among structures, but machinery requires the ternary identification (BD2–MZ1–VHL); registered: registry `retrieve_pdb(BRD4,VHL)` misses 5T35 in 24 keyword hits |
| KNOW-09 | KNOW | `/validate` + independent RDKit | attempted | **1.0** | Canonical SMILES, InChIKey RZVAJINKPMORJF-UHFFFAOYSA-N, MW 151.16, C8H9NO2 — all verified |
| KNOW-10 | KNOW | cell_context_atlas (shipped data) | attempted | **0.33** | MM1.S/DEFAULT BRD4×CRBN rows present but sourced `local_seed_prior` (not a permitted quantitative source) → engine says verify; partial credit |
| DISCOVER-06 | DISCOVER | cell_context_atlas + rationale | attempted | **0.0** rubric | Recommends MM1.S with expression rationale + verification caveat; rubric requires expert review |
| DESIGN-04 | DESIGN | real design engine (both-E3 request) | attempted | **0.0** rubric | Engine ran; scored candidates used **CRBN-only** ligands (panel requirement not met) → 0.0; expert review marked |
| KNOW-02 | KNOW | — | **abstained** | — | No source-backed BRD4 warhead identifiers (curated file: `BRD4_demo_JQ1_like`, source=`local_demo_jq1_like_warhead`) |
| KNOW-04 | KNOW | — | **abstained** | — | Counts exist (CRBN 26/VHL 32/FEM1B 7) but no degrader names+citations; protacdb_local rows are DEMO |
| KNOW-05 | KNOW | — | **abstained** | — | `select_e3_ligase` returns demo-named ligands with empty `article_doi` |
| REASON-09 | REASON | — | **abstained** | — | `score_lysine_ubiquitination` requires a supplied ternary pose (verified WARNING) |
| DISCOVER-01/04/08/11 | DISCOVER | — | **abstained** | — | Need case-supplied candidate tables; slice handlers accept free text |
| DESIGN-02 | DESIGN | — | **abstained** | — | Supplied-component inputs not consumed by the slice design surface |

## Aggregate (machinery, provisional)
- attempted n = 6; abstained n = 9
- mean score = **0.306**; correct (≥0.5) = **2/6**
- Wilson 95% CI (z=1.96) = **[0.097, 0.70]**
- empty-answer baselines: all 0.0 (no floor inflation)

## What this adjudication is and is not
- IS: real execution through the slice's actual handlers; machine grading
  against frozen GT; per-case abstention with recorded evidence; CI on the
  attempted set; registered findings for the engine's real gaps.
- IS NOT: a claim that the slice "passes" any case; expert sign-off;
  benchmark accuracy. Rubric cases await blind expert review; gold status
  column = `AWAITING_EXPERT_REVIEW` (48/48 unchanged).

## Registered findings (data gaps the slice surfaced, with evidence)
1. `retrieve_pdb(target=BRD4, e3=VHL)` → 24 RCSB keyword hits, **no 5T35**
   — the structural retrieval surface misses the canonical MZ1 ternary.
2. `curated_warheads.csv`: BRD4 rows are demo-named only (no resolvable DB ids).
3. `select_e3_ligase` ranks `CRBN_demo_*`/`VHL_demo_*` above DOI-backed
   pomalidomide/VH032 because demo rows carry higher `exit_vector_confidence`
   — a ranking-quality defect, evidence in `adjudication.json` + e3 CSV.
4. Target card (curated_table) does list O60885, 2OSS/3MXF/5T35 — unmatched by
   the registry tool (finding 1) — two surfaces disagree on structure lookup.
5. `cell_context_atlas.csv` = `local_seed_prior` rows only (3 rows) — not a
   permitted per-line quantitative source.

## Reproduction
```
python tui_dev/scripts/adjudicate_slice.py
```
(≈2 min; includes one real design run for DESIGN-04.)