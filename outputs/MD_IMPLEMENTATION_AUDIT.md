# MD-Docs vs Implementation Audit

_Generated 2026-08-12 · 104 checks · 94 OK, 10 FAIL_

| Doc | Claim | Status | Evidence |
|---|---|---|---|
| 00-INDEX.md | 00-INDEX.md: source file | ❌ | no **Source** line |
| 01-SupervisorAgent.md | 01-SupervisorAgent.md: file exists | ✅ | protacxtend/agents/supervisor_agent.py (59 lines) |
| 01-SupervisorAgent.md | 01-SupervisorAgent.md: class SupervisorAgent | ✅ | found |
| 02-DesignPlannerAgent.md | 02-DesignPlannerAgent.md: file exists | ✅ | protacxtend/agents/design_planner_agent.py (152 lines) |
| 02-DesignPlannerAgent.md | 02-DesignPlannerAgent.md: class DesignPlannerAgent | ✅ | found |
| 03-SafetyAgent.md | 03-SafetyAgent.md: file exists | ✅ | protacxtend/agents/safety_agent.py (55 lines) |
| 03-SafetyAgent.md | 03-SafetyAgent.md: class SafetyAgent | ✅ | found |
| 04-TargetResolverAgent.md | 04-TargetResolverAgent.md: file exists | ✅ | protacxtend/agents/target_agent.py (83 lines) |
| 04-TargetResolverAgent.md | 04-TargetResolverAgent.md: class TargetResolverAgent | ✅ | found |
| 04-TargetResolverAgent.md | 04-TargetResolverAgent.md: tool uniprot_lookup.py | ✅ | exists |
| 04-TargetResolverAgent.md | 04-TargetResolverAgent.md: tool alphafold_client.py | ✅ | exists |
| 05-TargetBinderRetrievalAgent.md | 05-TargetBinderRetrievalAgent.md: file exists | ✅ | protacxtend/agents/binder_agent.py (333 lines) |
| 05-TargetBinderRetrievalAgent.md | 05-TargetBinderRetrievalAgent.md: class TargetBinderRetrievalAgent | ✅ | found |
| 05-TargetBinderRetrievalAgent.md | 05-TargetBinderRetrievalAgent.md: tool chembl_lookup.py | ✅ | exists |
| 05-TargetBinderRetrievalAgent.md | 05-TargetBinderRetrievalAgent.md: tool pubchem_lookup.py | ✅ | exists |
| 05-TargetBinderRetrievalAgent.md | 05-TargetBinderRetrievalAgent.md: tool bindingdb_lookup.py | ✅ | exists |
| 05-TargetBinderRetrievalAgent.md | 05-TargetBinderRetrievalAgent.md: tool online_ligand_miner.py | ✅ | exists |
| 06-WarheadSelectionAgent.md | 06-WarheadSelectionAgent.md: file exists | ✅ | protacxtend/agents/warhead_agent.py (85 lines) |
| 06-WarheadSelectionAgent.md | 06-WarheadSelectionAgent.md: class WarheadSelectionAgent | ✅ | found |
| 07-E3LigandSelectionAgent.md | 07-E3LigandSelectionAgent.md: file exists | ✅ | protacxtend/agents/e3_agent.py (91 lines) |
| 07-E3LigandSelectionAgent.md | 07-E3LigandSelectionAgent.md: class E3LigandSelectionAgent | ✅ | found |
| 08-ExitVectorDetectionAgent.md | 08-ExitVectorDetectionAgent.md: file exists | ✅ | protacxtend/agents/exit_vector_agent.py (74 lines) |
| 08-ExitVectorDetectionAgent.md | 08-ExitVectorDetectionAgent.md: class ExitVectorDetectionAgent | ✅ | found |
| 09-LinkerGenerationAgent.md | 09-LinkerGenerationAgent.md: file exists | ✅ | protacxtend/agents/linker_agent.py (28 lines) |
| 09-LinkerGenerationAgent.md | 09-LinkerGenerationAgent.md: class LinkerGenerationAgent | ✅ | found |
| 10-MolecularConstructionAgent.md | 10-MolecularConstructionAgent.md: file exists | ✅ | protacxtend/agents/construction_agent.py (49 lines) |
| 10-MolecularConstructionAgent.md | 10-MolecularConstructionAgent.md: class MolecularConstructionAgent | ✅ | found |
| 11-CandidateValidationAgent.md | 11-CandidateValidationAgent.md: source file | ❌ | no **Source** line |
| 12-DegradationPredictionAgent.md | 12-DegradationPredictionAgent.md: file exists | ✅ | protacxtend/agents/prediction_agent.py (39 lines) |
| 12-DegradationPredictionAgent.md | 12-DegradationPredictionAgent.md: class DegradationPredictionAgent | ✅ | found |
| 13-ADMETAgent.md | 13-ADMETAgent.md: file exists | ✅ | protacxtend/agents/admet_agent.py (20 lines) |
| 13-ADMETAgent.md | 13-ADMETAgent.md: class ADMETAgent | ✅ | found |
| 14-NoveltyAgent.md | 14-NoveltyAgent.md: file exists | ✅ | protacxtend/agents/novelty_agent.py (20 lines) |
| 14-NoveltyAgent.md | 14-NoveltyAgent.md: class NoveltyAgent | ✅ | found |
| 15-ApplicabilityDomainAgent.md | 15-ApplicabilityDomainAgent.md: file exists | ✅ | protacxtend/agents/prediction_agent.py (39 lines) |
| 15-ApplicabilityDomainAgent.md | 15-ApplicabilityDomainAgent.md: class ApplicabilityDomainAgent | ✅ | found |
| 16-RankingAgent.md | 16-RankingAgent.md: file exists | ✅ | protacxtend/agents/ranking_agent.py (41 lines) |
| 16-RankingAgent.md | 16-RankingAgent.md: class RankingAgent | ✅ | found |
| 17-ProximityDiversityAgent.md | 17-ProximityDiversityAgent.md: file exists | ✅ | protacxtend/agents/proximity_agent.py (31 lines) |
| 17-ProximityDiversityAgent.md | 17-ProximityDiversityAgent.md: class ProximityDiversityAgent | ✅ | found |
| 18-ReflectionReviewAgent.md | 18-ReflectionReviewAgent.md: file exists | ✅ | protacxtend/agents/reflection_agent.py (48 lines) |
| 18-ReflectionReviewAgent.md | 18-ReflectionReviewAgent.md: class ReflectionReviewAgent | ✅ | found |
| 19-EvolutionRefinementAgent.md | 19-EvolutionRefinementAgent.md: file exists | ✅ | protacxtend/agents/evolution_agent.py (61 lines) |
| 19-EvolutionRefinementAgent.md | 19-EvolutionRefinementAgent.md: class EvolutionRefinementAgent | ✅ | found |
| 20-TernaryFeasibilityAgent.md | 20-TernaryFeasibilityAgent.md: file exists | ✅ | protacxtend/agents/ternary_agent.py (597 lines) |
| 20-TernaryFeasibilityAgent.md | 20-TernaryFeasibilityAgent.md: class TernaryFeasibilityAgent | ✅ | found |
| 20-TernaryFeasibilityAgent.md | 20-TernaryFeasibilityAgent.md: tool p4ward_wrapper.py | ✅ | exists |
| 20-TernaryFeasibilityAgent.md | 20-TernaryFeasibilityAgent.md: tool ternary_feasibility.py | ✅ | exists |
| 22-ReportAgent.md | 22-ReportAgent.md: file exists | ✅ | protacxtend/agents/report_agent.py (20 lines) |
| 22-ReportAgent.md | 22-ReportAgent.md: class ReportAgent | ✅ | found |
| 23-MemoryUpdateAgent.md | 23-MemoryUpdateAgent.md: source file | ❌ | no **Source** line |
| 01-SupervisorAgent.md | 01-SupervisorAgent.md: state.traces | ❌ | field NOT in WorkflowState schema |
| 02-DesignPlannerAgent.md | 02-DesignPlannerAgent.md: state.traces | ❌ | field NOT in WorkflowState schema |
| 03-SafetyAgent.md | 03-SafetyAgent.md: state.traces | ❌ | field NOT in WorkflowState schema |
| 04-TargetResolverAgent.md | 04-TargetResolverAgent.md: state.traces | ❌ | field NOT in WorkflowState schema |
| 05-TargetBinderRetrievalAgent.md | 05-TargetBinderRetrievalAgent.md: state.traces | ❌ | field NOT in WorkflowState schema |
| 15-ApplicabilityDomainAgent.md | 15-ApplicabilityDomainAgent.md: state.applicability_domain | ❌ | field NOT in WorkflowState schema |
| ARCHITECTURE_SUMMARY.md | ARCHITECTURE_SUMMARY.md: ref admet_predictors.py | ✅ | resolved to protacxtend/tools/admet_predictors.py |
| ARCHITECTURE_SUMMARY.md | ARCHITECTURE_SUMMARY.md: ref tool_status.py | ✅ | resolved to protacxtend/tools/tool_status.py |
| ARCHITECTURE_SUMMARY.md | ARCHITECTURE_SUMMARY.md: ref toolkit_registry.py | ✅ | resolved to protacxtend/tools/toolkit_registry.py |
| ARCHITECTURE_SUMMARY.md | ARCHITECTURE_SUMMARY.md: ref linker_scanner.py | ✅ | resolved to protacxtend/tools/linker_scanner.py |
| ARCHITECTURE_SUMMARY.md | ARCHITECTURE_SUMMARY.md: ref report_generator.py | ✅ | resolved to protacxtend/tools/report_generator.py |
| ARCHITECTURE_SUMMARY.md | ARCHITECTURE_SUMMARY.md: ref repo_tool_adapter.py | ✅ | resolved to protacxtend/tools/repo_tool_adapter.py |
| ARCHITECTURE_SUMMARY.md | ARCHITECTURE_SUMMARY.md: ref tool_registry.py | ✅ | resolved to protacxtend/tools/tool_registry.py |
| ARCHITECTURE_SUMMARY.md | ARCHITECTURE_SUMMARY.md: ref toolkit_router.py | ✅ | resolved to protacxtend/tools/toolkit_router.py |
| ARCHITECTURE_SUMMARY.md | ARCHITECTURE_SUMMARY.md: ref bindingdb_lookup.py | ✅ | resolved to protacxtend/tools/bindingdb_lookup.py |
| ARCHITECTURE_SUMMARY.md | ARCHITECTURE_SUMMARY.md: ref protac_toolbox.py | ✅ | resolved to protacxtend/tools/protac_toolbox.py |
| ARCHITECTURE_SUMMARY.md | ARCHITECTURE_SUMMARY.md: ref online_ligand_miner.py | ✅ | resolved to protacxtend/tools/online_ligand_miner.py |
| ARCHITECTURE_SUMMARY.md | ARCHITECTURE_SUMMARY.md: ref novelty_checker.py | ✅ | resolved to protacxtend/tools/novelty_checker.py |
| ARCHITECTURE_SUMMARY.md | ARCHITECTURE_SUMMARY.md: ref rcsb_pdb_lookup.py | ✅ | resolved to protacxtend/tools/rcsb_pdb_lookup.py |
| ARCHITECTURE_SUMMARY.md | ARCHITECTURE_SUMMARY.md: ref magnetdb_lookup.py | ✅ | resolved to protacxtend/tools/magnetdb_lookup.py |
| ARCHITECTURE_SUMMARY.md | ARCHITECTURE_SUMMARY.md: ref alphafold_client.py | ✅ | resolved to protacxtend/tools/alphafold_client.py |
| ARCHITECTURE_SUMMARY.md | ARCHITECTURE_SUMMARY.md: ref docking_pipeline.py | ✅ | resolved to protacxtend/tools/docking_pipeline.py |
| ARCHITECTURE_SUMMARY.md | ARCHITECTURE_SUMMARY.md: ref applicability_domain.py | ✅ | resolved to protacxtend/tools/applicability_domain.py |
| ARCHITECTURE_SUMMARY.md | ARCHITECTURE_SUMMARY.md: ref protac_autopilot_toolbox.py | ✅ | resolved to protacxtend/tools/protac_autopilot_toolbox.py |
| ARCHITECTURE_SUMMARY.md | ARCHITECTURE_SUMMARY.md: ref drugbank_client.py | ✅ | resolved to protacxtend/tools/drugbank_client.py |
| ARCHITECTURE_SUMMARY.md | ARCHITECTURE_SUMMARY.md: ref protacdb_client.py | ✅ | resolved to protacxtend/tools/protacdb_client.py |
| ARCHITECTURE_SUMMARY.md | ARCHITECTURE_SUMMARY.md: ref stereochemistry_engine.py | ✅ | resolved to protacxtend/tools/stereochemistry_engine.py |
| ARCHITECTURE_SUMMARY.md | ARCHITECTURE_SUMMARY.md: ref chemistry_core.py | ✅ | resolved to protacxtend/tools/chemistry_core.py |
| ARCHITECTURE_SUMMARY.md | ARCHITECTURE_SUMMARY.md: ref p4ward_wrapper.py | ✅ | resolved to protacxtend/tools/p4ward_wrapper.py |
| ARCHITECTURE_SUMMARY.md | ARCHITECTURE_SUMMARY.md: ref rdkit_chemistry.py | ✅ | resolved to protacxtend/tools/rdkit_chemistry.py |
| ARCHITECTURE_SUMMARY.md | ARCHITECTURE_SUMMARY.md: ref protac_repo_tool_wrappers.py | ✅ | resolved to protacxtend/tools/protac_repo_tool_wrappers.py |
| ARCHITECTURE_SUMMARY.md | ARCHITECTURE_SUMMARY.md: ref chembl_lookup.py | ✅ | resolved to protacxtend/tools/chembl_lookup.py |
| ARCHITECTURE_SUMMARY.md | ARCHITECTURE_SUMMARY.md: ref protacpedia_client.py | ✅ | resolved to protacxtend/tools/protacpedia_client.py |
| ARCHITECTURE_SUMMARY.md | ARCHITECTURE_SUMMARY.md: ref degradation_predictor.py | ✅ | resolved to protacxtend/tools/degradation_predictor.py |
| ARCHITECTURE_SUMMARY.md | ARCHITECTURE_SUMMARY.md: ref protac_component_wrappers.py | ✅ | resolved to protacxtend/tools/protac_component_wrappers.py |
| ARCHITECTURE_SUMMARY.md | ARCHITECTURE_SUMMARY.md: ref memory_manager.py | ✅ | resolved to protacxtend/tools/memory_manager.py |
| ARCHITECTURE_SUMMARY.md | ARCHITECTURE_SUMMARY.md: ref uniprot_lookup.py | ✅ | resolved to protacxtend/tools/uniprot_lookup.py |
| ARCHITECTURE_SUMMARY.md | ARCHITECTURE_SUMMARY.md: ref pubchem_lookup.py | ✅ | resolved to protacxtend/tools/pubchem_lookup.py |
| ARCHITECTURE_SUMMARY.md | ARCHITECTURE_SUMMARY.md: ref synglue_integration.py | ✅ | resolved to protacxtend/tools/synglue_integration.py |
| ARCHITECTURE_SUMMARY.md | ARCHITECTURE_SUMMARY.md: ref ternary_feasibility.py | ✅ | resolved to protacxtend/tools/ternary_feasibility.py |
| fey_protac.md | fey_protac.md: module protacxtend.tools.p | ❌ | IMPORT FAILS |
| PROTACPILOT_TECHNICAL_COHERENCE.md | PROTACPILOT_TECHNICAL_COHERENCE.md: ref schemas.py | ✅ | resolved to protacxtend/llm/schemas.py |
| PROTACPILOT_TECHNICAL_COHERENCE.md | PROTACPILOT_TECHNICAL_COHERENCE.md: ref e3_agent.py | ✅ | resolved to protacxtend/agents/e3_agent.py |
| PROTACPILOT_TECHNICAL_COHERENCE.md | PROTACPILOT_TECHNICAL_COHERENCE.md: ref graph.py | ✅ | resolved to protacxtend/agents/graph.py |
| PROTACPILOT_TECHNICAL_COHERENCE.md | PROTACPILOT_TECHNICAL_COHERENCE.md: ref linker_scanner.py | ✅ | resolved to protacxtend/tools/linker_scanner.py |
| PROTACPILOT_TECHNICAL_COHERENCE.md | PROTACPILOT_TECHNICAL_COHERENCE.md: ref p4ward_wrapper.py | ✅ | resolved to protacxtend/tools/p4ward_wrapper.py |
| PROTACPILOT_TECHNICAL_COHERENCE.md | PROTACPILOT_TECHNICAL_COHERENCE.md: ref design_planner_agent.py | ✅ | resolved to protacxtend/agents/design_planner_agent.py |
| PROTACPILOT_TECHNICAL_COHERENCE.md | PROTACPILOT_TECHNICAL_COHERENCE.md: ref prompts.py | ✅ | resolved to protacxtend/agents/prompts.py |
| PROTACPILOT_TECHNICAL_COHERENCE.md | PROTACPILOT_TECHNICAL_COHERENCE.md: ref protac_toolbox.py | ✅ | resolved to protacxtend/tools/protac_toolbox.py |
| PROTACPILOT_TECHNICAL_COHERENCE.md | PROTACPILOT_TECHNICAL_COHERENCE.md: ref linker_agent.py | ✅ | resolved to protacxtend/agents/linker_agent.py |
| PROTACPILOT_TECHNICAL_COHERENCE.md | PROTACPILOT_TECHNICAL_COHERENCE.md: ref base_agent.py | ✅ | resolved to protacxtend/agents/base_agent.py |
| PROTACPILOT_TECHNICAL_COHERENCE.md | PROTACPILOT_TECHNICAL_COHERENCE.md: ref retrosynthesis_filter.py | ✅ | resolved to protacxtend/tools/retrosynthesis_filter.py |
| PROTACPILOT_TECHNICAL_COHERENCE.md | PROTACPILOT_TECHNICAL_COHERENCE.md: ref ternary_feasibility.py | ✅ | resolved to protacxtend/tools/ternary_feasibility.py |
## Resolution & verdict (manual pass)

