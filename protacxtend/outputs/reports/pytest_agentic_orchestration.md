# Agentic PROTACXtend Report

Research-use only. Results are computational hypotheses and are not experimentally validated.

## User Request
Design CRBN-based PROTACs for BRD4. Generate 3 candidates using PEG and alkyl linkers with low hERG risk.

## Parsed Design Goal
- Target: BRD4
- E3 ligase: CRBN
- Candidate count: 3
- Validation depth: medium
- Objectives: maximize degradation confidence, minimize predicted DC50, maximize Dmax, preserve novelty, maintain synthetic plausibility, reduce hERG risk

## Assumptions
- No trained degradation model was loaded; DC50/Dmax are heuristic fallback values.

## Tools Used
- ADMETAgent
- ActiveLearningAgent
- ApplicabilityDomainAgent
- CandidateValidationAgent
- CellContextAgent
- CheapFilterAgent
- ControlledSearchAgent
- CooperativityPredictionAgent
- DegradationPredictionAgent
- DesignPlannerAgent
- E3LigandSelectionAgent
- EvolutionRefinementAgent
- ExitVectorDetectionAgent
- ExpensiveModelingSelectionAgent
- FinalRankingTournamentAgent
- HookEffectPredictionAgent
- LinkerGenerationAgent
- MemoryUpdateAgent
- MolecularConstructionAgent
- NoveltySimilarityAgent
- ProximityDiversityAgent
- RankingTournamentAgent
- ReflectionReviewAgent
- ReportAgent
- SafetyAgent
- StereochemistryEnumerationAgent
- SupervisorAgent
- TargetBinderRetrievalAgent
- TargetResolverAgent
- TernaryFeasibilityAgent
- WarheadSelectionAgent

## Models Used
- Degradation/DC50/Dmax: tack-style-v1 (DC50/Dmax primary) + chemprop cross-check
- ADME/Tox: descriptor/rule-based or configured backend; see candidate warnings.

## Fallbacks Used
- trained_degradation_model_missing_use_heuristic_fallback

## Candidate Summary
- Assembled candidates: 80
- Valid or unverified candidates: 40
- Ranked candidates: 40

## Ranking Table
| Rank | Candidate | Score | Tier |
| --- | --- | --- | --- |
| 1 | BRD4_demo_triazolobenzodiazepine_like | 0.75 | Tier 1 |
| 2 | BRD4_demo_quinazoline_like | 0.742 | Tier 1 |
| 3 | BRD4_demo_quinazoline_like | 0.742 | Tier 1 |

## Scientific Warnings
- BindingDB REST needs an API key (BINDINGDB_API_KEY); ChEMBL covers binding data.
- Evolution stopped: novelty_ratio<0.1 for 2 gens
- One or more candidates are outside or near the applicability domain.
- TargetBinderRetrievalAgent: Retrieved 3 binders from local_curated.

## Applicability-Domain Assessment
- Records: 40
- Any outside-domain or missing assessments are treated as confidence downgrades.

## Ternary Feasibility Status
- Records: 10
- Docking claims are made only when a docking backend actually ran.

## Provenance Table
| Candidate | Warhead | E3 ligand | Linker | Degradation model | RDKit status |
| --- | --- | --- | --- | --- | --- |
| SGA-2119c60093a5 | local_demo_bromodomain_warhead | CRBN_demo_pomalidomide_like | generative_linker_model | tack-style-v1 (DC50/Dmax primary) + chemprop cross-check | valid |
| SGA-f1725074757f | local_demo_brd4_binder | CRBN_demo_lenalidomide_like | generative_linker_model | tack-style-v1 (DC50/Dmax primary) + chemprop cross-check | valid |
| SGA-5b86dfaa2af5 | local_demo_brd4_binder | CRBN_demo_pomalidomide_like | generative_linker_model | tack-style-v1 (DC50/Dmax primary) + chemprop cross-check | valid |

## Failed Steps And Recovery Actions
- downgrade_confidence

## Reusable Memory Lessons
- Target/E3/linker combination produced valid or unverified candidates.
- Carry warning flags into future planning for this target/E3 context.

## Disclaimer
This report is for research use only. It does not provide experimentally validated PROTAC activity, clinical safety, dosing, or synthesis recommendations.
