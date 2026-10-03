# Gate-C four-system pilot — execution report

Run: `benchmark_results/gateC_four_system/gateC_4sys_v1`
Date: 2026-10-03 · Repo `sprint-2` · Execution mode: SCIENTIFIC · online retrieval: yes

> **This is execution/validation evidence, not a correctness or superiority result.**
> Eligible gold is `PENDING_INDEPENDENT_REVIEW` (0/48), so no accuracy, ranking or
> "better than Biomni" claim is made here.

## Systems

| ID | System | Implementation | Resource condition |
|---|---|---|---|
| S1 | LLM+RAG | `benchmark_runner.live_systems.RetrievalRAGLiveAdapter`; scientific retrieval connectors only, no domain/design tools | retrieval-matched lens on S3's sources |
| S2 | LLM+flat-tools | `benchmark_runner.live_systems.LLMFlatToolsLiveAdapter`; LLM calls the same ready tool catalog through a flat JSON interface, ≤3 rounds, no orchestration/evidence gating | **partially** tool-matched (some observations empty in SCIENTIFIC mode) |
| S3 | PROTACXtend | `benchmark_runner.live.PROTACXtendLiveAdapter`; full agent graph + evidence gates + typed abstention | native |
| S4 | Biomni | `benchmark_runner.live_systems.BiomniLiveAdapter` → official `biomni 0.0.8` (`/tmp/biomni_venv`), same DeepSeek model | **native (NOT resource-matched)** |

Fairness: same model/provider (`deepseek-v4-flash`, temperature 0, `thinking=disabled`,
24k cap) and the same blinded task text for S1–S4. Biomni uses its own tools/data-lake;
that difference is declared, not assumed away. Common result contract (system, task,
replicate, version, timestamps, output, evidence, tool trace, typed abstention, infra
error, latency, tokens, cost) is in `task_level_results.parquet` / `.csv`.

## Observed counts (16/16 intended runs executed)

| system | n | answered | abstained | errored | timed_out | unavailable | cost USD | mean latency s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| S1 LLM+RAG | 4 | 4 | 0 | 0 | 0 | 0 | 0.001703 | 12.3 |
| S2 LLM+flat-tools | 4 | 4 | 0 | 0 | 0 | 0 | 0.002575 | 6.3 |
| S3 PROTACXtend | 4 | 1 | 3 | 0 | 0 | 0 | 0.002415 | 1.1 |
| S4 Biomni | 4 | 3 | 1 | 0 | 0 | 0 | **not reported** | 171.1 |

- 0 infrastructure errors, 0 timeouts; every run executed on the first attempt.
- S4 cost is **not reported** by the installed Biomni adapter → recorded as unavailable,
  not zero.
- S4 tool-call counts are transcript-derived (6–25) after correcting an initial
  transcript-length bug.

## Objective pipeline-integrity checks (not correctness)

| Check | Result |
|---|---|
| REASON-02 declared `typed_abstention_MISSING_SCIENTIFIC_INPUT` | **S3 abstained (met)**; S1, S2, S4 answered (not met) |
| KNOW-01 declared `resolved_reviewed_human_accession` (O60885) | **S1, S2, S3, S4 all met** |

Interpretation (execution evidence only): on the one case whose expected behaviour is a
typed abstention, only the orchestrated agent abstained; the LLM-only variants produced
an answer. This is consistent with — but does not prove — the abstention-honesty
hypothesis. Four cases are not a powered comparison.

## Source-backed design repair (independent of Gate-C)

- Root cause: `CAPABILITY_NODES["DESIGN"]` omitted `design_path`, so `/design` never
  assembled the verified reference and the identity gate correctly rejected all
  demo-provenance candidates (0/144).
- Fix: add `design_path` to the deterministic DESIGN route (`protacxtend/agents/graph.py`).
- Result (real `/design` run, `outputs/execution/design_evidence/`): verified reference
  **MZ1** (BRD4–VHL; DOI 10.1021/acschembio.5b00216; PDB 5T35) assembled; identity gate
  **30/30 pass**; **30 degradation predictions**; `ternary_coordinates` and
  `synthesis_route` remain explicitly `unevaluated`. The regression test
  `tests/test_tui_slice_routing.py::test_execute_design_runs_existing_engine_with_honest_gates`
  passes.
- This is a **reconstruction control** validating the pipeline, not a novel design and
  not biological activity.

## What this run does NOT establish

- Correctness/accuracy or superiority of any system (gold pending; 4 cases).
- Scientific validity of any molecular or mechanistic answer.
- That S2 was fully tool-matched to S3 (declared partial).
- That S4 was resource-matched to S1–S3 (declared native).
- Any temporal, leakage, fault-injection or reproducibility result.

## Prerequisite for the 30-question × 4-system pilot

The larger pilot remains **BLOCKED** on eligible gold (0/48 independently adjudicated)
and on S2 completeness. The exact launch command is prepared in
`outputs/execution/REPRODUCE.md`; it must not be run until those gates pass.
