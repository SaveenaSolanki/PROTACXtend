> **VERDICT: DESIGN BRIEF ONLY** — candidates lack verified component/attachment provenance
> scientific_result: false
> reasons: candidates lack verified component/attachment provenance

# PROTACXtend PROTAC Design Report

PROTACXtend is a tool-augmented, memory-enabled, workflow-orchestrated agentic AI framework for component-aware PROTAC design.

## Objective
- User request: Design a CRBN-recruiting PROTAC for BRD4
- Target: BRD4
- E3 ligase: CRBN
- Candidate target count: 50

## Workflow Summary
- Binders retrieved: 100
- Warheads selected: 9
- E3 ligands selected: 3
- Linkers generated: 18
- Construction attempts: 1458
- Valid or unverified candidates: 150
- Cheap-filter survivors: 150/180
- Expensive-modeling finalists: 0
- Evolved candidates: 0

## Scientific Guardrails
- Values are computational predictions, not experimental validation.
- Model version is reported for degradation predictions.
- Cooperativity alpha is an exploratory proxy unless backed by measured ternary binding or a calibrated alpha model.
- Hook-effect risk is a concentration-occupancy proxy unless fitted to measured dose-response data.
- Expensive ternary modeling is restricted to the selected finalist subset, not the full generated space.
- PROTAC-DB evidence is used as a capped prior only; it is incomplete and absence from PROTAC-DB is not negative evidence.
- Human medicinal chemistry and safety review is required before synthesis or wet-lab testing.

## KNOW -> REASON -> DESIGN -> DISCOVER Contract
- Stopping state: REVISE
- Selected option: SGA-214601f354c0
- Next action: prepare experiment dossier
- Critique status: REVISE
- Decision-critical missing data: measured prospective outcome feedback
- Selected dynamic action: reason.dynamic_action_selection
- Evidence labels enforced: measured, curated, reported, computed, predicted, inferred, hypothetical, contradicted.

## Warnings
- TargetBinderRetrievalAgent: Retrieved 609 binders from ChEMBL, PubChem, BindingDB.
- TargetBinderRetrievalAgent: Live source unavailable; replayed 1 cached live-fetch record(s) (url=https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/smiles/COC%28%3DO%29CC1CC%28%…, fetched_at=2026-09-25T04:26:12Z, disk cache=/storage/saveena/protacxtend/data/live_cache). Replayed payloads are real prior live-API responses, not fixtures.
- TargetBinderRetrievalAgent: Live source unavailable; replayed 1 cached live-fetch record(s) (url=https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/smiles/CN1C%5BC%40H%5D%28c2cc…, fetched_at=2026-09-25T04:26:13Z, disk cache=/storage/saveena/protacxtend/data/live_cache). Replayed payloads are real prior live-API responses, not fixtures.
- TargetBinderRetrievalAgent: Live source unavailable; replayed 1 cached live-fetch record(s) (url=https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/smiles/CCOC%28%3DO%29C1%28C%2…, fetched_at=2026-09-25T04:26:19Z, disk cache=/storage/saveena/protacxtend/data/live_cache). Replayed payloads are real prior live-API responses, not fixtures.
- TargetBinderRetrievalAgent: Live source unavailable; replayed 1 cached live-fetch record(s) (url=https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/smiles/CCNC%28%3DO%29N1CCSC%2…, fetched_at=2026-09-25T04:26:21Z, disk cache=/storage/saveena/protacxtend/data/live_cache). Replayed payloads are real prior live-API responses, not fixtures.
- TargetBinderRetrievalAgent: Live source unavailable; replayed 1 cached live-fetch record(s) (url=https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/smiles/CN1CC%28c2ccccc2-c2ccc…, fetched_at=2026-09-25T04:26:22Z, disk cache=/storage/saveena/protacxtend/data/live_cache). Replayed payloads are real prior live-API responses, not fixtures.
- TargetBinderRetrievalAgent: Live source unavailable; replayed 1 cached live-fetch record(s) (url=https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/smiles/O%3DC%28C1CC1%29N1CCSC…, fetched_at=2026-09-25T04:26:23Z, disk cache=/storage/saveena/protacxtend/data/live_cache). Replayed payloads are real prior live-API responses, not fixtures.
- TargetBinderRetrievalAgent: Live source unavailable; replayed 1 cached live-fetch record(s) (url=https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/smiles/CC%28%3DO%29N1CCSC%28c…, fetched_at=2026-09-25T04:26:24Z, disk cache=/storage/saveena/protacxtend/data/live_cache). Replayed payloads are real prior live-API responses, not fixtures.
- TargetBinderRetrievalAgent: Live source unavailable; replayed 1 cached live-fetch record(s) (url=https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/smiles/Oc1ccc%28Cl%29cc1Nc1nc…, fetched_at=2026-09-25T04:26:26Z, disk cache=/storage/saveena/protacxtend/data/live_cache). Replayed payloads are real prior live-API responses, not fixtures.
- TargetBinderRetrievalAgent: Live source unavailable; replayed 1 cached live-fetch record(s) (url=https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/smiles/CN1CC%28c2ccc%28S%28%3…, fetched_at=2026-09-25T04:26:27Z, disk cache=/storage/saveena/protacxtend/data/live_cache). Replayed payloads are real prior live-API responses, not fixtures.
- TargetBinderRetrievalAgent: Live source unavailable; replayed 1 cached live-fetch record(s) (url=https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/smiles/CN1CC%28c2ccc%28-c3ccc…, fetched_at=2026-09-25T04:26:28Z, disk cache=/storage/saveena/protacxtend/data/live_cache). Replayed payloads are real prior live-API responses, not fixtures.
- Stereochemistry expansion changed candidate pool from 162 to 180 under capped policy.

