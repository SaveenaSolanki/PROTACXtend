# Task Ledger — 2026-09-02 pass (FINAL)

## Goal
(a) fix v0.1 deterministic e2e hang
(b) G6 full experiment reproduction for PROTAC-Degradation-Predictor
(c) rebuild TACK + synglue degradation artifacts in runtime sklearn

## Status — ALL DONE (2026-09-02 ~11:00)

| Task | Status | Evidence |
|------|--------|----------|
| a: reproduce hang | DONE | node stepper: hang in predict_degradation node |
| a: root-cause | DONE | 3 stacked causes: (1) TACK HGB OpenMP spin ~11s/model at load>40 → ~33s/mol (112-thread futex sig); (2) rank O(N×C) InChIKey via protacdb_evidence_prior linear scan; (3) one-time 22-26s xlsx parse (acceptable) |
| a: fix | DONE | thread_limits.py + runtime entry + tack predict bounded(1); _protacdb_exact_index O(1). TACK cold 33s→1.1s warm 11s→10ms; rank 150 cands ~9min→0.87s |
| a: verify e2e | DONE | e2e_final_20260902: run_end 196s status ok (was >50min hang) |
| b: G6 reproduction | DONE | seed-42 standard split; XGBoost force-retrain; test acc 81.6% / AUC 0.900 (maj vote) vs paper 80.8%/0.865 (arXiv 2406.02637) |
| c: TACK rebuild | DONE | sklearn 1.9.0 rebuild (rho 0.800/0.738; bin 0.846/0.917); no version warnings |
| c: synglue rebuild | DONE (honest partial) | RF legs unloadable on sklearn≥1.4 (dtype); training data absent; targeted warning suppression; transformer backend; 17 tests no warnings |
| final: test sweep | DONE | endpoint 15, protacdb+contract 13, repo/prod wiring 26, synglue 17, pareto 7 — green |

## Key numbers
- TACK predict: 33s → 1.1s cold; 11s → 0.010s warm
- rank_candidates 150: ~540s+ → 0.87s
- e2e deterministic: >50min hang → 196s
- G6: paper 80.8%/0.865 → reproduced 81.6%/0.900 (XGBoost maj-vote)

## Files changed (2026-09-02)
- synglue_agent/tools/thread_limits.py (new)
- synglue_agent/tools/tack_degradation.py (env defaults + bounded predict)
- synglue_agent/agents/runtime.py (apply_thread_limits at entry)
- synglue_agent/tools/protac_toolbox.py (_protacdb_exact_index; rank path)
- synglue_agent/tools/synglue_degradation.py (warning suppression + docstring)
- notes/debug_v01_stages.py, notes/time_degradation_batch.py, notes/time_post_degradation.py (debug tools)
- Repo data/studies + reports (G6); repo models/ dir; data/tack/* rebuilt
- CHANGELOG.md, outputs/DEGRADATION_BACKEND_REPAIR_AND_GATE_AUDIT.md