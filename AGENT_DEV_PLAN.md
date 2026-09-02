# Agent Development Plan — What I Need From You

## Current NP-Hard Search Implementation

The detailed implementation plan for solving the PROTAC NP-hard search bottlenecks through bounded agents is maintained in:

- `PROTACPILOT_NP_HARD_FEATURE_PLAN.md`

That document now specifies the exact agent order, per-agent input/output contracts, pruning rules, search budgets, cheap-filter thresholds, finalist-only expensive modeling policy, multi-objective ranking formula, uncertainty flags, resources, data requirements, and assay-feedback learning loop.

The new section includes:

- controlled linker/E3/exit-vector/stereoisomer generation rather than brute-force enumeration;
- cheap filters before expensive biological or structural modeling;
- finalist-only ternary modeling through `expensive_modeling_candidate_ids`;
- stronger proxy cooperativity scoring with visible evidence labels;
- concentration-dependent hook-effect modeling with proxy caveats;
- explicit cell-line and E3-expression inputs;
- active-learning assay feedback ingestion and retraining-readiness gates;
- exact resources needed for RDKit, docking/P4ward, expression tables, measured alpha/Kd data, dose-response data, and model retraining.

Core rule: PROTACXtend must not enumerate the full linker/E3/exit-vector/stereoisomer space. It must generate a controlled pool, cheaply filter it, run expensive ternary modeling only on finalists, preserve uncertainty labels, and feed assay results back into active-learning memory.

Implemented code map:

| Feature | Implementation |
| --- | --- |
| Controlled budgets | `ControlledSearchAgent`, `SearchPolicy`, `build_search_policy` |
| Capped stereochemistry | `StereochemistryEnumerationAgent`, `expand_stereoisomers_controlled` |
| Cheap filtering | `CheapFilterAgent`, `cheap_filter_candidates` |
| Finalist selection | `ExpensiveModelingSelectionAgent`, `select_expensive_modeling_finalists` |
| Cell context | `CellContextAgent`, `score_e3_context` |
| Cooperativity | `CooperativityPredictionAgent`, `predict_cooperativity` |
| Hook effect | `HookEffectPredictionAgent`, `predict_hook_effect` |
| Active learning | `ActiveLearningAgent`, `assay_feedback.py`, `update_active_learning_from_feedback` |
| Multi-objective ranking | `RankingAgent`, `rank_candidates` |

## Can Build Now (no API keys needed)

| Agent | What it needs | Status |
|-------|--------------|--------|
| TargetResolverAgent | UniProt REST API optional; local target data fallback | Implemented |
| WarheadSelectionAgent | Local curated_warheads.csv | Implemented |
| E3LigandSelectionAgent | Local curated_e3_ligands.csv | Implemented |
| ExitVectorDetectionAgent | RDKit preferred | Implemented |
| LinkerGenerationAgent | Local curated_linkers.csv + RDKit/generative fallback | Implemented with budget cap |
| MolecularConstructionAgent | RDKit preferred | Implemented with construction cap |
| StereochemistryEnumerationAgent | RDKit stereochemistry support | Implemented with cap |
| CandidateValidationAgent | RDKit + property rules | Implemented |
| CellContextAgent | Curated E3 context priors + user overrides | Implemented; needs real expression atlas next |
| ADMETAgent | RDKit descriptors | Implemented |
| NoveltyAgent | Local known_protac_smiles.csv | Implemented |
| ApplicabilityDomainAgent | Local property/domain heuristics | Implemented |
| CheapFilterAgent | Validity, property, ADMET, novelty, domain, context scores | Implemented |
| DegradationPredictionAgent | Heuristic model | Implemented; trained model still needed |
| RankingAgent | Multi-objective scoring | Implemented with new terms |
| ExpensiveModelingSelectionAgent | Ranking + diversity finalist selection | Implemented |
| TernaryFeasibilityAgent | Geometry proxy; P4ward path when configured | Implemented; calibration still needed |
| CooperativityPredictionAgent | Ternary/linker/interface/lysine proxy | Implemented as proxy |
| HookEffectPredictionAgent | Concentration-grid proxy | Implemented as proxy |
| ActiveLearningAgent | Assay feedback rows + memory | Implemented ingestion; retraining job still needed |
| ProximityDiversityAgent | RDKit fingerprints | Implemented |
| ReflectionReviewAgent | Rule-based critique | Implemented |
| SafetyAgent | Simple rule checks | Implemented |
| ReportAgent | Template + data | Implemented with NP-hard caveats |

## Need API Keys From You

| Agent/Source | What it needs | Where to get it | Free? |
|-------------|--------------|-----------------|-------|
| **ChEMBL** | Bioactivity data for binder retrieval | https://www.ebi.ac.uk/chembl/ws | ✅ Free registration |
| **PubChem** | Compound lookup | https://pubchem.ncbi.nlm.nih.gov/docs/programmatic-access | ✅ Free (no key) |
| **RCSB PDB** | Protein structures | https://data.rcsb.org/ | ✅ Free (no key) |
| **UniProt** | Protein annotation | https://www.uniprot.org/api-documentation | ✅ Free (no key) |
| **BindingDB** | Affinity data | https://www.bindingdb.org/rwd/bind/BindingDBAPI.jsp | ✅ Free |
| **DrugBank** | Drug-target data | https://go.drugbank.com/ | ❌ Licensed ($) |
| **PDB ID mapping** | ID conversion | https://www.uniprot.org/id-mapping | ✅ Free |

**Good news:** ChEMBL, PubChem, PDB, UniProt, BindingDB are all **free with no key or free registration**. I can start building against their public APIs immediately. Only DrugBank requires a paid license.

## Stereochemistry-Aware SMILES

Implemented or partially implemented:

1. **Isomeric SMILES parser** - RDKit-backed stereochemistry tools exist.
2. **Controlled stereoisomer enumeration** - `StereochemistryEnumerationAgent` expands only within budget.
3. **Linker attachment with stereo retention** - assembly and validation preserve stereoisomer-specific candidate records where possible.
4. **Validation** - stereoisomer variants are not silently collapsed without warning.

This path is RDKit-based and is now part of the implemented workflow.

---

## Remaining Build Work

The immediate implementation is present. The remaining work is production validation:

- connect real cell-line expression tables;
- fit hook-effect curves from measured dose-response data;
- calibrate cooperativity against measured alpha/Kd or validated ternary-pose data;
- run bounded P4ward/docking calibration on finalists;
- add a reproducible model-training job, registry, and rollback path for active learning.
