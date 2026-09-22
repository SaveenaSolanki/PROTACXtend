# TECHNICAL COHERENCE & AGENT_TOOLKIT AUDIT REPORT
**PROTACXtend (formerly ProtacPilot) — Architecture, Implementation Status, Gap Analysis, and Technical Review**

- **Date:** 2026-09-04
- **Repository:** `the-ahuja-lab/PROTACXtend` (`/storage/saveena/protacpilot`)
- **Reference Blueprint:** `Agent_Toolkit.xlsx` (Created 2026-07-31)
- **Source of Truth Documents:** `config/scientific_status.yaml`, `protacxtend/modules/PROTACXTEND_MODULE_BUILD.md`, `protacxtend/agents/graph.py`, `NP_HARD_AGENT_DESIGN.md`, `CODE_REPORT_2026-09-02.md`, `TECHNICAL_COHERENCE_REVIEW.md`

---

## 1. Executive Summary & Evolution Overview

### 1.1 Project Identity & Progression
The platform originally conceptualized as **ProtacPilot** (documented in `Agent_Toolkit.xlsx` on 2026-07-31) has evolved into **PROTACXtend** (software release v0.3 core release, September 2026). It is an autonomous, tool-augmented, agentic research platform for targeted protein degradation (TPD). 

Unlike conventional "black-box" generative models or blind screening scripts, PROTACXtend executes an explicit, governed **scientific contract**:
- Every scientific decision (target selection, exit vector determination, linker design, ternary docking, degradation prediction, ADMET screening) produces an auditable trace with evidence provenance, confidence scores, applicability domain flags, and limitation warnings.
- The system operates by default as a **deterministic ReAct-style agentic workflow** requiring **no external hosted LLM API** (no OpenAI/Anthropic/Gemini keys required in the core loop), preventing wet-lab hallucination.
- Execution is governed by a **31-node directed graph** (23 core scientific nodes + 8 controlled-search/feedback extensions) implemented in `protacxtend/agents/graph.py`.

### 1.2 Current State Snapshot (2026-09-04)
- **Agent Nodes:** 31 registered agent nodes (23 core scientific nodes + 8 search/feedback extension nodes) in `protacxtend/agents/graph.py`.
- **Chemistry Engine:** 74 public callable methods (96 total functions) in `protacxtend/tools/protac_toolbox.py`.
- **Scientific Modules (M1–M7):** Modules M1 through M6 are fully implemented; M1, M4, M5 are validated/trained and publicly claimed; M2 and M3 are structural/data-gated surrogates; M6 is code-complete but report-gated; M7 is active-learning CLI only.
- **Test Suite Health:** 
  - **Module Tests:** 95/95 passing unit tests (M1: 24, M2: 8, M3: 21, M4: 9, M5: 16, M6: 17).
  - **Integration & Orchestration Tests (`tests/`):** 144/144 passing tests (100% pass rate).
  - **Core Tests (`protacxtend/tests/`):** 423 passing unit tests (with 5 isolated test failures identified and diagnosed during audit).
  - **Total Passing Tests:** **662 automated tests passing**.
- **Machine Learning Artifacts:** 7 trained models committed directly to the repository (no external download required for core evaluation).

---

## 2. In-Depth Coherence Audit: `Agent_Toolkit.xlsx` vs. Current Codebase

`Agent_Toolkit.xlsx` served as the foundational blueprint for the platform. Below is a sheet-by-sheet technical reconciliation between what was specified on 2026-07-31 and what is implemented today on 2026-09-04.

```
┌───────────────────────────────────────────────────────────────────────────────────┐
│                           AGENT_TOOLKIT.XLSX MAPPING                             │
├───────────────────────┬───────────────────────┬───────────────────────────────────┤
│ Blueprint Sheet       │ Planned / Specified   │ Current Implementation Status     │
├───────────────────────┼───────────────────────┼───────────────────────────────────┤
│ Modalities            │ 18 TPD modalities     │ PROTAC: 100% full pipeline       │
│                       │                       │ Molecular Glue: partial (SynGlue) │
│                       │                       │ Others: Router/classifier only    │
├───────────────────────┼───────────────────────┼───────────────────────────────────┤
│ Tools_Expanded        │ 123 tools cataloged   │ 93 tool files in protacxtend/tools│
│                       │                       │ 74-method ProtacDesignToolbox     │
├───────────────────────┼───────────────────────┼───────────────────────────────────┤
│ Databases_Expanded    │ 48 databases          │ 8 live APIs + 5 curated local DBs │
├───────────────────────┼───────────────────────┼───────────────────────────────────┤
│ Packages              │ 43 packages           │ 42/43 installed (torchdrug miss)  │
├───────────────────────┼───────────────────────┼───────────────────────────────────┤
│ Skills                │ 26 agent skills       │ Mapped to 31 graph nodes & toolbox│
├───────────────────────┼───────────────────────┼───────────────────────────────────┤
│ Agent_Modules         │ 37 proposed modules   │ Unified into 31 governed nodes    │
├───────────────────────┼───────────────────────┼───────────────────────────────────┤
│ NP_Hard_Problems      │ 11 fundamental barriers│ 4 "Not started" in July are now   │
│                       │ (4 not started in July│ fully built (M1, M2, M3, M5);     │
│                       │  7 partial/built)     │ M6 attacks E3 ligase sparsity     │
├───────────────────────┼───────────────────────┼───────────────────────────────────┤
│ Implementation_Status │ 23 nodes tracked      │ Expanded to 31 registered nodes   │
└───────────────────────┴───────────────────────┴───────────────────────────────────┘
```

