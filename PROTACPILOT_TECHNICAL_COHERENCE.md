# PROTACXtend Technical Coherence Assessment
## Honest Self-Audit Against the Reviewer Critique

**Date**: 2026-07-31
 **Status**: Internal technical coherence audit, grounded in the actual source code
 **Scope**: Verifies the critique claim-by-claim against the code, then defines the precise
 engineering route from the current "deterministic traceable workflow" to a legitimate
 "agentic AI platform for PROTAC design"

---

## 0. Premise

The reviewer's central thesis is correct: **a sequential 23-node pipeline is workflow automation,
not agentism.** This document does not retrofit the chat thesis — it audits the actual code, fixes
the terminology, lists precisely what each gap is (with the code line that proves it), and proposes
a concrete evolution path with stages that can be shipped without rebuilding from scratch.

The reviewer's final judgment is also agreed: **do not rebuild from scratch.** The deterministic
foundation (RDKit chemistry, public-API data layer, P4ward, stereochemistry engine, linker scanner)
is a real asset that most "agentic" prototypes lack. The work to do is to *convert the fixed
sequence into an adaptive decision graph* on top of that foundation.

---

## 1. Terminology Correction (Fixed Immediately)

### 1.1 What the system actually is today

| Current label | What it actually is | Renaming required |
|--------------|---------------------|-------------------|
| ReAct agent | Deterministic pass-through wrapper | **Traceable deterministic scientific workflow node** |
| `run() → _execute() → _observation() → add_trace()` | A `try/except` + trace recorder | **TraceableExecutor** wrapper |
| `thought` / `action` / `observation` strings | Static class attributes + summary strings | **Decision log entries** (still trace-formatted, but with a `decision_type` enum) |
| Agent | A function `(WorkflowState) → WorkflowState` | **Workflow node** (until a real decision layer is added) |

### 1.2 What ReAct actually requires, and what is missing

Real ReAct (Yao et al. 2023) is a *loop* where a model:
1. Observes state
2. Decides whether information is missing
3. Selects a tool to call
4. Integrates the observation
5. Decides whether to continue, revise, or terminate

PROTACXtend today does step (4) mechanically — every node runs because it is next in
`zip(ordered, ordered[1:])` (`graph.py` line ~145). There is **no step (2), step (3), or step (5)**.
Therefore it is not ReAct.

### 1.3 What we will rename in v0.2 (no behavior change, no LLM)

```python
class WorkflowNode:            # was: ReActAgent
    node_name: str             # was: name
    decision_type: str         # was: thought — now one of:
                               #   "parse" | "resolve" | "retrieve" | "select" |
                               #   "construct" | "validate" | "predict" | "rank" |
                               #   "critique" | "report"
    operation: str             # was: action
    def execute(self, snapshot: WorkflowState) -> NodeResult: ...  # was: run()
```

The trace record will change from free `thought` text to a structured `DecisionLog`:

```python
{
  "node": "TargetResolverAgent",
  "decision_type": "resolve",
  "operation": "uniprot_lookup",
  "evidence_query": "HMGB2 organism_id:9606",
  "evidence_sources": ["UniProt:rest", "AlphaFold:api"],
  "outcome": "resolved",
  "tool_versions": {"uniprot_api": "2026_07", "alphafold_db": "v4"},
  "confidence": 0.9,
  "next_proposed_node": "TargetBinderRetrievalAgent",
  "reason_codes": []
}
```

---

## 2. Critique Claim-by-Claim Audit

I now verify every material claim in the critique against the actual source code.

### 2.1 "It is not yet truly agentic"

**Verdict: CONFIRMED.**

**Evidence from code** (`graph.py` lines ~50-90):
- `LocalSynGlueWorkflowGraph.__init__` is a **hardcoded list of 23 (name, fn) tuples**.
- The `run()` loop iterates `self.nodes` sequentially. No condition, no branching, no model.
- `LangGraph` compile path mirrors the same list: `graph.add_edge(current, nxt)` in a plain
  `zip`. No `add_conditional_edges`, no `Command` nodes, no routing callable.

