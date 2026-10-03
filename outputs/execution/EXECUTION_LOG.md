# Execution log — 2026-10-03

Concise record of what was actually run this pass. Exact reproduction in
`REPRODUCE.md`. No command below is invented; each was executed on this host.

## Discovery

- `find . -iname AGENTS.md` → none. `git branch --show-current` → `sprint-2`.
- Read `tpdeval/{systems,adapters}.py`, `benchmark_runner/{live,runner,baselines,adapters}.py`,
  `tpdeval/docs/03_VERDICT.md`, `study/03_EXPERIMENTAL_DESIGN.md`,
  `outputs/manuscript_strategy/tables/competitor_matrix.md`,
  `benchmark_results/reports/biomni_install_smoke.md`.
- Counted cases/gold/tools/backends/capabilities (§2–§4 of `current_state.md`).

## Gold-review infrastructure

1. `python3 scripts/gold_adjudication.py status` → 48 pending; consensus unapproved.
2. Found `reviewed_gold/kappa_report.json` claiming 48×`approve`, κ=1.0 while the
   workbooks had **0 filled verdicts** → stale synthetic artifact.
3. `python3 scripts/gold_adjudication.py kappa reviewer_1.csv reviewer_2.csv`
   → regenerated honestly: `n_filled_both=0`, kappa `null`.
4. `python3 scripts/gold_adjudication.py merge --dir benchmark/gateC/reviewed_gold`
   → `approved=false`, `unresolved=48`, `gold={}`.
5. Verified the three blind workbooks (`reviewer_1/2`, `adjudicator`) are empty and
   `gold_review.tsv` is 48×`PENDING_ADJUDICATION`. No gold manufactured.

## Source-backed design repair

6. Traced the 0/144 identity-gate failure to demo provenance
   (`curated_warheads.csv` = `local_demo_*`).
7. Found `protacxtend/tools/verified_components.py` + `verified_components.json`
   with 3 real references (MZ1/dBET1/MT-802) and confirmed in isolation that all 3
   pass the gate.
8. Root cause: `CAPABILITY_NODES["DESIGN"]` omitted `design_path` → verified node
   never scheduled. Added `design_path`.
9. `pytest tests/test_tui_slice_routing.py::test_execute_design_runs_existing_engine_with_honest_gates`
   → **1 passed** (was failing).
10. Real `/design` run: `30 valid / 30 identity-pass / 30 degradation predictions`,
    verified `SGA-VERIFIED-MZ1` (DC50 181.7 nM predicted). Evidence copied to
    `outputs/execution/design_evidence/`.

## Systems integration

11. New `benchmark_runner/live_systems.py` (S1/S2/S4) + `scripts/biomni_run.py`.
12. Smoke: S1 (retrieval → LLM) `status=ok`; S2 (flat tools + finalize) `status=ok`;
    Biomni answered O60885 in ~9.6 s.
13. Fixed `_guess_target` (supplied-inputs first), S2 finalization, adapter
    constructor convention (`cls(name, allow_real=...)`).

## Freeze

14. Wrote `study/freeze_manifest.json` (commit, tree, dirty hash, models, prompts,
    dataset/tool hashes, gold/rubric versions, budgets, seeds; no secrets).

## Gate-C four-system pilot

15. `python3 scripts/gateC_four_system.py --systems S1,S2,S3,S4 --online --run-id gateC_4sys_v1`
    → **16/16 runs executed**, 0 infra errors.
16. Corrected Biomni tool-call counting (transcript-derived) and regenerated
    `task_level_results.{parquet,csv}` + `summary.json` + `REPORT.md`.

## Validation

17. `pytest tests/test_source_backed_design_and_adapters.py protacxtend/tests/test_toolkit_status.py`
    → 14 passed.
18. `pytest tests/test_tpdeval.py` → updated honest integration-status assertions →
    29 passed (with the new test file).

## Observed results (execution evidence only)

| system | answered | abstained | errored | mean latency s |
|---|---:|---:|---:|---:|
| S1 LLM+RAG | 4 | 0 | 0 | 12.3 |
| S2 LLM+flat-tools | 4 | 0 | 0 | 6.3 |
| S3 PROTACXtend | 1 | 3 | 0 | 1.1 |
| S4 Biomni | 3 | 1 | 0 | 171.1 |

REASON-02 (declared missing input): only **S3** abstained. KNOW-01: all four met the
O60885 check. Correctness: **NOT SCORED** (gold pending).
