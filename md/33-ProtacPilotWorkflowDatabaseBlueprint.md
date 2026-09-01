# PROTACXtend Agent Workflow And Database Blueprint

## Purpose

This blueprint defines the foundation for PROTACXtend as a bounded, evidence-ranked, active-learning PROTAC design system. It does not claim to solve the whole PROTAC design space exhaustively. It turns the NP-hard search into a scientist-guided loop:

```text
request -> bounded generation -> cheap pruning -> finalist structural work
        -> evidence ranking -> scientist review -> experiment feedback
        -> calibrated retraining -> next design round
```

## 1. Data Schema

### Core Entities

| Table | Purpose | Required fields |
|---|---|---|
| `design_runs` | One scientist request and workflow execution | `run_id`, `user_request`, `mode`, `status`, `created_at`, `runtime_s`, `objective_json`, `warnings_json` |
| `targets` | Protein/gene target records | `target_id`, `gene_symbol`, `uniprot_id`, `organism`, `localization`, `structures_json`, `tractability_score`, `source_refs_json` |
| `binders` | Warheads or target binders | `binder_id`, `target_id`, `name`, `smiles`, `activity_type`, `activity_nM`, `assay_context`, `source`, `confidence` |
| `e3_ligases` | E3 ligase context records | `e3_id`, `name`, `family`, `complex_members_json`, `localization`, `ligandability_score`, `known_ligand_count` |
| `e3_ligands` | Recruiters/ligands for E3 ligases | `e3_ligand_id`, `e3_id`, `name`, `smiles`, `ligand_class`, `exit_vector_confidence`, `source`, `license_notes` |
| `cell_contexts` | Cell-line expression/context evidence | `context_id`, `cell_line`, `gene_symbol`, `e3_ligase`, `target_expression`, `e3_expression`, `proteomics_source`, `context_score`, `confidence` |
| `linkers` | Candidate linker inventory | `linker_id`, `name`, `smiles`, `linker_class`, `graph_length`, `effective_length`, `rotatable_bonds`, `tpsa`, `synthetic_feasibility` |
| `candidates` | Full PROTAC candidate records | `candidate_id`, `run_id`, `target_id`, `e3_id`, `warhead_id`, `e3_ligand_id`, `linker_id`, `full_smiles`, `parent_ids_json`, `provenance_json` |

### Evidence And Scoring Tables

| Table | Purpose | Required fields |
|---|---|---|
| `candidate_properties` | Calculated molecular descriptors | `candidate_id`, `mw`, `tpsa`, `logp`, `hbd`, `hba`, `rotatable_bonds`, `validity_status` |
| `degradation_predictions` | DC50/Dmax/probability predictions | `candidate_id`, `model_version`, `dc50_nM`, `dmax_percent`, `probability`, `confidence`, `warnings_json` |
| `admet_predictions` | Drug-like and safety-risk predictions | `candidate_id`, `mw`, `tpsa`, `logp`, `herg_risk`, `ames_risk`, `dili_risk`, `permeability_score`, `overall_penalty` |
| `novelty_results` | Similarity and duplicate flags | `candidate_id`, `nearest_known_id`, `max_tanimoto`, `duplicate_flag`, `novelty_score`, `patent_refs_json` |
| `ternary_feasibility` | Ternary geometry and structural outputs | `candidate_id`, `backend`, `pose_file`, `plausibility_score`, `interface_score`, `lysine_score`, `linker_strain_score`, `confidence`, `warnings_json` |
| `cooperativity_predictions` | Alpha/cooperativity estimates | `candidate_id`, `model_version`, `predicted_alpha`, `log_alpha`, `cooperativity_score`, `confidence`, `warning` |
| `hook_effect_predictions` | Concentration-dependent hook risk | `candidate_id`, `model_version`, `hook_concentration_nM`, `max_ternary_fraction`, `high_concentration_fraction`, `hook_risk`, `therapeutic_window_score` |
| `protacdb_evidence` | Partial external literature/database prior | `evidence_id`, `candidate_id`, `scope`, `evidence_family`, `value_type`, `value`, `units`, `source_ref`, `confidence` |
| `rankings` | Final multi-objective rank | `candidate_id`, `run_id`, `rank`, `tier`, `final_priority_score`, `confidence`, `reason`, `uncertainty_flags_json` |