All 10 remaining audit flags are **documentation drift or self-noted**, NOT missing
implementations — every agent class documented in `md/` exists in code:

| Flag | Resolution |
|---|---|
| 00-INDEX "no Source" | It IS the index, not an agent spec (not applicable) |
| 11-CandidateValidationAgent, 23-MemoryUpdateAgent "no Source" | Docs self-note "Source: not listed in the documented file tree"; classes exist: `CandidateValidationAgent` → `protacxtend/agents/construction_agent.py`, `MemoryUpdateAgent` → `protacxtend/agents/graph.py` |
| `state.traces` (01–05, 18…) | Schema field is `workflow_log: List[AgentTrace]` — old doc name, same data |
| `state.applicability_domain` (15) | Schema field is `applicability_domain_results` — old doc name |
| fey_protac / ASSET_MANIFEST refs | Checker regex artifacts; all real refs exist (`ternary_agent.py`, `p4ward_wrapper.py`, `protac_autopilot_toolbox.py` ✓) |

**Stale status flags fixed in this pass** (docs dated 2026-07-31, gaps closed since):
- 07 E3LigandSelection "4 of 600+ ligases" → 19 E3 groups / 114 cited ligands (2026-08-12)
- 12 DegradationPrediction "heuristic only" → trained Chemprop ensemble (v0.3)
- 14 Novelty "4-molecule reference set" → local similarity + live PubChem patents (2026-08-08)
- 20 Ternary "never executed" → ensemble executed in container + e2e (v0.3)

**One real doc bug found and fixed:** `ASSET_MANIFEST.md` regeneration instruction pointed at
`SynGlue_Py/Architecture_Code/03_TRIE_Index_build_trie.py` which is NOT present in the local
SynGlue_Py subset → now points at the upstream GitHub URL.

**Verdict:** all agent classes, tools and modules referenced by the project's Markdown
documentation are implemented in code. The `md/` specs remain accurate for architecture;
status flags updated to match the 2026-08 implemented reality. Run
`python scripts/audit_md_vs_code.py` to re-audit after any doc change.
