# Sprint 2 — Benchmark-Design Audit

Scope: scientific-agent benchmark **specification + skeleton only**. No
Biomni, AI Co-Scientist-compatible, PROTACXtend, or LLM benchmark runs were
executed. Sprint-1 code, result schema 1.0.0, website, and scientific
modules were not modified.

## Deliverables

| Item | State |
|---|---|
| benchmark/README.md | READY |
| benchmark/BENCHMARK_PROTOCOL.md | READY |
| benchmark/BLINDNESS_RULES.md | READY |
| benchmark/TASK_SCHEMA.json | READY |
| benchmark/RESULT_SCHEMA.json | READY (anchored to base schema 1.0.0) |
| benchmark/SCORING_RUBRIC.md | READY |
| benchmark/BASELINES.md | READY |
| benchmark/benchmark_manifest.csv | READY (48 tasks: KNOW 12 · REASON 12 · DESIGN 12 · DISCOVER 12; 24 objective-GT) |
| benchmark/cases/ | PARTIAL — directory + template present; per-task records pending |
| benchmark/ground_truth/ | PARTIAL — directory + policy; entries pending with citations |
| benchmark/runners/ | MISSING — adapter stubs only (intentionally not implemented in Sprint 2) |
| benchmark/scoring/ | MISSING — rubric defined, implementation deferred to approved runs |

## Systems defined

PROTACXtend · Biomni · AI Co-Scientist-compatible · Base LLM control
(same model/provider where possible) · DeepSeek Flash control · Local
Ollama control where appropriate. Identity/cost fields required per run.

## Per-task record fields

All mandated fields are covered by TASK_SCHEMA.json + manifest:
task_id · capability · scientific_question · supplied_inputs ·
hidden_information · permitted tools/databases · forbidden_information ·
expected_answer/ground_truth_ref · evidence_sources · automatic_scoring ·
expert_review · failure_criteria · runtime · token/API cost · tool_calls ·
provider/model/version · seed/repeat.

## Scoring dimensions

factual correctness · evidence/citation correctness · mechanistic
reasoning · design quality · experimental actionability ·
hallucination/error rate · uncertainty calibration · task completion ·
efficiency/cost — with per-capability weights and PASS/CONDITIONAL/FAIL
verdicts.

## Leakage / contamination

Binding BLINDNESS_RULES.md (blinded inputs, answer contamination, lock
before outcome, six-BRD4 case study excluded from the main benchmark, no
measured potency during inference, audit trail).

## Overall Sprint-2 readiness

| Aspect | State |
|---|---|
| Protocol + blindness + rubric + schemas + baselines | READY |
| Balanced 48-task registry (matrix) | READY |
| Case/ground-truth authoring | PARTIAL (next step after approval) |
| Runner & scoring implementation | MISSING (blocked by design approval; no runs until then) |
