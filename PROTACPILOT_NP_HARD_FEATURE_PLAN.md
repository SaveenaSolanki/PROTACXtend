# PROTACXtend NP-Hard Feature Plan

## Purpose

This plan converts the difficult PROTAC-design bottlenecks into an engineering roadmap for PROTACXtend. The current system now has first-pass agents for cell context, cooperativity, hook-effect risk, and active-learning feedback, but these are not yet production-grade biological predictors. The next work is to replace weak proxies with calibrated, evidence-backed models and to make every output traceable to data quality.

## Added Implementation Logic

This file now includes the careful, exact implementation logic requested for the NP-hard PROTAC design problems:

- controlled generation instead of exhaustive enumeration;
- bounded linker, E3 ligand, exit-vector, stereoisomer, construction, cheap-filter, expensive-modeling, and final-candidate budgets;
- exact agent order and per-agent read/write contracts;
- cheap first-pass filters for RDKit validity, MW, TPSA, rotatable bonds, synthetic feasibility, novelty, ADMET, and E3/cell context;
- expensive ternary modeling restricted to 10-50 finalists through `expensive_modeling_candidate_ids`;
- multi-objective ranking formula combining DC50, Dmax, ternary feasibility, cooperativity, hook window, E3 context, ADMET, novelty, and synthesis;
- explicit proxy uncertainty flags for cooperativity, hook effect, ternary evidence, low model confidence, weak cell/E3 context, and outside-domain predictions;
- cell-line and expression-override handling for context-aware E3 scoring;
- assay-feedback schema and active-learning retraining gates;
- resources needed for local compute, external tools, public databases, expression atlases, measured alpha/Kd data, and dose-response curves;
- implementation checklist and definition of done.

## Current State

| Capability | Current implementation | Current status | Main limitation |
| --- | --- | --- | --- |
| Cell-type/E3 context | `CellContextAgent`, `score_e3_context`, curated E3 expression defaults, user expression overrides | Working local scorer | Needs real tissue/cell-line expression atlas and mutation/resistance context |
| Cooperativity | `CooperativityPredictionAgent`, proxy alpha, linker strain, interface proxy, lysine proxy | Working heuristic proxy | Alpha is not experimentally calibrated; must be labelled exploratory |
| Hook effect | `HookEffectPredictionAgent`, concentration-grid ternary occupancy proxy | Working heuristic proxy | Needs fitted biochemical/cellular binding parameters |
| Active learning | `ActiveLearningAgent`, assay-feedback CSV writer, retraining-readiness gate | Working data intake | Needs model training job, validation split, registry, and rollback |
| Ranking | Weighted ranking includes `cooperativity`, `hook`, and `e3_context` | Integrated | Needs uncertainty-aware weighting and calibrated score ranges |
| Reporting | CSV/JSON/markdown include new fields | Integrated | Needs clearer scientific caveat section and assay recommendation cards |

## Principle

Do not try to brute-force NP-hard PROTAC search. Use agents to prune, score, diversify, simulate selectively, and learn from assays.

The production loop should be:

```text
Candidate generation
  -> chemical validity
  -> cell-context E3 feasibility
  -> degradation/ADMET/novelty screen
  -> ternary geometry ensemble
  -> cooperativity and hook model
  -> Pareto ranking
  -> assay recommendation
  -> assay feedback
  -> active-learning retraining
```

## Exact Agent Logic

The workflow must be treated as a bounded optimization funnel. Each agent receives a shared `WorkflowState`, reads only the fields listed below, writes explicit result objects, and records uncertainty when evidence is weak. No agent is allowed to silently convert a proxy into a measured value.

### Agent Order