### 2.1 Modalities Sheet (18 Targeted Degradation Modalities)
- **Blueprint:** Specified 18 distinct degradation modalities: PROTAC, Molecular Glue, LYTAC, AbTAC, AUTAC, ATTEC, AUTOTAC, GlueTAC, HaloPROTAC, Phospho-PROTAC, Homo-PROTAC, Dual-target PROTAC, Photo-PROTAC, TRAFTAC, Degron-tag, RIBOTAC, TF-PROTAC, and SNIPER.
- **Implemented Reality:**
  - **PROTAC:** Fully implemented end-to-end (target resolution $\rightarrow$ warhead selection $\rightarrow$ exit vector detection $\rightarrow$ linker generation $\rightarrow$ assembly $\rightarrow$ stereoisomers $\rightarrow$ ternary modeling $\rightarrow$ degradation ML $\rightarrow$ ADMET $\rightarrow$ Pareto ranking).
  - **Molecular Glue:** Partially implemented via `SynGlue_Py` and `synglue_agent`.
  - **Other Modalities:** Supported at the **Modality Router** level (`protacxtend/agents/modality_router.py`), which uses biological rule sets (intracellular vs extracellular, membrane vs cytosolic, aggregate vs monomeric) to direct users to the appropriate modality. However, 3D structure generation, docking, and degradation modeling are only implemented for PROTACs.

### 2.2 NP-Hard Problems Sheet (The 11 Computational Barriers)
In July 2026, `Agent_Toolkit.xlsx` marked 4 fundamental problems as "Not started / Not built". Between August and September 2026, **dedicated scientific modules were built for all four**:

1. **Problem 1: Linker Optimization (Non-convex landscape)**
   - *Blueprint:* Marked `Partial (scan+score only)`.
   - *Code Reality:* `tools/linker_scanner.py` (scan & geometry) + `tools/generative_linker.py` (char-GRU trained on PROTAC-DB linkers: `data/linkers/linker_generator.pt`) + curated library (241 linkers) + rule-based templates + `tools/linker_scoring.py` + evolutionary genetic optimization (`propose_linker_replacement` in `agents/evolution_agent.py`).
   - *Gap:* No global Bayesian Optimization or Monte Carlo Tree Search across the complete 150K chemical space; sampling and local evolution are used.

2. **Problem 2: E3 Ligase Sparsity (4/600 accessible ligases)**
   - *Blueprint:* Marked `Partial (nominal scoring)` — only CRBN, VHL, cIAP, MDM2 supported.
   - *Code Reality:* **Module 6 (Novel E3 Opportunity Engine)** built (`protacxtend/modules/e3_opportunity/`). Catalogs 30 E3 ligase genes evaluated across 8 evidence axes.
   - *Gap:* No de novo small-molecule ligand generation for unliganded E3s; recommendations are restricted to evidence-backed opportunities.

3. **Problem 3: Ternary Complex 3-Body Problem**
   - *Blueprint:* Marked `Built (P4ward Docker + geometric proxy)`.
   - *Code Reality:* Containerized `p4ward_wrapper.py` (Docker/local batch execution) + SE(3) geometric proxy (`ternary_feasibility.py`). Controlled by `select_expensive_modeling_finalists` (Node 24) to avoid combinatorial explosion (P4ward takes hours per case; only top-N finalists receive full docking).

4. **Problem 4: Cooperativity ($\alpha$) Prediction**
   - *Blueprint:* Marked `Not built / Not started`.
   - *Code Reality:* **Module 3 Built (`protacxtend/modules/cooperativity_alpha_predictor/`)**. Provides a structural surrogate / feasibility score. Grouped benchmark harness (Constant, Ridge, Random Forest, XGBoost, Gaussian Process) is fully functional (21/21 tests pass).
   - *Gap:* Public experimental-$\alpha$ labels are extremely sparse in literature (<50 validated ternary $\alpha$ values). Module 3 is honestly designated as a **DATA-GATED SURROGATE**, not a trained empirical predictor.

5. **Problem 5: Lysine Proximity (Constraint Satisfaction)**
   - *Blueprint:* Marked `Not built / Not started` (target lysine must be $\le 13$ Å from E2 catalytic site).
   - *Code Reality:* **Module 2 Built (`protacxtend/modules/lysine_ubiquitination_feasibility/`)**. Implements static geometry scoring: Shrake-Rupley Solvent Accessible Surface Area (SASA), transfer distance, approach angle, steric occlusion factor, and ensemble productive fraction.
   - *Gap:* Benchmark currently uses synthetic geometry fixtures; real-PDB validation set is pending.

