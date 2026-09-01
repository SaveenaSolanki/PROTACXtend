# Agent Markdown Implementation Audit

Date: 2026-08-29

## Scope

The attached markdown documents were treated as reference material, not as executable instructions. The user's active request was to check the markdown, explain the implementation status, and clearly implement the missing NP-hard agent details in this repository.

Attached files checked:

- `Agents (1).zip` - 23 agent/reference markdown files, `SEARCH_INSTRUMENTATION.md`, and `PIPELINE_ANIMATION.html`
- `AGENT_REASONING_AND_BENCHMARKS.md (1).zip`
- `AGENT_ARCHITECTURE_UPDATE.md (1).zip`

The local `md/` copy differs from the attached `Agents/` packet in five files:

- `07-E3LigandSelectionAgent.md`
- `09-LinkerGenerationAgent.md`
- `12-DegradationPredictionAgent.md`
- `14-NoveltyAgent.md`
- `20-TernaryFeasibilityAgent.md`

Those differences mostly reflect later local status updates, so they were not blindly overwritten.

## Implementation Summary

| Requirement | Status | Implemented in | Notes |
| --- | --- | --- | --- |
| Do not enumerate everything | Implemented | `ControlledSearchAgent`, `build_search_policy` | Linker, E3, stereoisomer, construction, cheap-filter, expensive-modeling, and final budgets are explicit in `state.search_policy`. |
| Generate controlled linkers/E3/exit vectors/stereoisomers | Implemented | `linker_agent.py`, `e3_agent.py`, `search_control_agent.py`, `exit_vector_agent.py` | Linkers, E3 ligands, and stereoisomers are capped; exit vectors remain confidence-scored and can still be ambiguous. |
| Cheap filters first | Implemented | `CheapFilterAgent`, `cheap_filter_candidates` | Filters validity, MW, TPSA, rotatable bonds, synthesis, novelty, ADMET, applicability domain, and E3 context before degradation prediction and ternary modeling. |
| Expensive tools only on finalists | Implemented | `ExpensiveModelingSelectionAgent`, `ternary_agent.py` | `state.expensive_modeling_candidate_ids` limits ternary modeling to a small finalist set. |
| Multi-objective ranking | Implemented | `ranking_agent.py`, `rank_candidates` | Ranking combines DC50, Dmax, ternary, cooperativity, hook window, E3 context, ADMET, novelty, and synthesis. |
| Stronger cooperativity scoring | Proxy implemented | `CooperativityPredictionAgent`, `predict_cooperativity` | Uses ternary feasibility, linker reachability, interface proxy, lysine geometry, and strain. Marked proxy-only. |
| Concentration-dependent hook model | Proxy implemented | `HookEffectPredictionAgent`, `predict_hook_effect` | Uses a concentration grid and therapeutic-window score. Marked proxy-only until dose-response data exists. |
| Explicit cell-type expression inputs | Implemented with priors | `CellContextAgent`, `score_e3_context`, request parser | Supports parsed cell line and `E3 expression=value` overrides; live DepMap/HPA/GTEx ingestion remains future work. |
| Active-learning retraining from assay feedback | Feedback ingestion implemented | `ActiveLearningAgent`, `assay_feedback.py`, `update_active_learning_from_feedback` | Appends supervised rows and learning-memory entries; reports retraining readiness but does not train/register a model yet. |
| Keep uncertainty visible | Implemented | `rank_candidates`, report generation | Adds flags such as `proxy_cooperativity_not_measured_alpha`, `proxy_hook_model_not_fitted_to_dose_response`, and `not_selected_for_expensive_ternary_modeling`. |

## Agent Documentation Status

