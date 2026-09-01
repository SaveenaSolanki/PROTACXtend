# PROTACXtend Agent APIs

## Workflow Entry Point

```
run_syn_glue_workflow(user_request: str) → WorkflowState
```

**Example:**
```python
from synglue_agent.agents.graph import run_syn_glue_workflow
state = run_syn_glue_workflow("Design a PROTAC for HMGB2 with ICM warhead and CRBN E3")
```

---

## Agent APIs

### 1. SupervisorAgent
Parses the user's natural-language request into a structured objective.

```
SupervisorAgent().run(state) → WorkflowState
  reads:  state.user_request
  sets:   state.parsed_objective (target_name, warhead_smiles, e3_ligase, etc.)
          state.design_plan (status, tools_to_call, stop_conditions)
```

### 2. SafetyAgent  
Validates input safety before the workflow proceeds.

```
SafetyAgent().run(state) → WorkflowState
  reads:  state.user_request, state.parsed_objective.warhead_smiles
  sets:   state.warnings (hazard patterns, invalid SMILES, unreasonable targets)
```

### 3. TargetResolverAgent
Resolves a target name to UniProt ID, AlphaFold structure, and curated data.

```
TargetResolverAgent().run(state) → WorkflowState
  reads:  state.parsed_objective.target_name
  sets:   state.target_record (uniprot_id, gene_symbol, alphafold_id, organism)
  API:    https://rest.uniprot.org (free, no key)
          https://alphafold.ebi.ac.uk/api (free, no key)
```

### 4. TargetBinderRetrievalAgent
Retrieves known ligands from ChEMBL, PubChem, and BindingDB.

```
TargetBinderRetrievalAgent().run(state) → WorkflowState
  reads:  state.target_record.uniprot_id, state.parsed_objective.target_name
  sets:   state.retrieved_binders (up to 100 records with SMILES, activity, source)
  APIs:
    ChEMBL:    https://www.ebi.ac.uk/chembl/api/data (free, no key)
    PubChem:   https://pubchem.ncbi.nlm.nih.gov/rest/pug (free, no key)
    BindingDB: https://bindingdb.org/rest (free, no key)
  Rate limit: 2 req/s, 30s timeout, 5 retries with exponential backoff
```

### 5. WarheadSelectionAgent
Selects warheads from user input or curated library.

```
WarheadSelectionAgent().run(state) → WorkflowState
  reads:  state.parsed_objective.warhead_smiles
          state.parsed_objective.target_name
  sets:   state.selected_warheads (name, smiles, source, potency, validity)
  data:   synglue_agent/data/curated_warheads.csv
```

### 6. E3LigandSelectionAgent
Selects E3 ligands based on target biology and subcellular colocalization.

```
E3LigandSelectionAgent().run(state) → WorkflowState
  reads:  state.parsed_objective.e3_ligase
          state.parsed_objective.e3_ligand_smiles
  sets:   state.selected_e3_ligands (name, e3_ligase, smiles, exit_vector_confidence)
  data:   synglue_agent/data/curated_e3_ligands.csv
  logic:  Subcellular colocalization scoring (CRBN=nuclear, VHL=cytoplasmic, etc.)
```

### 7. ExitVectorDetectionAgent
Identifies linker attachment points on warheads and E3 ligands.

```
ExitVectorDetectionAgent().run(state) → WorkflowState
  reads:  state.selected_warheads, state.selected_e3_ligands
  sets:   state.exit_vectors (atom_index, confidence, role, rationale)
  tool:   synglue_agent/tools/rdkit_chemistry.py → detect_exit_vector_atoms()
```

### 8. LinkerGenerationAgent
Generates linker candidates from curated library + generative design.

```
LinkerGenerationAgent().run(state) → WorkflowState
  reads:  state.parsed_objective.preferred_linker_types
  sets:   state.generated_linkers (name, smiles, class, length, properties)
  data:   synglue_agent/data/curated_linkers.csv
  tool:   internal linker-panel backend used by the PROTACXtend UI
```

### 9. MolecularConstructionAgent
Assembles warhead + linker + E3 into full PROTAC candidates.

```
MolecularConstructionAgent().run(state) → WorkflowState
  reads:  state.selected_warheads, state.selected_e3_ligands, state.generated_linkers
  sets:   state.construction_attempts, state.assembled_candidates
  tool:   toolbox.construct_protac_candidates() — 3 assembly strategies
```

### 10. CandidateValidationAgent
Validates constructed PROTACs for chemical validity and property filtering.

```
CandidateValidationAgent().run(state) → WorkflowState
  reads:  state.assembled_candidates
  sets:   state.valid_candidates
  tool:   toolbox.validate_candidates() — RDKit checks, property ranges
```

### 11. DegradationPredictionAgent
Predicts DC50, Dmax, and degradation probability.

