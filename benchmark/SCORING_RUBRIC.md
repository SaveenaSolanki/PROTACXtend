# Scoring Rubric

Scores are normalised **0.0–1.0** per dimension. Aggregate = weighted sum.
Weight defaults per capability are below; they may be overridden only in a
locked task config, never per-run.

## Dimensions

| Dimension | What is measured | Automatic (A) / Expert (E) |
|---|---|---|
| factual correctness | claims match supplied inputs + permitted sources | A (+E conflict review) |
| evidence/citation correctness | citations resolve, support the claim, provenance recorded | A (format/resolution) + E (relevance) |
| mechanistic reasoning | causal chain (target–warhead–E3–linker–ternary–ubiquitination) valid | E (rubric per capability) |
| design quality | constraints met (chemistry validity, dose logic, scaffold sense) | A (rules) + E (novelty/feasibility) |
| experimental actionability | recommendation is specific, controlled, measurable | E |
| hallucination/error rate | fabricated numbers, fake citations, unsupported statements / total claims | A |
| uncertainty calibration | stated confidence vs correctness across a task (or its repeats) | A (ECE-style) + E |
| task completion | requested deliverable produced, spec-compliant | A |
| efficiency/cost | runtime + tool calls + tokens per acceptable answer | A (per system cost ledger) |

## Default weights (rows sum to 1.0)

| Dimension | KNOW | REASON | DESIGN | DISCOVER |
|---|---|---|---|---|
| factual correctness | 0.25 | 0.10 | 0.05 | 0.10 |
| evidence/citation correctness | 0.25 | 0.10 | 0.05 | 0.10 |
| mechanistic reasoning | 0.10 | 0.35 | 0.15 | 0.15 |
| design quality | 0.00 | 0.10 | 0.35 | 0.10 |
| experimental actionability | 0.00 | 0.05 | 0.10 | 0.25 |
| hallucination/error rate | 0.15 | 0.10 | 0.10 | 0.10 |
| uncertainty calibration | 0.05 | 0.10 | 0.05 | 0.10 |
| task completion | 0.10 | 0.10 | 0.10 | 0.05 |
| efficiency/cost | 0.10 | 0.00 | 0.05 | 0.05 |

## Failure criteria

Any of the following marks the task **FAIL** regardless of score:

- fabricated experimental result presented as measured;
- fake/uncited citation used as the primary support;
- use of forbidden information or hidden ground truth (blindness breach);
- refusal to separate measured / retrieved / calculated / predicted / missing;
- deliverable missing or schema-invalid result envelope.

## Aggregation & verdict

- `aggregate = Σ w_i · score_i` (0–1)
- **PASS** ≥ 0.75 and no failure criterion triggered
- **CONDITIONAL** 0.50–0.74 or expert-flagged uncertainty
- **FAIL** < 0.50 or any failure criterion triggered

## Blinding in scoring

Automatic scores are computed before expert review; experts see only the
task + system output, never other systems' answers or ground-truth-derived
rankings, until all expert fields for the batch are recorded.