### Active-Learning Tables

| Table | Purpose | Required fields |
|---|---|---|
| `experiment_batches` | Scientist-selected synthesis/testing batches | `batch_id`, `run_id`, `created_by`, `status`, `candidate_ids_json`, `rationale` |
| `assay_results` | Measured experimental feedback | `assay_id`, `candidate_id`, `target`, `e3_ligase`, `cell_line`, `dc50_nM`, `dmax_percent`, `ternary_kd_nM`, `alpha`, `pampa`, `caco2`, `hook_concentration_nM`, `source`, `notes` |
| `training_datasets` | Versioned train/validation snapshots | `dataset_id`, `created_at`, `row_count`, `schema_version`, `file_path`, `source_hash`, `holdout_policy` |
| `model_registry` | Active/calibrated model artifacts | `model_id`, `task`, `version`, `dataset_id`, `artifact_path`, `metrics_json`, `status`, `promoted_at`, `rollback_model_id` |
| `audit_events` | Full traceability | `event_id`, `run_id`, `agent_name`, `action`, `input_hash`, `output_hash`, `elapsed_s`, `evidence_refs_json` |

## 2. Agent Roles

| Agent | Role | Main outputs |
|---|---|---|
| `SupervisorAgent` | Parse user request and constraints | `ParsedObjective` |
| `DesignPlannerAgent` | Decide workflow depth and repeat policy | `design_plan` |
| `ControlledSearchAgent` | Bound NP-hard combinatorics | `SearchPolicy` |
| `SafetyAgent` | Reject unsafe or impossible requests | `warnings`, `errors` |
| `TargetResolverAgent` | Resolve target, UniProt, structure availability | `TargetRecord` |
| `TargetBinderRetrievalAgent` | Retrieve known binders/warheads | `BinderRecord` |
| `WarheadSelectionAgent` | Choose warheads and annotate confidence | `WarheadRecord` |
| `E3LigandSelectionAgent` | Select E3 ligands/recruiters | `E3LigandRecord` |
| `ExitVectorDetectionAgent` | Find attachment points | `ExitVectorRecord` |
| `LinkerGenerationAgent` | Generate bounded linker set | `LinkerRecord` |
| `MolecularConstructionAgent` | Assemble candidate PROTACs | `CandidateRecord` |
| `StereochemistryEnumerationAgent` | Expand unresolved stereochemistry with caps | candidate variants |
| `CandidateValidationAgent` | Validate SMILES and properties | candidate flags |
| `CellContextAgent` | Score cell-line target/E3 context | `E3ContextPrediction` |
| `ADMETAgent` | Predict drug-like risks | `ADMETPrediction` |
| `NoveltyAgent` | Check known PROTAC similarity/patent refs | `NoveltyResult` |
| `ApplicabilityDomainAgent` | Estimate model-domain reliability | `ApplicabilityDomainResult` |
| `CheapFilterAgent` | Prune before expensive modeling | survivor set |
| `DegradationPredictionAgent` | Predict DC50/Dmax/degradation probability | `DegradationPrediction` |
| `RankingAgent` | Multi-objective ranking | `RankingResult` |
| `ProximityDiversityAgent` | Preserve chemical diversity | `DiversityCluster` |
| `ReflectionReviewAgent` | Identify weak evidence and rerank caveats | `ReflectionReview` |
| `EvolutionRefinementAgent` | Mutate/crossover top candidates | evolved candidates |
| `ExpensiveModelingSelectionAgent` | Choose structural finalists | finalist IDs |
| `TernaryFeasibilityAgent` | Run/score ternary geometry and poses | `TernaryFeasibilityResult` |
| `CooperativityPredictionAgent` | Estimate alpha/cooperativity | `CooperativityPrediction` |
| `HookEffectPredictionAgent` | Estimate hook effect risk | `HookEffectPrediction` |
| `ActiveLearningAgent` | Ingest feedback and update registry | `ActiveLearningUpdate` |
| `ReportAgent` | Generate scientist-facing report | markdown/JSON/CSV artifacts |
| `MemoryUpdateAgent` | Persist run memory/audit | memory artifact |