Therefore: **execution order is set at compile time, not determined by evidence at run time.** The
system is a pipeline, not an agent.

### 2.2 "ReAct is used too loosely"

**Verdict: CONFIRMED.**

**Evidence** (`base_agent.py` lines 15-44):
The base class only exposes a stub `ReActAgent`:
```python
def run(self, state):
    started = time.time()
    try:
        state = self._execute(state)
        observation = self._observation(state)
    except Exception as exc:
        state.errors.append(f"{self.name}: {exc}")
        observation = f"error={exc}"
    self.toolbox.add_trace(state, self.name, self.thought, self.action,
                          observation, time.time() - started)
    return state
```

There is no model call and no decision loop. The `thought` is a **class attribute** (a string
literal set once per class). The "ReAct" label is cosmetic.

### 2.3 "The degradation model is only heuristic"

**Verdict: CONFIRMED.**

**Evidence** (`protac_toolbox.py` `predict_degradation`, around lines 984-1028):
- Computes `model_confidence` from `candidate.synthetic_feasibility_score` and a flag
  (`compute_applicability_domain_score`).
- Returns pseudo DC50/Dmax derived from MW, linker length, TPSA, HBD.
- The schema field is honest about this:
  ```python
  model_version: str = "SynGlue-demo-heuristic-v0.1"
  ```
- The report's pipeline-status table itself states the gap explicitly
  (toolbox ~line 1825): `"next_integration_needed": "Load validated
   SynGlue/DeepPROTACs/PROTAC-STAN/Chemprop models with uncertainty."`

Therefore: every degradation output **is** today labelled as a heuristic rule-based score, not a
validated prediction. The schema is honest. The issue is that the heuristic is the *only* option.

### 2.4 "Ternary-complex scoring must go beyond a geometric proxy"

**Verdict: PARTIALLY CONFIRMED.**

**Evidence**:
- `ternary_feasibility.py` (332 lines) is a fast geometric proxy — fine.
- `p4ward_wrapper.py` (1,200 lines) calls **a single** simulator (P4ward Docker) and treats its
  output as the ternary verdict. There is **no ensemble, no DeepTernary, no PRosettaC
  cross-validation, no consensus**.
- The pipeline status row at ~line 1858 in `protac_toolbox.py` itself records the gap:
  `"Add calibrated gates, uncertainty-aware ranking, and real model/tool provenance."`

### 2.5 "E3 selection needs biological context"

**Verdict: CONFIRMED.**

**Evidence** (`e3_agent.py`, `toolbox.select_e3_ligands` ~line 538-584):
- The selection is driven by a **2-axis colocalization table** (subcellular POI location vs. E3
  default location) and the user's preferred E3 name. The data table has 8 entries
  (`curated_e3_ligands.csv`). There is no DepMap expression lookup, no tissue-expression cross-check,
  no resistance-mutation query, and no disease-relevance filter.
- Consequence (per critique): CRBN and VHL are picked because they have ligands and data, not
  because they are biologically optimal for the POI.

### 2.6 "Linker generation needs conformational intelligence"

**Verdict: CONFIRMED.**

**Evidence** (`linker_agent.py`, `toolbox.generate_linkers` ~line 623-700):
- Linkers come from `curated_linkers.csv` + `generate_rule_based_linkers` (programmatic PEG/alkyl
  enumeration).
- `linker_scanner.py` (the newer module) scores by attachment-point topology + simple RDKit
  2D descriptors. There is **no conformer ensemble, no exit-vector distance distribution, no
  linker strain in a ternary pose, no intramolecular H-bond scan, no macrocyclization
  evaluation**. The newer `linker_scanner.py` even fails to embed 3D conformers for fused-ring
  warheads like ICM (we patched it to fall back to 2D scoring, which is exactly the 2D-only
  limitation the reviewer flagged).
- `toolbox.evolve_candidates` (line 1375) is **post-hoc one-shot linker swapping** triggered by
  high ADMET penalty. It is *not* the generate→assemble→evaluate→repair loop the critique demands.

