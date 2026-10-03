# S2 ⇄ S3 tool-parity table (declared before comparison)

Both arms execute the **same underlying tool implementations** via
`protacxtend.runtime.agent_tools.run_agent_tool` → `agentic.registry.execute_tool`.
S2 exposes them through a flat JSON interface; S3 reaches them through specialist
agents/orchestration. S2 excludes 4 meta/introspection tools so it exercises domain
tools only.

| tool | kind | executor present | S2 catalog | S3 access |
|---|---|---|---|---|
| assign_e3_mechanism | target | yes | yes | TargetResolver/DegradationContext |
| build_candidate_dossier | decision | yes | yes | ranking/decision tools |
| check_synthetic_feasibility | chemistry | yes | yes | LinkerDesign/Component + construct |
| construct_protac | chemistry | yes | yes | LinkerDesign/Component + construct |
| deep_research | research | yes | yes | research tools (deep_research/search_*) |
| detect_exit_vectors | chemistry | yes | yes | LinkerDesign/Component + construct |
| generate_linkers | chemistry | yes | yes | LinkerDesign/Component + construct |
| inspect_repo_assets | decision | yes | yes | ranking/decision tools |
| inspect_smiles | chemistry | yes | yes | LinkerDesign/Component + construct |
| list_repo_tools | decision | yes | yes | ranking/decision tools |
| model_ternary_complex | structure | yes | yes | StructureRetrievalAgent |
| predict_admet | prediction | yes | yes | DegradationPrediction/ADMET agents |
| predict_cell_context | prediction | yes | yes | DegradationPrediction/ADMET agents |
| predict_cooperativity | structure | yes | yes | StructureRetrievalAgent |
| predict_deepprotacs | prediction | yes | yes | DegradationPrediction/ADMET agents |
| predict_degradation | prediction | yes | yes | DegradationPrediction/ADMET agents |
| predict_protac_activity | prediction | yes | yes | DegradationPrediction/ADMET agents |
| predict_protac_stan | prediction | yes | yes | DegradationPrediction/ADMET agents |
| predict_se3_protacs | prediction | yes | yes | DegradationPrediction/ADMET agents |
| rank_candidates | decision | yes | yes | ranking/decision tools |
| resolve_target | target | yes | yes | TargetResolver/DegradationContext |
| retrieve_e3_evidence | target | yes | yes | TargetResolver/DegradationContext |
| retrieve_fulltext | research | yes | yes | research tools (deep_research/search_*) |
| retrieve_pdb | structure | yes | yes | StructureRetrievalAgent |
| retrieve_target_binders | target | yes | yes | TargetResolver/DegradationContext |
| run_degradomap_experiment | decision | yes | yes | ranking/decision tools |
| run_protacpilot_structural | workflow | yes | yes | workflow facade |
| sample_ternary_ternify | structure | yes | yes | StructureRetrievalAgent |
| score_lysine_ubiquitination | structure | yes | yes | StructureRetrievalAgent |
| search_bindingdb | chemistry | yes | yes | LinkerDesign/Component + construct |
| search_chembl | chemistry | yes | yes | LinkerDesign/Component + construct |
| search_europe_pmc | research | yes | yes | research tools (deep_research/search_*) |
| search_pubchem | chemistry | yes | yes | LinkerDesign/Component + construct |
| search_pubmed | research | yes | yes | research tools (deep_research/search_*) |
| search_uniprot | target | yes | yes | TargetResolver/DegradationContext |
| search_web | research | yes | yes | research tools (deep_research/search_*) |
| select_e3_ligase | target | yes | yes | TargetResolver/DegradationContext |
| simulate_hook_effect | structure | yes | yes | StructureRetrievalAgent |
| split_protac_bellerophon | chemistry | yes | yes | LinkerDesign/Component + construct |
| verify_crossref | research | yes | yes | research tools (deep_research/search_*) |

**Common domain tools:** 40 (all with executors). **Parity gaps:** none at the tool-implementation level; the arms differ only in orchestration (S3) vs flat tool loop (S2).

## Executed-this-run evidence (S2 smoke, real calls)

| case | tool executed | status | has_data | provenance retained |
|---|---|---|---|---|
| KNOW-01 | resolve_target | ok | yes | yes |
| DESIGN-12 | resolve_target | ok | yes | yes |
| DISCOVER-08 | resolve_target | ok | yes | yes |
| REASON-02 | resolve_target | ok | yes | yes |

Legitimate outcomes are separated: `status=ok,has_data=True` (success),
`status=ok,has_data=False` (empty-but-ok), `failure_code=MISSING_SCIENTIFIC_INPUT`
(typed abstention), `status=error` (tool/infra failure).