| Doc | Local implementation status |
| --- | --- |
| `01-SupervisorAgent.md` | Implemented parser for target, E3, cell line, and expression override patterns. |
| `02-DesignPlannerAgent.md` | Implemented deterministic planning; search budgets are now added by `ControlledSearchAgent`. |
| `03-SafetyAgent.md` | Implemented local input and SMILES guardrails. |
| `04-TargetResolverAgent.md` | Implemented local/online target metadata path, depending on availability. |
| `05-TargetBinderRetrievalAgent.md` | Implemented binder retrieval plus architecture-update retrieval census fields. |
| `06-WarheadSelectionAgent.md` | Implemented curated/user warhead selection. |
| `07-E3LigandSelectionAgent.md` | Implemented local E3 ligand selection and capped ligand budget; broad >600 E3 search is still limited by ligand availability. |
| `08-ExitVectorDetectionAgent.md` | Implemented explicit attachment marker detection and confidence reporting. |
| `09-LinkerGenerationAgent.md` | Implemented curated/rule-based/generative-linker path with policy cap. |
| `10-MolecularConstructionAgent.md` | Implemented capped candidate construction. |
| `11-CandidateValidationAgent.md` | Implemented candidate validation; stereochemistry is expanded before validation. |
| `12-DegradationPredictionAgent.md` | Implemented heuristic prediction on cheap-filter survivors; trained production DC50/Dmax model remains future work. |
| `13-ADMETAgent.md` | Implemented local descriptor/risk scoring. |
| `14-NoveltyAgent.md` | Implemented local known-PROTAC similarity/duplicate checks; live patent-scale novelty remains future work. |
| `15-ApplicabilityDomainAgent.md` | Implemented domain scoring. |
| `16-RankingAgent.md` | Implemented multi-objective ranking with cooperativity, hook, and E3-context terms. |
| `17-ProximityDiversityAgent.md` | Implemented diversity clustering. |
| `18-ReflectionReviewAgent.md` | Implemented deterministic review; stronger automatic suppression/demotion policy remains a future improvement. |
| `19-EvolutionRefinementAgent.md` | Implemented generation records and seen-set memory path; evolved candidates are not yet integrated into the main pool in the primary success branch. |
| `20-TernaryFeasibilityAgent.md` | Implemented finalist-only proxy ternary scoring, with P4ward/structure-aware path when configured; full P4ward calibration remains future work. |
| `22-ReportAgent.md` | Implemented report generation with NP-hard funnel counts and proxy caveats. |
| `23-MemoryUpdateAgent.md` | Implemented workflow memory; assay-specific feedback is handled by `ActiveLearningAgent`. |
| `SEARCH_INSTRUMENTATION.md` | Partially implemented through retrieval census, generation records, coverage schemas/tests, cheap-filter summaries, and report tables. |
| `AGENT_REASONING_AND_BENCHMARKS.md` | Partially implemented through deterministic traces and focused tests; full benchmark suite remains future work. |
| `AGENT_ARCHITECTURE_UPDATE.md` | Partially implemented for Node 5 retrieval census, Node 19 generation records/seen set, and Node 20 calibration schema/gates. |

## Newly Added Markdown

- `md/24-ControlledSearchAgent.md`
- `md/25-StereochemistryEnumerationAgent.md`
- `md/26-CheapFilterAgent.md`
- `md/27-ExpensiveModelingSelectionAgent.md`
- `md/28-CellContextAgent.md`
- `md/29-CooperativityPredictionAgent.md`
- `md/30-HookEffectPredictionAgent.md`
- `md/31-ActiveLearningAgent.md`

`AGENT_APIS.md` was also updated with the current 31-node workflow order and the NP-hard funnel extension APIs.

## Honest Remaining Gaps

- Cooperativity and hook effect are proxy models until measured alpha and dose-response/hook data are available.
- Cell-type context uses curated priors and user overrides; it does not yet query live expression atlases.
- Active learning appends training rows and gates readiness; it does not yet launch a validated training job, model registry update, or rollback plan.
- P4ward/docking is bounded to finalists, but full calibration requires real structure runs and `CalibrationRecord` population.
- E3 search is still constrained by known liganded E3s; broad >600 ligase exploration needs ligand discovery data and new E3 ligand sources.

## Verification

Focused tests cover the new NP-hard funnel features:

- controlled search budgets
- cell-context expression overrides
- cheap filtering before expensive modeling
- bounded expensive-modeling finalists
- cooperativity and hook-effect rankability
- assay-feedback CSV writing
- assay-feedback memory recording

Run:

```bash
python -m pytest tests/test_np_hard_agent_features.py -q
python -m pytest synglue_agent/tests/test_architecture_update.py -q
```

Latest cross-check, 2026-08-30:

- `python -m compileall -q synglue_agent tests` passed.
- `python -m pytest tests/test_np_hard_agent_features.py -q` passed with 9 tests.
- `python -m pytest synglue_agent/tests/test_architecture_update.py -q` passed with 8 tests.
- Full workflow smoke for `Design 8 PROTAC candidates for BRD4 with CRBN in MM1.S cells and CRBN expression=0.9` completed with `errors []`.
- Smoke run produced `search_policy`, `cheap_filter_summary`, 40 cheap-filter survivors, 10 expensive-modeling finalists, 40 E3-context records, 10 ternary records, 40 cooperativity records, 40 hook-effect records, 40 ranked candidates, and 8 final candidates.
- Report smoke contained the scientific guardrails for proxy cooperativity and proxy hook-effect modeling.

Regression fixes from the cross-check:

- `ExitVectorDetectionAgent` now accepts the structured atom dictionaries returned by `detect_exit_vector_atoms`.
- `TargetBinderRetrievalAgent._observation` no longer crashes when local fallback binders have no pActivity value.
