# Server-agent final instruction — execution audit

Date 2026-09-24 · HEAD `82a0e4d` · deliverable `results/closure/`.

Instruction: `todo/PROTACXtend_SERVER_AGENT_FINAL_EXECUTION_PROMPT.md`.

## 0. Recon

* HEAD `82a0e4d1746b8b364b01ad823b16b64b727daefe` (branch `sprint-2`); worktree has
  24 modified + 58 untracked entries (all preserved; nothing reset/cleaned).
* Referenced paths: `benchmark/gateC/` present; `benchmark_results/closed48/` present
  (`closed48_locked`, `repaired_frozen`); `benchmark500/` present (archived, uncurated);
  `todo_audit/` present. **`AGENTS.md` absent.**
* Environment: Python 3.13.5, SCIENTIFIC mode, live DeepSeek key (verified call),
  no frozen pre-cutoff corpus, no wet-lab.

## 1. Freeze verification and 32-case reproduction

* Original `repaired_frozen/FREEZE_MANIFEST.json`: HEAD matches, but **2/5 module
  hashes mismatch** (`binder_agent.py`, `graph.py` edited 23:44 > freeze 23:38).
  → the reported frozen run no longer matches the tree, so it was **re-executed**.
* Re-run: `scripts/repair_closed48.py --out-dir benchmark_results/closed48/reproduced_current`.
  Result **casewise-identical**: repaired 25 completed / 7 abstained / 0 timeout;
  original 0 / 18 / 14. New freeze hashes 5/5 match.
* Original 32-subset counts computed from `closed48_locked` predictions: 0 complete /
  18 abstain / 14 timeout. Casewise pair IDs identical.

## 2. Results

| study | status | evidence |
|---|---|---|
| E1 | result complete (execution/provenance only) | `results/closure/e1_tool_matrix.csv` (+`_online`), `e1_raw_traces.jsonl`, `e1_proportions.json`, `e1_registry_reconciliation.json`, `e1_exclusions.csv` |
| E2 | engineering result only (gold pending) | `case_level.csv`, `e2_e3_analysis.json`, `fig3_e2_paired_outcomes.png/pdf` |
| E3 | engineering result only | `e2_e3_analysis.json`, `dev_gap_repaired.json`, `fig4_e3_recovery.png/pdf` |
| E4 | data ready (reviewer packet) | `e4_reviewer_packet.csv`, `e4_e5_status.json` |
| E5 | data ready + objective tiers | `e5_evidence_records.csv`, `BRD4_VHL_NO_GO.md`, `fig5_e4_e5_evidence_tiers.png/pdf` |
| E6 | engineering result only (guard ablation) | `e6_ablation_guard.json`, `fig6_e6_ablation.png/pdf` |
| E7 | not evaluated (protocol) | `E7_TEMPORAL_PROTOCOL.md` |
| E8 | not experimentally validated (computational panel) | `E8_COMPUTATIONAL_PANEL.md` |

Reports: `results/closure/RESULTS_E1_E8.md`, `CLAIM_EVIDENCE_MATRIX.md`, `CURRENT_STATE.md`.

## 3. Headline numbers

* E1 adapters: real-input execution 34/34; domain-valid 33/34 offline · 32/34 online;
  typed negative 31/34.
* E2/E3 arms on the same 48 IDs: original agent 0 complete / 26 abstain / 22 timeout;
  repaired 28 complete / 18 abstain / 0 timeout (46 cases run); direct_tool 45 complete;
  fixed_workflow 48 partial; retrieval-only 25/23; tool-only 44/4; Base-LLM 48/0.
* E3 gap: 45 direct-vs-agent gaps; repaired 27 closed by completion, 18 typed
  abstention, 0 open.
* **The full agent does NOT beat direct tools on completion (28 vs 45/48).**

## 4. Scientific scores

**None.** Gold 0/48; only execution outcomes computed. Rubric scores against authored
ground truth are flagged non-independent. Measured DC50 labels 0/233.

## 5. Blockers

* **Annotation (human):** 48 gold adjudications + 29 reviewer decisions; E4 two blinded
  experts.
* **Engineering:** frozen as-of corpus + time-pinned tools (E7); fault-injection
  harness (E3); ablation switches on the structured path (E6); source-backed warhead
  with validated exit vector (E5).
* **Experiments (wet lab):** E8 dose/time, proteasome/E3 dependence, selectivity, controls.

## 6. Reproduce

```bash
python scripts/repair_closed48.py --workers 8 --out-dir benchmark_results/closed48/reproduced_current
python scripts/e1_tool_matrix.py --tag e1_offline
python scripts/e1_tool_matrix.py --online --tag e1_online
python scripts/run_dev_gap_cases.py --cases DESIGN-01,DESIGN-06,DESIGN-08,DESIGN-11,DESIGN-12,KNOW-04,KNOW-11,REASON-03,REASON-05,REASON-06,REASON-08,REASON-09,REASON-10,REASON-12
python scripts/assemble_closure_results.py
python scripts/e4_e5_evidence.py
python scripts/e6_ablation_guard.py
python -m pytest tests/test_figure_quality.py -q
```