```
DegradationPredictionAgent().run(state) → WorkflowState
  reads:  state.valid_candidates, state.target_record, state.parsed_objective
  sets:   state.degradation_predictions
  tool:   toolbox.predict_degradation() — heuristic (SynGlue-demo-heuristic-v0.1)
```

### 12. ADMETAgent
Computes ADME/Tox descriptors and risk flags.

```
ADMETAgent().run(state) → WorkflowState
  reads:  state.valid_candidates
  sets:   state.admet_predictions (MW, logP, TPSA, HBD, HBA, RotB, hERG, AMES, DILI)
  tool:   synglue_agent/tools/admet_predictors.py
```

### 13. NoveltyAgent
Checks candidates against known PROTACs.

```
NoveltyAgent().run(state) → WorkflowState
  reads:  state.valid_candidates
  sets:   state.novelty_results (nearest_known, tanimoto, novelty_score)
  data:   synglue_agent/data/known_protac_smiles.csv
```

### 14. TernaryFeasibilityAgent
Evaluates ternary complex feasibility via P4ward or geometric proxy.

```
TernaryFeasibilityAgent().run(state) → WorkflowState
  reads:  state.valid_candidates, state.parsed_objective
  sets:   state.ternary_feasibility_results
  tool:   synglue_agent/tools/ternary_feasibility.py (geometry proxy)
          synglue_agent/tools/p4ward_wrapper.py (full P4ward, requires Docker)
```

### 15. RankingAgent
Multi-parameter ranking with adjustable weights.

```
RankingAgent(final=False).run(state) → WorkflowState
  reads:  state.valid_candidates, state.degradation_predictions,
          state.admet_predictions, state.novelty_results
  sets:   state.ranking_results (rank, tier, final_priority_score, confidence)
  params: final=True → updates state.final_ranked_candidates
  tool:   toolbox.rank_candidates()
```

### 16. ProximityDiversityAgent
Clusters chemically similar candidates.

```
ProximityDiversityAgent().run(state) → WorkflowState
  reads:  state.valid_candidates
  sets:   state.diversity_clusters (cluster_id, representative_id, diversity_score)
  tool:   toolbox.cluster_candidates() — Tanimoto ≥ 0.62 threshold
```

### 17. ReflectionReviewAgent
Critiques top candidates for evidence strength and potential overclaims.

```
ReflectionReviewAgent().run(state) → WorkflowState
  reads:  state.ranking_results, state.valid_candidates
  sets:   state.reflection_reviews (plausibility, evidence, risk scores)
  tool:   toolbox.critique_candidates()
```

### 18. ReportAgent
Generates final markdown/CSV report.

```
ReportAgent().run(state) → WorkflowState
  reads:  all state fields
  sets:   state.report (markdown string)
          state.pipeline_status (step-by-step execution table)
  tool:   toolbox.generate_markdown_report()
  output: state.report (printed summary + detailed table)
```

### NP-hard Funnel Extension Agents

These agents were added to keep PROTAC design bounded instead of enumerating the full combinatorial search space. They are deterministic orchestration and proxy-scoring agents; they do not make experimental claims unless assay feedback is supplied.

```python
ControlledSearchAgent().run(state) -> WorkflowState
  reads:  state.parsed_objective.candidate_count, requested E3/cell context
  sets:   state.search_policy
  logic:  caps linker, E3, stereoisomer, construction, cheap-filter, expensive-modeling, and final budgets
```

```python
StereochemistryEnumerationAgent().run(state) -> WorkflowState
  reads:  state.assembled_candidates, state.search_policy.stereoisomer_budget_per_candidate
  sets:   state.assembled_candidates
  logic:  expands undefined stereocenters only up to the controlled budget and preserves stereoisomer IDs
```

```python
CellContextAgent().run(state) -> WorkflowState
  reads:  state.valid_candidates, state.target_record, state.parsed_objective.cell_line,
          state.parsed_objective.expression_overrides
  sets:   state.e3_context_predictions
  logic:  scores E3 expression, target/E3 localization fit, ligand availability, structure support, and resistance risk
  caveat: curated/default expression priors unless explicit expression overrides are provided
```

```python
CheapFilterAgent().run(state) -> WorkflowState
  reads:  state.valid_candidates, ADMET, novelty, applicability-domain, E3 context
  sets:   state.valid_candidates, state.cheap_filter_summary
  logic:  removes invalid/extreme candidates before degradation prediction and ternary modeling
```

```python
ExpensiveModelingSelectionAgent().run(state) -> WorkflowState
  reads:  state.valid_candidates, state.ranking_results, state.search_policy.expensive_modeling_budget
  sets:   state.expensive_modeling_candidate_ids
  logic:  selects a ranked/diverse finalist set for docking/P4ward or geometry-proxy ternary scoring
```