```text
SupervisorAgent
  -> DesignPlannerAgent
  -> ControlledSearchAgent
  -> SafetyAgent
  -> TargetResolverAgent
  -> TargetBinderRetrievalAgent
  -> WarheadSelectionAgent
  -> E3LigandSelectionAgent
  -> ExitVectorDetectionAgent
  -> LinkerGenerationAgent
  -> MolecularConstructionAgent
  -> StereochemistryEnumerationAgent
  -> CandidateValidationAgent
  -> CellContextAgent
  -> ADMETAgent
  -> NoveltyAgent
  -> ApplicabilityDomainAgent
  -> CheapFilterAgent
  -> DegradationPredictionAgent
  -> InitialRankingAgent
  -> ProximityDiversityAgent
  -> ReflectionReviewAgent
  -> EvolutionRefinementAgent
  -> ExpensiveModelingSelectionAgent
  -> TernaryFeasibilityAgent
  -> CooperativityPredictionAgent
  -> HookEffectPredictionAgent
  -> FinalRankingAgent
  -> ActiveLearningAgent
  -> ReportAgent
  -> MemoryUpdateAgent
```

### Agent Contracts

| Agent | Reads | Writes | Exact logic | Hard stop / warning |
| --- | --- | --- | --- | --- |
| `ControlledSearchAgent` | parsed objective | `search_policy` | Computes bounded budgets from requested candidate count. Construction budget is a small multiple of final count; expensive modeling is capped at 10-50. | Warn if requested count exceeds policy cap. |
| `WarheadSelectionAgent` | target, binders, user warhead | selected warheads | Selects only high-confidence binders or user-provided warhead. Scores potency, derivatization, exit-vector confidence, source confidence. | Stop if no warhead. Flag hypothetical exit vectors. |
| `E3LigandSelectionAgent` | requested E3, curated ligands, search policy | selected E3 ligands | Restricts E3 ligand set to requested ligase or default CRBN/VHL, then caps by `e3_ligand_budget`. | Stop if no ligand. Warn if requested E3 has no local ligand. |
| `ExitVectorDetectionAgent` | warheads, E3 ligands | exit-vector records | Detects explicit dummy atoms and confidence. Missing attachment markers are not invented as high confidence. | Flag ambiguous vectors. |
| `LinkerGenerationAgent` | linker classes, search policy | generated linkers | Uses curated/rule-based/generative linkers, then caps to `linker_budget`. | Warn if fallback linker library is used. |
| `MolecularConstructionAgent` | selected warheads, E3 ligands, linkers | construction attempts, assembled candidates | Builds only up to `construction_budget`, deduplicates canonical SMILES, records assembly strategy. | Stop if no assembled candidate. |
| `StereochemistryEnumerationAgent` | assembled candidates, policy | assembled candidates | Enumerates undefined stereoisomers only up to `stereoisomer_budget_per_candidate` and `construction_budget`. | Flag each enumerated stereoisomer as needing separate scoring. |
| `CandidateValidationAgent` | assembled candidates | valid candidates | RDKit sanitization, canonicalization, MW/TPSA/logP/HBD/HBA/rotor descriptors, PROTAC property warnings. | Stop if zero valid/unverified candidates. |
| `CellContextAgent` | valid candidates, target context, cell line, expression overrides | E3 context predictions | Scores E3 expression, colocalization, ligand availability, structural support, resistance risk. User expression overrides are allowed but marked. | Flag weak cell/E3 context. |
| `ADMETAgent` | valid candidates | ADMET predictions | Computes cheap property/toxicity/permeability proxies before structural modeling. | Flag high hERG/DILI/solubility/P-gp risk. |
| `NoveltyAgent` | valid candidates, known PROTAC set | novelty results | Computes local similarity and duplicate flags. | Reject near-exact duplicates in cheap filter. |
| `ApplicabilityDomainAgent` | valid candidates | applicability-domain results | Scores similarity to model domain from molecular properties/training proximity. | Flag outside-domain predictions. |
| `CheapFilterAgent` | valid candidates, ADMET, novelty, domain, E3 context | reduced valid candidates, `cheap_filter_summary` | Hard-rejects invalid, extreme MW/TPSA/rotors, very low synthesis, dual high toxicity, duplicates. Ranks survivors by property/ADMET/novelty/domain/E3 context and caps to `cheap_filter_budget`. | Stop if zero survivors. |
| `DegradationPredictionAgent` | cheap-filter survivors | degradation predictions | Predicts DC50, Dmax, probability, confidence, and applicability. | Flag model fallback and low confidence. |
| `InitialRankingAgent` | cheap-filter survivors plus cheap predictions | ranking results | Ranks before structural work to select finalists. | Mark missing structural evidence. |
| `ExpensiveModelingSelectionAgent` | ranking results, candidates, policy | finalist IDs | Selects ranked, diverse finalists only, capped by `expensive_modeling_budget`. | No expensive model may run on non-finalists. |
| `TernaryFeasibilityAgent` | finalist IDs, structures, candidates | ternary feasibility results | Runs docking/P4ward only when requested and available; otherwise runs geometry proxy only for finalists. | Flag proxy-only ternary evidence. |
| `CooperativityPredictionAgent` | candidates, ternary results | cooperativity predictions | Computes exploratory score from interface proxy, linker strain, lysine geometry proxy, ternary feasibility. Alpha field must be marked proxy unless calibrated/measured. | Always flag proxy alpha if no measured/calibrated evidence. |
| `HookEffectPredictionAgent` | degradation, cooperativity, E3 context | hook-effect predictions | Simulates ternary fraction over 0.1-10000 nM concentration grid using Kd priors, alpha proxy, and E3 context. | Flag high hook risk and proxy-only dose model. |
| `FinalRankingAgent` | all prediction families | final ranked candidates | Uses weighted multi-objective ranking: DC50, Dmax, ADMET, ternary, cooperativity, hook window, E3 context, novelty, synthesis. | Keep uncertainty flags visible. |
| `ActiveLearningAgent` | assay feedback, valid candidates | active-learning update, training rows, learning memory | Appends feedback rows and records structured learning entries. Does not claim retraining unless thresholds are met. | Warn if no feedback or insufficient rows. |
| `ReportAgent` | complete state | markdown/CSV/JSON report | Reports scores, model versions, proxy caveats, finalist counts, and uncertainty flags. | Must not remove scientific guardrails. |