6. **Problem 6: De Novo PPI Interface Design**
   - *Blueprint:* Marked `Partial (geometric proxy only)`.
   - *Code Reality:* Remains a geometric proxy (`tools/ternary_feasibility.py`). De novo energy/diffusion-based PPI interface generation is not built.

7. **Problem 7: Hook Effect (Non-monotonic dose response)**
   - *Blueprint:* Marked `Not built / Not started`.
   - *Code Reality:* **Module 1 Built (`protacxtend/modules/hook_effect_modeler/`) — VALIDATED BASELINE**. Solves three-body mass-action equilibrium (Douglass et al. 2013) using bounded non-linear least squares in $\log_{10}$ space. Computes $C_{\text{max}}$, $[PT]_{\text{max}}$, hook onset, severity, and Monte Carlo uncertainty. 24/24 unit tests pass.
   - *Gap:* Models thermodynamic equilibrium; does not model time-dependent proteasomal degradation kinetics.

8. **Problem 8: bRo5 Permeability $\times$ Potency Pareto Optimization**
   - *Blueprint:* Marked `Built (descriptors + risk flags)`.
   - *Code Reality:* Implemented in `tools/admet_predictors.py` (MW, TPSA, LogP, rotatable bonds, permeability proxy) + `tools/pareto_ranking.py` (non-dominated sorting & crowding distance).

9. **Problem 9: Proteotype Selectivity (Context-Dependent Degradation)**
   - *Blueprint:* Marked `Not built / Not started`.
   - *Code Reality:* **Module 5 Built (`protacxtend/modules/cell_context_selector/`) — TRAINED**. Conditions degradation predictions on DepMap 24Q4 transcriptomics (1,913 curated PROTAC-Degradation-DB records across 180 cell lines). Leg D (context) outperforms Leg B (no context) on unseen PROTACs ($R^2 = 0.605$ vs $0.513$).
   - *Gap:* Transcriptomic context only; proteomics matrix is missing from 24Q4; unseen cell-line transfer is not claimed.

10. **Problem 10: Stereochemistry of Ternary Complex**
    - *Blueprint:* Marked `Built`.
    - *Code Reality:* `tools/stereochemistry_engine.py` and Node 12 (`expand_stereoisomers`). Enumerate chiral centers, preserves stereocenters through chemical assembly, and evaluates stereoisomers individually.

11. **Problem 11: Sparse Sampling (The 600 PROTAC problem)**
    - *Blueprint:* Marked `Partial (similarity only)`.
    - *Code Reality:* `tools/novelty_checker.py` (Tanimoto similarity vs curated known PROTACs) + Applicability Domain Agent (Node 17) + Grouped OOD splits in M4/M5.

### 2.3 Tools & Packages
- **Tools:** `Agent_Toolkit.xlsx` cataloged 123 potential tools. The repository implements **93 standalone tool files** in `protacxtend/tools/` and encapsulates 74 core methods inside `ProtacDesignToolbox`. External compute-heavy tools (AlphaFold, GROMACS, OpenMM) are abstracted via adapter patterns with offline fallbacks.
- **Packages:** 43 packages were listed. As verified by `check_packages.py`, **42 of 43 packages are installed and functional** in the conda/python environment; only `torchdrug` is absent.

---