```python
CooperativityPredictionAgent().run(state) -> WorkflowState
  reads:  state.valid_candidates, state.ternary_feasibility_results
  sets:   state.cooperativity_predictions
  logic:  estimates proxy alpha from ternary feasibility, linker strain, interface, and lysine geometry
  caveat: ranking flags proxy_cooperativity_not_measured_alpha until measured or calibrated alpha is available
```

```python
HookEffectPredictionAgent().run(state) -> WorkflowState
  reads:  state.valid_candidates, state.degradation_predictions,
          state.cooperativity_predictions, state.e3_context_predictions
  sets:   state.hook_effect_predictions
  logic:  evaluates a concentration grid and therapeutic-window score for high-dose hook risk
  caveat: ranking flags proxy_hook_model_not_fitted_to_dose_response until fitted dose-response data is available
```

```python
ActiveLearningAgent().run(state) -> WorkflowState
  reads:  state.assay_feedback, state.valid_candidates
  sets:   state.active_learning_update
  tool:   synglue_agent/tools/assay_feedback.py
  logic:  appends candidate -> measured DC50/Dmax/hook/cell-line feedback rows and gates retraining readiness
```

---

## Tool APIs

### StereochemistryEngine (`tools/stereochemistry_engine.py`)

```python
get_stereochemistry_profile(smiles) → StereochemistryProfile
  # Returns chiral centers, E/Z bonds, stereoisomer count

validate_stereochemistry(smiles) → dict
  # Returns valid=True/False, issues list

enumerate_stereoisomers(smiles, max_isomers=32) → list[dict]
  # Returns all possible stereoisomers with SMILES and configs

assemble_with_stereo_preservation(wh_smi, lk_smi, e3_smi) → dict
  # Returns PROTAC SMILES with stereo preserved

compare_stereoisomers(smi_a, smi_b) → dict
  # Returns equivalent=True/False, differences list
```

### LinkerScanner (`tools/linker_scanner.py`)

```python
scan_linkers(warhead_smiles, e3_ligand_smiles, ...) → list[LinkerScanResult]
  # Scans N linkers × M attachment points, returns ranked results

detect_attachment_points(smiles, role) → list[AttachmentPoint]
  # Finds OH, NH, COOH, ArC-H, AlC-H attachment points

load_linker_library(linker_types=None) → list[dict]
  # Loads linkers from curated CSV + built-in defaults

scan_linkers_from_state(state) → list[LinkerScanResult]
  # Convenience: runs scan from a WorkflowState object
```

### P4ward Wrapper (`tools/p4ward_wrapper.py`)

```python
# Generates P4ward inputs, runs Docker, parses outputs
# Requires: Docker, paulajlr/p4ward:latest image (4.7 GB)
# Runtime: 2-4 hours per run
# Input:  receptor.pdb, ligase.pdb, receptor_ligand.mol2,
#         ligase_ligand.mol2, protac.smiles, config.ini
# Output: ternary interface scores, lysine distances, CRL models
```

---

## Workflow Graph Node Order

```
1.  parse_user_request       → SupervisorAgent
2.  create_design_plan       → DesignPlannerAgent
3.  control_np_hard_search   → ControlledSearchAgent
4.  safety_precheck          → SafetyAgent
5.  resolve_target           → TargetResolverAgent
6.  retrieve_target_binders  → TargetBinderRetrievalAgent
7.  select_warheads          → WarheadSelectionAgent
8.  select_e3_ligands        → E3LigandSelectionAgent
9.  detect_exit_vectors      → ExitVectorDetectionAgent
10. generate_linkers         → LinkerGenerationAgent
11. construct_protacs        → MolecularConstructionAgent
12. expand_stereoisomers     → StereochemistryEnumerationAgent
13. validate_protacs         → CandidateValidationAgent
14. score_cell_context       → CellContextAgent
15. predict_admet            → ADMETAgent
16. check_novelty            → NoveltyAgent
17. assess_applicability     → ApplicabilityDomainAgent
18. cheap_filter_candidates  → CheapFilterAgent
19. predict_degradation      → DegradationPredictionAgent
20. initial_ranking          → RankingAgent(final=False)
21. diversity_clustering     → ProximityDiversityAgent
22. reflection_review        → ReflectionReviewAgent
23. evolution_refinement     → EvolutionRefinementAgent
24. select_modeling_finalists→ ExpensiveModelingSelectionAgent
25. ternary_feasibility      → TernaryFeasibilityAgent
26. predict_cooperativity    → CooperativityPredictionAgent
27. predict_hook_effect      → HookEffectPredictionAgent
28. final_ranking            → RankingAgent(final=True)
29. active_learning_update   → ActiveLearningAgent
30. generate_report          → ReportAgent
31. update_memory            → MemoryUpdateAgent
```