## Exact Pruning Logic

### Search Budgets

Default policy in `build_search_policy`:

| Budget | Rule |
| --- | --- |
| `final_candidate_budget` | requested count, capped at 500 |
| `linker_budget` | `max(12, min(64, final_count * 2))` |
| `e3_ligand_budget` | 3 if E3 specified, otherwise 6 |
| `construction_budget` | `max(cheap_budget, min(1000, max(final_count * 6, 80)))` |
| `cheap_filter_budget` | `max(expensive_budget, min(250, max(final_count * 3, 40)))` |
| `expensive_modeling_budget` | `max(10, min(50, final_count, requested_count))` |
| `stereoisomer_budget_per_candidate` | 4 |

This means a request for 50 final candidates should not cause exhaustive search. It should build at most hundreds of candidates, cheaply filter them, and model only the top 10-50.

### Cheap Reject Rules

Candidates are rejected before degradation/ternary modeling when any hard rule fires:

| Rule | Reason code |
| --- | --- |
| invalid or unsanitizable SMILES | `invalid_smiles` |
| MW > 1800 | `mw_above_1800` |
| TPSA > 360 | `tpsa_above_360` |
| rotatable bonds > 45 | `rotors_above_45` |
| synthetic feasibility < 0.18 | `very_low_synthetic_feasibility` |
| hERG high and DILI high | `dual_high_toxicity_risk` |
| near-exact known PROTAC duplicate | `duplicate_known_protac` |

Survivors are scored with:

```text
cheap_score =
  0.38 * property_score
+ 0.25 * ADMET_score
+ 0.17 * novelty_score
+ 0.12 * applicability_domain_score
+ 0.08 * E3_context_score
```

Where `property_score` combines MW, TPSA, rotatable bonds, synthesis score, and E3 context. The top `cheap_filter_budget` candidates survive.

### Expensive Modeling Selection

Finalist selection must use rank and diversity:

```text
sort candidates by:
  final_priority_score
  confidence
  cheap_filter_score

for candidate in sorted candidates:
  keep if Tanimoto similarity to already-kept finalists < 0.82
  stop at expensive_modeling_budget

if diversity filter leaves too few:
  backfill by rank until budget is reached
```

Only `expensive_modeling_candidate_ids` may be passed to docking, P4ward, or future expensive ternary engines.

## Exact Multi-Objective Ranking Logic

Current default weights:

