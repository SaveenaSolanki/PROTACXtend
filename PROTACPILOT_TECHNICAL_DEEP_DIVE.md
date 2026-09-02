# PROTACXtend — Technical Architecture Deep Dive
## Orchestration, Agent Mechanics, Biology, and Implementation Details

**Document date**: 2026-07-31
 **Scope**: How the 23-node agentic workflow works internally — framework, state model, agent
 execution protocol, model layer, biology pipeline, and what is deterministic vs what needs an LLM.

---

## Table of Contents

1. [Orchestration Framework](#1-orchestration-framework)
2. [State Model & Data Flow](#2-state-model--data-flow)
3. [Agent Execution Protocol (ReAct)](#3-agent-execution-protocol-react)
4. [Per-Agent Technical Detail](#4-per-agent-technical-detail)
5. [Toolbox Layer (73 methods)](#5-toolbox-layer-73-methods)
6. [Biology Pipeline](#6-biology-pipeline)
7. [External API Integration — Technical Detail](#7-external-api-integration--technical-detail)
8. [Deterministic vs LLM-delegated](#8-deterministic-vs-llm-delegated)
9. [Retry & Error Handling](#9-retry--error-handling)
10. [Provenance & Safety Guardrails](#10-provenance--safety-guardrails)
11. [What Is NOT Built (Technical Gaps)](#11-what-is-not-built-technical-gaps)

---

## 1. Orchestration Framework

### 1.1 Engine: LangGraph (with local fallback)

PROTACXtend uses a **state-machine workflow graph** orchestrated by LangGraph when available, with a
deterministic fallback (`LocalSynGlueWorkflowGraph`) that runs in any Python environment without
LangGraph installed.

```python
# synglue_agent/agents/graph.py

class LocalSynGlueWorkflowGraph:
    def __init__(self):
        self.nodes: List[Node] = [
            ("parse_user_request",       SupervisorAgent().run),
            ("create_design_plan",       DesignPlannerAgent().run),
            ("safety_precheck",           SafetyAgent().run),
            ("resolve_target",            TargetResolverAgent().run),
            ("retrieve_target_binders",   TargetBinderRetrievalAgent().run),
            ("select_warheads",           WarheadSelectionAgent().run),
            ("select_e3_ligands",         E3LigandSelectionAgent().run),
            ("detect_exit_vectors",       ExitVectorDetectionAgent().run),
            ("generate_linkers",          LinkerGenerationAgent().run),
            ("construct_protacs",         MolecularConstructionAgent().run),
            ("validate_protacs",          CandidateValidationAgent().run),
            ("predict_degradation",       DegradationPredictionAgent().run),
            ("predict_admet",             ADMETAgent().run),
            ("check_novelty",              NoveltyAgent().run),
            ("assess_applicability",      ApplicabilityDomainAgent().run),
            ("initial_ranking",           RankingAgent(final=False).run),
            ("diversity_clustering",      ProximityDiversityAgent().run),
            ("reflection_review",          ReflectionReviewAgent().run),
            ("evolution_refinement",      EvolutionRefinementAgent().run),
            ("optional_ternary_feasibility", TernaryFeasibilityAgent().run),
            ("final_ranking",             RankingAgent(final=True).run),
            ("generate_report",           ReportAgent().run),
            ("update_memory",              MemoryUpdateAgent().run),
        ]
```

### 1.2 Execution loop

The graph runs a **simple sequential pipeline** — not a branching DAG. Each node receives the
global `WorkflowState`, executes, and returns the updated state:

```
state = WorkflowState(user_request="...")
for node_name, node_fn in self.nodes:
    state = node_fn(state)              # ← each agent mutates state
    if self._should_retry(node_name, state):
        state = node_fn(state)          # ← retry once
    if self._should_stop(state):
        break                            # ← early terminate
```

**Key design choices:**

| Choice | Rationale |
|--------|-----------|
| Sequential, not parallel | Each agent depends on prior output (warhead selection needs target resolution) |
| Shared mutable state | Avoids message-passing overhead; matches LangGraph `StateGraph` semantics |
| No LLM in the loop (default) | All 23 agents are **deterministic** Python code — no model calls required |
| Retry on missing output | `DesignPlannerAgent` sets retryable steps; graph retries once if output is empty |
| Early stop on fatal errors | Missing target, no warheads, no candidates, no valid candidates → stops pipeline |

### 1.3 LangGraph integration

When `langgraph` is installed, the same 23 nodes are compiled into a `StateGraph`:

```python
def build_langgraph_workflow():
    from langgraph.graph import END, StateGraph
    graph = StateGraph(WorkflowState)
    for name, node in local.nodes:
        graph.add_node(name, node)
    graph.set_entry_point(ordered[0])
    for current, nxt in zip(ordered, ordered[1:]):
        graph.add_edge(current, nxt)
    graph.add_edge(ordered[-1], END)
    return graph.compile()
```

This means the workflow can run as a **LangGraph state machine** in production (with checkpointing,
streaming, human-in-the-loop interrupts) or as a **plain Python loop** in minimal environments.

### 1.4 Adapter hooks for production frameworks

The codebase includes stub adapters for:
- **Agno** (`AgnoSupervisorAdapter`) — delegates to an Agno team callable
- **LangChain** (`LangChainToolAdapter`) — wraps a function as a `.invoke()`-compatible tool

These are intentionally lightweight so the project imports without those frameworks installed.

---

## 2. State Model & Data Flow

### 2.1 WorkflowState — the central data container

```python
# synglue_agent/backend/schemas.py

class WorkflowState(BaseModel):
    # ── Input ──
    user_request: str

    # ── Parsed objective ──
    parsed_objective: ParsedObjective          # target, warhead, E3, linker prefs, constraints

    # ── Plan ──
    design_plan: dict = {}                     # tools, retry policy, stop conditions

    # ── Target ──
    target_record: TargetRecord | None = None  # uniprot_id, gene, organism, AlphaFold
    retrieved_binders: list[BinderRecord] = [] # ChEMBL/PubChem/BindingDB results

    # ── Components ──
    selected_warheads: list[WarheadRecord] = []
    selected_e3_ligands: list[E3LigandRecord] = []
    exit_vectors: list[ExitVectorRecord] = []
    generated_linkers: list[LinkerRecord] = []

    # ── Candidates ──
    construction_attempts: list[ConstructionAttempt] = []
    assembled_candidates: list[CandidateRecord] = []
    valid_candidates: list[CandidateRecord] = []

    # ── Predictions ──
    degradation_predictions: list[DegradationPrediction] = []
    admet_predictions: list[ADMETPrediction] = []
    novelty_results: list[NoveltyResult] = []
    applicability_domain: list[ApplicabilityDomainResult] = []
    ternary_feasibility_results: list[TernaryFeasibilityResult] = []

    # ── Ranking ──
    ranking_results: list[RankingResult] = []
    diversity_clusters: list[DiversityCluster] = []
    reflection_reviews: list[ReflectionReview] = []
    final_ranked_candidates: list[RankingResult] = []

    # ── Output ──
    report: str = ""
    pipeline_status: list[dict] = []
    traces: list[AgentTrace] = []

    # ── Diagnostics ──
    warnings: list[str] = []
    errors: list[str] = []
```

### 2.2 Data flow diagram

```
User Request
    │
    ▼
┌──────────────┐     ┌──────────────────┐     ┌────────────────┐
│ Supervisor   │────▶│ DesignPlanner    │────▶│ SafetyAgent    │
│ (regex NL    │     │ (policy engine)  │     │ (hazard check) │
│  parser)     │     │                  │     │                │
└──────────────┘     └──────────────────┘     └────────────────┘
    │ parsed_objective    │ design_plan             │ warnings
    ▼                     ▼                         ▼
┌──────────────┐     ┌──────────────────┐
│ TargetResolver│────▶│ BinderRetrieval  │
│ (UniProt API) │     │ (ChEMBL+PubChem+ │
│ + AlphaFold   │     │  BindingDB APIs) │
└──────────────┘     └──────────────────┘
    │ target_record       │ retrieved_binders
    ▼                     ▼
┌──────────────┐     ┌──────────────────┐     ┌────────────────┐
│ WarheadSelect │────▶│ E3LigandSelect   │────▶│ ExitVector     │
│ (library +    │     │ (colocalization  │     │ Detection      │
│  user input)  │     │  scoring)        │     │ (RDKit atoms)  │
└──────────────┘     └──────────────────┘     └────────────────┘
    │ selected_warheads   │ selected_e3_ligands    │ exit_vectors
    ▼                     ▼                         ▼
                   ┌──────────────────┐
                   │ LinkerGeneration │
                   │ (12+ types)      │
                   └──────────────────┘
                            │ generated_linkers
                            ▼
                   ┌──────────────────┐
                   │ Construction     │────▶ validate ──▶ predict ──▶ rank
                   │ (3 strategies)   │     │           │           │
                   └──────────────────┘     ▼           ▼           ▼
                                     CandidateRecord  ADMET  Degradation  Ranking
                                                                │
                                                                ▼
                                                     Ternary (optional)
                                                     Diversity → Reflection
                                                     FinalRank → Report → Memory
```

### 2.3 Pydantic compatibility layer

The schemas use Pydantic when available, but ship a **fallback `BaseModel`** so the code runs
even without Pydantic installed:

```python
try:
    from pydantic import BaseModel, Field
    PYDANTIC_AVAILABLE = True
except Exception:
    class BaseModel:  # minimal fallback
        def __init__(self, **data): ...
        def model_dump(self): ...
```

This means:
- **Production**: Full Pydantic validation, serialization, JSON schema
- **Minimal env**: Plain Python attributes, `model_dump()` still works

---

## 3. Agent Execution Protocol (ReAct)

### 3.1 Base class: `ReActAgent`

Every agent extends the same base:

```python
class ReActAgent:
    name = "ReActAgent"
    thought = "Use deterministic SynGlue tools."
    action = "run"

    def __init__(self, toolbox: ProtacDesignToolbox | None = None):
        self.toolbox = toolbox or ProtacDesignToolbox()

    def run(self, state: WorkflowState) -> WorkflowState:
        started = time.time()
        try:
            state = self._execute(state)          # ← agent logic
            observation = self._observation(state) # ← summarize what happened
        except Exception as exc:
            state.errors.append(f"{self.name}: {exc}")
            observation = f"error={exc}"
        self.toolbox.add_trace(state, self.name, self.thought,
                              self.action, observation, time.time() - started)
        return state

    def _execute(self, state): return state        # ← override
    def _observation(self, state): return "completed"
```

### 3.2 The ReAct pattern (Thought → Action → Observation)

Each agent produces a **trace** with three fields:

| Field | What goes in it | Example |
|-------|-----------------|---------|
| `thought` | Scientific reasoning (class attribute) | "Resolve target gene to UniProt entry and AlphaFold structure." |
| `action` | Tool call name (class attribute) | "resolve_target" |
| `observation` | Quantitative summary of what happened | "uniprot=P09429, gene=HMGB2" |

The trace is stored in `state.traces` for the final report. This is the **same pattern** as an LLM
ReAct agent, but here it runs deterministically — no language model in the loop by default.

### 3.3 Where does the LLM come in?

**Nowhere by default.** All 23 agents are pure Python.

The `AgentProtocol` and `AgnoSupervisorAdapter` / `LangChainToolAdapter` classes exist as **hooks**
for production deployment where the agent logic could be delegated to an LLM (e.g., GPT-4 for
natural-language parsing, or Claude for report writing). But the local execution uses zero LLM calls.

### 3.4 The system prompt (for production LLM mode)

```python
SUPERVISOR_SYSTEM_PROMPT = """You are SynGlue-Agent, a PROTAC design co-scientist.
Plan tool use, never invent chemistry, never report predictions as experiments,
and require human expert review before synthesis or wet-lab work."""

SAFETY_GUARDRAILS = [
    "Never invent final SMILES manually.",
    "Never invent potency or degradation values.",
    "Never present predictions as experimental validation.",
    "Always report model version and provenance.",
    ...
]
```

These exist for when someone plugs in an actual LLM — the guardrails ensure the model never
fabricates chemistry.

---

## 4. Per-Agent Technical Detail

### 4.1 SupervisorAgent (NL Parser)

| Aspect | Detail |
|--------|--------|
| **Model** | None (regex + keyword extraction) |
| **Input** | `state.user_request` (natural language string) |
| **Method** | `toolbox.parse_user_request()` — regex patterns for target, E3, SMILES, linker types, ADMET constraints |
| **Output** | `ParsedObjective` with: `target_name`, `warhead_smiles`, `e3_ligase`, `preferred_linker_types`, `candidate_count`, `admet_constraints`, `optimization_objective` |
| **Parsing logic** | Regex: `\bfor\s+([A-Za-z0-9\-]+)` → target; `SMILES[:=]?` → warhead; keyword scan for CRBN/VHL/IAP/MDM2; `PEG`/`alkyl`/`triazole` → linker types; `(\d+)\s+candidates` → count |

### 4.2 DesignPlannerAgent (Policy Engine)

| Aspect | Detail |
|--------|--------|
| **Model** | None (deterministic rules) |
| **Input** | `ParsedObjective` + `user_request` |
| **Output** | `design_plan` dict with: `tools_to_call`, `repeat_policy`, `external_evidence_policy`, `stop_conditions`, `scientific_invalidity_rules`, `deeper_validation`, `candidate_budget` |
| **Logic** | Checks for keywords: `DOCK`/`TERNARY`/`POSE` → enable docking; `RETROSYNTHESIS`/`SYNTHESIS` → enable retrosynthesis; `ADME`/`HERG`/`AMES`/`DILI` → enable strict ADMET |
| **Retry policy** | `max_retries_per_step=1`, retryable steps: resolve_target, retrieve_binders, predict_degradation, predict_admet, ternary_feasibility |

### 4.3 TargetResolverAgent (UniProt + AlphaFold)

| Aspect | Detail |
|--------|--------|
| **Model** | None (REST API client) |
| **API 1** | `https://rest.uniprot.org/uniprotkb/search?query={target_name}&format=json&size=1` — resolves gene name → UniProt entry |
| **API 2** | `https://alphafold.ebi.ac.uk/api/prediction/{uniprot_id}` — fetches AlphaFold predicted structure URL |
| **Fallback** | Appends `AND+organism_id:9606` (human) if first search fails |
| **Local data** | `curated_targets.csv` (4 targets with druggability/tractability annotations) |
| **Timeout** | 15s per API call |
| **Output** | `TargetRecord(uniprot_id, gene_symbol, target_name, organism, alphafold_id, external_ids)` |

### 4.4 TargetBinderRetrievalAgent (ChEMBL + PubChem + BindingDB)

| Aspect | Detail |
|--------|--------|
| **Model** | None (REST API client) |
| **API 1** | ChEMBL: `ebi.ac.uk/chembl/api/data` — target search → assay search → activity fetch → molecule SMILES |
| **API 2** | PubChem: `pubchem.ncbi.nlm.nih.gov/rest/pug` — enriches existing binders with InChIKey + MW |
| **API 3** | BindingDB: `bindingdb.org/rest/getLigandsByUniprot?uniprot={id}` — Ki/IC50 data |
| **Rate limiting** | 2 req/s (`DELAY=0.5`), 30s timeout, 5 retries with exponential backoff (`DELAY * 2^attempt`) |
| **Caching** | In-memory dict (`_cache`) keyed by MD5 of URL |
| **Fallback** | Local `curated_warheads.csv` if no remote binders found |
| **Dedup** | By canonical SMILES, sorted by `p_activity` (best first), capped at 100 |
| **Output** | `List[BinderRecord]` (name, smiles, activity_type, activity_nM, p_activity, source) |

### 4.5 WarheadSelectionAgent

| Aspect | Detail |
|--------|--------|
| **Model** | None (library lookup + user input fusion) |
| **Input** | `ParsedObjective.warhead_smiles` (if user provided) + `retrieved_binders` (from ChEMBL) + `curated_warheads.csv` |
| **Logic** | If user provides SMILES → validate + add. If not, use top retrieved binders. Score by potency (`compute_p_activity`). |
| **Output** | `List[WarheadRecord]` with name, smiles, source, potency |

### 4.6 E3LigandSelectionAgent

| Aspect | Detail |
|--------|--------|
| **Model** | None (colocalization rules) |
| **Input** | `ParsedObjective.e3_ligase` + target subcellular location |
| **Logic** | CRBN = nuclear accessible; VHL = cytoplasmic/nuclear; cIAP = cytoplasmic; MDM2 = nuclear. Scoring by colocalization match. |
| **Data** | `curated_e3_ligands.csv` (8 ligands: pomalidomide, lenalidomide, VH032, etc.) |
| **Output** | `List[E3LigandRecord]` |

### 4.7 ExitVectorDetectionAgent

| Aspect | Detail |
|--------|--------|
| **Model** | None (RDKit atom analysis) |
| **Input** | Warhead + E3 ligand SMILES |
| **Logic** | Uses RDKit: find atoms with `GetDegree()==1` that are O (OH) or N (NH), or peripheral aromatic C-H. Scores by solvent exposure. |
| **Output** | `List[ExitVectorRecord]` (atom_index, confidence, role) |
| **Stereo awareness** | Uses `stereochemistry_engine.find_attachment_stereo_impact()` to flag inversion risk |

### 4.8 LinkerGenerationAgent

| Aspect | Detail |
|--------|--------|
| **Model** | None (curated + rule-based generation) |
| **Input** | `ParsedObjective.preferred_linker_types` |
| **Methods** | `toolbox.generate_linkers()` — loads from `curated_linkers.csv` + `generate_rule_based_linkers()` (generates PEG/alkyl/triazole/piperazine variants programmatically) |
| **Output** | `List[LinkerRecord]` with name, smiles, class, heavy_atoms, effective_length_A |
| **Linker types** | PEG3-PEG7, C4-C14 alkyl, piperazine, triazole, semi-rigid, mixed polar |

### 4.9 MolecularConstructionAgent

| Aspect | Detail |
|--------|--------|
| **Model** | None (RDKit chemical assembly) |
| **Input** | Warhead + linker + E3 SMILES (with attachment markers `[*:1]`, `[*:2]`) |
| **Strategies** | 3 assembly approaches: (1) SMILES concatenation, (2) RDKit `editable_mol` dummy atom joining, (3) reaction SMARTS |
| **Output** | `List[ConstructionAttempt]` → `List[CandidateRecord]` (full PROTAC SMILES) |

### 4.10 DegradationPredictionAgent ⚠️

| Aspect | Detail |
|--------|--------|
| **Model** | **Heuristic only** — `toolbox.predict_degradation()` |
| **Input** | Candidate SMILES + target/E3 info |
| **Logic** | Heuristic scoring based on: MW (penalize >1200), linker length (optimal 12-20 atoms), TPSA (penalize >250), HBD (penalize >5). Returns pseudo DC50/Dmax. |
| **WARNING** | No trained ML model. Values are heuristic estimates, NOT experimental predictions. |
| **Output** | `List[DegradationPrediction]` (DC50_nM, Dmax_percent, confidence, model_version="SynGlue-demo-heuristic-v0.1") |

### 4.11 ADMETAgent

| Aspect | Detail |
|--------|--------|
| **Model** | None (RDKit descriptors + risk heuristics) |
| **Input** | Candidate SMILES |
| **Computed** | MW, logP, TPSA, HBD, HBA, RotB (via RDKit `Descriptors`), bRo5 compliance, hERG/AMES/DILI risk flags (heuristic) |
| **Output** | `List[ADMETPrediction]` |

### 4.12 TernaryFeasibilityAgent

| Aspect | Detail |
|--------|--------|
| **Model** | P4ward (Docker) or geometric proxy |
| **Mode 1** | Geometric proxy (`ternary_feasibility.py`, 332 lines): exit vector angles, linker reachability, fast |
| **Mode 2** | P4ward Docker (`p4ward_wrapper.py`, 1200 lines): 3600 poses × minimization, 2-4 hours |
| **Output** | `List[TernaryFeasibilityResult]` (ternary_score, interface_complementarity, lysine_distances) |

---

## 5. Toolbox Layer (73 methods)

The `ProtacDesignToolbox` class (`protac_toolbox.py`, 2028 lines) is the **single engine** behind
most agents. Agents are thin wrappers that call toolbox methods:

```python
class ReActAgent:
    def __init__(self):
        self.toolbox = ProtacDesignToolbox()  # ← shared toolbox instance
```

### Method categories

| Category | Methods | Called by |
|----------|---------|-----------|
| Data loading (7) | `load_table`, `load_curated_targets/warheads/e3_ligands/linkers`, `load_known_protacs`, `load_external_warhead_seed` | All agents |
| Request parsing (2) | `parse_user_request`, `safety_precheck` | Supervisor, Safety |
| Target resolution (3) | `resolve_target`, `retrieve_known_binders`, `_retrieve_external_seed_binders` | Target, Binder |
| Selection (5) | `mine_external_binders`, `compute_p_activity`, `select_warheads`, `score_warhead_potency`, `select_e3_ligands` | Warhead, E3 |
| Exit vectors & linkers (5) | `detect_exit_vectors`, `generate_linkers`, `generate_rule_based_linkers`, `remove_duplicate_linkers`, `state_of_the_art_tool_catalog` | ExitVector, Linker |
| Construction (3) | `construct_protac_candidates`, `assemble_components`, `_join_on_dummy` | Construction |
| Validation (6) | `validate_smiles`, `validate_linker`, `canonicalize_smiles`, `compute_basic_properties`, `validate_candidates`, `remove_duplicate_candidates` | Validation |
| Prediction (5) | `predict_degradation`, `predict_admet`, `_risk_label`, `check_novelty`, `calculate_similarity` | Degradation, ADMET, Novelty |
| Ranking (8) | `rank_candidates`, `compute_dc50_score`, `compute_dmax_score`, `assign_candidate_tier`, `cluster_candidates`, `choose_diverse_representatives`, `critique_candidates`, `evolve_candidates` | Ranking, Diversity, Reflection, Evolution |
| Reporting (7) | `generate_candidate_table`, `generate_agent_workflow_table`, `generate_pipeline_status_table`, `generate_markdown_report`, `export_csv`, `export_json`, `write_workflow_memory` | Report, Memory |
| Tracing (1) | `add_trace` | All agents |
| Internal (8) | `_safe_float`, `_safe_int`, `_clamp`, `_norm_name`, `_has_attachment`, `_remove_attachment_markers`, `_annotate_hypothetical_attachment`, `_stable_id` | Toolbox internal |

---

## 6. Biology Pipeline

### 6.1 The PROTAC degradation mechanism

```
Cell
 │
 ├── PROTAC enters cell (must be permeable — bRo5 challenge)
 │
 ├── PROTAC binds POI (warhead → target protein, K_D^wh)
 │
 ├── PROTAC binds E3 ligase (anchor → E3, K_D^e3)
 │
 ├── TERNARY COMPLEX forms (POI–PROTAC–E3)
 │   ├── New PPI interface created (not natural)
 │   ├── Linker may engage contacts with both proteins
 │   └── Cooperativity α: K_D^ternary ≠ K_D^wh × K_D^e3
 │
 ├── E2~Ub loads onto E3 ligase complex
 │
 ├── Ubiquitin transfer to surface LYSINE on POI
 │   ├── Lysine must be ≤13 Å from E2 catalytic CYS
 │   ├── Lysine must be solvent-accessible
 │   └── Multiple ubiquitination → poly-Ub chain
 │
 ├── 26S Proteasome recognizes poly-Ub → DEGRADATION
 │
 └── PROTAC released (catalytic — one PROTAC degrades many POIs)
```

### 6.2 How each NP-hard problem maps to PROTACXtend

| NP-hard problem | Biology | PROTACXtend module |
|-----------------|---------|---------------------|
| Linker optimization | Same warhead+E3, different linker → different degradation. Single atom matters. | `linker_scanner.py` (scan+score), `p4ward_wrapper.py` (full ternary) |
| E3 sparsity | 600+ E3 ligases, only 4 usable. Limiting reagent. | `e3_agent.py` (selects from 4 available) |
| Ternary complex | 3-body protein-ligand-protein system. Non-convex. | `ternary_feasibility.py` (proxy), `p4ward_wrapper.py` (full) |
| Cooperativity α | Emergent from PPI + linker contacts. Not pairwise additive. | Not built (needs ITC + crystal data) |
| Lysine proximity | Constraint: Lys NZ ≤13 Å from E2 catalytic CYS. | Not built |
| Hook effect | Dose-response is non-monotonic. Saturation kills ternary complex. | Not built |
| bRo5 | PROTACs violate Lipinski. MW 700-1200. | `admet_predictors.py` |
| Stereochemistry | Each chiral center doubles search space. | `stereochemistry_engine.py` |

### 6.3 The HMGB2-ICM case study biology

| BIOLOGY FACT | EVIDENCE |
|--------------|---------|
| ICM binds HMGB2 Box A | Lee et al. 2014, *Nat Chem Biol* — ICM-BP fluorescent probe |
| ICM is **buried** in HMGB2 pocket | PyMOL visualization: OH27/OH29 point into protein |
| OH groups are NOT solvent-exposed | Cannot serve as exit vectors → H1 REJECTED (0/3600) |
| N-phenyl position IS solvent-exposed | Lee 2014 ICM-BP probe proved this — phenyl is modifiable |
| A1_4COOH forms salt bridge to LYS8 | COO⁻ ↔ LYS8 NZ at 3.8 Å (electrostatic) |
| Predicted Kd ~100 nM | ε=25 (surface salt bridge), honest range 10-500 nM |
| P4ward geometric screen | A1_4COOH: 8-16/3600 passes (vs 0 for OH27) |
| ICM alone is NOT a molecular glue | 0/20 poses show ICM-CRBN contact (H3 REJECTED) |

---

## 7. External API Integration — Technical Detail

### 7.1 Rate limiting

```python
_last_request_time = 0.0
DELAY = 0.5  # 2 requests per second

def _rate_limit():
    global _last_request_time
    now = time.time()
    elapsed = now - _last_request_time
    if elapsed < DELAY:
        time.sleep(DELAY - elapsed)
    _last_request_time = time.time()
```

### 7.2 Retry with exponential backoff

```python
MAX_RETRIES = 5

for attempt in range(1, MAX_RETRIES + 1):
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            _cache[cache_key] = data  # ← cache hit on success
            return data
    except (HTTPError, URLError, OSError, JSONDecodeError) as e:
        if attempt < MAX_RETRIES:
            time.sleep(DELAY * (2 ** attempt))  # ← 0.5, 1.0, 2.0, 4.0, 8.0s
```

### 7.3 Caching

- In-memory dict `_cache` keyed by `hashlib.md5(url.encode()).hexdigest()`
- Cache survives across agent calls within a single workflow run
- No TTL — cache is cleared on process restart

### 7.4 API endpoints used

| API | Base URL | Auth | Rate limit | Used for |
|-----|----------|------|------------|----------|
| UniProt | `rest.uniprot.org/uniprotkb` | None | 2 req/s | Target → UniProt ID |
| AlphaFold | `alphafold.ebi.ac.uk/api` | None | 2 req/s | Structure URL |
| ChEMBL | `ebi.ac.uk/chembl/api/data` | None | 2 req/s | Target → assays → activities → SMILES |
| PubChem | `pubchem.ncbi.nlm.nih.gov/rest/pug` | None | 2 req/s | SMILES → InChIKey + MW |
| BindingDB | `bindingdb.org/rest` | None | 2 req/s | UniProt → Ki/IC50 ligands |
| RCSB PDB | `data.rcsb.org/rest/v1` | None | 2 req/s | Structure retrieval |

### 7.5 ChEMBL multi-step query

The ChEMBL search is a **4-step chain**:

```
Step 1: target/search?q={target_name}       → target_chembl_id
Step 2: assay.json?target_chembl_id={id}     → list of assay_chembl_ids
Step 3: assay/{assay_id}/activity.json       → list of activities (IC50, Ki)
Step 4: molecule/{molecule_chembl_id}.json   → canonical SMILES
```

Each step is rate-limited, cached, and retried.

---

## 8. Deterministic vs LLM-Delegated

### 8.1 Current state: 100% deterministic

**No LLM is used in the default PROTACXtend workflow.** Every agent is pure Python:

| Component | Implementation | LLM? |
|-----------|---------------|------|
| NL parsing | Regex + keyword extraction | ❌ No |
| Target resolution | UniProt REST API | ❌ No |
| Binder retrieval | ChEMBL/PubChem/BindingDB APIs | ❌ No |
| Warhead/E3 selection | Library lookup + colocalization rules | ❌ No |
| Exit vector detection | RDKit atom analysis | ❌ No |
| Linker generation | Curated CSV + rule-based generation | ❌ No |
| PROTAC construction | RDKit SMILES assembly | ❌ No |
| Degradation prediction | Heuristic scoring | ❌ No |
| ADMET | RDKit descriptors + risk heuristics | ❌ No |
| Ranking | Weighted composite formula | ❌ No |
| Report | Template + table generation | ❌ No |

### 8.2 Where LLMs would plug in (production mode)

The architecture is designed for LLM augmentation without rewriting:

| Agent | Current (deterministic) | Production (LLM) |
|-------|------------------------|-------------------|
| SupervisorAgent | Regex parsing | GPT-4/Claude NL understanding |
| DesignPlannerAgent | Rule-based plan | LLM policy reasoning |
| ReflectionReviewAgent | Deterministic critique | LLM scientific critique |
| ReportAgent | Template | LLM natural-language report |
| NoveltyAgent | Tanimoto only | LLM literature scan + patent search |

The `AgnoSupervisorAdapter` and `LangChainToolAdapter` are the hooks for this.

### 8.3 Why deterministic is the right default

1. **Reproducibility** — same input → same output, every time
2. **No API cost** — zero LLM tokens consumed
3. **No hallucination** — chemistry is validated by RDKit, not generated by a model
4. **Testable** — every agent has deterministic unit tests
5. **Offline** — runs without internet (except API-based agents)

---

## 9. Retry & Error Handling

### 9.1 Graph-level retry

```python
def _should_retry(self, node_name, state, retry_counts):
    plan = state.design_plan or {}
    retry_policy = plan.get("repeat_policy", {})
    retryable_steps = set(retry_policy.get("retryable_steps", []))
    max_retries = int(retry_policy.get("max_retries_per_step", 0))

    if node_name not in retryable_steps:
        return False
    if retry_counts.get(node_name, 0) >= max_retries:
        return False
    return self._step_output_missing(node_name, state)
```

Retryable steps (set by DesignPlannerAgent):
- `resolve_target` — retry if `target_record` is None
- `retrieve_target_binders` — retry if no binders and no user warhead
- `predict_degradation` — retry if candidates exist but no predictions
- `predict_admet` — retry if candidates exist but no ADMET
- `optional_ternary_feasibility` — retry if ranking exists but no ternary data

### 9.2 Early stop conditions

```python
terminal_errors = [
    "Planner requires a target protein/gene",  # no target → can't proceed
    "No warheads selected",                     # nothing to build from
    "No E3 ligands selected",
    "No PROTAC candidates assembled",
    "No valid or unverified candidates",
]
if any(marker in error for error in state.errors):
    break  # ← stop pipeline
```

### 9.3 Agent-level error capture

```python
def run(self, state):
    try:
        state = self._execute(state)
    except Exception as exc:
        state.errors.append(f"{self.name}: {exc}")
    self.toolbox.add_trace(...)  # ← still logs the error
    return state
```

Every agent catches its own exceptions and logs them as traces + state errors. The pipeline continues
unless a terminal error is hit.

---

## 10. Provenance & Safety Guardrails

### 10.1 Provenance tracking

Every prediction carries its source:

```python
class DegradationPrediction(BaseModel):
    dc50_nM: Optional[float]
    dmax_percent: Optional[float]
    model_version: str          # "SynGlue-demo-heuristic-v0.1"
    confidence: float           # 0-1
    rationale: str             # human-readable explanation
```

```python
class BinderRecord(BaseModel):
    smiles: str
    activity_nM: Optional[float]
    source: str                # "ChEMBL (assay CHEMBL1234)" / "BindingDB" / "local_curated"
```

### 10.2 Safety guardrails

```python
SAFETY_GUARDRAILS = [
    "Never invent final SMILES manually.",
    "Never invent potency or degradation values.",
    "Never present predictions as experimental validation.",
    "Always report model version and provenance.",
    "Always validate molecules before prediction.",
    "Always flag out-of-domain and low-confidence predictions.",
    "Always separate computational prioritization from synthesis recommendation.",
    "Require human expert review before synthesis or wet-lab testing.",
]
```

### 10.3 Scientific invalidity rules (from planner)

```python
"scientific_invalidity_rules": [
    "Reject invalid RDKit molecules when RDKit validation is available.",
    "Flag candidates with hypothetical or ambiguous exit vectors for chemist review.",
    "Do not treat heuristic DC50/Dmax values as trained-model predictions.",
    "Penalize high hERG, AMES, DILI, solubility, or permeability risk rather than hiding the candidate.",
    "Require human review before synthesis, wet-lab testing, dosing, or biological claims.",
]
```

---

## 11. What Is NOT Built (Technical Gaps)

| Gap | What's missing | Technical requirement |
|-----|----------------|----------------------|
| **Trained degradation ML model** | The `DegradationPredictionAgent` uses a heuristic. No D-MPNN, no graph neural network, no transformer. | Need: 500+ PROTACs with DC50/Dmax labels, featurization (graph + protein), Chemprop or custom D-MPNN, training infrastructure |
| **Cooperativity (α) predictor** | No model maps ternary complex structure → α value | Need: ternary complex ITC data + crystal structures, featurization of PPI interface + linker contacts |
| **Lysine proximity scorer** | No module enumerates target surface lysines and checks distance to E2 catalytic CYS | Need: E3-E2 structural templates, BioPython/PyMOL for surface lysine enumeration, distance calculation |
| **Hook effect modeler** | No dose-response curve fitting | Need: Douglass 3-body equilibrium model (JACS 2013), fitted α per PROTAC, multi-dose degradation data |
| **Novel E3 ligand discovery** | Only 4/600 E3 ligands are usable | Need: covalent fragment screening data, E3结构生物学, novel ligand development |
| **Active learning loop** | No intelligent experiment selection | Need: Bayesian optimization, synthesis cost model, experimental feedback interface |
| **Proteotype selectivity** | Same PROTAC may behave differently in different cells | Need: proteomics data (DepMap, CPTAC), E3/POI expression matrices per cell line |

---

## Summary

**PROTACXtend is a 100% deterministic agentic workflow** — no LLM calls by default. It uses:
- **LangGraph** (with local Python fallback) for 23-node sequential orchestration
- **ReAct pattern** (Thought → Action → Observation) for every agent, stored as traces
- **Pydantic** (with fallback) for 19 typed schemas passed as shared mutable state
- **RDKit** as the core chemistry engine (SMILES, stereochemistry, descriptors, assembly)
- **6 free public APIs** (UniProt, AlphaFold, ChEMBL, PubChem, BindingDB, RCSB) with rate limiting, caching, and exponential backoff
- **Heuristic degradation prediction** (no ML model — explicitly labeled as such)
- **P4ward** (Docker) for full ternary complex simulation when requested
- **Safety guardrails** that prevent hallucinated chemistry and require human review

The architecture is designed to **plug in LLMs** (GPT-4, Claude, Agno teams, LangChain tools)
without rewriting — but runs fully deterministic by default for reproducibility, cost, and safety.