## 3. System Architecture: How PROTACXtend Works

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                               PROTACXTEND WORKFLOW ARCHITECTURE                                 │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘

     [1. User Natural Language Query]  (e.g., "Design CRBN PROTACs targeting BRD4 in VCaP cells")
                    │
                    ▼
  ┌─────────────────────────────────────────────────────────────────────────────────────────┐
  │ KNOW LAYER (Retrieval & Grounding)                                                      │
  │ • Live APIs: UniProt (PDB/AlphaFold lookup), ChEMBL, PubChem, BindingDB                │
  │ • Literature Clients: Europe PMC, PubMed, OpenAlex, Crossref (DOI verification)        │
  │ • Local Registries: PROTAC-DB 3.0, TACK, PROTAC-Degradation-DB, DepMap 24Q4            │
  └─────────────────────────────────────────────────────────────────────────────────────────┘
                    │
                    ▼
  ┌─────────────────────────────────────────────────────────────────────────────────────────┐
  │ REASON LAYER (Agentic Graph Nodes 1–9)                                                  │
  │ • SupervisorAgent: Parses target, E3 ligase, constraints, cell line                     │
  │ • DesignPlannerAgent: Dynamic policy, step retry rules, stop criteria                   │
  │ • TargetResolverAgent & BinderRetrievalAgent: Pulls potent binders (pChEMBL ≥ 6.0)      │
  │ • WarheadSelectionAgent & E3LigandSelectionAgent: Warhead + E3 recruiter pairing       │
  │ • ExitVectorDetectionAgent: RDKit solvent-accessible attachment point identification    │
  └─────────────────────────────────────────────────────────────────────────────────────────┘
                    │
                    ▼
  ┌─────────────────────────────────────────────────────────────────────────────────────────┐
  │ DESIGN LAYER (Chemistry Engine Nodes 10–14)                                             │
  │ • LinkerGenerationAgent: 74-method engine (curated 241, rule-based, char-GRU generative)│
  │ • MolecularConstructionAgent: Amide coupling, click chemistry, SNAr assembly            │
  │ • StereochemistryEnumerationAgent: Enumerates stereocenters with chirality preservation │
  │ • CandidateValidationAgent: RDKit sanitization, valency, PAINS screening                │
  │ • CellContextAgent (Module 5): Early transcriptomic compatibility evaluation            │
  └─────────────────────────────────────────────────────────────────────────────────────────┘
                    │
                    ▼
  ┌─────────────────────────────────────────────────────────────────────────────────────────┐
  │ DISCOVER LAYER (Predictive & Mechanistic Evaluation Nodes 15–31)                        │
  │ • Fast Filters (Nodes 15–19):                                                           │
  │   - ADMETAgent: hERG, AMES, BBB, Lipinski/Veber bRo5 radar                              │
  │   - NoveltyAgent: Tanimoto distance to known PROTACs                                    │
  │   - ApplicabilityDomainAgent: In-domain vs OOD confidence calculation                   │
  │   - DegradationPredictionAgent (Module 4): pDC50 and Dmax regression                    │
  │ • Tournament & Refinement (Nodes 20–23):                                                │
  │   - Initial Ranking (final=False): Multi-objective property scoring                     │
  │   - ProximityDiversityAgent: Taylor-Butina clustering (T ≥ 0.62)                        │
  │   - ReflectionReviewAgent: Rule-based critic for physical inconsistencies               │
  │   - EvolutionRefinementAgent: Genetic linker crossover and mutation                     │
  │ • Expensive Modeling Finalists Gate (Node 24):                                          │
  │   - Prunes candidate pool to top N (budget-governed)                                    │
  │ • Deep Mechanistic Modeling (Nodes 25–27):                                              │
  │   - TernaryFeasibilityAgent: P4ward 3-body docking + SE(3) geometric score              │
  │   - CooperativityPredictionAgent (Module 3): Interface alpha surrogate                 │
  │   - HookEffectPredictionAgent (Module 1): Mass-action equilibrium dose-response solve   │
  │ • Final Selection & Closure (Nodes 28–31):                                              │
  │   - Final Ranking (final=True): Full Pareto front re-ranking + diversity prune          │
  │   - ActiveLearningAgent (Module 7): CLI feedback registration                           │
  │   - ReportAgent & MemoryUpdateAgent: Generates scientific dossier (MD, CSV, JSON)       │
  └─────────────────────────────────────────────────────────────────────────────────────────┘