```text
final_priority_score =
  0.24 * DC50_score
+ 0.19 * Dmax_score
+ 0.13 * ADMET_score
+ 0.12 * ternary_score
+ 0.11 * cooperativity_score
+ 0.08 * hook_window_score
+ 0.06 * E3_context_score
+ 0.05 * novelty_score
+ 0.02 * synthetic_score
```

Confidence is separate from score:

```text
confidence =
  0.32 * degradation_model_confidence
+ 0.24 * applicability_domain_similarity
+ 0.18 * cooperativity_confidence
+ 0.14 * E3_context_confidence
+ 0.12 * synthetic_feasibility
```

Important: a high score with low confidence is not a validated design. It is a candidate for additional evidence generation.

## Exact Uncertainty Logic

The report and ranking must preserve these flags:

| Condition | Flag |
| --- | --- |
| degradation confidence < 0.45 | `low_degradation_model_confidence` |
| outside applicability domain | `outside_applicability_domain` |
| high hERG or DILI | `high_admet_toxicity_risk` |
| high hook risk | `high_hook_effect_risk` |
| weak E3/cell context | `weak_cell_type_e3_context` |
| candidate not selected for ternary modeling | `not_selected_for_expensive_ternary_modeling` |
| cooperativity is proxy-only | `proxy_cooperativity_not_measured_alpha` |
| hook model is not dose-response fitted | `proxy_hook_model_not_fitted_to_dose_response` |
| RDKit unavailable | `rdkit_not_installed` |

These flags are not cosmetic. They decide whether the next action is assay, docking, data collection, or deprioritization.

## Resources Needed

### Local Compute Resources

| Work item | Minimum resource | Recommended resource | Notes |
| --- | --- | --- | --- |
| Parsing, selection, cheap filters | CPU, <4 GB RAM | CPU, 8 GB RAM | Fast local path |
| RDKit validation/descriptors | CPU, 4-8 GB RAM | CPU, 8-16 GB RAM | Required for reliable chemistry |
| Similarity/novelty | CPU, 4-8 GB RAM | CPU, 16 GB RAM | Scales with known PROTAC library size |
| Degradation model inference | CPU, 8 GB RAM | CPU, 16 GB RAM | Current sklearn warnings should be resolved by matching versions |
| Docking | CPU, 8-32 cores | CPU, 32 cores | Run only on finalists |
| P4ward ternary modeling | CPU, many hours per batch | 32-64 cores or cluster | Never run on full generated set |
| Future deep ternary model | GPU optional | NVIDIA GPU, 16-24 GB VRAM | For DeepTernary/PROTAC-STAN-like models |
| Active-learning retraining | CPU/GPU depending model | Reproducible training environment | Needs model registry |

### Data Resources

| Resource | Required for | Current status |
| --- | --- | --- |
| `synglue_agent/data/curated_warheads.csv` | initial warhead selection | local |
| `synglue_agent/data/curated_e3_ligands.csv` | E3 ligand selection | local |
| `synglue_agent/data/curated_linkers.csv` | controlled linker generation | local |
| `synglue_agent/data/known_protac_smiles.csv` | novelty/duplicate filtering | local |
| ChEMBL | POI binder data | client exists |
| PubChem | compound lookup and patent hints | client exists |
| BindingDB | affinity evidence | client exists/planned depending route |
| UniProt | target metadata/localization | client exists |
| RCSB PDB | experimental structures | client exists |
| AlphaFold DB | predicted structures | client exists |
| DepMap/CCLE | cell-line expression | needed as static table |
| GTEx/HPA | tissue expression/localization | needed as static table |
| Measured assay feedback | active learning | schema and ingestion path exist |
| Measured ternary alpha/Kd | calibrated cooperativity | needed |
| Dose-response curves | fitted hook model | needed |

### External Tool Resources

| Tool | Role | Use policy |
| --- | --- | --- |
| RDKit | validation, descriptors, stereochemistry, fingerprints | required for chemistry-grade filtering |
| AutoDock Vina/GNINA | warhead/pose docking | finalists only |
| P4ward | ternary complex modeling | finalists only; expensive |
| OpenBabel | file conversion/3D prep | when docking/P4ward is used |
| Chemprop/sklearn models | degradation prediction | must record version and applicability |
| Future DeepTernary/PROTAC-STAN | structure-aware ternary scoring | add only with benchmark gate |

