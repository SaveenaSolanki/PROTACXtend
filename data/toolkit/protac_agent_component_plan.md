# PROTAC Agent Gap-To-Component Build Plan

## Summary
- Workflow modules audited: 17
- Executable verified modules: 0
- Executable not tested modules: 4
- Heuristic stubs: 9
- Local-demo-data-only modules: 4
- Registered-only/planned primary modules: 0

This audit is based on repository source, configs, reports, registries, and local PROTAC repo audit files only. It does not install dependencies, run training, run docking, call external APIs, or alter generated scientific candidates.

## Current Classification

| Step | Agent | Status | Priority | Current file | Callable/class |
| --- | --- | --- | --- | --- | --- |
| 1 | Target Resolver Agent | `executable_not_tested` | `P1_core_required` | `protacxtend/agents/target_agent.py; protacxtend/tools/protac_toolbox.py` | `TargetResolverAgent.run; ProtacDesignToolbox.resolve_target` |
| 2 | Binder Retrieval Agent | `local_demo_data_only` | `P1_core_required` | `protacxtend/agents/binder_agent.py; protacxtend/tools/protac_toolbox.py` | `TargetBinderRetrievalAgent.run; retrieve_known_binders; mine_external_binders` |
| 3 | Warhead Selection Agent | `heuristic_stub` | `P1_core_required` | `protacxtend/agents/warhead_agent.py; protacxtend/tools/warhead_selector.py` | `WarheadSelectionAgent.run; ProtacDesignToolbox.select_warheads` |
| 4 | Exit Vector Agent | `heuristic_stub` | `P1_core_required` | `protacxtend/agents/exit_vector_agent.py; protacxtend/tools/exit_vector_detector.py` | `ExitVectorDetectionAgent.run; detect_exit_vectors` |
| 5 | E3 Ligand Agent | `local_demo_data_only` | `P1_core_required` | `protacxtend/agents/e3_agent.py; protacxtend/tools/e3_selector.py` | `E3LigandSelectionAgent.run; select_e3_ligands` |
| 6 | Linker Generation Agent | `local_demo_data_only` | `P1_core_required` | `protacxtend/agents/linker_agent.py; protacxtend/tools/linker_generator.py` | `LinkerGenerationAgent.run; generate_state_of_the_art_linker_panel` |
| 7 | Construction / Assembly Agent | `executable_not_tested` | `P1_core_required` | `protacxtend/agents/construction_agent.py; protacxtend/tools/molecular_constructor.py` | `MolecularConstructionAgent.run; CandidateValidationAgent.run; construct_protac_candidates` |
| 8 | DC50 Prediction Agent | `heuristic_stub` | `P0_truthfulness_fix` | `protacxtend/agents/prediction_agent.py; protacxtend/tools/degradation_predictor.py` | `DegradationPredictionAgent.run; predict_degradation; predict_dc50_dmax` |
| 9 | Dmax Prediction Agent | `heuristic_stub` | `P0_truthfulness_fix` | `protacxtend/agents/prediction_agent.py; protacxtend/tools/degradation_predictor.py` | `DegradationPredictionAgent.run; predict_degradation; predict_dc50_dmax` |
| 10 | ADME/Tox Agent | `heuristic_stub` | `P0_truthfulness_fix` | `protacxtend/agents/admet_agent.py; protacxtend/tools/admet_predictors.py` | `ADMETAgent.run; predict_admet; run_rule_based_admet_flags` |
| 11 | Novelty/IP Agent | `local_demo_data_only` | `P0_truthfulness_fix` | `protacxtend/agents/novelty_agent.py; protacxtend/tools/novelty_checker.py` | `NoveltyAgent.run; check_novelty; search_pubchem_similarity_for_novelty` |
| 12 | Ternary Feasibility Agent | `heuristic_stub` | `P0_truthfulness_fix` | `protacxtend/agents/ternary_agent.py; protacxtend/tools/ternary_feasibility.py` | `TernaryFeasibilityAgent.run; assess_ternary_feasibility; run_optional_docking_stub` |
| 13 | Retrosynthesis Agent | `heuristic_stub` | `P0_truthfulness_fix` | `protacxtend/tools/retrosynthesis_filter.py` | `retrosynthesis_feasibility_filter; explain_retrosynthesis_score` |
| 14 | Ranking Agent | `heuristic_stub` | `P0_truthfulness_fix` | `protacxtend/agents/ranking_agent.py; protacxtend/tools/ranker.py` | `RankingAgent.run; rank_candidates; pairwise_tournament_ranking` |
| 15 | Reflection/Evolution Agent | `heuristic_stub` | `P4_nice_to_have` | `protacxtend/agents/reflection_agent.py; protacxtend/agents/evolution_agent.py` | `ReflectionReviewAgent.run; EvolutionRefinementAgent.run; evolve_candidates` |
| 16 | Safety/Human Review Agent | `executable_not_tested` | `P0_truthfulness_fix` | `protacxtend/agents/safety_agent.py` | `SafetyAgent.run; safety_precheck` |
| 17 | Report Generation Agent | `executable_not_tested` | `P0_truthfulness_fix` | `protacxtend/agents/report_agent.py; protacxtend/tools/report_generator.py` | `ReportAgent.run; generate_markdown_report; generate_candidate_table` |

