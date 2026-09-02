# SynGlue-Agent PROTAC Design Report

SynGlue-Agent is a tool-augmented, memory-enabled, workflow-orchestrated agentic AI framework for component-aware PROTAC design.

## Objective
- User request: Design 5 BRD4 CRBN PROTAC candidates with structure-aware ranking in MM1.S cells
- Target: MM1
- E3 ligase: CRBN
- Candidate target count: 5

## Workflow Summary
- Binders retrieved: 0
- Warheads selected: 5
- E3 ligands selected: 3
- Linkers generated: 12
- Construction attempts: 80
- Valid or unverified candidates: 40
- Cheap-filter survivors: 40/80
- Expensive-modeling finalists: 10
- Evolved candidates: 17

## Scientific Guardrails
- Values are computational predictions, not experimental validation.
- Model version is reported for degradation predictions.
- Cooperativity alpha is an exploratory proxy unless backed by measured ternary binding or a calibrated alpha model.
- Hook-effect risk is a concentration-occupancy proxy unless fitted to measured dose-response data.
- Expensive ternary modeling is restricted to the selected finalist subset, not the full generated space.
- Human medicinal chemistry and safety review is required before synthesis or wet-lab testing.

## Active Learning
- Feedback records added: 0
- Training rows available: 0
- Retraining recommendation: collect_more_feedback_before_retraining

## Warnings
- BindingDB REST needs an API key (BINDINGDB_API_KEY); ChEMBL covers binding data.
- TargetBinderRetrievalAgent: No binders found from any source.
- No target-matched warheads found. Included demo warheads for demonstration.
- Evolution stopped: novelty_ratio<0.1 for 2 gens
- No target PDB structure available for docking.

## Top Ranked Candidates

| Rank | Tier | Target | E3 ligase | Warhead name | Linker class | Predicted DC50 nM | Predicted Dmax % | Predicted cooperativity alpha | Hook risk | E3 context score | hERG risk | Novelty score | Final priority score | Warning flags |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Tier 2 | MM1 | CRBN | BRD4_demo_JQ1_like | piperazine | 19.2 | None | 17.74 | high | 0.91 | low | 0.722 | 0.614 | low_degradation_model_confidence;high_hook_effect_risk;proxy_cooperativity_not_measured_alpha;proxy_hook_model_not_fitted_to_dose_response |
| 2 | Tier 2 | MM1 | CRBN | BRD4_demo_JQ1_like | triazole | 20.4 | None | 17.761 | high | 0.91 | medium | 0.785 | 0.608 | low_degradation_model_confidence;high_hook_effect_risk;proxy_cooperativity_not_measured_alpha;proxy_hook_model_not_fitted_to_dose_response |
| 3 | Tier 2 | MM1 | CRBN | BRD4_demo_JQ1_like | piperazine | 12.0 | None | 14.752 | high | 0.91 | medium | 0.774 | 0.607 | low_degradation_model_confidence;high_hook_effect_risk;proxy_cooperativity_not_measured_alpha;proxy_hook_model_not_fitted_to_dose_response |
| 4 | Tier 2 | MM1 | CRBN | BRD4_demo_triazolobenzodiazepine_like | piperazine | 25.0 | None | 12.67 | high | 0.91 | low | 0.798 | 0.607 | low_degradation_model_confidence;high_hook_effect_risk;proxy_cooperativity_not_measured_alpha;proxy_hook_model_not_fitted_to_dose_response |
| 5 | Tier 2 | MM1 | CRBN | BRD4_demo_quinazoline_like | piperazine | 14.7 | None | 14.752 | high | 0.91 | medium | 0.859 | 0.606 | high_hook_effect_risk;proxy_cooperativity_not_measured_alpha;proxy_hook_model_not_fitted_to_dose_response |

## Agent Workflow Table