## 3. Scoring Functions

All scores should be normalized to `[0, 1]`, versioned, and evidence-labeled.

### Degradation Score

```text
dc50_score = clamp(1 - log10(dc50_nM + 1) / 5)
dmax_score = clamp(dmax_percent / 100)
degradation_score = 0.58 * dc50_score + 0.42 * dmax_score
```

### ADMET Score

```text
admet_score = clamp(1 - overall_admet_penalty)
```

Penalty sources:

- high MW/TPSA/rotatable bonds
- hERG, AMES, DILI
- poor solubility/permeability
- reactive groups and PAINS alerts

### Ternary Structural Score

For pose-backed candidates:

```text
real_structural_score =
  0.34 * interface_quality_score
+ 0.31 * lysine_geometry_score
+ 0.20 * linker_strain_score
+ 0.15 * interface_contact_presence
```

For candidates without a pose:

```text
ternary_score = geometry_proxy_score
evidence_level = proxy_only
```

### Cooperativity Score

```text
cooperativity_score =
  0.38 * interface_contact_score
+ 0.27 * linker_strain_score
+ 0.22 * lysine_geometry_score
+ 0.13 * ternary_plausibility_score
```

Then optionally blend a capped PROTAC-DB ternary-affinity prior:

```text
cooperativity_score =
  (1 - prior_weight) * model_score
+ prior_weight * protacdb_ternary_prior
```

### Hook-Effect Score

Use a ternary occupancy grid across concentration:

```text
hook_risk = high if high_concentration_fraction << max_ternary_fraction
therapeutic_window_score = area near useful degradation window without collapse
```

### Cell Context Score

```text
context_score =
  0.36 * e3_expression_score
+ 0.24 * target_expression_score
+ 0.18 * colocalization_score
+ 0.12 * ligand_availability_score
+ 0.10 * resistance_inverse_score
```

### Novelty And Diversity

```text
novelty_score = 1 - max_tanimoto_to_known_protacs
diversity_bonus = cluster_coverage_bonus_for_top_ranked_set
```

## 4. Candidate Ranking Algorithm

### Ranking Inputs

- degradation score
- ADMET score
- ternary score
- cooperativity score
- hook therapeutic-window score
- cell-context score
- novelty score
- synthetic feasibility
- applicability-domain confidence
- PROTAC-DB evidence prior

### Default Final Priority Score

```text
final_priority_score =
  w_dc50          * dc50_score
+ w_dmax          * dmax_score
+ w_admet         * admet_score
+ w_ternary       * ternary_score
+ w_cooperativity * cooperativity_score
+ w_hook          * hook_window_score
+ w_cell_context  * cell_context_score
+ w_novelty       * novelty_score
+ w_synthetic     * synthetic_score
+ capped_protacdb_bonus
```

### Ranking Rules

1. Hard reject invalid SMILES, extreme ADMET outliers, and impossible synthesis flags.
2. Preserve diversity before final ranking so one chemotype does not dominate.
3. Run expensive structural scoring only on finalists.
4. Penalize unsupported confidence, not novelty itself.
5. Treat PROTAC-DB absence as unknown, not negative evidence.
6. Report rank reason and uncertainty flags for every finalist.

## 5. Active-Learning Loop

### Loop

```text
ranked candidates
-> scientist selects experiment batch
-> assay results imported
-> data validator normalizes units/context
-> training snapshot created
-> model retraining job runs
-> validation against holdout families
-> promote or rollback
-> next run uses calibrated model version
```

