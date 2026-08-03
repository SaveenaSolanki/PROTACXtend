# SynGlue-Agent PROTAC Design Report

SynGlue-Agent is a tool-augmented, memory-enabled, workflow-orchestrated agentic AI framework for component-aware PROTAC design.

## Objective
- User request: Design CRBN-based PROTACs for NOXO1. Generate 10 candidates using PEG and alkyl linkers with low hERG risk.
- Target: NOXO1
- E3 ligase: CRBN
- Candidate target count: 10

## Workflow Summary
- Binders retrieved: 1
- Warheads selected: 1
- E3 ligands selected: 3
- Linkers generated: 7
- Construction attempts: 10
- Valid or unverified candidates: 11
- Evolved candidates: 1

## Scientific Guardrails
- Values are computational predictions, not experimental validation.
- Model version is reported for degradation predictions.
- Human medicinal chemistry and safety review is required before synthesis or wet-lab testing.

## Warnings
- RDKit is not installed; local run uses approximate descriptors and unverified fallback assembly.
- Target was not found locally; resolved from ChEMBL online fallback.
- CHEMBL5271171: Hypothetical attachment marker added by deterministic tool; chemist review required.

## Top Ranked Candidates

| Rank | Tier | Target | E3 ligase | Warhead name | Linker class | Predicted DC50 nM | Predicted Dmax % | hERG risk | Novelty score | Final priority score | Warning flags |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Tier 2 | NOXO1 | CRBN | CHEMBL5271171 | PEG | 172.92 | 55.5 | low | 0.646 | 0.579 | rdkit_unavailable_unverified_smiles;hypothetical_exit_vector_requires_chemist_review;install_rdkit_for_chemical_validation;rdkit_not_installed |
| 2 | Tier 2 | NOXO1 | CRBN | CHEMBL5271171 | alkyl | 208.43 | 54.1 | low | 0.646 | 0.571 | rdkit_unavailable_unverified_smiles;hypothetical_exit_vector_requires_chemist_review;install_rdkit_for_chemical_validation;rdkit_not_installed |
| 3 | Tier 2 | NOXO1 | CRBN | CHEMBL5271171 | PEG | 194.21 | 51.4 | low | 0.726 | 0.57 | rdkit_unavailable_unverified_smiles;hypothetical_exit_vector_requires_chemist_review;install_rdkit_for_chemical_validation;rdkit_not_installed |
| 4 | Tier 2 | NOXO1 | CRBN | CHEMBL5271171 | alkyl | 217.61 | 53.8 | low | 0.646 | 0.568 | rdkit_unavailable_unverified_smiles;hypothetical_exit_vector_requires_chemist_review;install_rdkit_for_chemical_validation;rdkit_not_installed |
| 5 | Tier 2 | NOXO1 | CRBN | CHEMBL5271171 | PEG | 187.78 | 52.7 | low | 0.646 | 0.567 | rdkit_unavailable_unverified_smiles;hypothetical_exit_vector_requires_chemist_review;install_rdkit_for_chemical_validation;rdkit_not_installed |
| 6 | Tier 2 | NOXO1 | CRBN | CHEMBL5271171 | alkyl | 222.51 | 53.1 | low | 0.646 | 0.563 | rdkit_unavailable_unverified_smiles;hypothetical_exit_vector_requires_chemist_review;install_rdkit_for_chemical_validation;rdkit_not_installed |
| 7 | Tier 2 | NOXO1 | CRBN | CHEMBL5271171 | alkyl | 220.05 | 53.5 | low | 0.646 | 0.563 | rdkit_unavailable_unverified_smiles;hypothetical_exit_vector_requires_chemist_review;install_rdkit_for_chemical_validation;rdkit_not_installed |
| 8 | Tier 2 | NOXO1 | CRBN | CHEMBL5271171 | alkyl | 241.71 | 50.0 | low | 0.726 | 0.561 | rdkit_unavailable_unverified_smiles;hypothetical_exit_vector_requires_chemist_review;install_rdkit_for_chemical_validation;rdkit_not_installed |
| 9 | Tier 2 | NOXO1 | CRBN | CHEMBL5271171 | alkyl | 244.41 | 49.7 | low | 0.726 | 0.559 | rdkit_unavailable_unverified_smiles;hypothetical_exit_vector_requires_chemist_review;install_rdkit_for_chemical_validation;rdkit_not_installed |
| 10 | Tier 2 | NOXO1 | CRBN | CHEMBL5271171 | alkyl | 249.9 | 49.1 | low | 0.726 | 0.556 | rdkit_unavailable_unverified_smiles;evolved_candidate_requires_revalidation;install_rdkit_for_chemical_validation;rdkit_not_installed |

