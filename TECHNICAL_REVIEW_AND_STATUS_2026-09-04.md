# TECHNICAL REVIEW & CODEBASE STATUS REPORT (2026-09-04)
**Comprehensive Architecture Audit, Blueprint Comparison, Scientific Module Verification, and Gap Analysis**

- **Repository:** `the-ahuja-lab/PROTACXtend` (`/storage/saveena/protacpilot`)
- **Software Release:** `v0.3 core release` (PyPI package: `protacxtend`)
- **Reference Specification:** `Agent_Toolkit.xlsx` (Created 2026-07-31)
- **Source of Truth Files:**
  - `config/scientific_status.yaml` (scientific validation statuses & claims)
  - `protacxtend/agents/graph.py` (31-node governed workflow registry)
  - `protacxtend/tools/protac_toolbox.py` (74-method chemistry & modeling toolbox)
  - `protacxtend/modules/PROTACXTEND_MODULE_BUILD.md` (sequential build tracker)
  - `NP_HARD_AGENT_DESIGN.md` (11 computational barriers & tiered agent search)
  - `CODE_REPORT_2026-09-02.md` & `TECHNICAL_COHERENCE_REVIEW.md`

---

## 1. Executive Summary & Current Health

PROTACXtend represents the evolution of the July 2026 **ProtacPilot** conceptual toolkit into a tool-augmented, deterministic agentic research platform for targeted protein degradation (TPD).

Unlike black-box generative chemistry or blind screening scripts, PROTACXtend executes an explicit, governed **scientific contract**:
1. **Auditable Evidence Chain:** Every executed design step produces structured evidence recording inputs, outputs, biological/chemical tools, model versions, confidence scores, applicability domain states, and explicit scientific limitations.
2. **Deterministic ReAct Execution (Zero LLM Hallucination):** The core workflow operates without hosted LLMs (no external OpenAI/Anthropic/Gemini API calls in the default pipeline). Decisions are made by verifiable algorithmic rules, biophysical equations, and calibrated local ML models.
3. **Multi-Objective Pareto Decision Making:** Evaluates degraders across ternary binding, lysine accessibility, cooperativity, hook-effect onset, cell-context transcriptomics, and beyond-Rule-of-5 (bRo5) ADMET properties.
4. **Governed Workflow Graph:** 31 agent nodes (23 core scientific nodes + 8 controlled-search/feedback extensions) executed as a linear state machine with configurable repeat policies and hard terminal gates, with full interoperability via LangGraph.

### Health & Maturity Dashboard (2026-09-04)
- **Codebase Scope:** 320+ Python source files across `protacxtend/` (38 agent files, 93 tool files, 61 module files, 10 research retrieval files).
- **Core Chemistry Engine:** 74 public callable methods in `ProtacDesignToolbox` (96 total functions).
- **Scientific Modules (M1–M7):** 6 modules fully built (M1–M6); M1 (Hook effect), M4 (Degradation ML), and M5 (Cell context) are validated and publicly claimed; M2 (Lysine Ub) and M3 (Cooperativity $\alpha$) are structural/data-gated surrogates; M6 (E3 Opportunity) is code-complete but report-gated; M7 (Active learning) has CLI surface.
- **Machine Learning Models:** 7 trained ML artifacts committed directly to the repository.
- **Test Suite Results:**
  - **Sequential Module Suites:** **95 / 95 passing unit tests** (M1: 24, M2: 8, M3: 21, M4: 9, M5: 16, M6: 17).
  - **Backend & Integration Suites (`tests/`):** **144 / 144 passing tests (100% pass rate)** across agentic orchestration, scientific contract, chemistry core, and benchmark infrastructure.
  - **Core Agent Suites (`protacxtend/tests/`):** **423 passing unit tests**, with 5 isolated failures identified during audit (1 directory path bug, 4 optional `ollama` import errors).
  - **Total Verified Passing Tests:** **662 automated tests passing**.

---