### Promotion Gates

A new model can be promoted only if it improves:

- held-out DC50/Dmax rank correlation
- ternary Kd/alpha calibration
- hook-effect classification
- permeability classification
- uncertainty calibration

It must not regress:

- out-of-domain warning rate
- exact-known positive recall
- known failure rejection

## 6. UI/Workflow For Scientists

### Primary Views

| View | Scientist action |
|---|---|
| `Design Request` | Enter target, E3 preference, cell line, constraints, count |
| `Search Budget` | Inspect controlled search caps before run |
| `Candidate Table` | Sort/filter by rank, DC50, Dmax, ADMET, structural score, novelty |
| `Evidence Panel` | See source of every score: proxy, PROTAC-DB prior, pose-backed, calibrated |
| `Structural Finalists` | Upload/view pose PDBs, inspect interface/lysine/linker-strain metrics |
| `Pareto/Diversity` | Compare potency vs ADMET vs novelty vs structural feasibility |
| `Experiment Batch` | Select candidates for synthesis/testing and export CSV |
| `Assay Feedback` | Import DC50/Dmax/alpha/permeability/hook data |
| `Model Registry` | See active model version, validation metrics, rollback option |
| `Report` | Export markdown/CSV/JSON bundle |

### Required UI Guardrails

- Always show evidence level beside every score.
- Never show proxy-only score as experimentally validated.
- Show "PROTAC-DB incomplete" near database-derived priors.
- Show cell line and E3 expression source when context scoring is used.
- Show rank reasons and uncertainty flags in the candidate table.
- Separate "recommended for modeling" from "recommended for synthesis".

## 7. Implementation Architecture For PROTACXtend

### Runtime Layers

```text
Streamlit UI / FastAPI / CLI
        |
        v
synglue_agent.agents.runtime.run_protacpilot
        |
        v
deterministic graph or agentic graph
        |
        v
scientific tools + database loaders + model registry
        |
        v
outputs/runs/{run_id} + database tables + audit events
```

### Current Code Anchors

| Layer | Current path |
|---|---|
| Streamlit UI | `synglue_agent/app/streamlit_app.py` |
| API | `synglue_agent/backend/api_routes.py` |
| Unified runtime | `synglue_agent/agents/runtime.py` |
| Deterministic graph | `synglue_agent/agents/graph.py` |
| Agent schemas | `synglue_agent/backend/schemas.py` |
| Main toolbox | `synglue_agent/tools/protac_toolbox.py` |
| Structural scorer | `synglue_agent/tools/structural_scoring.py` |
| PROTAC-DB loader | `synglue_agent/tools/protacdb_client.py` |
| Cell-context engine | `synglue_agent/tools/e3_context_engine.py` |
| Active-learning agent | `synglue_agent/agents/active_learning_agent.py` |

### Build Order

1. Freeze schema names and JSON payload contracts.
2. Add SQLite/Postgres persistence adapter matching this blueprint.
3. Store every run as both files and database rows.
4. Add UI evidence badges and schema-backed candidate table filters.
5. Add structural finalist upload/P4ward output ingestion.
6. Add experiment batch export/import.
7. Add active-learning model registry view.
8. Add validation dashboards for promoted models.

## Near-Term Implementation Tickets

| Priority | Ticket | Outcome |
|---|---|---|
| P0 | Add database schema migration file | Durable tables for runs, candidates, scores, assays, registry |
| P0 | Persist `WorkflowState` into schema tables | UI/API can query historical runs |
| P0 | Add evidence-level fields to candidate table | Scientists can distinguish proxy vs pose vs calibrated evidence |
| P1 | Add structural finalist ingestion UI | Upload or select P4ward pose PDBs |
| P1 | Add experiment batch export/import | Active learning starts from real assay feedback |
| P1 | Add model registry backend | Versioned training, validation, promotion, rollback |
| P2 | Add validation dashboard | Scientist can inspect model trust before using scores |