## Top Ranked Candidates

| Rank | Tier | Target | E3 ligase | Warhead name | Linker class | Predicted DC50 nM | Predicted Dmax % | Predicted cooperativity alpha | Hook risk | E3 context score | PROTAC-DB prior score | PROTAC-DB prior scope | hERG risk | Novelty score | Final priority score | Warning flags |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Tier 1 | BRD4 | CRBN | BRD4_demo_quinazoline_like | alkyl | 21.64 | 97.4 | 18.257 | high | 0.79 | 0.531 | target_e3_neighborhood | medium | 0.82 | 0.771 | low_degradation_model_confidence;high_admet_toxicity_risk;high_hook_effect_risk;proxy_cooperativity_not_measured_alpha;proxy_hook_model_not_fitted_to_dose_response;protacdb_prior_is_target_e3_neighborhood_not_exact_compound |
| 2 | Tier 1 | BRD4 | CRBN | BRD4_demo_triazolobenzodiazepine_like | generative | 22.15 | 74.9 | 16.301 | high | 0.79 | 0.531 | target_e3_neighborhood | low | 0.756 | 0.764 | low_degradation_model_confidence;high_hook_effect_risk;proxy_cooperativity_not_measured_alpha;proxy_hook_model_not_fitted_to_dose_response;protacdb_prior_is_target_e3_neighborhood_not_exact_compound |
| 4 | Tier 1 | BRD4 | CRBN | BRD4_demo_triazolobenzodiazepine_like | triazole | 23.64 | 81.0 | 14.074 | high | 0.79 | 0.531 | target_e3_neighborhood | medium | 0.8 | 0.753 | low_degradation_model_confidence;high_hook_effect_risk;proxy_cooperativity_not_measured_alpha;proxy_hook_model_not_fitted_to_dose_response;protacdb_prior_is_target_e3_neighborhood_not_exact_compound |
| 6 | Tier 1 | BRD4 | CRBN | BRD4_demo_triazolobenzodiazepine_like | alkyl | 26.46 | 91.0 | 15.514 | high | 0.79 | 0.531 | target_e3_neighborhood | medium | 0.733 | 0.751 | low_degradation_model_confidence;high_hook_effect_risk;proxy_cooperativity_not_measured_alpha;proxy_hook_model_not_fitted_to_dose_response;protacdb_prior_is_target_e3_neighborhood_not_exact_compound |
| 7 | Tier 1 | BRD4 | CRBN | BRD4_demo_quinazoline_like | triazole | 29.97 | 85.7 | 18.907 | medium | 0.79 | 0.531 | target_e3_neighborhood | medium | 0.853 | 0.75 | low_degradation_model_confidence;proxy_cooperativity_not_measured_alpha;proxy_hook_model_not_fitted_to_dose_response;protacdb_prior_is_target_e3_neighborhood_not_exact_compound |
| 9 | Tier 1 | BRD4 | CRBN | BRD4_demo_triazolobenzodiazepine_like | triazole | 17.91 | 84.2 | 16.066 | high | 0.79 | 0.531 | target_e3_neighborhood | medium | 0.789 | 0.75 | low_degradation_model_confidence;high_hook_effect_risk;proxy_cooperativity_not_measured_alpha;proxy_hook_model_not_fitted_to_dose_response;protacdb_prior_is_target_e3_neighborhood_not_exact_compound |
| 10 | Tier 1 | BRD4 | CRBN | BRD4_demo_quinazoline_like | generative | 28.55 | 79.2 | 19.183 | high | 0.79 | 0.531 | target_e3_neighborhood | medium | 0.802 | 0.749 | low_degradation_model_confidence;high_hook_effect_risk;proxy_cooperativity_not_measured_alpha;proxy_hook_model_not_fitted_to_dose_response;protacdb_prior_is_target_e3_neighborhood_not_exact_compound |
| 12 | Tier 1 | BRD4 | CRBN | BRD4_demo_quinazoline_like | alkyl | 40.91 | 84.8 | 21.146 | medium | 0.79 | 0.531 | target_e3_neighborhood | medium | 0.784 | 0.745 | low_degradation_model_confidence;proxy_cooperativity_not_measured_alpha;proxy_hook_model_not_fitted_to_dose_response;protacdb_prior_is_target_e3_neighborhood_not_exact_compound |
| 13 | Tier 1 | BRD4 | CRBN | BRD4_demo_triazolobenzodiazepine_like | generative | 69.48 | 78.0 | 15.11 | medium | 0.79 | 0.531 | target_e3_neighborhood | low | 0.791 | 0.744 | stereoisomer_requires_separate_scoring;low_degradation_model_confidence;proxy_cooperativity_not_measured_alpha;proxy_hook_model_not_fitted_to_dose_response;protacdb_prior_is_target_e3_neighborhood_not_exact_compound |
| 16 | Tier 1 | BRD4 | CRBN | BRD4_demo_triazolobenzodiazepine_like | generative | 65.54 | 81.5 | 17.365 | low | 0.79 | 0.531 | target_e3_neighborhood | low | 0.732 | 0.738 | low_degradation_model_confidence;proxy_cooperativity_not_measured_alpha;proxy_hook_model_not_fitted_to_dose_response;protacdb_prior_is_target_e3_neighborhood_not_exact_compound |