## Mapping From The 11 NP-Hard Problems To Agent Logic

| NP-hard problem | Agent strategy | Exact mitigation |
| --- | --- | --- |
| Linker design | `ControlledSearchAgent`, `LinkerGenerationAgent`, `CheapFilterAgent` | cap linker budget, score linker properties, avoid exhaustive linker enumeration |
| E3 ligase selection | `E3LigandSelectionAgent`, `CellContextAgent` | restrict to liganded E3s, score cell expression/localization/resistance |
| Ternary formation | `ExpensiveModelingSelectionAgent`, `TernaryFeasibilityAgent` | model only 10-50 finalists, use geometry proxy or P4ward |
| Cooperativity | `CooperativityPredictionAgent` | proxy score from ternary geometry, interface, linker strain, lysine geometry; true alpha requires measured/calibrated data |
| Lysine positioning | `TernaryFeasibilityAgent`, cooperativity proxy | use reachability/lysine geometry proxy now; add residue-level lysine distance from structures next |
| Protein-protein interface | `TernaryFeasibilityAgent`, cooperativity proxy | score interface plausibility and structural support; add BSA/contact extractor next |
| Hook effect | `HookEffectPredictionAgent` | simulate ternary occupancy over concentration grid and flag high-dose drop |
| Permeability vs potency | `ADMETAgent`, `CheapFilterAgent`, `FinalRankingAgent` | score ADMET separately from potency; avoid potency-only selection |
| Cell-type dependence | `CellContextAgent` | include cell line and E3 expression override; add DepMap/GTEx/HPA tables next |
| Stereochemistry | `StereochemistryEnumerationAgent` | cap stereoisomer enumeration and score variants separately |
| Limited data | `ActiveLearningAgent`, `assay_feedback.py`, memory | append assay results, generate training rows, record learnings, gate retraining by data volume |

## Failure Escalation Rules

| Failure | Next action |
| --- | --- |
| No target resolved | ask user for target gene/UniProt |
| No warhead | retrieve more binders or ask for warhead SMILES |
| No E3 ligand | switch to available E3 set or ask for E3 ligand |
| Ambiguous exit vectors | lower confidence, require chemist review |
| Too many stereoisomers | cap enumeration, flag unresolved stereochemistry |
| No cheap-filter survivors | relax property thresholds or generate smaller/polar linker set |
| Low degradation confidence | require assay or stronger model/domain data |
| No ternary structure | use geometry proxy and mark low confidence |
| High hook risk | recommend wider concentration assay and avoid high-dose-only interpretation |
| Assay contradicts prediction | record failure in learning memory and prioritize retraining/calibration |

## Implementation Checklist

Use this checklist before claiming the NP-hard funnel is implemented correctly:

- `search_policy` appears in `WorkflowState`.
- Linker count is capped by `search_policy.linker_budget`.
- Construction count is capped by `search_policy.construction_budget`.
- Stereoisomer expansion is capped and variants are not collapsed silently.
- Cheap filters run before expensive ternary modeling.
- `cheap_filter_summary` reports input, kept, rejected, and reason counts.
- `expensive_modeling_candidate_ids` contains at most 50 IDs.
- Ternary modeling reads only finalist IDs.
- Ranking reason includes DC50, Dmax, ADMET, ternary, cooperativity, hook, E3 context, novelty, and synthesis.
- Proxy cooperativity and proxy hook are visibly flagged.
- Assay feedback writes training rows.
- Assay feedback writes structured learning memory.
- Report contains proxy caveats and active-learning status.

## Phase 1: Make Current Proxies Honest And Stable

Goal: keep the new agents useful while preventing false confidence.

Tasks:

| Task | Files | Output | Acceptance criteria |
| --- | --- | --- | --- |
| Add explicit caveats to report | `synglue_agent/tools/protac_toolbox.py` | Report section for proxy limitations | Markdown report states alpha/hook are proxy-only unless measured/fitted |
| Add model-version labels to ranking table | `protac_toolbox.py`, schemas | Per-candidate model provenance | CSV/JSON expose `cooperativity-proxy-v0.1` and `hook-occupancy-v0.1` |
| Add uncertainty flags | `rank_candidates` | `proxy_cooperativity`, `proxy_hook_model` flags | Ranking marks candidates as proxy-scored when no measured data exists |
| Add unit tests for parser | `tests/` | Cell-line/expression parsing coverage | Tests pass for `in MM1.S cells`, `cell line HCT116`, `CRBN expression=high` |

Priority: immediate.

## Phase 2: Real Cell-Type And E3 Context

Goal: move from hand-curated defaults to context-aware E3 selection.

Data needed:

| Data source | Use | Requirement |
| --- | --- | --- |
| DepMap/CCLE expression | E3 and target abundance in cancer cell lines | Static snapshot committed or cached locally |
| GTEx or Human Protein Atlas | tissue expression | Static median expression table |
| CRBN/VHL pathway status | resistance risk | Mutation/dependency annotations where available |
| subcellular localization | POI/E3 colocalization | UniProt/HPA-derived labels |

Tasks:

| Task | Output | Acceptance criteria |
| --- | --- | --- |
| Build `data/e3_context/cell_line_expression.csv` | normalized expression table | Includes CRBN, VHL, MDM2, cIAP1 for common cell lines |
| Extend `e3_context_engine.py` | expression lookup + fallback | Known cell line uses real table; unknown uses default |
| Add mutation/resistance flags | resistance-aware E3 score | CRBN-low/mutated and VHL-loss contexts penalized |
| Add user-facing context summary | report paragraph | Report explains why an E3 was favored or penalized |

Priority: high.

## Phase 3: Production Cooperativity Model

Goal: replace the current proxy alpha with calibrated ternary-complex evidence.

Important scientific constraint:

Current `predicted_alpha` is only a heuristic. Do not present it as true cooperativity. True alpha needs measured ternary binding or a calibrated model trained against measured ternary data.

Required model inputs:

| Input | Source |
| --- | --- |
| Binary POI-warhead affinity | ChEMBL, BindingDB, user assay |
| Binary E3-ligand affinity | curated E3 ligand table or literature |
| Ternary pose ensemble | P4ward, docking, future DeepTernary/PROTAC-STAN |
| Interface contacts | pose analysis |
| Linker strain | conformer ensemble |
| Lysine distance/orientation | structure analysis |
| Measured alpha labels | SPR, BLI, TR-FRET, AlphaLISA, literature |

Tasks:

| Task | Output | Acceptance criteria |
| --- | --- | --- |
| Add ternary pose feature extractor | interface BSA, contacts, clashes, linker strain | Runs on P4ward/pose outputs |
| Separate K_LPT proxy from alpha | `TernaryAffinityPrediction` or renamed fields | No BSA-only value is called alpha |
| Build measured alpha dataset schema | `data/assay_feedback/ternary_binding.csv` | Stores POI, E3, PROTAC, Kd values, alpha, method |
| Train first calibrated model | regression/classification artifact | Cross-validation report and applicability domain |
| Gate alpha reporting by evidence level | schema/report/ranking | Report says measured, calibrated, or proxy |

Priority: high.

## Phase 4: Better Hook-Effect And PK/PD Modeling

Goal: turn hook-risk from a prior-based curve into a fitted concentration-response model.

Needed parameters:

| Parameter | Meaning |
| --- | --- |
| `Kd_POI` | PROTAC-warhead binary affinity |
| `Kd_E3` | PROTAC-E3 binary affinity |
| `alpha` | ternary cooperativity |
| `target_expression` | cellular POI abundance |
| `e3_expression` | cellular E3 abundance |
| `k_ub` | ubiquitination rate proxy |
| `k_deg` | degradation rate |
| `k_resynthesis` | target recovery rate |

Tasks:

| Task | Output | Acceptance criteria |
| --- | --- | --- |
| Implement closed-form ternary equilibrium solver | ternary fraction vs concentration | Unit tests against known analytical cases |
| Fit hook curves from assay feedback | fitted `DC50`, `Dmax`, hook concentration | Accepts dose-response CSV |
| Add time-dependent degradation model | degradation vs time/concentration | Supports 4 h, 8 h, 24 h assay windows |
| Add assay design recommendation | suggested concentration grid | Report recommends wide dose range when hook risk is high |

