# PROTACXtend Architecture & the Scientific Contract

**PROTACXtend** runs every request through **one canonical execution stack**
(`protacxtend/canonical/`):

```
User -> Scientific Request Parser -> Orchestrator -> Task Graph
     -> 9 Specialized Scientific Modules -> Tool Executor -> Evidence Store
     -> Critic / Verifier -> Decision Engine -> TherapeuticStrategy
```

See [`CANONICAL_STACK.md`](CANONICAL_STACK.md) (ADR-001) for the decision record
and migration notes. The historical implementations are now **execution
engines** reached through the canonical Tool Executor, not parallel entry
points:

- `protacxtend/agents/graph.py` — the deterministic engine
  (`engine="deterministic"`), a **23-node core scientific workflow** plus **8
  controlled-search/feedback extensions** = **31 documented agent nodes**.
- `protacxtend/agents/agentic_core.py` — the adaptive engine
  (`engine="adaptive"`), a conditional graph over live scientific nodes.
- `protacxtend/agentic/` — deprecated seven-layer wrapper; do not build on it.

`protacxtend.agents.runtime.run_protacpilot(mode=...)` is still the single
runtime entry point and always attaches the canonical critic, module results
and a fully typed `TherapeuticStrategy` to its result. The strategy carries
target validation, E3/warhead/linker/candidate fields, structure/ternary and
degradation assessments, ADME/safety/resistance risks, an experimental plan,
go/no-go criteria, evidence, contradictions, uncertainty and a run manifest —
and is persisted to `outputs/runs/<run_id>/therapeutic_strategy.json`. See
[`CANONICAL_STACK.md`](CANONICAL_STACK.md) for the field reference.

---

## The scientific-contract philosophy

Traditional PROTAC design models operate as opaque black boxes — taking inputs and outputting SMILES strings without explaining *why* a particular linker length was chosen or *how* ternary complex geometry was evaluated.

PROTACXtend transforms every stage into an explicit decision chain:
- **Invisible interactions** → **Visible reasoning traces**
- **Black-box predictions** → **Step-by-step decision chains**
- **Opaque outputs** → **Auditable evidence trails & human escalation gates**

Every executed scientific step records its input, output, evidence source, tool/model
version, confidence, applicability-domain status, warning state and limitation.

```
┌─────────────────────────────────────────────────────────────┐
│                    USER REQUEST                              │
│ "Design CRBN PROTACs for BRD4 degradation"                  │
└────────────────────────┬────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  SUPERVISOR NODE                                            │
│  "Parse objective → extract target/E3/constraints"          │
└────────────────────────┬────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  TARGET RESOLVER (UniProt & AlphaFold API)                  │
│  "BRD4" → ChEMBL lookup → CHEMBL6066530                     │
└────────────────────────┬────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  BINDER RETRIEVAL (ChEMBL + PubChem + BindingDB)            │
│  87 binders found → dedup on InChIKey → 100 unique          │
└────────────────────────┬────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  WARHEAD SELECTION & EXIT VECTOR DETECTION                   │
│  4 top warheads selected by pChembl + exit vector check     │
└────────────────────────┬────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  E3 LIGAND SELECTION (CRBN / VHL / IAP / MDM2)              │
│  CRBN: pomalidomide, lenalidomide (2 curated ligands)       │
└────────────────────────┬────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  LINKER GENERATION (74-method engine: curated, rules, GRU)  │
│  16 linkers: 8 curated + 4 rule-based + 4 generative        │
└────────────────────────┬────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  MOLECULAR CONSTRUCTION & STEREOCHEMISTRY                   │
│  32 candidates assembled → RDKit sanitized & stereoisomers  │
└────────────────────────┬────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  TERNARY COMPLEX FEASIBILITY (P4ward + SE(3) Proxy)         │
│  Geometric proxy score: 0.85 → PROCEED                       │
└────────────────────────┬────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  DEGRADATION PREDICTION (Chemprop Ensemble + TACK)          │
│  Chemprop DC50=14.2nM, Dmax=82%, class=active               │
└────────────────────────┬────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  ADMET & SAFETY RISK EVALUATION                              │
│  hERG=0.02, AMES=0.08, BBB=0.65, Lipinski & Veber OK       │
└────────────────────────┬────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  HUMAN ESCALATION GATE & FINAL REPORT GENERATION            │
│  16 ranked candidates output with markdown report + CSV/JSON│
└────────────────────────┴────────────────────────────────────┘
```

---

## 🧱 31-Node Governed Agent Inventory

PROTACXtend organizes its workflow into **31 specialized agent nodes** registered in `protacxtend/agents/graph.py`, structured into a **23-node core scientific workflow** and **8 controlled-search/feedback extensions**:

