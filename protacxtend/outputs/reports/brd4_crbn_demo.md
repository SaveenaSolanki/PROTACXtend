# SynGlue-Agent PROTAC Design Report

SynGlue-Agent is a tool-augmented, memory-enabled, workflow-orchestrated agentic AI framework for component-aware PROTAC design.

## Objective
- User request: Design CRBN-based PROTACs for BRD4. Generate 50 candidates using PEG, alkyl, piperazine, and triazole linkers with low DC50, high Dmax, acceptable ADME/Tox, medium novelty, and medium synthetic feasibility.
- Target: BRD4
- E3 ligase: CRBN
- Candidate target count: 50

## Workflow Summary
- Binders retrieved: 3
- Warheads selected: 3
- E3 ligands selected: 3
- Linkers generated: 9
- Construction attempts: 50
- Valid or unverified candidates: 50
- Evolved candidates: 0

## Scientific Guardrails
- Values are computational predictions, not experimental validation.
- Model version is reported for degradation predictions.
- Human medicinal chemistry and safety review is required before synthesis or wet-lab testing.

## Warnings
- RDKit is not installed; local run uses approximate descriptors and unverified fallback assembly.

## Top Ranked Candidates

| Rank | Tier | Target | E3 ligase | Warhead name | Linker class | Predicted DC50 nM | Predicted Dmax % | hERG risk | Novelty score | Final priority score | Warning flags |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Tier 1 | BRD4 | CRBN | BRD4_demo_JQ1_like | PEG | 31.93 | 80.7 | low | 0.627 | 0.734 | rdkit_unavailable_unverified_smiles;install_rdkit_for_chemical_validation;rdkit_not_installed |
| 2 | Tier 1 | BRD4 | CRBN | BRD4_demo_triazolobenzodiazepine_like | PEG | 31.93 | 80.7 | low | 0.595 | 0.734 | rdkit_unavailable_unverified_smiles;install_rdkit_for_chemical_validation;rdkit_not_installed |
| 3 | Tier 1 | BRD4 | CRBN | BRD4_demo_triazolobenzodiazepine_like | PEG | 31.93 | 80.7 | low | 0.595 | 0.733 | rdkit_unavailable_unverified_smiles;install_rdkit_for_chemical_validation;rdkit_not_installed |
| 4 | Tier 1 | BRD4 | CRBN | BRD4_demo_JQ1_like | PEG | 31.93 | 80.7 | low | 0.627 | 0.73 | rdkit_unavailable_unverified_smiles;install_rdkit_for_chemical_validation;rdkit_not_installed |
| 5 | Tier 1 | BRD4 | CRBN | BRD4_demo_triazolobenzodiazepine_like | PEG | 31.93 | 80.7 | low | 0.595 | 0.729 | rdkit_unavailable_unverified_smiles;install_rdkit_for_chemical_validation;rdkit_not_installed |
| 6 | Tier 1 | BRD4 | CRBN | BRD4_demo_triazolobenzodiazepine_like | PEG | 31.93 | 80.7 | low | 0.551 | 0.729 | rdkit_unavailable_unverified_smiles;install_rdkit_for_chemical_validation;rdkit_not_installed |
| 7 | Tier 1 | BRD4 | CRBN | BRD4_demo_triazolobenzodiazepine_like | PEG | 31.93 | 80.7 | low | 0.551 | 0.727 | rdkit_unavailable_unverified_smiles;install_rdkit_for_chemical_validation;rdkit_not_installed |
| 8 | Tier 1 | BRD4 | CRBN | BRD4_demo_triazolobenzodiazepine_like | triazole | 36.16 | 79.1 | low | 0.654 | 0.727 | rdkit_unavailable_unverified_smiles;install_rdkit_for_chemical_validation;rdkit_not_installed |
| 9 | Tier 1 | BRD4 | CRBN | BRD4_demo_JQ1_like | triazole | 36.16 | 79.1 | low | 0.65 | 0.725 | rdkit_unavailable_unverified_smiles;install_rdkit_for_chemical_validation;rdkit_not_installed |
| 10 | Tier 1 | BRD4 | CRBN | BRD4_demo_JQ1_like | piperazine | 33.28 | 80.2 | low | 0.558 | 0.723 | rdkit_unavailable_unverified_smiles;install_rdkit_for_chemical_validation;rdkit_not_installed |

## Agent Workflow Table

| Agent type | Data sources/tools | Query parameters | Quantitative outputs | Processing time |
| --- | --- | --- | --- | --- |
| Target Resolver Agent | local curated targets; UniProt/ChEMBL/PDB/AlphaFold stubs | target=BRD4, organism=human | UniProt=O60885, structures=3, tractability=0.86 | milliseconds locally; seconds with online APIs |
| Warhead Selection Agent | curated binders, RDKit validation, exit-vector maps | activity IC50/Ki/Kd <= 1000 nM; derivatization feasible | binders=3, warheads=3 | milliseconds locally; minutes with database queries |
| Construction Agent | curated templates, reaction SMARTS, known-linker grafting, matched linker replacement | warhead + linker + E3 with valid exit vectors | attempts=50, valid=50 | seconds locally; longer with retrosynthesis |
| Ranking Agent | SynGlue demo models, ADME/Tox, novelty, feasibility | low DC50, high Dmax, novelty | ranked=50, final=50 | seconds |