### 2.7 "Synthetic accessibility needs to be explicit"

**Verdict: CONFIRMED.**

**Evidence**:
- `retrosynthesis_filter.py` is **17 lines**:
  ```python
  def retrosynthesis_feasibility_filter(candidate, threshold=0.45):
      return candidate.synthetic_feasibility_score >= threshold
  ```
  It is a *threshold on a heuristic score*. No AiZynthFinder, no ASKCOS, no IBM RXN, no
  RAscore/SCScore model inference, no purchasability lookup.
- The pipeline status row itself documents this:
  `"AiZynthFinder/ASKCOS/IBM RXN/RAscore are not run."`
  (`protac_toolbox.py` ~line 1857)

### 2.8 "Shared mutable state is risky"

**Verdict: CONFIRMED.**

**Evidence**:
- The entire workflow passes a single `WorkflowState` instance (`schemas.py`). Every agent
  mutates fields directly. `state.valid_candidates.append(...)`, `state.warnings.append(...)`,
  `state.parsed_objective = ...` are the norm.
- No snapshot. No reducer. No immutability. No per-candidate state.
- Already causes the real bug class the critique predicts: in the **binder agent fix history** we
  had to switch from `dict-key` access to `getattr` because the schema half-mutated when one agent
  passed a dict-like object and another passed a Pydantic instance. That is exactly the
  "unclear ownership of fields" symptom.

### 2.9 "Raw 'thought' storage should be removed"

**Verdict: CONFIRMED.**

**Evidence** (`AgentTrace` schema, `add_trace` in toolbox ~line 2019):
- Traces store free-form `thought`, `action`, `observation` strings. The
  critique's `reason_codes` / `evidence` / `tool_version` / `confidence` fields do not exist
  as structured fields today.

### 2.10 "Retry logic is too static"

**Verdict: CONFIRMED.**

**Evidence** (`graph.py` `_should_retry`, lines ~108-130):
- The retry policy allows `max_retries_per_step = 1`, on a fixed allow-list of 5 steps
  (`resolve_target`, `retrieve_target_binders`, `predict_degradation`, `predict_admet`,
  `optional_ternary_feasibility`).
- The retry condition is a boolean "did the expected output get populated" — *not*
  failure-class-aware. A P4ward crash and a ChEMBL timeout are treated identically.

### 2.11 "Currently no evidence sufficiency gate, parallel evaluation, conditional routing"

**Verdict: CONFIRMED.**

**Evidence**:
- No `assessment_evidence_sufficiency` node exists.
- The planner (`design_planner_agent.py` ~line 152) sets `should_run_docking` /
  `should_run_retrosynthesis` as **booleans derived from user keywords in the request string**
  (e.g. `"DOCK"` / `"SYNTHESIS"` in the input). Evidence sufficiency is never *measured*.
- There is no candidate-level repair loop, no parallel evaluation fan-out, no
  human-approval gate node, no Pareto ranking.

**Positive outlier (and the reviewer missed this)**:
The `RankingAgent` *does* already compute `uncertainty_flags` and the `ApplicabilityDomainAgent`
*does* assign `domain_status = inside / borderline / outside`
(`protac_toolbox.py` ~lines 1147-1177 and 1224-1232). These are genuinely used as penalties in
the score and as explicit flags in the final report. So the *output* side of uncertainty already
exists; what does not exist is the *decision* side (uncertainty driving a routing decision).

---

## 3. What the Foundations Already Have Right (Don't Rebuild)

The critique's "do not discard" list maps to concrete assets:

| Reviewer recommendation | Existing asset |
|-------------------------|----------------|
| Deterministic foundation | All 23 nodes are pure Python, fully testable, no LLM cost, no hallucination |
| Provenance-aware | Every prediction carries `model_version`, `source`, `confidence` |
| Modular | 73-method `ProtacDesignToolbox` + 61 tool files, each with a narrow contract |
| Safety guardrails | `prompts.py` + `safety_precheck()` hard-block in-vivo dosing language |
| Uncertainty + applicability domain | `ApplicabilityDomainAgent` + `uncertainty_flags` live in `RankingResult` |
| Chemistry engine | RDKit + custom stereochemistry engine (417 lines) + linker scanner (632 lines) |
| Structural engine | P4ward Docker wrapper (1,200 lines) + geometric proxy (332 lines) |
| Public data layer | 6 live free APIs with rate limiting, caching, exponential backoff |