```

### 3.1 The 31-Node Governed Graph (`protacxtend/agents/graph.py`)
The execution order defined in `protacxtend/agents/graph.py` lines 66–98 is:

| Step | Node Identifier | Agent Class | Function |
|:---:|---|---|---|
| 1 | `parse_user_request` | `SupervisorAgent` | Natural language goal decomposition |
| 2 | `create_design_plan` | `DesignPlannerAgent` | Workflow plan, repeat policies, budgets |
| 3 | `control_np_hard_search` | `ControlledSearchAgent` | Resource limits across combinatorial spaces |
| 4 | `safety_precheck` | `SafetyAgent` | Chemical hazards, reactive group checks |
| 5 | `resolve_target` | `TargetResolverAgent` | UniProt / ChEMBL / AlphaFold protein mapping |
| 6 | `retrieve_target_binders`| `TargetBinderRetrievalAgent` | Bioactivity data retrieval from live APIs |
| 7 | `select_warheads` | `WarheadSelectionAgent` | Binder ranking and warhead curation |
| 8 | `select_e3_ligands` | `E3LigandSelectionAgent` | Recruiter selection (CRBN, VHL, IAP, MDM2) |
| 9 | `detect_exit_vectors` | `ExitVectorDetectionAgent` | Solvent-exposed vector detection via RDKit |
| 10 | `generate_linkers` | `LinkerGenerationAgent` | 74-method linker sampling (curated, rules, GRU) |
| 11 | `construct_protacs` | `MolecularConstructionAgent` | Chemical assembly (warhead + linker + E3) |
| 12 | `expand_stereoisomers` | `StereochemistryEnumerationAgent`| Chiral center resolution & enumeration |
| 13 | `validate_protacs` | `CandidateValidationAgent` | RDKit sanitization, property filtering |
| 14 | `score_cell_context` | `CellContextAgent` | Module 5 DepMap transcriptomic scoring |
| 15 | `predict_admet` | `ADMETAgent` | bRo5 ADMET, hERG, AMES, BBB, solubility |
| 16 | `check_novelty` | `NoveltyAgent` | Tanimoto similarity vs 485K curated degraders |
| 17 | `assess_applicability_domain`| `ApplicabilityDomainAgent` | Distance to training sets & OOD flagging |
| 18 | `cheap_filter_candidates`| `CheapFilterAgent` | Hard pruning of non-developable molecules |
| 19 | `predict_degradation` | `DegradationPredictionAgent` | Module 4 $\text{pDC}_{50}$ and $D_{\max}$ predictions |
| 20 | `initial_ranking` | `RankingAgent(final=False)` | First-stage multi-objective ranking |
| 21 | `diversity_clustering` | `ProximityDiversityAgent` | Taylor-Butina structural clustering |
| 22 | `reflection_review` | `ReflectionReviewAgent` | Critic review for scientific discrepancies |
| 23 | `evolution_refinement` | `EvolutionRefinementAgent` | Genetic algorithm linker mutations |
| 24 | `select_expensive_modeling_finalists` | `ExpensiveModelingSelectionAgent` | Gatekeeper pruning for expensive 3D docking |
| 25 | `optional_ternary_feasibility` | `TernaryFeasibilityAgent` | P4ward containerized docking / SE(3) proxy |
| 26 | `predict_cooperativity` | `CooperativityPredictionAgent` | Module 3 cooperativity $\alpha$ surrogate |
| 27 | `predict_hook_effect` | `HookEffectPredictionAgent` | Module 1 mass-action 3-body dose simulation |
| 28 | `final_ranking` | `RankingAgent(final=True)` | Final Pareto ranking + diverse representative pick |
| 29 | `active_learning_update`| `ActiveLearningAgent` | Registers observed feedback into memory |
| 30 | `generate_report` | `ReportAgent` | Assembles final Markdown/CSV/JSON dossier |
| 31 | `update_memory` | `MemoryUpdateAgent` | Persists session graph and candidate artifacts |

### 3.2 Dual-Runtime Engine
1. **`LocalSynGlueWorkflowGraph`:** Deterministic linear state machine. Iterates over the 31 nodes in strict order. Features automatic retry handling governed by `design_plan["repeat_policy"]` (e.g., retrying target resolution or binder retrieval up to `max_retries_per_step`). It includes **hard terminal error gates** that safely halt execution if fatal conditions arise (e.g., `"Planner requires a target protein/gene"`, `"No warheads selected"`, `"No E3 ligands selected"`, `"No PROTAC candidates assembled"`).
2. **`LangGraph` Workflow:** Shares the exact same node registry. Can be exported and run in distributed, asynchronous agentic environments with checkpointing.

### 3.3 Two-Stage Ranking Logic (`RankingAgent`)
Code audit of `protacxtend/agents/ranking_agent.py` confirmed the exact behavioral difference between the two ranking nodes:
- **`initial_ranking` (Node 20, `final=False`):** Ranks candidate molecules based solely on early 2D predictions (warhead affinity, linker length, early cell-context score, ADMET radar, and novelty).
- **`final_ranking` (Node 28, `final=True`):** Re-scores the survivors using the complete evidence vector, incorporating computationally heavy 3D metrics (`ternary_feasibility_results`, `cooperativity_predictions`, `hook_effect_predictions`, and `e3_context_predictions`). Crucially, it triggers `self.toolbox.choose_diverse_representatives()`, which applies structural clustering to ensure the top-N output molecules represent distinct chemical series rather than minor linker variants of a single scaffold.

---

## 4. Deep Dive into the 7 Sequential Scientific Modules (M1–M7)

```
┌───────────────────────────────────────────────────────────────────────────────────┐
│                     THE M1–M7 SEQUENTIAL MODULE PROGRAM                          │
├────────┬───────────────────────────────────┬───────────────────────┬──────────────┤
│ Module │ Name                              │ Status in Source Truth│ Tests Pass   │
├────────┼───────────────────────────────────┼───────────────────────┼──────────────┤
│ M1     │ Hook Effect Modeler               │ VALIDATED BASELINE    │ 24 / 24      │
│ M2     │ Lysine Ubiquitination Feasibility │ STRUCTURAL SURROGATE  │  8 / 8       │
│ M3     │ Cooperativity (α) Predictor       │ DATA-GATED SURROGATE  │ 21 / 21      │
│ M4     │ Degradation ML                    │ TRAINED               │  9 / 9       │
│ M5     │ Cell Context Selector             │ TRAINED               │ 16 / 16      │
│ M6     │ Novel E3 Opportunity Engine       │ UNDER EVALUATION      │ 17 / 17      │
│ M7     │ Active Learning Feedback Loop     │ PARTIAL (CLI only)    │ — (CLI stub) │
└────────┴───────────────────────────────────┴───────────────────────┴──────────────┘
```

### Module 1: Hook Effect Modeler (`protacxtend/modules/hook_effect_modeler/`)
- **Status:** `VALIDATED BASELINE` (Publicly claimed).
- **Mathematical Logic:** Solves the 3-body mass-action equilibrium system:
  $$\text{POI} + \text{PROTAC} \rightleftharpoons \text{POI}\cdot\text{PROTAC} \quad (K_T)$$
  $$\text{E3} + \text{PROTAC} \rightleftharpoons \text{E3}\cdot\text{PROTAC} \quad (K_E)$$
  $$\text{POI}\cdot\text{PROTAC} + \text{E3} \rightleftharpoons \text{POI}\cdot\text{PROTAC}\cdot\text{E3} \quad (K_E / \alpha)$$
  $$\text{E3}\cdot\text{PROTAC} + \text{POI} \rightleftharpoons \text{POI}\cdot\text{PROTAC}\cdot\text{E3} \quad (K_T / \alpha)$$
  Solved numerically via Scipy `least_squares` in $\log_{10}$-space with total mass conservation ($T_0, E_0, L_0$). Path independence (microscopic reversibility) is guaranteed and verified.
- **Outputs:** Concentration-occupancy curve, $[PT]_{\text{max}}$, $C_{\text{max}}$, $\text{Hook}_{90}$ and $\text{Hook}_{50}$ dose thresholds, and Monte Carlo confidence intervals.
- **Limitation:** Equilibrium only; does not model cellular proteasomal turnover kinetics.

### Module 2: Lysine Ubiquitination Feasibility (`protacxtend/modules/lysine_ubiquitination_feasibility/`)
- **Status:** `STRUCTURAL SURROGATE` (Publicly claimed as surrogate).
- **Biophysical Logic:** Evaluates whether target lysines can physically receive ubiquitin from the recruited E2 conjugating enzyme:
  1. Shrake-Rupley SASA calculations on target lysines.
  2. Euclidean distance to E2 catalytic cysteine ($\le 13$ Å constraint).
  3. Approach angle and steric occlusion factor.
  4. Ensemble productive fraction over conformational ensembles.
- **Limitation:** Static crystal/model geometry; dynamic real-PDB benchmark is currently pending.

### Module 3: Cooperativity ($\alpha$) Predictor (`protacxtend/modules/cooperativity_alpha_predictor/`)
- **Status:** `DATA-GATED SURROGATE` (Publicly claimed as data-gated).
- **Biophysical Logic:** $\alpha = \frac{K_D^{\text{binary}}}{K_D^{\text{ternary}}}$. When $\alpha > 1$, ternary complex formation is thermodynamically favored. Module 3 extracts geometric interface features (intermolecular contacts, SASA burial, linker strain proxy).
- **Limitation:** There are fewer than 50 rigorously validated experimental $\alpha$ values published in literature. Therefore, PROTACXtend honestly maintains this module in **DATA-GATED SURROGATE** status with a benchmark harness ready (Ridge, RF, XGBoost, GP) until experimental labels are curated.

### Module 4: Degradation ML (`protacxtend/modules/degradation_ml/`)
- **Status:** `TRAINED` (Publicly claimed).
- **ML Architecture:** Regression models predicting $\text{pDC}_{50}$ and $D_{\max}$ from 64/32 published, curated degrader labels. Features include Morgan circular fingerprints, RDKit 2D physicochemical descriptors, and target/E3 one-hot representations.
- **Validation:** Independent audit approved on 2026-09-02 (9/9 tests pass). Entity-context forwarding fix applied; in-sample $R^2 \approx 0.95$. Classification probability task honestly disabled due to sparse negative labels.
- **Artifact:** `protacxtend/modules/degradation_ml/models/pdc50_model.joblib`.

### Module 5: Cell Context Selector (`protacxtend/modules/cell_context_selector/`)
- **Status:** `TRAINED` (Publicly claimed with explicit qualifiers).
- **Data & Architecture:** Conditions degrader efficacy on cell-line transcriptomics. Trained on 1,913 curated PROTAC-Degradation-DB records mapped across 180 cell lines and integrated with DepMap 24Q4 transcriptomics (1,512 matched rows in `data/context_joined.csv`).
- **Benchmark:** Grouped CV benchmark legs A through G. Leg D (PROTAC + transcriptomic context) decisively outperforms Leg B (PROTAC features only) on held-out unseen PROTACs ($R^2 = 0.605$ vs $0.513$).
- **Limitation:** Transcriptomic context only; proteotype (mass-spectrometry proteomics) is not claimed; unseen cell-line transfer is not claimed.
- **Artifact:** `protacxtend/modules/cell_context_selector/models/cell_context_model.joblib`.

### Module 6: Novel E3 Opportunity Engine (`protacxtend/modules/e3_opportunity/`)
- **Status:** `UNDER EVALUATION` (Code complete, 17/17 tests passing, report-gated; **NOT publicly claimed**).
- **Engine Logic:** Evaluates 30 human E3 ligase genes across 8 evidence axes (DepMap expression, UniProt subcellular localization, AlphaFold structural lysines, published recruiter precedents, selectivity, disease context, uncertainty).
- **Decision Gates:** Assigns verdicts `SUPPORTED`, `PROMISING`, `EXPLORATORY`, `INSUFFICIENT`. Strict gate: high mRNA expression alone NEVER generates a `SUPPORTED` verdict; direct published chemical recruitment precedent is mandatory.
- **Benchmark:** Retrospective Random Forest benchmark achieves AUROC 0.93 on unseen E3 ligases.

### Module 7: Active Learning & Feedback Loop (`protacxtend/agents/active_learning_agent.py`)
- **Status:** `PARTIAL` / `PLANNED`.
- **Status:** CLI `/learn` command records observed wet-lab or user feedback into session memory. Multi-objective Bayesian Optimization (BO) closed-loop acquisition is planned for the next release cycle.

---

## 5. Independent Predictors & Committed ML Models

PROTACXtend maintains **complete model independence** across 5 distinct degradation engines and explicitly rejects silent ensemble averaging:
1. **Module 4 pDC50 Model:** `protacxtend/modules/degradation_ml/models/pdc50_model.joblib`
2. **Module 5 Cell-Context Model:** `protacxtend/modules/cell_context_selector/models/cell_context_model.joblib`
3. **TACK DC50 Model:** `data/tack/tack_dc50_model.joblib` (trained on 4,184 rows)
4. **TACK Dmax Model:** `data/tack/tack_dmax_model.joblib`
5. **TACK Binary Classifier:** `data/tack/tack_bin_model.joblib` (trained on 6,561 rows)
6. **SynGlue Multitask Transformer:** `data/synglue/models/multitask_transformer.pt` (reads GROVER caches: 1,104 warhead rows, 117 E3 rows)
7. **Chemprop Multitarget D-MPNN:** `outputs/benchmark/chemprop_multitarget/model_0/best.pt`

**Unified Degradation Engine:** The heuristic unification layer in `protacxtend/agents/degradation_node.py` is designated **UNDER EVALUATION** in `config/scientific_status.yaml` and is never presented as an authoritative single predictor.

---

## 6. Technical Issues, Inconsistencies & Gaps Discovered

During our code execution, AST parsing, and test suite evaluation, the following specific issues and discrepancies were identified:

### Issue 1: Version String Mismatch Across Project Files
- **Finding:** `pyproject.toml` line 7 defines `version = "0.1.0"`. In contrast, `README.md`, `config/scientific_status.yaml`, and documentation refer to `"v0.3 core release"`, while the website footer displays `"v2.11"`.
- **Impact:** Causes version ambiguity for automated package builders and package managers.
- **Fix Required:** Update `pyproject.toml` to `version = "0.3.0"` and synchronize release identifiers across docs and website metadata.

### Issue 2: Pytest Collection Pollution by Vendor Repositories in `data/`
- **Finding:** Executing root-level `python3 -m pytest` fails with 156 collection errors because pytest discovers test suites inside external cloned repositories located under `data/synthesis_prediction/repos/` (`chainer-chemistry` and `linchemin`).
- **Impact:** Prevents developers and contributors from running standard `pytest` without path restrictions.
- **Root Cause:** `pytest.ini` lacks directory filtering.
- **Fix Required:** Update `pytest.ini` to explicitly define test discovery roots and ignore vendor directories:
  ```ini
  [pytest]
  testpaths = protacxtend/tests protacxtend/modules
  norecursedirs = data env .venvs work website CLI
  ```

### Issue 3: Hardcoded Non-Existent Path in `test_launcher_e.py`
- **Finding:** In `protacxtend/tests/test_launcher_e.py`, line 28 runs:
  ```python
  for cwd in [ROOT, ROOT / "CLI", Path("/tmp")]:
      monkeypatch.chdir(cwd)
  ```
  This causes a fatal `FileNotFoundError: [Errno 2] No such file or directory: '/storage/saveena/protacpilot/CLI'`.
- **Impact:** Causes a test failure in `test_resolve_uses_absolute_extension_from_any_cwd`.
- **Fix Required:** Guard the directory navigation with `if (ROOT / "CLI").is_dir():` or test against existing directories (`ROOT / "protacxtend"`).

### Issue 4: Missing Optional Dependency Guard in `test_llm_layer.py`
- **Finding:** `protacxtend/tests/test_llm_layer.py` lines 84, 100, 109, and 171 directly execute `import ollama`. When `ollama` is not installed, 4 test cases crash with `ModuleNotFoundError: No module named 'ollama'`.
- **Impact:** 4 test failures in environments without local Ollama installations.
- **Fix Required:** Add `pytest.importorskip("ollama")` at the module or test class level, or mock the import in test setup.

### Issue 5: Discrepancy in Node Inventory in `documentation/ARCHITECTURE.md`
- **Finding:** In `documentation/ARCHITECTURE.md`, Section 3 ("23-Node Agentic Inventory") provides a table listing only 23 nodes, omitting Extension Nodes 24 through 31 (`select_expensive_modeling_finalists`, `optional_ternary_feasibility`, `predict_cooperativity`, `predict_hook_effect`, `final_ranking`, `active_learning_update`, `generate_report`, `update_memory`).
- **Impact:** Confuses reviewers comparing `ARCHITECTURE.md` against `protacxtend/agents/graph.py` and `config/scientific_status.yaml` (which both specify 31 registered nodes).
- **Fix Required:** Update the table in `documentation/ARCHITECTURE.md` to display the complete 31-node workflow with clear visual separation between Core Nodes (1–23) and Controlled Extension Nodes (24–31).

### Issue 6: Broken Relative Documentation Links
- **Finding:** `CODE_REPORT_2026-09-02.md` and `TECHNICAL_COHERENCE_REVIEW.md` reference `docs/CLAIMS.md`. However, `docs/` at the repository root contains no such file; the file is located at `protacxtend/modules/e3_opportunity/docs/CLAIMS.md`.
- **Impact:** 404 / file-not-found errors when navigating documentation via relative links.
- **Fix Required:** Correct the paths in top-level reports to point to `protacxtend/modules/e3_opportunity/docs/CLAIMS.md`.

### Issue 7: Uncommitted Optional SynGlue Model Artifacts
- **Finding:** In `protacxtend/tools/synglue_degradation.py`, `MODEL_PATHS` references optional Random Forest checkpoints (`rf_dc50.joblib`, `rf_dmax.joblib`, `grover_fixed.pt`). These files are not committed to Git.
- **Impact:** The tool cleanly falls back to the committed `multitask_transformer.pt`, but documentation must remain explicit that the Random Forest weights are optional experimental extras.

### Issue 8: Terminology Divergence for Module 7 Status
- **Finding:** `config/scientific_status.yaml` lists Module 7 (`active_learning`) as `PARTIAL`, whereas the website status cards state `PLANNED`.
- **Impact:** Minor wording discrepancy between machine-readable config and web presentation.
- **Fix Required:** Standardize terminology: designate Module 7 as `PARTIAL (CLI ONLY) / ACTIVE LEARNING BO PLANNED`.

---

## 7. Operational Interfaces & Verification Commands

PROTACXtend provides four production-ready interfaces for execution, benchmarking, and demonstration:

### 7.1 Command-Line Interface (`protacxtend`)
Defined in `protacxtend/cli.py` with 18 subcommands:
```bash
# 1. Full end-to-end design campaign (Target + E3)
protacxtend design --target BRD4 --e3 CRBN --num-candidates 16

