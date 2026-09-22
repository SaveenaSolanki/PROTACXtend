# ADR-001 — Canonical Execution Stack (collapse of the parallel agent stacks)

- **Status:** Accepted
- **Date:** 2026-09-22
- **Context:** PROTACXtend grew two (later three) parallel control flows. This
  made benchmark attribution impossible, failure tracing difficult, provenance
  inconsistent and routing ambiguous.
- **Decision:** One canonical execution stack
  (`protacxtend.canonical`). The historical stacks are demoted to *execution
  engines* reached through the canonical Tool Executor. There is one parser,
  one task graph, one evidence ledger, one critic and one decision engine per
  run.

## Problem

Before this change there were parallel agent architectures:

| Stack | Module | Role | Problem |
| --- | --- | --- | --- |
| A. Deterministic scientific workflow | `protacxtend/agents/graph.py` (`LocalSynGlueWorkflowGraph`, 31 nodes) | Fixed-order pipeline | Its own parse, provenance, warnings, stop logic |
| B. Adaptive agentic graph | `protacxtend/agents/agentic_core.py` (`build_agentic_graph`) | Conditional LangGraph over real nodes | Its own parse, decision log, gates, stop logic |
| C. Seven-layer wrapper | `protacxtend/agentic/` (`OrchestratorAgent`) | Marketing "agentic" layer wrapping A | Deprecated, but still importable and confusing |

Each stack had its own parsing, error taxonomy, provenance and stopping rules.
A benchmark could not attribute a score to a module, a failure could not be
traced across stacks, and the same request could route differently depending
on `mode`.

## Canonical stack

```text
User
 │
 ▼
Scientific Request Parser        protacxtend.canonical.request_parser
 │
 ▼
Orchestrator                     protacxtend.canonical.orchestrator
 │
 ▼
Task Graph                       protacxtend.canonical.task_graph
 │
 ▼
Specialized Scientific Modules   protacxtend.canonical.modules   (9 modules)
 │
 ▼
Tool Executor                    protacxtend.canonical.tool_executor
 │
 ▼
Evidence Store                   protacxtend.canonical.evidence
 │
 ▼
Critic / Verifier                protacxtend.canonical.critic
 │
 ▼
Decision Engine                  protacxtend.canonical.decision
 │
 ▼
TherapeuticStrategy              protacxtend.canonical.schemas
```

### The nine specialized scientific modules

Modules are logical divisions beneath **one** orchestrator. They do not own
control flow and do not require separate state.

1. `target_disease` — Target & Disease
2. `tpd_tractability` — TPD Tractability
3. `e3_selection` — E3 Selection
4. `chemistry_warhead` — Chemistry / Warhead
5. `structure_ternary` — Structure / Ternary
6. `degradation` — Degradation
7. `adme_safety` — ADME / Safety
8. `resistance_biomarker` — Resistance / Biomarker
9. `experimental_design` — Experimental Design

Critics are **separate** from modules (`critic.py`), as are the decision engine
(`decision.py`) and the evidence ledger (`evidence.py`).

### Where the old stacks went

The two scientific engines still exist because they contain real, tested
scientific tooling. They are now *leaves* selected by the Tool Executor:

- `engine="deterministic"` → `protacxtend.agents.graph.run_syn_glue_workflow`
- `engine="adaptive"` → `protacxtend.agents.agentic_core.run_agentic_workflow`
  with `protacxtend.agents.real_nodes.real_nodes()`

`protacxtend.agents.runtime.run_protacpilot(mode=...)` is still the single
runtime entry point, but it now always post-processes the engine result
through the canonical stack. The returned payload carries:

- `canonical.critic` — one verdict
- `canonical.module_results` — one typed result per module (benchmark attribution key)
- `canonical.task_graph` — the executed DAG
- `therapeutic_strategy` — the typed `TherapeuticStrategy`

`protacxtend/agentic/` is deprecated (banner in its `__init__.py`); do not build
on it.

## Typed scientific output — `TherapeuticStrategy`

Every discovery run returns a fully typed `TherapeuticStrategy`
(`protacxtend.canonical.schemas`, `STRATEGY_SCHEMA_VERSION =
"TherapeuticStrategy.v1"`). It is the decision artifact for benchmarking, UI
rendering, scoring and downstream plots; markdown/CSV/JSON are renderings of
it. The runtime also writes it to
`outputs/runs/<run_id>/therapeutic_strategy.json`.

