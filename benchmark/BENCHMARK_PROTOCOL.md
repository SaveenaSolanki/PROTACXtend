# PROTACXtend Scientific-Agent Benchmark — Protocol

Status: **specification (Sprint 2)** · no runs yet.

## 1. Objective

Evaluate scientific agents on evidence-grounded targeted-protein-degradation
tasks across the governed contract **KNOW → REASON → DESIGN → DISCOVER**,
with explicit blindness rules, objective ground truth wherever possible, and
separate automatic + expert scoring.

## 2. Task registry

`benchmark_manifest.csv` registers every task. One full record per task is
stored under `cases/` as JSON conforming to `TASK_SCHEMA.json`. Ground truth
lives under `ground_truth/` with citations; prospective case-study inputs are
never promoted to ground truth.

### Per-task record (every task must record)

| Field group | Fields |
|---|---|
| identity | `task_id`, `capability` (KNOW/REASON/DESIGN/DISCOVER), title |
| question | `scientific_question`, `supplied_inputs`, `hidden_information` |
| constraints | `permitted_tools_databases`, `forbidden_information` |
| answer | `expected_answer`, `ground_truth_ref`, `evidence_sources` |
| scoring | `automatic_scoring_fields`, `expert_review_fields`, `failure_criteria` |
| budget | `runtime`, `token_cost`, `api_cost`, `tool_calls`, `provider_model_version`, `seed`, `repeat` |

## 3. Balanced matrix (48 tasks = 12 × 4 capabilities)

See `benchmark_manifest.csv`. Distribution target: 10–15 per capability,
40–60 total. Objective ground truth is used wherever the task admits it
(KNOW fact/citation checks, deterministic chemistry facts, rule-based design
constraints); mechanistic and design reasoning tasks pair deterministic
checks with expert review.

## 4. Execution lifecycle (after runners are approved — not yet)

1. **Prepare** — select task + system; load blinded inputs; lock task file.
2. **Run** — system executes with permitted tools only; record provider/model,
   seed, repeat, tool calls, tokens, wall time, cost estimate.
3. **Result** — produce a benchmark result envelope per `RESULT_SCHEMA.json`
   (anchored to result schema 1.0.0) + readable CLI summary.
4. **Score** — automatic dimensions from rubric; then expert review on
   expert-only fields while automatic scores are hidden.
5. **Audit** — blindness log, leakage scan, cost ledger, verdict.

## 5. Scoring dimensions (see `SCORING_RUBRIC.md`)

factual correctness · evidence/citation correctness · mechanistic reasoning ·
design quality · experimental actionability · hallucination/error rate ·
uncertainty calibration · task completion · efficiency/cost.

## 6. Systems (see `BASELINES.md`)

PROTACXtend · Biomni · AI Co-Scientist-compatible workflow · Base LLM control
(same model/provider where technically possible) · DeepSeek Flash control ·
Local Ollama control where appropriate.

## 7. Non-goals (Sprint 2)

No execution of Biomni, AI Co-Scientist-compatible workflow, PROTACXtend, or
any LLM benchmark run. No changes to Sprint-1 code, result schema 1.0.0,
website, or scientific modules.