## 2. Where We Are: Exact Implementation Status

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                CURRENT IMPLEMENTATION STATUS MATRIX                              │
├────────────────────────────────┬──────────────────────┬───────────────────────┬──────────────────┤
│ Layer / Component              │ Code Location        │ Scientific Status     │ Verified Metrics │
├────────────────────────────────┼──────────────────────┼───────────────────────┼──────────────────┤
│ KNOW: Literature Retrieval     │ research/sources.py  │ TRAINED-API (Live)    │ 4 APIs + SearXNG │
│ KNOW: Target Bioactivity       │ tools/target_binders │ TRAINED-API (Live)    │ ChEMBL/PubChem/BD│
│ REASON: 31-Node Governed Graph │ agents/graph.py      │ PRODUCTION RUNTIME    │ 31 nodes mapped  │
│ DESIGN: Chemistry Toolbox      │ tools/protac_toolbox │ DETERMINISTIC ENGINE  │ 74 public methods│
│ DESIGN: Linker Generation      │ tools/generative_*   │ TRAINED (char-GRU)    │ 241 curated + GRU│
│ MECH M1: Hook Effect           │ modules/hook_effect  │ VALIDATED BASELINE    │ 24/24 tests pass │
│ MECH M2: Lysine Ubiquitination │ modules/lysine_ub    │ STRUCTURAL SURROGATE  │ 8/8 tests pass   │
│ MECH M3: Cooperativity (α)     │ modules/cooperativity│ DATA-GATED SURROGATE  │ 21/21 tests pass │
│ DISCOVER M4: Degradation ML    │ modules/degradation  │ TRAINED (joblib)      │ 9/9 tests pass   │
│ DISCOVER M5: Cell Context      │ modules/cell_context │ TRAINED (DepMap 24Q4) │ 16/16 tests pass │
│ REASON M6: E3 Opportunity      │ modules/e3_opp       │ UNDER EVALUATION      │ 17/17 tests pass │
│ LEARN M7: Active Learning      │ agents/active_learn  │ PARTIAL (CLI only)    │ BO loop planned  │
│ DISCOVER: TACK Degradation     │ tools/tack_*         │ TRAINED (joblib)      │ DC50/Dmax/Bin    │
│ DISCOVER: SynGlue Degrader     │ tools/synglue_*      │ TRAINED (Transformer) │ multitask.pt     │
│ DISCOVER: Chemprop D-MPNN      │ outputs/benchmark    │ TRAINED (PyTorch)     │ best.pt          │
│ DECISION: Pareto Tournament    │ tools/pareto_ranking │ MULTI-OBJECTIVE       │ Non-dominated F1 │
└────────────────────────────────┴──────────────────────┴───────────────────────┴──────────────────┘
```

---

## 3. What We Have: Detailed Codebase Inventory

### 3.1 Governed 31-Node Agentic Inventory (`protacxtend/agents/graph.py`)
The pipeline runs as a deterministic linear sequence governed by `LocalSynGlueWorkflowGraph`:

#### Phase I: Core Scientific Workflow (Nodes 1–23)
1. **`parse_user_request` (`SupervisorAgent`):** Natural language parsing $\rightarrow$ structured `ParsedObjective` (target, E3, cell line, constraints).
2. **`create_design_plan` (`DesignPlannerAgent`):** Generates workflow policy, repeat policies, budgets, and step timeouts.
3. **`control_np_hard_search` (`ControlledSearchAgent`):** Enforces budget caps across combinatorial search spaces.
4. **`safety_precheck` (`SafetyAgent`):** Screens inputs for hazardous chemistry, reactive groups, and PAINS alerts.
5. **`resolve_target` (`TargetResolverAgent`):** Live UniProt, ChEMBL, and AlphaFold DB protein mapping.
6. **`retrieve_target_binders` (`TargetBinderRetrievalAgent`):** Live bioactivity retrieval (ChEMBL, PubChem, BindingDB) with pChEMBL $\ge 6.0$ filtering.
7. **`select_warheads` (`WarheadSelectionAgent`):** Curation of target binders with solvent-exposure compatibility.
8. **`select_e3_ligands` (`E3LigandSelectionAgent`):** Curates ligands for CRBN, VHL, cIAP, MDM2 with colocalization scoring.
9. **`detect_exit_vectors` (`ExitVectorDetectionAgent`):** RDKit-based detection of non-disruptive attachment points.
10. **`generate_linkers` (`LinkerGenerationAgent`):** Samples linkers via curated library (241), rule templates (PEG/alkyl), and char-GRU generative model.
11. **`construct_protacs` (`MolecularConstructionAgent`):** In silico synthesis (amide coupling, click chemistry, SNAr) assembling warhead + linker + E3.
12. **`expand_stereoisomers` (`StereochemistryEnumerationAgent`):** Identifies chiral centers, enforces stereocenter preservation, and enumerates isomers ($\le 32$).
13. **`validate_protacs` (`CandidateValidationAgent`):** RDKit valence sanitization, tautomer handling, and parameter bounds check.
14. **`score_cell_context` (`CellContextAgent`):** Early transcriptomic compatibility evaluation via Module 5 (DepMap 24Q4).
15. **`predict_admet` (`ADMETAgent`):** Evaluates beyond-Rule-of-5 (bRo5) properties: hERG, AMES, BBB, solubility proxy, Lipinski/Veber violations.
16. **`check_novelty` (`NoveltyAgent`):** Tanimoto similarity calculation against 485,329 known degrader structures.
17. **`assess_applicability_domain` (`ApplicabilityDomainAgent`):** Distance-to-training-set and Out-of-Domain (OOD) uncertainty flags.
18. **`cheap_filter_candidates` (`CheapFilterAgent`):** Fast non-dominated pruning to discard physically non-developable candidates.
19. **`predict_degradation` (`DegradationPredictionAgent`):** Predicts $\text{pDC}_{50}$ and $D_{\max}$ via Module 4 ML and TACK models.
20. **`initial_ranking` (`RankingAgent(final=False)`):** Multi-objective composite scoring across affinity and 2D developability.
21. **`diversity_clustering` (`ProximityDiversityAgent`):** Taylor-Butina structural clustering ($T \ge 0.62$) to prevent monocultures.
22. **`reflection_review` (`ReflectionReviewAgent`):** Algorithmic critic auditing intermediate outputs for physical discrepancies.
23. **`evolution_refinement` (`EvolutionRefinementAgent`):** Genetic algorithm proposing linker mutations, length variations, and scaffold hops.

#### Phase II: Controlled Search & Feedback Extensions (Nodes 24–31)
24. **`select_expensive_modeling_finalists` (`ExpensiveModelingSelectionAgent`):** Computational gatekeeper selecting the top-N diverse finalists for heavy 3D simulation.
25. **`optional_ternary_feasibility` (`TernaryFeasibilityAgent`):** 3-body ternary docking via containerized P4ward pipeline + SE(3) geometric proxy.
26. **`predict_cooperativity` (`CooperativityPredictionAgent`):** Module 3 biophysical surrogate estimating ternary cooperativity factor $\alpha$.
27. **`predict_hook_effect` (`HookEffectPredictionAgent`):** Module 1 mass-action equilibrium solver simulating dose-response and hook-effect window.
28. **`final_ranking` (`RankingAgent(final=True)`):** Re-scores candidates using 3D evidence, calculates the Pareto front, and calls `choose_diverse_representatives`.
29. **`active_learning_update` (`ActiveLearningAgent`):** Registers candidate observations and updates feedback memory.
30. **`generate_report` (`ReportAgent`):** Assembles human-readable Markdown dossier, CSV tables, and structured JSON payloads.
31. **`update_memory` (`MemoryUpdateAgent`):** Persists session history, reasoning graph, and candidate structures to disk.

---

### 3.2 Master Chemistry Toolbox (`ProtacDesignToolbox`)
Defined in `protacxtend/tools/protac_toolbox.py` with **74 public callable methods**:
- **Cheminformatics Core:** SMILES validation, InChIKey indexing, tautomer generation, Bemis-Murcko scaffold extraction, attachment vector mapping.
- **Stereochemistry Engine:** Detection of chiral centers, $E/Z$ double bond stereochemistry, stereoisomer enumeration with stereocenter preservation.
- **Linker Scanner & Generation:** $N \times M$ linker attachment scanning, conformational rigidity scoring, char-GRU neural generator sampling.
- **Docking & Structural Wrappers:** Containerized P4ward ternary docking wrapper, SE(3) equivariant interface proxy, SASA calculation.
- **ADMET & Developability:** Lipinski/Veber bRo5 radar, PAINS filtering, permeability proxy, hERG/AMES/BBB estimators.
- **Pareto & Decision Engine:** Non-dominated sorting, crowding distance calculation, Taylor-Butina diversity selection.

---

### 3.3 Deep Dive into the 7 Sequential Scientific Modules (M1–M7)

#### Module 1: Hook Effect Modeler (`protacxtend/modules/hook_effect_modeler/`)
- **Status:** `VALIDATED BASELINE` (Claim Level: Scientific).
- **Core Mathematics:** Solves the 3-body mass-action equilibrium without linear approximations:
  $$[\text{TL}] = \frac{[\text{T}][\text{L}]}{K_T}, \quad [\text{EL}] = \frac{[\text{E}][\text{L}]}{K_E}, \quad [\text{TLE}] = \alpha \frac{[\text{TL}][\text{E}]}{K_E} = \alpha \frac{[\text{EL}][\text{T}]}{K_T}$$
  Total mass conservation equations:
  $$T_0 = [\text{T}] + [\text{TL}] + [\text{TLE}], \quad E_0 = [\text{E}] + [\text{EL}] + [\text{TLE}], \quad L_0 = [\text{L}] + [\text{TL}] + [\text{EL}] + [\text{TLE}]$$
  Solved numerically via Scipy `least_squares` in $\log_{10}$-space.
- **Verification:** **24/24 unit tests passing** (mass balance, zero-dose exactness, hook onset, thermodynamic cycle path independence, Monte Carlo bounds).

#### Module 2: Lysine Ubiquitination Feasibility (`protacxtend/modules/lysine_ubiquitination_feasibility/`)
- **Status:** `STRUCTURAL SURROGATE`.
- **Biophysical Mechanism:**
  1. Shrake-Rupley SASA calculation on target lysine $\epsilon$-amino groups.
  2. Euclidean distance to E2 catalytic cysteine ($\le 13$ Å constraint).
  3. Approach angle and steric occlusion factor.
  4. Ensemble productive fraction across flexible ternary conformations.
- **Verification:** **8/8 unit tests passing**. Limitation: Static baseline; real-PDB benchmark pending.

#### Module 3: Cooperativity ($\alpha$) Predictor (`protacxtend/modules/cooperativity_alpha_predictor/`)
- **Status:** `DATA-GATED SURROGATE`.
- **Mechanism:** Computes ternary interface contact area, linker conformational strain, and buried surface area. Benchmark harness supports Ridge, Random Forest, XGBoost, and Gaussian Process regressors.
- **Honest Gate:** Public experimental-$\alpha$ labels are extremely sparse in literature (<50 validated ternary $\alpha$ values). Module 3 is designated as a **DATA-GATED SURROGATE**, avoiding overclaiming until experimental labels are curated.
- **Verification:** **21/21 unit tests passing**.

#### Module 4: Degradation ML (`protacxtend/modules/degradation_ml/`)
- **Status:** `TRAINED`.
- **Architecture:** Machine learning regression predicting $\text{pDC}_{50}$ and $D_{\max}$ from 64/32 published degrader labels. Features combine Morgan circular fingerprints (radius 2, 2048 bits), RDKit 2D descriptors, and target/E3 one-hot encodings.
- **Audit Verification:** Audit approved on 2026-09-02; entity-context forwarding fix verified; in-sample $R^2 \approx 0.95$. Classification probability task honestly disabled. Artifact: `pdc50_model.joblib`. **(9/9 unit tests passing)**.

#### Module 5: Cell Context Selector (`protacxtend/modules/cell_context_selector/`)
- **Status:** `TRAINED`.
- **Data & Benchmark:** Integrates 1,913 curated PROTAC-Degradation-DB records mapped across 180 cell lines with DepMap 24Q4 transcriptomics (1,512 matched rows in `data/context_joined.csv`).
- **Performance:** Grouped benchmark legs A–G: Leg D (with transcriptomic context) beats Leg B (PROTAC-only) on unseen PROTACs ($R^2 = 0.605$ vs $0.513$).
- **Limitation:** Transcriptomic context only; proteotype (mass-spectrometry proteomics) is not claimed; unseen cell line transfer is not claimed. Artifact: `cell_context_model.joblib`. **(16/16 unit tests passing)**.

#### Module 6: Novel E3 Opportunity Engine (`protacxtend/modules/e3_opportunity/`)
- **Status:** `UNDER EVALUATION` (Code complete, report-gated, **NOT publicly claimed**).
- **Mechanism:** Evaluates 30 human E3 ligase genes across 8 evidence axes (expression, localization, structural lysines, published recruiters, selectivity, disease context, uncertainty).
- **Decision Gate:** Assigns verdicts `SUPPORTED`, `PROMISING`, `EXPLORATORY`, `INSUFFICIENT`. Strict gate: high mRNA expression alone NEVER generates a `SUPPORTED` verdict; direct chemical recruitment precedent is required.
- **Performance:** Retrospective Random Forest benchmark achieves AUROC 0.93 on unseen E3s. **(17/17 unit tests passing)**.

#### Module 7: Active Learning (`protacxtend/agents/active_learning_agent.py`)
- **Status:** `PARTIAL / PLANNED`.
- **Mechanism:** CLI `/learn` surface is functional for registering wet-lab experimental feedback. Multi-objective Bayesian Optimization (BO) active learning loop is planned.

---

### 3.4 Committed Machine Learning Artifacts (7 Models)
PROTACXtend maintains complete predictor independence across 5 degradation backends (never silently averaged):
1. `protacxtend/modules/degradation_ml/models/pdc50_model.joblib` (Module 4)
2. `protacxtend/modules/cell_context_selector/models/cell_context_model.joblib` (Module 5)
3. `data/tack/tack_dc50_model.joblib` (TACK DC50, 4,184 training rows)
4. `data/tack/tack_dmax_model.joblib` (TACK Dmax)
5. `data/tack/tack_bin_model.joblib` (TACK Binary, 6,561 training rows)
6. `data/synglue/models/multitask_transformer.pt` (SynGlue Multitask Transformer)
7. `outputs/benchmark/chemprop_multitarget/model_0/best.pt` (Chemprop D-MPNN)

---

## 4. Coherence Audit: `Agent_Toolkit.xlsx` vs. PROTACXtend Reality

| Sheet in `Agent_Toolkit.xlsx` | Planned in July 2026 Blueprint | Implemented in Codebase Today | Status |
|---|---|---|:---:|
| **Modalities** | 18 TPD modalities | PROTAC is 100% implemented end-to-end; Molecular Glues partially supported via SynGlue; others routed via biological rules in `modality_router.py`. | ✅ Substantially Achieved |
| **NP_Hard_Problems** | 11 computational barriers (4 marked "Not started") | Dedicated modules built for all 4 previously unstarted problems: Hook effect (M1), Lysine proximity (M2), Cooperativity (M3), Proteotype/Cell context (M5). M6 tackles E3 sparsity. | 🚀 Exceeded Blueprint |
| **Tools_Expanded** | 123 tools cataloged | 93 tool files in `protacxtend/tools/`; 74 public methods in `ProtacDesignToolbox`; compute-heavy tools wrapped with safe fallbacks. | ✅ Substantially Achieved |
| **Databases_Expanded** | 48 databases cataloged | 8 live APIs active (UniProt, ChEMBL, PubChem, BindingDB, Europe PMC, PubMed, OpenAlex, Crossref) + local curated DBs (PROTAC-DB 3.0, TACK, DepMap 24Q4). | ✅ Verified Live |
| **Packages** | 43 environment packages | Verified via `check_packages.py`: 42 of 43 packages installed in environment (only `torchdrug` absent). | ✅ 98% Installed |
| **Skills** | 26 agent skills | Mapped directly to the 31 registered agent graph nodes and toolbox routines. | ✅ Fully Mapped |
| **Agent_Modules** | 37 proposed modules | Unified into the governed 31-node workflow (`LocalSynGlueWorkflowGraph` + LangGraph). | ✅ Consolidated |
| **Implementation_Status** | 23 nodes tracked (18 built, 3 partial, 2 not built) | Expanded to 31 registered agent nodes (23 core + 8 extensions). | 🚀 Exceeded Blueprint |

---

## 5. Concrete Issues & Gaps Found (Audit Register)

During code inspection and test suite execution, 8 concrete issues were identified:

### Issue 1: Pytest Collection Errors on External Repositories in `data/`
- **Location:** `pytest.ini`
- **Finding:** Running `pytest` at the root attempts to scan external repositories inside `data/synthesis_prediction/repos/` (`chainer-chemistry` and `linchemin`), triggering 156 collection errors.
- **Fix:** Add `testpaths = protacxtend/tests protacxtend/modules tests` and `norecursedirs = data env .venvs work website CLI` to `pytest.ini`.

### Issue 2: Missing Optional Dependency Guard in `test_llm_layer.py`
- **Location:** `protacxtend/tests/test_llm_layer.py:84,100,109,171`
- **Finding:** Directly calls `import ollama`. In environments without Ollama, 4 test cases crash with `ModuleNotFoundError: No module named 'ollama'`.
- **Fix:** Add `pytest.importorskip("ollama")` at the class or test level.

### Issue 3: Missing Directory in `test_launcher_e.py`
- **Location:** `protacxtend/tests/test_launcher_e.py:28`
- **Finding:** Test executes `monkeypatch.chdir(ROOT / "CLI")`. The directory `CLI/` is absent, causing a fatal `FileNotFoundError`.
- **Fix:** Guard with `if (ROOT / "CLI").is_dir():` or test against an existing directory (`ROOT / "protacxtend"`).

### Issue 4: Node Inventory Inconsistency in `documentation/ARCHITECTURE.md` (Fixed)
- **Location:** `documentation/ARCHITECTURE.md:89`
- **Finding:** The architecture document previously listed only 23 agent nodes in its breakdown table, omitting the 8 extension nodes.
- **Action Taken:** Updated `documentation/ARCHITECTURE.md` during this review to document all 31 registered agent nodes (Core Nodes 1–23 and Extension Nodes 24–31).

### Issue 5: Version String Mismatch Across Project Metadata
- **Location:** `pyproject.toml:7`
- **Finding:** `pyproject.toml` defines `version = "0.1.0"`, while docs, README, and `scientific_status.yaml` claim `"v0.3 core release"`, and the website footer displays `"v2.11"`.
- **Fix:** Synchronize versioning: bump `pyproject.toml` to `0.3.0`.

### Issue 6: Broken Relative Documentation Links
- **Location:** `CODE_REPORT_2026-09-02.md` and `TECHNICAL_COHERENCE_REVIEW.md`
- **Finding:** Top-level docs reference `docs/CLAIMS.md`. The actual file resides at `protacxtend/modules/e3_opportunity/docs/CLAIMS.md`.
- **Fix:** Update relative documentation links.

### Issue 7: Uncommitted Optional SynGlue Model Artifacts
- **Location:** `protacxtend/tools/synglue_degradation.py:67-69`
- **Finding:** Mentions optional Random Forest weights (`rf_dc50.joblib`, `rf_dmax.joblib`, `grover_fixed.pt`) that are not committed to Git. The tool falls back cleanly to the committed `multitask_transformer.pt`, but documentation should continue to clarify that the RF weights are optional extras.

### Issue 8: Minor Status Terminology Divergence for Module 7
- **Location:** `config/scientific_status.yaml` vs `website/index.html`
- **Finding:** `scientific_status.yaml` labels Module 7 as `PARTIAL`, whereas website copy labels it `PLANNED`.
- **Fix:** Standardize wording to `PARTIAL (CLI ONLY) / BO ACTIVE LEARNING PLANNED`.

---

## 6. How to Run & Verify

### 1. End-to-End PROTAC Design Campaign (CLI)
```bash
protacxtend design --target BRD4 --e3 CRBN --num-candidates 16
```
Generates candidate SMILES, stereoisomers, ternary feasibility score, degradation $\text{pDC}_{50}$, ADMET profile, and structured Markdown report.

### 2. Mechanistic Hook Effect Simulation (Module 1)
```bash
protacxtend dose --kd-poi 14.2 --kd-e3 250 --alpha 1.8 --min-dose 0.1 --max-dose 10000
```
Outputs the mathematical ternary concentration curve, $C_{\text{max}}$, $[PT]_{\text{max}}$, and hook onset dose.

### 3. Transcriptomic Cell-Context Degradation (Module 5)
```bash
protacxtend context --target BRD4 --e3 CRBN --cell-line VCaP
```

### 4. Run All Sequential Scientific Module Tests (95 passed)
```bash
python3 -m pytest \
  protacxtend/modules/hook_effect_modeler/tests \
  protacxtend/modules/lysine_ubiquitination_feasibility/tests \
  protacxtend/modules/cooperativity_alpha_predictor/tests \
  protacxtend/modules/degradation_ml/tests \
  protacxtend/modules/cell_context_selector/tests \
  protacxtend/modules/e3_opportunity/tests -q
```

### 5. Run Fast Unit Test Suite (423 passed)
```bash
python3 -m pytest protacxtend/tests/ -m "not slow and not network" -k "not test_launcher_e and not test_llm_layer" -q
```

---

## 7. Strategic Recommendations & Roadmap

1. **Test Infrastructure Hygiene:** Patch `pytest.ini` immediately to ignore `data/synthesis_prediction/repos/` and add `@pytest.mark.skipif` for `ollama` in `test_llm_layer.py`. This ensures green CI passes out-of-the-box for all contributors.
2. **Release Version Alignment:** Reconcile `pyproject.toml` (`0.3.0`), README, and website footer to eliminate packaging confusion.
3. **Module 6 Status Closure:** Complete the final status report audit for Module 6 (Novel E3 Opportunity Engine) so that its `public_claim` flag can be flipped to `true` in `config/scientific_status.yaml`.
4. **Active Learning (Module 7):** Proceed to the implementation of the multi-objective Bayesian Optimization feedback loop now that Modules 1–6 are complete.