## Agent Workflow Table

| Agent type | Selected tool | Tool status | Real output generated | Integration note | Data sources/tools | Query parameters | Quantitative outputs | Processing time |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Controlled Search Agent | Search policy | registered | yes - explicit NP-hard search budgets | planned integration | bounded deterministic budget policy | requested_candidates=50 | linker_budget=64, construction_budget=300, expensive_budget=50 | milliseconds locally |
| Target Resolver Agent | Target assessment | registered | yes - local/ChEMBL target metadata | planned integration | local curated target table; ChEMBL target fallback if network is available; no PDB/AlphaFold fetch is run here | target=BRD4, organism=human | UniProt=O60885, structures=3, tractability=0.86 | milliseconds locally; seconds only if online ChEMBL fallback is reached |
| Binder Retrieval Agent | Warhead mining | registered | yes - binder records returned | PubChem and BindingDB remain planned integrations unless their specific callables are invoked. | local curated binders; optional ChEMBL online fallback; PubChem name lookup only as ChEMBL helper; BindingDB is planned, not run | activity IC50/Ki/Kd/EC50 <= 1000 nM; assay confidence threshold | binders=100, unique_smiles=100 | milliseconds locally; minutes only with online APIs |
| Warhead Selection Agent | Warhead mining | registered | yes - selected warhead records | planned integration | selected binders, local scoring, optional RDKit validation; curated exit-vector markers only | activity IC50/Ki/Kd <= 1000 nM; derivatization feasible | binders=100, warheads=9 | milliseconds locally |
| E3 Ligand Agent | E3 ligase selection | registered | yes - local E3 ligand records | External HPA/DepMap/ProteomicsDB/E3Net expression queries remain planned integrations. | local curated CRBN/VHL/IAP/MDM2 handles plus optional explicit expression context | requested_e3=CRBN, cell_line=default | e3_ligands=3, ligases=1 | milliseconds locally |
| Cell Context Agent | E3-context compatibility | registered | yes - deterministic cell/E3 context scores | planned integration | curated E3 expression evidence, target localization rules, optional user expression overrides | cell_line=default, overrides=False | e3_context_records=150 | milliseconds locally |
| Exit Vector Agent | Warhead Agent | registered | yes - local exit-vector annotations | planned integration | explicit attachment markers and local confidence rules; no structural exit-vector modeling is run | warhead and E3 ligand component SMILES | vectors=12, ambiguous=0 | milliseconds locally |
| Linker Generation Agent | Linker design | registered | yes - curated/rule-based linker records | Generative linker models remain planned integrations. | curated linker CSV plus rule-based enumeration; LinkInvent/DiffLinker/DeLinker are planned, not run | linker_types=PEG,alkyl,piperazine,triazole | linkers=18, classes=5 | milliseconds locally; model generation not run |
| Construction Agent | Assembly Agent | registered | yes - assembled candidate records | Retrosynthesis-aware route planning is planned integration. | local dummy-atom assembly with RDKit when installed; named strategies currently share the same assembler | warhead + linker + E3 with valid exit vectors | attempts=1458, valid=150 | seconds locally |
| Cheap Filter Agent | Cheap molecular filter | registered | yes - pre-ternary filtered candidate set | planned integration | RDKit validity, MW, TPSA, rotatable bonds, synthetic feasibility, novelty, ADMET, applicability domain, E3 context | max_keep=150 | kept=150, rejected=9 | milliseconds to seconds locally |
| Prediction Agent | DC50/Dmax prediction | registered | no - heuristic demo predictions only | Trained DC50/Dmax prediction is planned integration. | heuristic demo predictor in codebase; no trained SynGlue/DeepPROTACs/PROTAC-STAN model is loaded | cheap-filter survivors, components, target, E3 ligase, optional cell context | degradation_predictions=150 | seconds locally |
| ADME/Tox Agent | ADME/Tox skill | registered | no - heuristic/local ADME-Tox triage only | External ADME/Tox predictors remain planned integrations. | RDKit descriptors when available plus heuristic risk triage; SwissADME/ADMETlab/pkCSM/ProTox-II are not run | PROTAC-aware thresholds; no strict Lipinski rejection | admet_records=150 | seconds locally |
| Novelty Agent | Novelty/IP check | registered | yes - local similarity/duplicate records | SureChEMBL/Lens/Google Patents/PubChem novelty search is planned integration. | local known-PROTAC set; RDKit Morgan similarity when available; patent/PubChem/ChEMBL novelty search is not run | candidate SMILES and similarity thresholds | novelty_records=150 | seconds locally |
| Ternary Feasibility Agent | Ternary complex modeling | registered | no - geometry proxy only | Docking/ternary modeling is planned integration. | finalist-only geometry proxy; docking/P4ward only when structure-aware ranking is requested and tools are available | finalist_ids=0 | ternary_records=50 | seconds locally; docking not run |
| Cooperativity Agent | Cooperativity proxy | registered | yes - proxy alpha estimates | Measured alpha or calibrated structure/ML cooperativity model is still needed for validation. | ternary geometry, linker strain, interface-contact proxy, and lysine-geometry proxy | valid candidates plus ternary feasibility records | cooperativity_records=150 | milliseconds locally |
| Hook Effect Agent | Concentration occupancy model | registered | yes - concentration-dependent hook-risk curves | Occupancy parameters are priors until fitted to cellular dose-response data. | DC50/Dmax predictions, E3 affinity priors, cooperativity alpha, and cell-context E3 score | 0.1-10000 nM concentration grid | hook_records=150, high_risk=128 | milliseconds locally |
| Ranking Agent | Ranking skill | registered | yes - ranking records over current outputs | planned integration | weighted deterministic ranking over available local/heuristic outputs | balanced degradation, ADME/Tox, novelty, and synthesis feasibility | ranked=150, final=50 | seconds |
| Reflection/Evolution Agent | Mini-PROTAC optimization | registered | yes - local deterministic review/evolution records | Full generative mini-PROTAC optimization is planned integration. | deterministic critique and linker replacement over current candidate records | top candidates and weaknesses | reviews=20, evolved=0 | seconds to minutes |
| Safety/Human Review Agent | Assay planning skill | registered | no - assay/human-review plan not generated; local guardrail status only | Expert assay planning and human-review packet generation are planned integrations. | local guardrail rules and warning aggregation | final candidates and requested use | warnings=12, errors=0, human_review_required=True | milliseconds locally |

## Pipeline Status Labels

| step_name | selected_tool_or_method | tool_status | output_type | real_output_generated | stub_or_heuristic | limitation | next_integration_needed |
| --- | --- | --- | --- | --- | --- | --- | --- |
| target resolution | Target assessment; optional UniProt executable lookup available separately | Target assessment: heuristic_stub; UniProt: executable | TargetRecord | True | local_demo_or_api_wrapper | Workflow still primarily uses local curated target records unless explicit executable wrappers are called. | Route target resolution through UniProt/Open Targets/RCSB executable wrappers with no silent local fallback. |
| warhead/binder retrieval | Warhead mining; local curated binders; PubChem lookup wrapper available separately | Warhead mining: heuristic_stub; PubChem lookup: executable only if wrapper exists and succeeds | list[BinderRecord] | True | local_demo | BindingDB is not connected; PubChem is not claimed unless its wrapper is explicitly called and succeeds. | Connect ChEMBL/BindingDB executable mining and provenance filtering. |
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