These are the *pillars* the agentic layer will sit on. They are **much harder to build than the
graph layer that will sit on top of them**. Rebuilding from scratch would throw away the only
non-trivial chemistry-engineering work in the project.

---

## 4. Engineering Positions (Fixed in v0.2)

These four corrections are non-negotiable and cost almost nothing to land:

### Position 4.1 — Terminology
- `ReActAgent` → `WorkflowNode`
- `thought/action/observation` → `decision_type/operation/outcome` + structured `DecisionLog`
- `run(state)` → `execute(snapshot) -> NodeResult`
- System description in README/`AGENT_APIS.md` updated to:
  "provenance-aware, modular, deterministic PROTAC design workflow with an agent-ready
  orchestration layer"
- (Not "agentic AI", not "ReAct", until §6 below ships.)

### Position 4.2 — Honest labels on every prediction
- `predict_degradation` report row will say:
  **"Rule-based prioritization score — not a validated degradation prediction."**
  (Already true in `model_version`; will add a visible banner in the report body.)
- `ternary_feasibility` proxy output will say:
  **"Geometric filter — not evidence of productive degradation."**
- `synthetic_feasibility_score` explanation will say:
  **"Heuristic proxy. AiZynthFinder/ASKCOS/RAscore not run."**

### Position 4.3 — No "ReAct" claim in production text
Until a real planning loop is shipped (§6 Phase 2), the documentation will not use "ReAct" or
"agent" as if they meant "module that runs in sequence". The terms will be reserved for their
technical definitions.

### Position 4.4 — Keep the deterministic foundation, gate the agentic upgrades behind a flag
- `parsed_objective.agentic_mode` (default `false`)
- When `false`: current sequential pipeline (v0.1 behavior, fully reproducible)
- When `true`: adaptive decision graph (v0.2+, see §6)
- This means external users who depend on the deterministic output for reproducibility (e.g.
  internal CADD teams, external reviewers running benchmarks) **never regress**.

---

## 5. Structural Engineering Issues — Concrete Fix Plans

### 5.1 Shared mutable state → Snapshot-reducer pattern

**Target** (already adopted by LangGraph internally; we expose it explicitly):

```
            ┌─────────────┐
 snapshot → │  Node.execute │ → NodeResult
            └─────────────┘
                                  │
                                  ▼
                         ┌────────────────┐
                         │ state_reducer   │  ← pure function
                         │  (validated)    │
                         └────────────────┘
                                  │
                                  ▼
                         new_versioned_state
```

```python
@dataclass(frozen=True)
class NodeResult:
    outputs: dict[str, Any]            # what this node produced
    evidence: list[EvidenceRef]         # cited sources/artifacts
    warnings: list[str]
    uncertainty_flags: list[str]
    status: Literal["ok", "skip", "needs_retry", "needs_human", "fatal"]
    proposed_state_updates: dict       # never mutates the input snapshot
    next_proposed_node: str | None = None  # for adaptive routing
    reason_codes: list[str] = field(default_factory=list)

def state_reducer(prev: WorkflowState, result: NodeResult) -> WorkflowState:
    # applies result.proposed_state_updates with validation
    # raises on conflicting writes / unknown fields
    return new_state
```

**Migration**: ship incrementally.
1. v0.2: add `NodeResult` as a *returned side-channel* (agents still mutate state, but also return
   a `NodeResult` for testing). 
2. v0.3: make agents return only `NodeResult`; reducer applies updates.
3. Per-candidate state: a separate `CandidateLedger` keyed by `candidate_id`, so 1000 candidates
   can be evaluated in parallel without global-state races.

### 5.2 Trace storage → Structured evidence records

Replace free-text traces with:

```python
class DecisionLog(BaseModel):
    node: str
    decision_type: Literal[
        "parse","resolve","retrieve","select","construct","validate",
        "predict","rank","critique","repair","escalate","route"
    ]
    operation: str
    tool_invoked: str
    tool_version: str
    evidence_refs: list[str]            # URLs, file paths, run IDs
    reason_codes: list[str]            # e.g. ["ADMET_PENALTY_HIGH", "STERIC_CLASH"]
    confidence: float
    next_proposed_node: str | None
    elapsed_s: float
```

Stored in `state.decision_log: list[DecisionLog]` (not `traces`). The old `traces` field is kept
for backward compatibility until v0.3 then removed.

### 5.3 Retry → Failure-class-aware dispatch

Replace the static allow-list with a `FailureClassifier`:

```python
class FailureClass(Enum):
    API_TIMEOUT          # exponential retry, then cached fallback source
    API_NOT_FOUND        # try alternate source, then degrade gracefully
    NO_BINDERS           # try alternate DB, then literature RAG, then human
    INVALID_ATTACHMENT   # recompute exit vectors, escalate to chemist
    LINKER_GEOMETRY_FAIL # regenerate linker with constrained length/rigidity
    P4WARD_FAILURE       # downgrade to geometric proxy + flag uncertainty
    OUT_OF_DOMAIN        # escalate to human review, downweight score
    INVALID_STEREO       # enumerate stereoisomers, revalidate
    UNEXPECTED           # log, mark node_status="needs_human"

FAILURE_RESPONSES = {
    FailureClass.API_TIMEOUT: {
        "action": "retry_exponential",
        "retries": 5, "base_delay_s": 0.5,
        "fallback_source": "cached_or_local_curated",
    },
    FailureClass.LINKER_GEOMETRY_FAIL: {
        "action": "repair_loop",
        "regenerate": "linker_scanner(length_constraint=[8,16], rigidity='increased')",
        "max_repairs": 3,
    },
    FailureClass.OUT_OF_DOMAIN: {
        "action": "escalate_human",
        "downweight_score": True,
    },
    # ...
}
```

This unblocks the "linker repair loop" the reviewer specifically calls out.

### 5.4 Fixed sequence → Adaptive decision graph

The graph will gain three new node classes that the pipeline never had:

1. `EvidenceSufficiencyGate` — measures whether target biology, warhead evidence, and E3 context
   are dense enough to attempt PROTAC design. Returns `status: "proceed" | "insufficient" |
   "partially_sufficient"` and a list of *missing evidence streams*.
2. `RepairController` — given a failed candidate + `reason_codes`, invokes a bounded repair
   workflow (linker regeneration, exit-vector re-detection, stereoisomer enumeration). Repair is
   bounded by `max_repairs=3` (no unbounded loop).
3. `HumanApprovalGate` — produces an *escalation packet* (candidate, evidence, uncertainty,
   alternative options) and sets `pipeline_status = "paused_for_human"`. This satisfies the
   reviewer's "human-in-loop" requirement without requiring a chat step.

The compiled LangGraph will use `add_conditional_edges` for routing:

```python
graph.add_conditional_edges(
    "evidence_sufficiency_gate",
    route_by_status,
    {
        "proceed": "candidate_generation",
        "insufficient": "request_more_evidence",
        "partially_sufficient": "candidate_generation_with_warnings",
    },
)
```

This is the smallest code change that converts the system from pipeline → adaptive graph.

---

## 6. The Agentic Evolution Path

Three phases. Each phase is shippable and *useable* on its own. The current v0.1 is reproducible
and stays the default.

### Phase 1 — v0.2 "Honest Deterministic + Adaptive Routing" (no LLM)

- Apply Position 4 corrections (terminology, labels, `ReActAgent` rename).
- Implement `NodeResult` + reducer (§5.1).
- Implement failure-class dispatcher (§5.3).
- Add `EvidenceSufficiencyGate`, `RepairController`, `HumanApprovalGate` nodes (§5.4).
- Wire conditional edges into the graph.
- Keep the LLM slot **empty** — all routing decisions are deterministic rules.