| Agent type | Selected tool | Tool status | Real output generated | Integration note | Data sources/tools | Query parameters | Quantitative outputs | Processing time |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Controlled Search Agent | Search policy | registered | yes - explicit NP-hard search budgets | planned integration | bounded deterministic budget policy | requested_candidates=5 | linker_budget=12, construction_budget=80, expensive_budget=10 | milliseconds locally |
| Target Resolver Agent | Target assessment | registered | yes - local/ChEMBL target metadata | planned integration | local curated target table; ChEMBL target fallback if network is available; no PDB/AlphaFold fetch is run here | target=MM1, organism=human | UniProt=Q16293, structures=0, tractability=0.0 | milliseconds locally; seconds only if online ChEMBL fallback is reached |
| Binder Retrieval Agent | Warhead mining | registered | no - no binder records | PubChem and BindingDB remain planned integrations unless their specific callables are invoked. | local curated binders; optional ChEMBL online fallback; PubChem name lookup only as ChEMBL helper; BindingDB is planned, not run | activity IC50/Ki/Kd/EC50 <= 1000 nM; assay confidence threshold | binders=0, unique_smiles=0 | milliseconds locally; minutes only with online APIs |
| Warhead Selection Agent | Warhead mining | registered | yes - selected warhead records | planned integration | selected binders, local scoring, optional RDKit validation; curated exit-vector markers only | activity IC50/Ki/Kd <= 1000 nM; derivatization feasible | binders=0, warheads=5 | milliseconds locally |
| E3 Ligand Agent | E3 ligase selection | registered | yes - local E3 ligand records | External HPA/DepMap/ProteomicsDB/E3Net expression queries remain planned integrations. | local curated CRBN/VHL/IAP/MDM2 handles plus optional explicit expression context | requested_e3=CRBN, cell_line=MM1.S | e3_ligands=3, ligases=1 | milliseconds locally |
| Cell Context Agent | E3-context compatibility | registered | yes - deterministic cell/E3 context scores | planned integration | curated E3 expression evidence, target localization rules, optional user expression overrides | cell_line=MM1.S, overrides=False | e3_context_records=40 | milliseconds locally |
| Exit Vector Agent | Warhead Agent | registered | yes - local exit-vector annotations | planned integration | explicit attachment markers and local confidence rules; no structural exit-vector modeling is run | warhead and E3 ligand component SMILES | vectors=8, ambiguous=0 | milliseconds locally |
| Linker Generation Agent | Linker design | registered | yes - curated/rule-based linker records | Generative linker models remain planned integrations. | curated linker CSV plus rule-based enumeration; LinkInvent/DiffLinker/DeLinker are planned, not run | linker_types=PEG,alkyl,piperazine,triazole | linkers=12, classes=5 | milliseconds locally; model generation not run |
| Construction Agent | Assembly Agent | registered | yes - assembled candidate records | Retrosynthesis-aware route planning is planned integration. | local dummy-atom assembly with RDKit when installed; named strategies currently share the same assembler | warhead + linker + E3 with valid exit vectors | attempts=80, valid=40 | seconds locally |
| Cheap Filter Agent | Cheap molecular filter | registered | yes - pre-ternary filtered candidate set | planned integration | RDKit validity, MW, TPSA, rotatable bonds, synthetic feasibility, novelty, ADMET, applicability domain, E3 context | max_keep=40 | kept=40, rejected=4 | milliseconds to seconds locally |
| Prediction Agent | DC50/Dmax prediction | registered | no - heuristic demo predictions only | Trained DC50/Dmax prediction is planned integration. | heuristic demo predictor in codebase; no trained SynGlue/DeepPROTACs/PROTAC-STAN model is loaded | cheap-filter survivors, components, target, E3 ligase, optional cell context | degradation_predictions=40 | seconds locally |
| ADME/Tox Agent | ADME/Tox skill | registered | no - heuristic/local ADME-Tox triage only | External ADME/Tox predictors remain planned integrations. | RDKit descriptors when available plus heuristic risk triage; SwissADME/ADMETlab/pkCSM/ProTox-II are not run | PROTAC-aware thresholds; no strict Lipinski rejection | admet_records=40 | seconds locally |
| Novelty Agent | Novelty/IP check | registered | yes - local similarity/duplicate records | SureChEMBL/Lens/Google Patents/PubChem novelty search is planned integration. | local known-PROTAC set; RDKit Morgan similarity when available; patent/PubChem/ChEMBL novelty search is not run | candidate SMILES and similarity thresholds | novelty_records=40 | seconds locally |
| Ternary Feasibility Agent | Ternary complex modeling | registered | no - geometry proxy only | Docking/ternary modeling is planned integration. | finalist-only geometry proxy; docking/P4ward only when structure-aware ranking is requested and tools are available | finalist_ids=10 | ternary_records=10 | seconds locally; docking not run |
| Cooperativity Agent | Cooperativity proxy | registered | yes - proxy alpha estimates | Measured alpha or calibrated structure/ML cooperativity model is still needed for validation. | ternary geometry, linker strain, interface-contact proxy, and lysine-geometry proxy | valid candidates plus ternary feasibility records | cooperativity_records=40 | milliseconds locally |
| Hook Effect Agent | Concentration occupancy model | registered | yes - concentration-dependent hook-risk curves | Occupancy parameters are priors until fitted to cellular dose-response data. | DC50/Dmax predictions, E3 affinity priors, cooperativity alpha, and cell-context E3 score | 0.1-10000 nM concentration grid | hook_records=40, high_risk=38 | milliseconds locally |
| Ranking Agent | Ranking skill | registered | yes - ranking records over current outputs | planned integration | weighted deterministic ranking over available local/heuristic outputs | balanced degradation, ADME/Tox, novelty, and synthesis feasibility | ranked=40, final=5 | seconds |
| Reflection/Evolution Agent | Mini-PROTAC optimization | registered | yes - local deterministic review/evolution records | Full generative mini-PROTAC optimization is planned integration. | deterministic critique and linker replacement over current candidate records | top candidates and weaknesses | reviews=20, evolved=17 | seconds to minutes |
| Safety/Human Review Agent | Assay planning skill | registered | no - assay/human-review plan not generated; local guardrail status only | Expert assay planning and human-review packet generation are planned integrations. | local guardrail rules and warning aggregation | final candidates and requested use | warnings=5, errors=0, human_review_required=True | milliseconds locally |