### Core Scientific Workflow (Nodes 1–23)
| # | Node Name | Agent Class | Function & Responsibility |
|---|-----------|-------------|---------------------------|
| 1 | `parse_user_request` | `SupervisorAgent` | Extracts target, E3 ligase, cell line, and constraints from natural language. |
| 2 | `create_design_plan` | `DesignPlannerAgent` | Policy engine setting iteration depth, tool selection, retry rules, and stop thresholds. |
| 3 | `control_np_hard_search` | `ControlledSearchAgent` | Resource limits and search budgets across combinatorial and NP-hard spaces. |
| 4 | `safety_precheck` | `SafetyAgent` | Screens SMILES for hazardous substructures, reactive functional groups, and PAINS. |
| 5 | `resolve_target` | `TargetResolverAgent` | Queries UniProt, ChEMBL, and AlphaFold DB for target protein metadata. |
| 6 | `retrieve_target_binders` | `TargetBinderRetrievalAgent` | Pulls bioactivity data from live ChEMBL, PubChem, and BindingDB APIs. |
| 7 | `select_warheads` | `WarheadSelectionAgent` | Filters binders based on pChembl values, selectivity, and attachment points. |
| 8 | `select_e3_ligands` | `E3LigandSelectionAgent` | Selects E3 ligase recruiters (CRBN, VHL, IAP, MDM2) with colocalization scoring. |
| 9 | `detect_exit_vectors` | `ExitVectorDetectionAgent` | RDKit-based detection of solvent-exposed attachment vectors. |
| 10 | `generate_linkers` | `LinkerGenerationAgent` | Generates linkers using 74-method toolbox (curated, rule-based, char-GRU generative). |
| 11 | `construct_protacs` | `MolecularConstructionAgent` | Assembles warhead, linker, and E3 ligand via reaction and assembly strategies. |
| 12 | `expand_stereoisomers` | `StereochemistryEnumerationAgent` | Chiral center detection, E/Z geometry preservation, and stereoisomer enumeration. |
| 13 | `validate_protacs` | `CandidateValidationAgent` | Sanitizes molecules and verifies physicochemical parameter ranges. |
| 14 | `score_cell_context` | `CellContextAgent` | Module 5 DepMap transcriptomic cell-context scoring and cell line compatibility. |
| 15 | `predict_admet` | `ADMETAgent` | Computes hERG inhibition, AMES mutagenicity, BBB permeability, and Lipinski flags. |
| 16 | `check_novelty` | `NoveltyAgent` | Calculates Tanimoto similarity against 485,329 known degrader structures. |
| 17 | `assess_applicability_domain` | `ApplicabilityDomainAgent` | Evaluates model confidence boundaries and flags out-of-domain structures. |
| 18 | `cheap_filter_candidates` | `CheapFilterAgent` | Prunes non-viable candidates before expensive deep evaluation. |
| 19 | `predict_degradation` | `DegradationPredictionAgent` | Module 4 ML ensemble + TACK model for $DC_{50}$ and $D_{\max}$ predictions. |
| 20 | `initial_ranking` | `RankingAgent(final=False)` | Computes initial multi-objective composite score across affinity and 2D properties. |
| 21 | `diversity_clustering` | `ProximityDiversityAgent` | Performs Taylor-Butina clustering ($T \ge 0.62$) to ensure structural diversity. |
| 22 | `reflection_review` | `ReflectionReviewAgent` | Audits reasoning steps for overclaiming or conflicting predictions. |
| 23 | `evolution_refinement` | `EvolutionRefinementAgent` | Executes genetic algorithm operations to optimize linker length and composition. |

### Controlled Search & Feedback Extensions (Nodes 24–31)
| # | Node Name | Agent Class | Function & Responsibility |
|---|-----------|-------------|---------------------------|
| 24 | `select_expensive_modeling_finalists` | `ExpensiveModelingSelectionAgent` | Budget gate pruning candidate pool to top-N finalists for 3D modeling. |
| 25 | `optional_ternary_feasibility` | `TernaryFeasibilityAgent` | 3D ternary complex docking simulation via containerized P4ward & SE(3) proxy. |
| 26 | `predict_cooperativity` | `CooperativityPredictionAgent` | Module 3 ternary complex cooperativity ($\alpha$) surrogate prediction. |
| 27 | `predict_hook_effect` | `HookEffectPredictionAgent` | Module 1 mass-action 3-body equilibrium solver for dose response & hook risk. |
| 28 | `final_ranking` | `RankingAgent(final=True)` | Re-ranks candidates incorporating 3D data and selects diverse Pareto representatives. |
| 29 | `active_learning_update` | `ActiveLearningAgent` | Registers observed feedback into memory for iterative campaign updates. |
| 30 | `generate_report` | `ReportAgent` | Generates structured Markdown reports, CSV spreadsheets, and JSON payloads. |
| 31 | `update_memory` | `MemoryUpdateAgent` | Persists session history and reasoning graphs to disk for future runs. |

---

## 🛠️ Master Toolbox Architecture (`protac_toolbox.py`)

The engine is backed by a **74-method master toolbox** (public methods/functions
defined in `tools/protac_toolbox.py`; AST-counted 2026-09-03) spanning:
1. **RDKit Chemistry Core**: SMILES sanitization, InChIKey indexing, tautomer generation, exit vector mapping.
2. **Stereochemistry Engine**: Chiral center resolution, E/Z geometry control, stereoisomer enumeration.
3. **Linker Scanner**: Systematic $N \times M$ linker attachment scanning and conformational flexibility scoring.
4. **P4ward Wrapper**: 3D ternary complex docking simulation via containerized P4ward pipeline.
5. **ADMET & Safety**: Filter rules for Pan-Assay Interference Compounds (PAINS) and reactive groups.
