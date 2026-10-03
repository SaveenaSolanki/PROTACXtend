# Audit of `todo/PROTACXtend_02_TOOLKIT_DEPTH.md`

`_02` defines a scientific contract (`ToolSpec`, `ToolRun`, `EvidenceItem`,
`RunManifest`), a KNOW→REASON→DESIGN→DISCOVER→DECIDE depth ladder, a work order,
metric definitions, and a minimum artifact tree. This file checks each.

Date 2026-09-23 · HEAD `0abbe83`.

## 1. Scientific contract types

| required type | where | completeness |
|---|---|---|
| `ToolSpec` (capability ID, biological question, input schema+units, organism, availability/license, runtime, version, valid output domain, limitations, provenance, failure codes) | **no typed class**; `protacxtend/agentic/registry.py::TOOL_SPECS` (list of dicts) with `name, kind, purpose, inputs, evidence_type, limitations, readiness, deterministic, ml, surrogate, retrieved` | `partial` — missing license, runtime, units, version, failure codes, output domain |
| `ToolRun` (input hashes/origins, params, artifacts, env/version, elapsed, success/abstention/typed failure, evidence links) | `protacxtend/results/schema.py:40` (dataclass) | `verified` (fields: tool, status, executed, valid_output, version, backend, evidence_kind, params, params_sha256, error, timestamps, latency, artifacts, provenance) |
| `EvidenceItem` (entity pair + signed claim, source+timestamp, assay context, measured/predicted/surrogate/unknown, strength, contradictions) | `protacxtend/results/schema.py:120` (dataclass) | `verified` (kind, direction, entity, context, claim, strength, date, experimental_system, sample_size, confidence, provenance) |
| `RunManifest` (full lineage) | `protacxtend/canonical/schemas.py:310` | `verified` structurally; see provenance caveat F-13 |

**Caveat that matters:** the *types* exist, but the canonical strategy's
`evidence_refs` are internal field labels, not external sources (F-13), and the
strategy path does not populate `ToolRun` records (the agent-tool path does).

## 2. Functional chain depth

| layer | minimum | depth increment | live state |
|---|---|---|---|
| **KNOW** retrieval | disambiguation, dated sources, normalization | typed KG with `supported_by` | `protacxtend/research/graph.py` exists; no dated document cache; no cutoff (E7 absent) |
| **REASON** biology | causal rationale, essentiality, expression, E3 context | negative-finding invalidation, calibrated no-go | `protacxtend/research/reasoning.py`, critic raises `REVISE`; no blinded rubric |
| **DESIGN** chemistry | verified ligands, vectors, valid linkers | reject infeasible valence/physchem | `canonical/modules.ChemistryWarheadModule`, RDKit validity check; **but scientific run used `local_demo_*` warheads** (F-03) |
| **DESIGN** structure | experimental/qualified binary + ternary + clash/interface | pose ensembles + uncertainty, not single rank | `canonical` `structure_ternary`, cooperativity-proxy; critic blocks structural claims without evidence (`verified`) |
| **DISCOVER** synthesis | assay-aware degradation, permeability, ranking | context link + hook/off-target | TACK-style model + warnings; all labelled predicted (`verified`) |
| **DECIDE** strategy | typed candidate/risk/uncertainty/experiment/no-go | each threshold maps to a falsifying observation | `TherapeuticStrategy.v1` emitted; go/no-go criteria present; `stopping_state=REVISE` |

## 3. Work order status

1. **Read-only reconcile** → done by this audit (`00_STATUS...`, `FINDINGS.md`).
2. **Input/mode contract** → **fails on the canonical path** (F-03). Agent path passes.
3. **Knowledge retrieval** → clients exist; dated cache + cutoff absent.
4. **Tool adapters** → 34 agent adapters; registry tools not adapted (F-07).
5. **Planner and recovery** → `FailureCode` + retry logic exists in
   `agent_tools`/`executor`; no seeded-fault harness (E3 absent).
6. **Critics** → one `CriticVerifier`, not three (F-12).
7. **Memory** → `protacxtend/memory/` present; **no versioning/cutoff/approval
   isolation found** (F-11).
8. **Decision view** → typed strategy + manifest render; confidence is not
   calibrated on held-out cases (no held-out set).
9. **Benchmark + release gate** → E1 funnel empty, 1 executed task,
   no gold adjudication, no splits, no release freeze.

## 4. Metrics that "should appear" in the toolkit report

`availability`, `execution_success`, `valid_output`, `detection_rate`,
`recovery_rate`, `fallback_success`, `appropriate_abstention`,
`hallucinated_continuation`, tool-selection precision, citation support,
wall time, resource use, surrogate success.

**None of these is computed for the registry set.** The only measured values are
per single runs (`latency_s`) and the offline-smoke mean. `get_tool_status` and
`summarize_toolkit_status` return `available: 0, executable: 0` (F-07).

## 5. Minimum artifact tree

| required | present |
|---|---|
| `docs/tool_registry_snapshot.json` | ✗ |
| `docs/universal_reconciliation.md` | ✗ |
| `benchmarks/cases/*.jsonl` | partial — `benchmark/cases/*.json` (48) |
| `benchmarks/gold_review.tsv` | ✗ |
| `benchmarks/splits.json` | ✗ |
| `benchmarks/pre_registration.md` | ✗ |
| `benchmarks/results/<run_id>/manifest.json`, `tool_runs.jsonl`, `predictions.jsonl`, `failures.jsonl`, `scores.json` | ✗ (only `benchmark_results/pilots/*.json`) |

## Verdict

`_02` is an accurate *specification* of what is missing. The repo satisfies the
**type layer** and the **agent-tool guardrails**, but not the **funnel**
(registration→execution→valid output), the **provenance-to-source** layer, the
**three critics**, the **cutoff-aware memory**, or the **artifact tree**.
