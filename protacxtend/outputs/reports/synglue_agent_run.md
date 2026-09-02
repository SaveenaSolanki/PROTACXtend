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
- Linkers generated: 10
- Construction attempts: 50
- Valid or unverified candidates: 50
- Evolved candidates: 0

## Scientific Guardrails
- Values are computational predictions, not experimental validation.
- Model version is reported for degradation predictions.
- Human medicinal chemistry and safety review is required before synthesis or wet-lab testing.

## Top Ranked Candidates

| Rank | Tier | Target | E3 ligase | Warhead name | Linker class | Predicted DC50 nM | Predicted Dmax % | hERG risk | Novelty score | Final priority score | Warning flags |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Tier 1 | BRD4 | CRBN | BRD4_demo_triazolobenzodiazepine_like | piperazine | 33.28 | 80.2 | low | 0.795 | 0.749 |  |
| 2 | Tier 1 | BRD4 | CRBN | BRD4_demo_triazolobenzodiazepine_like | piperazine | 33.28 | 80.2 | low | 0.798 | 0.748 |  |
| 3 | Tier 1 | BRD4 | CRBN | BRD4_demo_triazolobenzodiazepine_like | PEG | 31.93 | 80.7 | low | 0.732 | 0.747 |  |
| 4 | Tier 1 | BRD4 | CRBN | BRD4_demo_triazolobenzodiazepine_like | PEG | 31.93 | 80.7 | low | 0.732 | 0.745 |  |
| 5 | Tier 1 | BRD4 | CRBN | BRD4_demo_triazolobenzodiazepine_like | PEG | 31.93 | 80.7 | low | 0.712 | 0.744 |  |
| 6 | Tier 1 | BRD4 | CRBN | BRD4_demo_triazolobenzodiazepine_like | PEG | 31.93 | 80.7 | low | 0.712 | 0.744 |  |
| 7 | Tier 1 | BRD4 | CRBN | BRD4_demo_JQ1_like | PEG | 31.93 | 80.7 | low | 0.781 | 0.743 |  |
| 8 | Tier 1 | BRD4 | CRBN | BRD4_demo_JQ1_like | piperazine | 33.28 | 80.2 | low | 0.793 | 0.742 |  |
| 9 | Tier 1 | BRD4 | CRBN | BRD4_demo_triazolobenzodiazepine_like | triazole | 36.16 | 79.1 | low | 0.8 | 0.742 |  |
| 10 | Tier 1 | BRD4 | CRBN | BRD4_demo_JQ1_like | PEG | 31.93 | 80.7 | low | 0.699 | 0.741 |  |

## Agent Workflow Table

| Agent type | Data sources/tools | Query parameters | Quantitative outputs | Processing time |
| --- | --- | --- | --- | --- |
| Target Resolver Agent | local curated targets; UniProt/ChEMBL/PDB/AlphaFold stubs | target=BRD4, organism=human | UniProt=O60885, structures=3, tractability=0.86 | milliseconds locally; seconds with online APIs |
| Binder Retrieval Agent | curated binders, ChEMBL/PubChem/BindingDB stubs, local PROTAC records | activity IC50/Ki/Kd/EC50 <= 1000 nM; assay confidence threshold | binders=3, unique_smiles=3 | milliseconds locally; minutes with online APIs |
| Warhead Selection Agent | curated binders, RDKit validation, exit-vector maps | activity IC50/Ki/Kd <= 1000 nM; derivatization feasible | binders=3, warheads=3 | milliseconds locally; minutes with database queries |
| E3 Ligand Agent | curated CRBN/VHL/IAP/MDM2 handles, E3 usage priors | requested_e3=CRBN | e3_ligands=3, ligases=1 | milliseconds locally |
| Exit Vector Agent | explicit attachment markers, SMARTS rules, curated maps | warhead and E3 ligand component SMILES | vectors=6, ambiguous=0 | milliseconds locally |
| Linker Generation Agent | curated library, rule enumeration, BRICS/RECAP hooks, LinkInvent/Reinvent stubs | linker_types=PEG,alkyl,piperazine,triazole | linkers=10, classes=4 | milliseconds locally; model generation can take minutes |
| Construction Agent | curated templates, reaction SMARTS, BRICS/RECAP, known-linker grafting, MMP replacement, generative hooks, retrosynthesis filter | warhead + linker + E3 with valid exit vectors | attempts=50, valid=50 | seconds locally; longer with retrosynthesis |
| Prediction Agent | SynGlue DC50/Dmax interface, component embeddings, applicability-domain model | full PROTAC, components, target, E3 ligase, optional cell context | degradation_predictions=50 | seconds locally; model dependent |
| ADME/Tox Agent | RDKit descriptors, hERG/AMES/DILI/CYP/P-gp/solubility wrappers | PROTAC-aware thresholds; no strict Lipinski rejection | admet_records=50 | seconds locally |
| Novelty Agent | known PROTAC set, Morgan fingerprints/string fallback, scaffold/component novelty | candidate SMILES and similarity thresholds | novelty_records=50 | seconds locally |
| Ternary Feasibility Agent | PDB/AlphaFold, geometry filter, docking wrappers, PRODIGY-like interface scoring | top candidates after first ranking | ternary_records=0 | seconds locally; docking can take hours |
| Ranking Agent | SynGlue demo models, ADME/Tox, novelty, feasibility | low DC50, high Dmax, novelty | ranked=50, final=50 | seconds |
| Reflection/Evolution Agent | candidate provenance, warning logs, linker replacement, E3 switch, exit-vector alternatives | top candidates and weaknesses | reviews=20, evolved=0 | seconds to minutes |
| Safety/Human Review Agent | guardrail rules, applicability domain, toxicity risk, provenance logs | final candidates and requested use | warnings=0, errors=0, human_review_required=True | milliseconds locally |