## Candidate-Level Provenance Contract

Every future candidate score for DC50, Dmax, ADME/Tox endpoints, novelty/IP, ternary feasibility, retrosynthesis, ranking, and final priority must carry these fields:
- `score_name`
- `score_value`
- `evidence_type`
- `tool_status`
- `source_tool_or_database`
- `source_file_or_url`
- `model_version`
- `run_timestamp`
- `input_hash`
- `limitations`
- `confidence`
- `uncertainty`
- `applicability_domain`
- `claim_allowed`

Allowed `evidence_type` values: `trained_model`, `external_api`, `local_database`, `rdkit_descriptor`, `heuristic_proxy`, `not_run`, `missing`.
Allowed `tool_status` values are the required audit labels, and `executable_not_tested` must never be counted as `executable_verified`.

## Component Build Plan

### Phase 0: Truthfulness and report-label corrections
- Add per-score tool_status, evidence_type, limitation, provenance, and uncertainty_source fields.
- Rename DC50/Dmax report columns or labels to heuristic until trained model backends are loaded.
- Add forbidden-claim tests and executable-count tests.

### Phase 1: Executable local data loaders and schemas
- Validate CSV schemas for targets, E3 ligands, linkers, known PROTACs, PROTAC-DB, and PROTACpedia local files.
- Require local_demo_data_only labels whenever only local seed/demo rows are used.
- Add candidate score provenance object to candidate JSON/table exports.

### Phase 2: Core wrappers for UniProt, ChEMBL, PubChem, local PROTAC databases, RDKit validation
- Connect source-labeled target, binder, chemistry, novelty, and assembly wrappers behind structured result objects.
- Mock external calls in tests; do not call APIs by default.
- Make wrapper failure modes explicit and non-silent.

### Phase 3: Validated prediction model wrappers for DC50, Dmax, ADME/Tox
- Load trained model artifacts only when explicitly configured.
- Record model version, training metadata pointer, uncertainty, and applicability domain.
- Keep heuristic and descriptor-rule fallbacks clearly labeled.

### Phase 4: Ternary feasibility and docking as optional heavy modules
- Keep docking/structure modules disabled/manual by default.
- Add wrapper contracts for protein prep, ligand prep, docking, ternary modeling, and interface scoring.
- Never report docking scores when docking did not run.

### Phase 5: Agent orchestration and ranking with uncertainty/provenance gates
- Block strong claims from heuristic/local-demo upstream scores.
- Aggregate score provenance into ranking confidence.
- Require human-review packet before any synthesis or experimental recommendation language.

## Forbidden-Claim Tests
- Fail if heuristic DC50/Dmax is described as a trained model prediction.
- Fail if ternary feasibility is described as docking/modeling when docking_status is skipped or not run.
- Fail if novelty/IP is described as patent-safe when patent search did not run.
- Fail if ADME/Tox endpoint risk is described as ML/API-predicted when backend is descriptor/rule/heuristic.
- Fail if ranking confidence omits upstream heuristic/local-demo provenance.
- Fail if final reports omit tool_status, evidence_type, or limitation for any score.
- Fail if candidate JSON lacks per-score provenance fields.
- Fail if executable_not_tested is counted as executable_verified.

## What Must Never Be Claimed Until Verified
- Trained DC50/Dmax prediction without a loaded, versioned, validated model.
- Real ternary docking/modeling when docking_status is skipped, not_run, or stub.
- Patent-safe or IP-clear novelty without patent search evidence.
- ML/API ADME/Tox endpoint prediction when only descriptors, rules, or heuristics ran.
- Calibrated ranking confidence without upstream provenance and uncertainty gates.
- Chemically validated assembly when RDKit/RDChiral validation did not pass.