## Agent Workflow Table

| Agent type | Data sources/tools | Query parameters | Quantitative outputs | Processing time |
| --- | --- | --- | --- | --- |
| Target Resolver Agent | local curated targets; UniProt/ChEMBL/PDB/AlphaFold stubs | target=NOXO1, organism=human | UniProt=Q8NFA2, structures=0, tractability=0.42 | milliseconds locally; seconds with online APIs |
| Binder Retrieval Agent | curated binders, ChEMBL/PubChem/BindingDB stubs, local PROTAC records | activity IC50/Ki/Kd/EC50 <= 1000 nM; assay confidence threshold | binders=1, unique_smiles=1 | milliseconds locally; minutes with online APIs |
| Warhead Selection Agent | curated binders, RDKit validation, exit-vector maps | activity IC50/Ki/Kd <= 1000 nM; derivatization feasible | binders=1, warheads=1 | milliseconds locally; minutes with database queries |
| E3 Ligand Agent | curated CRBN/VHL/IAP/MDM2 handles, E3 usage priors | requested_e3=CRBN | e3_ligands=3, ligases=1 | milliseconds locally |
| Exit Vector Agent | explicit attachment markers, SMARTS rules, curated maps | warhead and E3 ligand component SMILES | vectors=4, ambiguous=0 | milliseconds locally |
| Linker Generation Agent | curated library, rule enumeration, BRICS/RECAP hooks, LinkInvent/Reinvent stubs | linker_types=PEG,alkyl | linkers=7, classes=2 | milliseconds locally; model generation can take minutes |
| Construction Agent | curated templates, reaction SMARTS, BRICS/RECAP, known-linker grafting, MMP replacement, generative hooks, retrosynthesis filter | warhead + linker + E3 with valid exit vectors | attempts=10, valid=11 | seconds locally; longer with retrosynthesis |
| Prediction Agent | SynGlue DC50/Dmax interface, component embeddings, applicability-domain model | full PROTAC, components, target, E3 ligase, optional cell context | degradation_predictions=11 | seconds locally; model dependent |
| ADME/Tox Agent | RDKit descriptors, hERG/AMES/DILI/CYP/P-gp/solubility wrappers | PROTAC-aware thresholds; no strict Lipinski rejection | admet_records=11 | seconds locally |
| Novelty Agent | known PROTAC set, Morgan fingerprints/string fallback, scaffold/component novelty | candidate SMILES and similarity thresholds | novelty_records=11 | seconds locally |
| Ternary Feasibility Agent | PDB/AlphaFold, geometry filter, docking wrappers, PRODIGY-like interface scoring | top candidates after first ranking | ternary_records=0 | seconds locally; docking can take hours |
| Ranking Agent | SynGlue demo models, ADME/Tox, novelty, feasibility | low hERG risk | ranked=11, final=10 | seconds |
| Reflection/Evolution Agent | candidate provenance, warning logs, linker replacement, E3 switch, exit-vector alternatives | top candidates and weaknesses | reviews=10, evolved=1 | seconds to minutes |
| Safety/Human Review Agent | guardrail rules, applicability domain, toxicity risk, provenance logs | final candidates and requested use | warnings=3, errors=0, human_review_required=True | milliseconds locally |