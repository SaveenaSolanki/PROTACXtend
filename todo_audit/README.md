# PROTACXtend `todo/` closure audit

**Date:** 2026-09-23
**Auditor:** automated repository audit (agent session)
**Scope:** the five markdown files in `todo/` —
`PROTACXtend_00_STATUS_AND_CLOSURE.md`, `_01_EXPERIMENTS.md`, `_02_TOOLKIT_DEPTH.md`,
`_03_AGENT_PROMPTS.md`, `_04_CHECKLIST.md` — audited **against the live repository**,
not against the reports they describe.

This folder is the "proper audit file/folder" requested. Every claim below is
linked to a code path, a command, and a captured artifact under `evidence/`.
No task is marked done from prose; only from a reproduced run.

---

## Method

1. **Reconcile** — record `git rev-parse HEAD`, `git status`, environment
   (`evidence/git_state.txt`).
2. **Re-run every command named in `TODO.md` / `todo/`** and capture stdout.
3. **Probe the guardrails** the todo files claim exist (scientific mode,
   fixture refusal, parser gate, scoring engine) directly, including negative
   cases.
4. **Compare claims to artifacts** in `benchmark/`, `benchmark_results/`,
   `outputs/strategies/`, `protacxtend/toolkit/`.
5. Record the result as `verified`, `partial`, `failed`, or `absent` and
   attach the exact command.

## Status legend

| status | meaning |
|---|---|
| `verified` | reproduced in this workspace from the stated command; artifact captured |
| `partial` | exists but only satisfies part of the claim (e.g. declares, does not execute) |
| `failed` | reproduced a result that contradicts the claim |
| `absent` | claimed capability/artifact does not exist |
| `open` | not run in this session (needs network/data/expert), reason stated |

## Files

| file | content |
|---|---|
| `FINDINGS.md` | consolidated, severity-ranked findings F-01…F-16 |
| `QUESTIONS.md` | every question this audit asks, grouped by owner |
| `00_STATUS_AND_CLOSURE.md` | audit of the closure map + evidence ladder |
| `01_EXPERIMENTS.md` | E1–E8 readiness audit |
| `02_TOOLKIT_DEPTH.md` | tool registry / provenance / critic audit |
| `03_AGENT_PROMPTS.md` | audit of each copy-ready prompt's executability |
| `04_CHECKLIST.md` | the checklist with verified boxes and evidence |
| `05_BENCHMARK_AUDIT_AND_NEXT_STEPS.md` | audit of `todo/_05`; gates A–E status |
| `06_BENCHMARK_500.md` | audit + execution of the two 500-task workbooks |
| `gateA/` | **executed**: archive, rename inspection, cross-route matrix (`_05` Gate A) |
| `gateB/` | **executed**: scientific-mode + protein-identity repair + traces (`_05` Gate B) |
| `csv/claim_reconciliation.csv` | claim → code path → artifact → status |
| `evidence/` | raw captured outputs |
| `verify.sh` | one-shot reproducible re-run of the fast checks |

## Reproduce

```bash
cd /storage/saveena/protacxtend
bash todo_audit/verify.sh          # fast, offline, writes todo_audit/evidence/
```

## Headline

**500-task benchmark built and executed (2026-09-23):** both `todo/*.xlsx`
workbooks (temporal 500 + general 500 = **1000 tasks**) are ingested, validated,
hashed and split; the full set was executed in SCIENTIFIC mode
(476 executed with traceable evidence, 524 typed abstentions, 0 fabricated
scores). See `benchmark500/` and `todo_audit/06_BENCHMARK_500.md`. Gold for all
1000 tasks is **uncurated in the source workbooks**, so scientific-correctness
dimensions are delivered blank and `pending_adjudication` — not invented.

**Remediation status (2026-09-23):** Gates A and B of
`todo/PROTACXtend_05_BENCHMARK_AUDIT_AND_NEXT_STEPS.md` have been executed.
F-03 (scientific mode), F-04 (BRD4 identity), F-15 (install) and F-16 (pytest)
are fixed with regression tests; see `gateA/README.md` and `gateB/README.md`.
The full 48-task run and the `0.885` self-grade remain blocked on Gate C and
are **not** presented as therapeutic performance.

The original audit found the infrastructure real and mostly tested, but the
two claims that mattered most for publication were not yet true (now fixed):

1. **The 48-task pilot was not executed** — only KNOW-01 ran for real, and it
   *scored 0.0*. The 48/48 `mean=0.885` figure is *offline self-grading* of
   authored answers against criteria auto-derived from those same answers.
2. **SCIENTIFIC mode was not enforced on the canonical path** — it is now;
   scientific and demo no longer produce identical output, and BRD4 resolves to
   the reviewed `O60885`.