## Pipeline Status Labels

| step_name | selected_tool_or_method | tool_status | output_type | real_output_generated | stub_or_heuristic | limitation | next_integration_needed |
| --- | --- | --- | --- | --- | --- | --- | --- |
| target resolution | Target assessment; optional UniProt executable lookup available separately | Target assessment: heuristic_stub; UniProt: executable | TargetRecord | True | local_demo_or_api_wrapper | Workflow still primarily uses local curated target records unless explicit executable wrappers are called. | Route target resolution through UniProt/Open Targets/RCSB executable wrappers with no silent local fallback. |
| warhead/binder retrieval | Warhead mining; local curated binders; PubChem lookup wrapper available separately | Warhead mining: heuristic_stub; PubChem lookup: executable only if wrapper exists and succeeds | list[BinderRecord] | False | not_connected | BindingDB is not connected; PubChem is not claimed unless its wrapper is explicitly called and succeeds. | Connect ChEMBL/BindingDB executable mining and provenance filtering. |
| E3 ligand selection | E3 ligase selection from local curated E3 ligand table | E3 ligase selection: heuristic_stub | list[E3LigandRecord] | True | local_demo | No HPA/DepMap/ProteomicsDB/E3Net expression or context query is run. | Add tissue/cell-line-aware E3 expression and ligand source checks. |
| linker generation | Linker design using curated CSV plus rule-based enumeration | Linker design: heuristic_stub | list[LinkerRecord] | True | local_demo | LinkInvent/DiffLinker/DeLinker are registered but not executed. | Connect generative linker tools and 3D constraints. |
| assembly | Assembly Agent using local dummy-atom/RDKit join when possible | Assembly Agent: heuristic_stub; RDKit: executable | list[CandidateRecord] | True | local_demo | Named assembly strategies still share scaffold logic; no retrosynthetic route proof. | Use validated RDKit/RDChiral reactions with atom mapping and route checks. |
| DC50/Dmax prediction | Heuristic SynGlue-demo degradation predictor | DC50/Dmax prediction: heuristic_stub | list[DegradationPrediction] | False | heuristic_stub | Predicted DC50/Dmax values are heuristic demo outputs, not trained model outputs. | Load validated SynGlue/DeepPROTACs/PROTAC-STAN/Chemprop models with uncertainty. |
| ADME/Tox prediction | ADMET backend orchestrator (local_model/api/descriptor_rule_based/heuristic_stub) | RDKit descriptors: executable; ADME/Tox backend=descriptor_rule_based | list[ADMETPrediction] | True | descriptor_rule_based | Descriptor-rule output is not ML endpoint prediction; API/model paths depend on config. | Add validated local ADMET models and configured external endpoints for full endpoint coverage. |
| novelty/IP | Novelty/IP check against local known-PROTAC set | Novelty/IP check: heuristic_stub | list[NoveltyResult] | True | local_demo | Patent/PubChem/ChEMBL/SureChEMBL/Lens novelty searches are not run. | Add exact/similarity/substructure searches across public and patent databases. |
| retrosynthesis | Synthesis planning / retrosynthesis feasibility filter | Synthesis planning: heuristic_stub | synthetic_feasibility_score | False | heuristic_stub | AiZynthFinder/ASKCOS/IBM RXN/RAscore are not run. | Connect route planning and purchasable building-block checks. |
| ternary feasibility | Ternary complex modeling; GNINA docking registered but not run | Ternary complex modeling: heuristic_stub; GNINA docking: registered but not executable | list[TernaryFeasibilityResult] | False | heuristic_stub | No docking engine, PRosettaC/HADDOCK/GNINA, or MD refinement is run. | Connect protein prep, docking/ternary modeling, and interface scoring. |
| ranking | Ranking skill using weighted deterministic score over current outputs | Ranking skill: heuristic_stub | list[RankingResult] | True | heuristic | Ranking inherits limitations of heuristic/local upstream outputs. | Add calibrated gates, uncertainty-aware ranking, and real model/tool provenance. |
| final report | Report generation from current WorkflowState | Report generation: heuristic_stub | markdown/json/csv report artifacts | False | not_connected | Report is real as an artifact, but scientific claims remain limited by upstream status labels. | Keep report labels synchronized with executable tool provenance. |