**Definition of done**:
- Pipeline can skip retrosynthesis when evidence says structures are unresolved.
- Pipeline can regenerate a linker when the ternary pose fails.
- Pipeline can escalate candidates outside applicability domain to a human-review queue.
- `next_proposed_node` on every `DecisionLog` explains *why* the next step was chosen.

**At this point the system is a legitimate "adaptive scientific workflow".** It is still not
"agentic AI" because there is no model making judgment calls.

### Phase 2 — v0.3 "LLM-Augmented Decision Layer" (small, scoped LLM usage)

LLMs are added **only** where deterministic rules are strictly worse:

| Decision | Why LLM is better than rules |
|----------|------------------------------|
| Explaining conflicting evidence | Requires natural-language synthesis of heterogeneous sources |
| Proposing repair strategies *when* rule library is empty | Open-ended hypothesis generation |
| Decomposing ambiguous user requests | Tail regex cannot handle arbitrary phrasing |
| Generating the final human-readable evidence report | Template reports lose nuance |

Implementation: a thin `PlannerLLM` that receives the current `DecisionLog` + a structured
prompt and returns a `PlannerDecision` (json-validated). The deterministic plumbing stays.

```python
class PlannerDecision(BaseModel):
    next_node: str
    reason: str
    tool_overrides: dict[str, Any]
    confidence: float
    escalated_to_human: bool
```

LLM is nowhere near the chemistry: SMILES are still validated by RDKit, conformers by the
existing engines, structures by P4ward, safety by `safety_precheck`. An LLM cannot invent a
SMILES and have it pass — the guardrails reject it downstream. This is the safety model the
reviewer wants.

### Phase 3 — v0.4 "Validated Predictive Layer" (replaces heuristic)

This phase is the **real scientific upgrade** and is independent of the LLM question.

Subprojects (in priority order):

1. **Replace the degradation heuristic with a calibrated model with uncertainty.**
   - Train on PROTAC-8K / DegradeMaster / homologated PROTAC-DB 3.0 data (6,111 PROTACs).
   - Start with Chemprop D-MPNN as a baseline (open-source, available now).
   - Add cell-line / E3 expression context vectors (DepMap, HPA, ProteomicsDB).
   - Output: DC50, Dmax, degradation probability, calibrated uncertainty interval,
     applicability-domain flag. The heuristic stays as a fallback when the model is
     OOD.

2. **Ternary ensemble.**
   - Run P4ward + DeepTernary SE(3)-equivariant model + PRosettaC (or HADDOCK).
   - Consensus vote: keep candidates that ≥2-of-3 predict productive interface.
   - Compute predicted buried surface area, interface complementarity, lysine
     accessibility — all the features the reviewer lists.

3. **Linker conformational loop.**
   - Integrate CREST/xTB for conformer ensembles on the linker.
   - Compute exit-vector distance distributions.
   - Feed linker strain into the ternary scorer as an energy penalty.
   - Surface intramolecular H-bond and macrocyclization opportunities as structured
     `reason_codes`.

4. **Synthetic accessibility for real.**
   - AiZynthFinder (open source) as the primary route planner.
   - RAscore as a fast synthetic-accessibility filter before AiZynthFinder.
   - ZINC/Enamine/eMolecules lookup for purchasability of building blocks.
   - Output: route tree (with confidence per step), purchasability, unstable-functional-group
     flag, protecting-group requirement.

5. **E3 context engine.**
   - Load DepMap expression matrix for CRBN, VHL, DCAF15, RNF114, KEAP1, FEM1B, cIAP, MDM2.
   - Add disease-relevance filter (Open Targets GraphQL).
   - Add resistance-mutation flag (COSMIC).
   - Output: a ranked E3 recommendation with reason_codes including "expression_in_context",
     "colocalization", "resistance_risk", "ligand_chemistry_available".

6. **Pareto ranking.**
   - Replace the single weighted composite (`toolbox.rank_candidates`, line 1204) with
     NSGA-II over (DC50, Dmax, permeability, novelty, synthesis_score) — plus hard gates
     that discard any candidate flagged by the safety or applicability-domain filter.