| Field | Type | Meaning |
| --- | --- | --- |
| `target` | `str` | resolved target gene |
| `disease_context` | `str` | disease/indication context |
| `target_validation` | `TargetValidation` | UniProt, structures, validation status, limitations |
| `tpd_tractability` | `TPDTractabilityAssessment` | binders, E3 ligands, structure availability, tractability |
| `recommended_e3` | `str` | selected E3 ligase |
| `alternative_e3s` | `list[str]` | other viable recruiters |
| `rejected_e3s` | `list[dict]` | recruiter + reason + score |
| `warheads` | `list[dict]` | warhead name/SMILES/source/potency |
| `attachment_vectors` | `list[dict]` | exit-vector atoms/vectors |
| `linker_hypotheses` | `list[dict]` | linker name/SMILES/class |
| `candidate_protacs` | `list[dict]` | ranked candidates with degradation/ADMET joined |
| `binary_structure_assessment` | `BinaryStructureAssessment` | binary structure availability/method |
| `ternary_complex_assessment` | `TernaryComplexAssessment` | ternary records, scores, `claim_allowed` |
| `degradation_prediction` | `DegradationPredictionSummary` | model versions, heuristic flag, `claim_allowed`, DC50 |
| `adme_risks` | `list[ADMERisk]` | per-candidate penalties/flags |
| `safety_risks` | `list[SafetyRisk]` | cardiotox/AMES/DILI/AD risks |
| `resistance_mechanisms` | `list[ResistanceMechanism]` | E3 mutations, pathway bypass |
| `biomarkers` | `list[Biomarker]` | target/E3 context markers |
| `combination_strategy` | `CombinationStrategy` | flag + rationale (never overclaimed) |
| `experimental_plan` | `ExperimentalPlan` | objective, candidate ids, assay ladder, controls, success/failure criteria |
| `go_no_go_criteria` | `list[GoNoGoCriterion]` | criterion, threshold, status, met |
| `evidence` | `EvidenceBundle` | record counts by module/type + refs |
| `contradictions` | `list[Contradiction]` | conflicting evidence + resolution |
| `uncertainty` | `UncertaintyDecomposition` | model/structural/evidence/context/biology/data |
| `run_manifest` | `RunManifest` | run id, engine, versions, module status/runtimes, config, artifact paths |

Backward-compatible derived views (`recommended_candidates`,
`recommended_experiments`, `e3_ligase`, `indication`, `module_status`,
`evidence_refs`, `claims_allowed`, `limitations`, `critic`) are still populated.

### Guarantees

- **No silent fields:** each field is either populated or explicitly marked
  unavailable with a `limitations`/status entry.
- **Measured/predicted separation survives:** `degradation_prediction.claim_allowed`
  is `False` for heuristic fallbacks; `ternary_complex_assessment.claim_allowed`
  is `False` without structure evidence.
- **`go_no_go_criteria` are always populated** so a run cannot "succeed"
  without exposing the gates it passed or failed.
- **`run_manifest` ties the strategy to the evidence, modules and versions**
  that produced it.

## Consequences

**Positive**

- **Benchmark attribution:** every claim maps to exactly one `module_id` and a
  stable `evidence_ref`.
- **Failure tracing:** the task graph records per-module status, errors and
  runtime; the critic aggregates failure categories in one place.
- **Provenance consistency:** a single `CanonicalEvidenceStore`; the final
  strategy references evidence keys, not re-derived numbers.
- **Unambiguous routing:** one parser in, one decision engine out, regardless
  of which engine ran.
- **Typed output:** `TherapeuticStrategy` replaces ad-hoc report coupling.

**Costs / limits**

- The engines are not yet rewritten *as* modules; modules interpret the shared
  engine state. This is deliberate: it preserves tested scientific behaviour
  while unifying the control plane.
- `TherapeuticStrategy` is the decision artifact; markdown/CSV/JSON remain
  renderings.
- New scientific capabilities must be added as a module (or as a tool behind
  one) plus a critic rule, never as a new top-level agent.

## How to add a capability

1. Add/extend a tool call in `canonical/tool_executor.py` (fail closed,
   provenance recorded).
2. Bind it to one of the nine modules in `canonical/modules.py` (or add a new
   module only if it truly requires separate state, and register it in
   `MODULE_CLASSES` + `module_dependencies()`).
3. Add a critic rule in `canonical/critic.py` if it can change the verdict.
4. Add tests under `tests/test_canonical_stack.py`.