Priority: high.

## Phase 5: Active-Learning Retraining

Goal: convert assay results into improved ranking and prediction models.

Current status:

`ActiveLearningAgent` writes feedback rows and reports whether enough data exists for calibration or retraining. It does not yet train and register a production model.

Feedback schema:

| Field | Example |
| --- | --- |
| `candidate_id` | `cand1` |
| `smiles` | full PROTAC SMILES |
| `target` | `BRD4` |
| `e3_ligase` | `CRBN` |
| `cell_line` | `MM1.S` |
| `measured_dc50_nM` | `25.0` |
| `measured_dmax_percent` | `82.0` |
| `measured_hook_concentration_nM` | `300.0` |
| `degradation_observed` | `true` |

Tasks:

| Task | Output | Acceptance criteria |
| --- | --- | --- |
| Add feedback import CLI | `python -m ... import-feedback file.csv` | Validates and appends assay rows |
| Add training pipeline | model artifact + metrics JSON | Produces repeatable train/validation split |
| Add model registry | versioned model metadata | Workflow can load latest approved model |
| Add rollback support | previous model restore | Bad model can be deactivated |
| Add active-learning acquisition | next assay batch recommendation | Selects diverse, uncertain, high-value candidates |

Priority: medium-high.

## Phase 6: Search And Optimization Improvements

Goal: make the agent system better at exploring the combinatorial space without exploding compute.

Tasks:

| Task | Output | Acceptance criteria |
| --- | --- | --- |
| Add Pareto-front selector using new fields | multi-objective candidate set | Keeps candidates across potency, ADMET, hook, context, novelty |
| Add budget-aware scheduler | cheap-to-expensive evaluation plan | P4ward/docking only runs on selected candidates |
| Add linker active-learning policy | linker suggestions from prior failures | Avoids repeated failed linker classes |
| Add stereochemistry-aware ranking | separate score per stereoisomer | No stereoisomer is collapsed without warning |

Priority: medium.

## Phase 7: Validation And Benchmarking

Goal: prove the new agents improve candidate prioritization.

Benchmarks:

| Benchmark | Measures |
| --- | --- |
| Known successful PROTACs | whether known actives rank high |
| Known weak/inactive degraders | whether failures rank lower |
| Cell-line transfer cases | whether context score changes ranking appropriately |
| Hook-effect dose-response cases | whether predicted hook concentration matches assay trend |
| Measured alpha cases | whether calibrated model separates cooperative from anti-cooperative compounds |

Acceptance criteria:

| Milestone | Required result |
| --- | --- |
| Proxy sanity | New agents produce stable values and no crashes |
| Retrospective ranking | Actives enriched in top 20 percent |
| Cell context | E3-low context lowers candidate rank |
| Hook model | Bell-shaped curves flagged when high-dose decline exists |
| Active learning | New feedback changes future rankings in expected direction |

Priority: continuous.

## Immediate Next Sprint

Recommended first sprint, in order:

1. Add report caveats and provenance labels for proxy alpha/hook.
2. Add parser tests for cell-line and expression overrides.
3. Add static E3 expression table for common cell lines.
4. Add dose-response feedback import format.
5. Implement analytical ternary-equilibrium solver and compare against the current hook proxy.
6. Split cooperativity reporting into `K_LPT/ternary affinity proxy` and true `alpha` evidence level.
7. Add active-learning acquisition function for the next assay batch.

## Definition Of Done

The system is production-ready for these features only when:

- every score has a model version and evidence level,
- proxy outputs are visibly labelled as proxy outputs,
- cell-line context comes from real expression data or explicit user override,
- hook-effect predictions can ingest measured dose-response data,
- cooperativity predictions distinguish measured alpha, calibrated alpha, and exploratory proxy,
- assay feedback can retrain or calibrate a model reproducibly,
- reports show both recommendation and uncertainty,
- tests cover parser, scoring, ranking, report export, and feedback import.