7. **Benchmarks.**
   - Retrospective benchmark: run the full pipeline on PROTAC-DB 3.0 *withheld test set*.
     Report: top-10 hit rate (did we recover known degraders?), DC50 RMSE, novelty
     recall.
   - Ablation: v0.1 deterministic sequential vs v0.2 adaptive graph vs v0.3 LLM-augmented
     vs v0.4 predictive. The ablation table is the proof that the agentic architecture
     adds measurable value. Without this table, the word "agentic" has no evidence base.

---

## 7. LLM-Deterministic Responsibility Split (Definitive)

| Responsibility | Owner | Why |
|----------------|-------|-----|
| Molecular construction (SMILES assembly) | Deterministic RDKit | Hallucination risk is unacceptable |
| Stereochemistry | Deterministic RDKit + stereochemistry_engine | Bounded, mechanical, auditable |
| Conformer generation | Deterministic CREST/xTB/ETKDG | Physics-based |
| Docking & structural measurement | Deterministic Vina/P4ward/DeepTernary | Scientific reproducibility |
| Prediction-model inference | Deterministic Chemprop / custom models | Trained weights are the IP |
| Database querying | Deterministic API clients | Already rate-limited and cached |
| Retrosynthesis | Deterministic AiZynthFinder/ASKCOS | Trained on reaction templates |
| Ranking calculations | Deterministic Pareto / score function | Must be reproducible for re-run |
| Interpreting ambiguous scientific objective | LLM (Claude/GPT-4) | Tail regex cannot handle arbitrary phrasing |
| Decomposing a compound request | LLM | LLM is better at NL decomposition |
| Tool selection based on evidence availability | LLM with structured output | Map evidence profile → tool set |
| Integrating conflicting literature findings | LLM | Requires natural-language synthesis |
| Proposing repair strategies when rule library is empty | LLM | Open-ended hypothesis |
| Generating the final human-readable evidence report | LLM | Template reports lose nuance |
| Escalation packets for human review | LLM drafts, deterministic validator approves | The validator enforces no hallucinated chemistry |

The split is binary: **anything that affects molecular structure or numerical predictions is
deterministic. Anything that affects natural-language interpretation or human-facing
communication can be an LLM, gated by a deterministic validator.**

---

## 8. Minimum Requirements to Earn the Label "Agentic AI"

The reviewer's checklist, audited against current state and against the phased plan:

| Requirement | v0.1 status | v0.2 status | v0.3 status | v0.4 status |
|-------------|-------------|-------------|-------------|-------------|
| Conditional routing (not all 23 nodes always run) | ❌ Absent | ✅ via `EvidenceSufficiencyGate` + conditional edges | ✅ | ✅ |
| Bounded repair loops for warhead, exit-vector, linker failures | ❌ Absent | ✅ via `RepairController(max_repairs=3)` | ✅ | ✅ |
| Dynamic tool selection from evidence availability | ❌ Absent (keyword triggers only) | ✅ deterministic evidence → tool set | ✅ | ✅ |
| Parallel candidate evaluation | ❌ Sequential | ⚠️ Node structure allows it; needs execution backend | ⚠️ | ✅ (Celery/Ray) |
| Uncertainty calibration + applicability-domain detection | ⚠️ Flags exist, no calibration | ✅ Calibrated gates drive routing | ✅ | ✅ (trained model) |
| Candidate-specific evidence graphs | ❌ Shared state | ✅ `CandidateLedger` per candidate | ✅ | ✅ |
| Human approval checkpoints before expensive modeling / final rec | ❌ Absent | ✅ `HumanApprovalGate` node | ✅ | ✅ |
| Multi-objective Pareto ranking | ❌ Weighted composite only | ⚠️ Optional | ⚠️ | ✅ NSGA-II |
| Retrospective benchmarking on known PROTACs | ❌ Absent | ⚠️ Benchmark harness skeleton | ⚠️ | ✅ Full benchmark |
| Ablation against non-agentic pipeline | ❌ Absent | ⚠️ Same codepath with `agentic_mode=false` | ⚠️ | ✅ Published ablation table |

