# Audit of `todo/PROTACXtend_01_EXPERIMENTS.md` (E1–E8)

`_01` is a **protocol** (Version 0.1), so the audit question is: *which parts are
backed by infrastructure in this repo, and which are paper only?*

The shared benchmark contract requires per-case `case_id`, source DOI/PMID,
gold + alternatives, contradictions, exclusion rationale, expert adjudication,
and a leakage group. `benchmark/cases/*.json` (TASK_SCHEMA 2.0.0) provides
`task_id`, `capability`, `supplied_inputs`, `hidden_information`,
`permitted_tools_databases`, `data_cutoff_date`, `blindness`, `budget`.
It does **not** provide expert adjudication, leakage group, contradictions, or
alternatives inline (those sit in `ground_truth/`). No `splits.json` groups them.

## E1 — Capability audit

| needed | present? |
|---|---|
| registry export | `protacxtend/toolkit/registry.py`, `tools/tool_registry.py` |
| runnable-status field | **no** — `get_tool_status` hard-codes `executable: False` (F-07) |
| real positive / missing / invalid probes | agent-tool path has `PROBE_FIXTURES` + typed failures |
| L0/L1/L2 funnel report | absent |

**Verdict:** `partial`. 296 registered, 34 with executors on the agent surface,
0 declared executable in the registry. Denominator is unresolved (Q13).

## E2 — Eval500

| needed | present? |
|---|---|
| adjudicated task bank | 48 cases authored (`SPRINT2A`), **500 not attempted** (correct — see `_03` rule "never write Eval500 if <500") |
| expert gold | 29 flagged, **no adjudication** (F-06) |
| source cutoff | per-case `data_cutoff_date` present |
| group-held-out splits | **absent** (F-10) |
| pre-registration | **absent** |
| blinded run | 4-task acceptance only; `scored/` empty (F-09) |
| baselines under equal budget | Base-LLM + Biomni at n=4 |

**Verdict:** `absent` as a 500-item study; `partial` as a 48-item pilot.
**Do not title any result "Eval500".**

## E3 — Tool orchestration

| needed | present? |
|---|---|
| 100 executable tasks | 48 authored; 1 executed |
| fault injection schedule | not found |
| retry / fallback / abstention policy | `modes.FailureCode` exists; policy in `agent_tools.run_agent_tool` handles failure codes but there is no seeded fault harness |
| router vs fixed vs direct comparison | not run |

**Verdict:** `absent`.

## E4 — Therapeutic reasoning

- 50 disease contexts: not built.
- two blinded experts: no reviewer registry.
- 0/1/2 rubric + adjudication: no adjudication file.
**Verdict:** `absent` (mechanistic rubrics exist in the grader, but no study).

## E5 — TPD mechanics

- 100 context-specific target–E3–compound–assay records: `data/benchmark/` and
  `protacxtend/data/curated_targets.csv` exist but no curated 100-record
  assay-context table with DC50/Dmax/dose/time/cell/replicate fields.
- assay-aware degradation: `protacxtend/modules/degradation_ml` + TACK-style
  models exist and are labelled surrogate/predicted (critic enforces).
**Verdict:** `absent` as a dataset; `partial` on the predictor plumbing.

## E6 — Ablations

- `scripts/ablation_agentic_vs_pipeline.py` and
  `protacpilot-memory/benchmarks/ablation.py` (now deleted/renamed) exist, but
  no frozen case IDs, seeds, or paired-CI output under `benchmark_results/`.
**Verdict:** `absent`.

## E7 — Temporal validation

- No `t0`, no as-of archive, no cutoff-aware retrieval, no leakage checks
  (`grep -rln "cutoff\|as_of\|temporal\|leakage" protacxtend/memory protacxtend/learning` = empty; F-11).
- `data_cutoff_date` exists per case but is not enforced in retrieval.
**Verdict:** `absent`.

## E8 — End-to-end discovery cases

- No pre-registered target/compound list; no wet-lab coordination artifacts;
  `outputs/p4ward_evidence/` is computational only.
**Verdict:** `absent`.

## Authoritative sources (`_01` footer)

`protacxtend/research/sources.py`, `retrieval.py`, `protacxtend/backend/*_client.py`
implement Europe PMC/PubMed/CrossRef/UniProt/PDB access. But `_01` explicitly
requires a **per-source extraction audit** (schema, license, actual counts,
publication-vs-entry dates); none exists in the tree.
**Verdict:** `partial` (clients exist; extraction audit absent).

## Summary table

| study | infra | data | gold | splits | run | overall |
|---|---|---|---|---|---|---|
| E1 | partial | registry | n/a | n/a | agent probes | `partial` |
| E2 | yes | 48/500 | 29 pending | no | n=4 | `absent` |
| E3 | partial | 48 | n/a | no | no | `absent` |
| E4 | partial | no | no | no | no | `absent` |
| E5 | partial | no | no | no | no | `absent` |
| E6 | partial | n/a | n/a | no | no | `absent` |
| E7 | no | no | no | no | no | `absent` |
| E8 | no | no | no | no | no | `absent` |
