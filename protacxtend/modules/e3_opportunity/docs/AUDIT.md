# AUDIT — Module 6 (Novel E3 Ligase Opportunity Engine) status report

Independent audit under the sequential-module rule (this report gates Module 7).
Audit date: 2026-09-03 · Auditor: lead-dev workspace · Verdict: **APPROVED**
(retrospective-validated; prospective validation stays open — see conditions).

## Checks performed

| # | Check | Evidence | Result |
|---|---|---|---|
| 1 | Code presence & entry points | `rank_e3_ligases()` / `evaluate_e3_ligandability()` (module `rank.py`/`predict.py`); verdict set `SUPPORTED/PROMISING/EXPLORATORY/INSUFFICIENT EVIDENCE` (rank.py:37) | ✅ |
| 2 | Catalog integrity | `data/e3_catalog.csv` = 30 genes × (family, mode, UniProt, adaptors, structure facts, resistance) — 30 rows re-measured | ✅ |
| 3 | Evidence axes (8) | cell-context expression (Module-5 DepMap reuse) · UniProt localization (78-gene cache) · recruiter tractability (DOI-cited) · biological precedent · structural availability · surface lysines (structures only) · selectivity · uncertainty/OOD | ✅ in code + SPEC |
| 4 | Anti-overclaim rules in code | `LOW_EXPRESSION_CAP = 0.2` caps verdicts (rank.py:38,145); expression-only never SUPPORTED (test `test_expression_alone_never_supported`); SUPPORTED requires direct precedent (rank.py:177) | ✅ |
| 5 | Missing evidence → UNKNOWN, never fabricated | structure/lysine/context paths return explicit None/UNKNOWN/OOD (tests `test_structure_unknown_*`, `test_missing_context_is_uncertainty_not_fabrication`) | ✅ |
| 6 | Test suite | `pytest protacxtend/modules/e3_opportunity/tests` → **17/17 passed** (2026-09-03 re-run; catalog, precedent, expression-cap, cell-dependence, determinism, ranking) | ✅ |
| 7 | Benchmark artifact | `artifacts/benchmark_results.json` — grouped regimes (random / unseen-E3 / unseen-cell), models incl. expression_only & recruiter_only ablations, AUROC/AP/hit@3/MRR per regime | ✅ reproducible artifact |
| 8 | Stated metrics trace | "RF AUROC .98 (easy) → .93 unseen-E3; recruiter ablation −0.52" traced to benchmark_results.json + VALIDATION.md | ✅ |
| 9 | Claim register discipline | `docs/CLAIMS.md` splits SUPPORTED vs NOT-YET-SUPPORTED, each tagged to evidence; reviewed 2026-09-03 | ✅ |
| 10 | Agent tool | `run_e3_opportunity` (`tools/e3_opportunity_tool.py`): tool_spec + graph-safe wrapper (never raises) | ✅ |
| 11 | Docs | README/SPEC/VALIDATION/LIMITATIONS/REFERENCES present and consistent | ✅ |
| 12 | Config alignment | `config/scientific_status.yaml` → implemented: true (was false); public claim follows this audit | ✅ (updated) |

## Findings

1. **Approved with conditions (no code fixes required):** benchmark negatives are
   curated absence-of-record rows — a **prospective set** (newly reported POI–E3
   degraders vs predictions) remains the definitive test of SUPPORTED/PROMISING
   calibration (tracked, `FOLLOW_UP_TASKS.md` #8). Do not publish prospective
   performance claims until that set is scored.
2. **Catalog scope is 30 genes, not 600+** — the engine ranks within the curated
   catalog; it does NOT claim ligand design for the other E3s (Module-8/de-novo
   track is out of scope here).
3. Per-verdict claims remain governed by `docs/CLAIMS.md`; this audit approves the
   engine + methodology + honesty infrastructure, not hypothetical future
   degraders.

## Verdict

APPROVED 2026-09-03 (17/17 tests, benchmark artifact + register verified).
Module-7 start gate closed. Config: `novel_e3_engine.status: PARTIAL` (retro
validated, prospective open), `implemented: true`, `public_claim: true`.