**Labeling rule**:
- v0.1 → "deterministic traceable PROTAC design workflow" (current wording is corrected)
- v0.2 → "adaptive deterministic scientific workflow" (first true routing, no LLM)
- v0.3 → "agent-augmented scientific workflow"
- v0.4 → **"agentic AI platform for PROTAC design"** (only after benchmark + ablation prove the
  agentic architecture adds measurable value on held-out known PROTACs)

"Agentic AI" is the *terminal* label, not the starting one.

---

## 9. What We Will NOT Do

Equally important — these are anti-patterns the critique implicitly warns against and we will
reject explicitly:

1. **We will not put an LLM in front of RDKit.** An LLM cannot generate SMILES that bypass
   validation. The deterministic validator is the gate, not the LLM.
2. **We will not call GPT-4 for routine ranking.** Ranking is a Pareto computation over a
   numerical score vector — it is reproducible and should stay that way.
3. **We will not publish "DC50 = X nM" from the heuristic without the "rule-based score — not a
   validated prediction" banner.** The model_version label stays in the user-facing report.
4. **We will not retire the deterministic pipeline.** It becomes the `agentic_mode=false`
   baseline for every benchmark/ablation and for every user who needs pure reproducibility.
5. **We will not ship Phase 3 (validated models) until Phase 2 (adaptive graph) is done.**
   Adding an ML model on a fixed pipeline only reproduces the same flaw at a different layer —
   you would get a *model* that cannot be repaired, only replaced.

---

## 10. Final Technical Position

The reviewer is right that the system is not agentic. The reviewer is also right that it should
not be rebuilt. The intermediate position — which is the contribution of this document — is:

> **PROTACXtend v0.1 is a provenance-aware, modular, deterministic PROTAC design workflow.**
> **It has all the right deterministic foundations (chemistry engine, stereo engine, linker
> scanner, P4ward, public-data layer, applicability-domain flag, uncertainty flags) to become
> agentic, but it executes those foundations in a fixed sequence instead of an adaptive graph.**
> **The v0.2 milestone is to add the adaptive graph and structured decision log without
> touching the deterministic foundations or invoking any LLM.**
> **The v0.3 milestone is to add a small, scoped LLM layer for NL decomposition and report
> generation, with deterministic validators enforcing every chemical claim.**
> **The v0.4 milestone — and only the v0.4 milestone — earns the label "agentic AI platform
> for PROTAC design", because only then does the agentic architecture have to prove, via
> benchmark + ablation on held-out known PROTACs, that it adds measurable value.**

---

## Appendix A — Verified Code Locations Referenced in This Document

- `graph.py` line ~50-90: hardcoded 23-node pipeline → confirms §2.1
- `graph.py` line ~108-130: `_should_retry` static policy → confirms §2.10
- `base_agent.py` line ~15-44: stub `ReActAgent` → confirms §2.2
- `protac_toolbox.py` `predict_degradation` ~984-1028: heuristic only → confirms §2.3
- `protac_toolbox.py` ~1825/1857-1858: self-documented gaps → confirms §2.3, §2.4, §2.7
- `e3_agent.py` / `toolbox.select_e3_ligands` ~538-584: colocalization table only → confirms §2.5
- `linker_agent.py` / `toolbox.evolve_candidates` ~1375: one-shot linker replacement → confirms §2.6
- `retrosynthesis_filter.py` 17 lines total → confirms §2.7
- `schemas.py` `WorkflowState` single mutable class → confirms §2.8
- `toolbox.add_trace` ~line 2019: free-text traces → confirms §2.9
- `toolbox.rank_candidates` ~1180-1277: weighted composite (not Pareto) → confirms §2.11
- `toolbox.critique_candidates` ~1325-1373: post-hoc review, no repair loop → confirms §2.1

Every claim in this document can be audited from these line numbers against the source code in the
repository as of 2026-07-31.