# PROTACXtend Scientific-Agent Benchmark (Sprint 2 — specification & skeleton)

**Status: SPECIFICATION ONLY — no benchmark experiments have been run.**
Do not execute Biomni, AI Co-Scientist-compatible workflows, PROTACXtend, or
any LLM benchmark runs until this framework is approved and runners exist.

The framework organises scientific-agent evaluation around the governed
contract **KNOW → REASON → DESIGN → DISCOVER**.

## Layout

```
benchmark/
├── README.md                 this overview
├── BENCHMARK_PROTOCOL.md     full protocol: task records, systems, matrix, execution
├── BLINDNESS_RULES.md        leakage & contamination prevention (binding)
├── TASK_SCHEMA.json          canonical per-task record schema
├── RESULT_SCHEMA.json        benchmark result envelope (anchored to result schema 1.0.0)
├── SCORING_RUBRIC.md         scoring dimensions, weights, aggregation
├── BASELINES.md              benchmark systems & control policy
├── benchmark_manifest.csv    task registry (~48 tasks, 12 per capability)
├── cases/                    one record file per task (JSON, TASK_SCHEMA.json)
├── ground_truth/             objective/measured ground truth with citations (no predictions)
├── runners/                  per-system adapter stubs (to be implemented; none run yet)
├── scoring/                  scoring implementation stubs + verified score records
├── manifests/                auto-discovered tools/agents/workflows (Sprint-1 infra)
├── configs/                  per-run configuration
├── outputs/                  raw run outputs (git-ignored at run time)
└── reports/                  human + machine reports
```

## Benchmark systems

- **PROTACXtend** (candidate system under evaluation)
- **Biomni**
- **AI Co-Scientist-compatible workflow**
- **Base LLM control** — same model/provider as the candidate where technically possible
- **DeepSeek Flash control**
- **Local Ollama control** where appropriate

## Balanced task matrix (objective ground truth wherever possible)

| Capability | Tasks | Ground-truth style |
|---|---|---|
| KNOW (retrieval/evidence) | 12 | objective (citation/existence checks) |
| REASON (mechanistic reasoning) | 12 | semi-objective (modeled, expert-audited) |
| DESIGN (generation/ranking) | 12 | objective rules + expert review |
| DISCOVER (prioritise/uncertainty/actionability) | 12 | expert + experimental actionability |

Total: **48 tasks** (within the 40–60 target; 10–15 per capability).

## Binding constraints

- The existing **six-BRD4/VHL workflow stays a controlled blinded case study
  outside the main benchmark** (see `protacxtend/case_study/`); its measured
  potency is never used during inference (see `BLINDNESS_RULES.md`).
- Sprint-1 code, result schema **1.0.0**, website, and scientific modules are
  **not modified** by this framework.

Read `BENCHMARK_PROTOCOL.md` first, then `BLINDNESS_RULES.md`,
`SCORING_RUBRIC.md`, and `BASELINES.md`.
