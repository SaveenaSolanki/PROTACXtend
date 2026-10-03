# Audit of `todo/PROTACXtend_03_AGENT_PROMPTS.md`

`_03` is a list of copy-ready prompts for a repository agent. This file reports
what happened when each prompt was **actually executed** against this tree, and
whether it can complete today.

Date 2026-09-23 · HEAD `0abbe83`.

## P0 — Reconcile the universal tracker and pilot

| instruction | outcome |
|---|---|
| Read `AGENTS.md`, universal tracker, `TODO.md`, `CODEBASE_STATE.md`, `P0B_FIXTURE_AUDIT.md` | `AGENTS.md` and a `universal*.md` tracker **do not exist** in this tree. `TODO.md`, `CODEBASE_STATE.md`, `P0B_FIXTURE_AUDIT.md` exist. |
| Cross-check the three report claims vs HEAD, table with claim/code/artifact/status | done → `csv/claim_reconciliation.csv` |
| Inspect 48/50 manifests + scorer | done — 48 cases, 48 GT, 29 expert-review, grader works |
| Have experts adjudicate flagged gold | **cannot** — no reviewers / no adjudication artifact |
| Select matching KNOW/REASON/DESIGN/DISCOVER tools, execute full 48 SCIENTIFIC | **cannot complete** — routing runs the design engine for KNOW; only KNOW-01 executed (score 0.0); F-01/F-02 |
| Save traces, failure taxonomy, per-case results | traces exist for n=1; no failure taxonomy file |
| Update tracker with verified outcomes | done in `todo_audit/` |

**Prompt is executable only up to the expert/routing steps.** The blocker is a
design/routing decision, not tooling.

## P1 — Close toolkit depth

| instruction | outcome |
|---|---|
| Audit every registered tool incl. uncallable/web-only/licence/backend | partially done → `evidence/registry_summary.txt` (296 rows, 0 declared executable) |
| Implement `ToolSpec → ToolRun → EvidenceItem → RunManifest` across direct/agent/API/CLI | types exist; canonical path does not emit `ToolRun`; `ToolSpec` is untyped dicts |
| SCIENTIFIC must fail typed on missing inputs and refuse fixtures | agent path **passes**; canonical path **fails** (F-03) |
| Question-matched routing, retry/fallback/abstention, critics, cutoff memory | routing not question-matched (F-02); retry codes exist; one critic; no cutoff |
| Meaningful cross-path guardrail tests | `tests/test_execution_modes.py`, `test_p0b_fixture_elimination.py` pass (F-16/§) |
| Coverage table by level + reproducible manifest | not produced |

**Prompt is largely executable but cannot be marked complete** (F-03/F-07/F-11/F-12).

## E1–E8 prompts

| prompt | can run today? | reason |
|---|---|---|
| **E1** capability audit (real positive+invalid per tool) | partly | agent surface yes; registry status always `executable:False`; no environment freeze |
| **E2** Eval500 | no | <500 adjudicated cases (48 exist); no splits/pre-registration |
| **E3** orchestration (100 tasks + fault injection) | no | no fault harness; 1 executed task |
| **E4** therapeutic reasoning (50 contexts, 2 blinded experts) | no | no contexts, no reviewers |
| **E5** mechanistic TPD (100 assay records) | no | dataset absent |
| **E6** ablations | no | no frozen IDs/seeds/paired CIs |
| **E7** temporal | no | no cutoff/as-of/leakage infra (F-11) |
| **E8** discovery | no | no pre-registered targets / wet-lab |
| **Figure repair** | no | no machine-readable scored table exists (`scored/` empty) |

## Summary

- **Executable today:** repository reconciliation, registry census, guardrail
  probes, parser gate, grader smoke, agent-tool E1 style probes.
- **Blocked by decision:** which path is canonical/scientific; what the
  executed pilot is.
- **Blocked by data/experts:** E2 gold + splits, E4 reviewers, E5 dataset, E7
  archive, E8 wet-lab.
- **Blocked by missing code:** fault injection (E3), cutoff memory (E7),
  three critics, `ToolSpec` typing, `scored/` writer, baseline adapters.

The prompts are well-formed; this audit does not mark any of them complete
because `_03` itself says "Never mark a task complete from these instructions
alone."