# 2. Mechanistic Hook Effect dose-response modeling (Module 1)
protacxtend dose --kd-poi 14.2 --kd-e3 250 --alpha 1.8 --min-dose 0.1 --max-dose 10000

# 3. Lysine ubiquitination and structural feasibility (Modules 2 & 3)
protacxtend structure --pdb 5T35 --target-chain A --e3-chain B

# 4. Transcriptomic cell-context evaluation (Module 5)
protacxtend context --target BRD4 --e3 CRBN --cell-line VCaP

# 5. Scientific Dossier & Contract Trace
protacxtend contract --target BRD4 --e3 CRBN --format markdown
```

### 7.2 REST API Server (`FastAPI`)
Implemented in `protacxtend/backend/api_routes.py`:
- `GET /health`: Healthcheck and model artifact status.
- `POST /design`: Asynchronous design pipeline initiation.
- `POST /mode`: Fast modality routing (PROTAC vs Glue vs LYTAC).
- `POST /agentic-design`: Governed agent graph execution endpoint.
- **Run command:** `uvicorn protacxtend.backend.api_routes:app --host 0.0.0.0 --port 8001`

### 7.3 Streamlit Interactive Web Application
Implemented in `app/streamlit_app.py`:
- Interactive parameter selection, 2D structure rendering, 3D ternary complex viewer, interactive dose-response curves, and Pareto frontier scatter plots.
- **Run command:** `streamlit run app/streamlit_app.py --server.port 8501`

### 7.4 Verification Test Suite
```bash
# Run all 6 scientific module test suites (95 passed)
python3 -m pytest \
  protacxtend/modules/hook_effect_modeler/tests \
  protacxtend/modules/lysine_ubiquitination_feasibility/tests \
  protacxtend/modules/cooperativity_alpha_predictor/tests \
  protacxtend/modules/degradation_ml/tests \
  protacxtend/modules/cell_context_selector/tests \
  protacxtend/modules/e3_opportunity/tests -q

# Run fast core unit tests (excluding network and slow tests)
python3 -m pytest protacxtend/tests/ -m "not slow and not network" -k "not test_launcher_e and not test_llm_layer" -q
```

---

## 8. Summary Checklist & Remediation Matrix

| Area | Current State | Target State | Priority |
|---|---|---|:---:|
| **Node Graph** | 31 registered nodes in `graph.py` | Align `documentation/ARCHITECTURE.md` to reflect all 31 nodes | High |
| **Pytest Configuration** | 156 collection errors on `data/` | Add `testpaths` and `norecursedirs` to `pytest.ini` | High |
| **Unit Test Fixes** | 5 failing tests (`test_launcher_e`, `test_llm_layer`) | Guard `ROOT / "CLI"` check and mock `ollama` import | High |
| **Version Alignment** | `pyproject.toml` has `0.1.0` | Bump `pyproject.toml` to `0.3.0` | Medium |
| **Doc Paths** | Broken relative `docs/CLAIMS.md` | Update to `protacxtend/modules/e3_opportunity/docs/CLAIMS.md` | Medium |
| **Scientific Claims** | M1, M4, M5 claimed; M2, M3 surrogates; M6 report-gated; M7 planned | Strict adherence to `config/scientific_status.yaml` | Continuous |
