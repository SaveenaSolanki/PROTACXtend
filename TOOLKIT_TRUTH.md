# PROTACXtend Toolkit — Source of Truth

_Generated 2026-09-16T08:32:39.910107+00:00_

This document and the sibling workbook `analysis/inventory/PROTACXtend_Toolkit_Truth.xlsx` are the single source of truth for **what the toolkit contains and at exactly which version**.

## 1. Headline counts

| metric | value |
|---|---|
| toolkit_tools | 115 |
| tools_installed | 30 |
| tools_callable | 30 |
| tools_installable | 47 |
| tools_commercial | 13 |
| tools_web_only | 13 |
| tools_repo_required | 21 |
| agent_tools | 34 |
| agent_tools_ready | 34 |
| datasets | 59 |
| datasets_present | 53 |
| capabilities | 27 |
| capabilities_ready | 20 |

## 2. Installed & callable tools (with exact version)

| tool | category | version | provider env | method |
|---|---|---|---|---|
| PyMOL | molecular_visualization | File "<string>", line 1, in <module> | PATH:/usr/bin/pymol | binary |
| NGLView | molecular_visualization | 4.0.1 | protacpilot | pip |
| AutoDock Vina | ligand_docking | AutoDock Vina v1.2.3 | PATH:/usr/bin/vina | conda |
| AutoDock4 | ligand_docking | AutoDock 4.2.6 | PATH:/usr/bin/autodock4 | binary |
| GNINA | ligand_docking | bin:gnina | docking:/home/saveenas/.protacxtend/envs/docking/bin/gnina | conda |
| LightDock | protein_protein_docking | bin:lightdock3.py | ppi:/home/saveenas/.protacxtend/envs/ppi/bin/lightdock3.py | conda |
| GROMACS | molecular_dynamics | bin:gmx | gromacs:/home/saveenas/.protacxtend/envs/gromacs/bin/gmx | conda |
| OpenMM | molecular_dynamics | 8.6.1 | protacpilot | pip |
| AMBER / AmberTools | molecular_dynamics | bin:sander | gromacs:/home/saveenas/.protacxtend/envs/gromacs/bin/sander | binary |
| gmx_MMPBSA | binding_energy | bin:gmx_MMPBSA | gromacs:/home/saveenas/.protacxtend/envs/gromacs/bin/gmx_MMPBSA | binary |
| MMPBSA.py | binding_energy | bin:MMPBSA.py | gromacs:/home/saveenas/.protacxtend/envs/gromacs/bin/MMPBSA.py | binary |
| Meeko | ligand_preparation | 0.7.1 | current | pip |
| PDBFixer | structure_preparation | 1.12.0 | protacpilot | pip |
| PropKa | structure_preparation | propka3 3.5.1 | protacpilot:/home/saveenas/miniconda3/envs/protacpilot/bin/propka3 | conda |
| PDB2PQR | structure_preparation | pdb2pqr 3.7.1 | protacpilot:/home/saveenas/miniconda3/envs/protacpilot/bin/pdb2pqr | conda |
| OpenBabel | ligand_preparation | 3.1.0 | protacpilot | pip |
| RDKit ETKDG | conformer_generation | 2026.03.4 | current | pip |
| CReM | de_novo_generation | 0.3.1 | protacpilot | pip |
| mmpdb | fragmentation | mmpdb, version 3.1.4 | protacpilot:/home/saveenas/miniconda3/envs/protacpilot/bin/mmpdb | conda |
| BRICS | fragmentation | 2026.03.4 | current | pip |
| RECAP | fragmentation | 2026.03.4 | current | pip |
| GuacaMol | de_novo_generation | 0.5.5 | protacpilot | pip |
| AiZynthFinder | retrosynthesis | 4.4.1 | protacpilot | pip |
| RXNMapper | reaction_prediction | 0.4.3 | protacpilot | pip |
| RDChiral | reaction_prediction | 1.1.0 | protacpilot | pip |
| Therapeutics Data Commons | admet_toxicity | installed | protacpilot | pip |
| Chemprop | molecular_ml | 2.3.1 | current | pip |
| DeepChem | molecular_ml | 2.8.0 | protacpilot | pip |
| ESM-2 | protein_language_models | 2.0.0 | current | pip |
| SciSpacy | literature_mining | 0.6.2 | toolkit-venv | pip |

## 3. Full toolkit provisioning matrix

`pip`/`conda` = auto-installable; `repo` = own repo + weights; `web` = hosted only; `commercial` = licence required.

| tool | category | method | installed | callable | reason |
|---|---|---|---|---|---|
| PyMOL | molecular_visualization | binary | yes | yes | source/apt binary — provide on PATH or install into a conda env |
| UCSF ChimeraX | molecular_visualization | binary | no | no | source/apt binary — provide on PATH or install into a conda env |
| UCSF Chimera | molecular_visualization | binary | no | no | source/apt binary — provide on PATH or install into a conda env |
| VMD | molecular_visualization | binary | no | no | source/apt binary — provide on PATH or install into a conda env |
| NGLView | molecular_visualization | pip | yes | yes | pip-installable Python package |
| Mol* | molecular_visualization | web | no | no | web-only service — https://molstar.org/viewer/ |
| AutoDock Vina | ligand_docking | conda | yes | yes | conda-forge / bioconda package |
| AutoDock-GPU | ligand_docking | conda | no | no | conda-forge / bioconda package |
| AutoDock4 | ligand_docking | binary | yes | yes | source/apt binary — provide on PATH or install into a conda env |
| Smina | ligand_docking | conda | no | no | conda-forge / bioconda package |
| GNINA | ligand_docking | conda | yes | yes | conda-forge / bioconda package |
| rDock | ligand_docking | conda | no | no | conda-forge / bioconda package |
| DOCK6 | ligand_docking | conda | no | no | conda-forge / bioconda package |
| LeDock | ligand_docking | conda | no | no | conda-forge / bioconda package |
| PLANTS | ligand_docking | conda | no | no | conda-forge / bioconda package |
| GOLD | ligand_docking | commercial | no | no | commercial/licensed — manual provisioning and licence required |
| Glide | ligand_docking | commercial | no | no | commercial/licensed — manual provisioning and licence required |
| MOE Dock | ligand_docking | commercial | no | no | commercial/licensed — manual provisioning and licence required |
| ICM-Pro | ligand_docking | commercial | no | no | commercial/licensed — manual provisioning and licence required |
| PRosettaC | ternary_complex_modeling | repo | no | no | github.com/BCLCommons/PRosettaC + Rosetta licence |
| RosettaDock | protein_protein_docking | binary | no | no | source/apt binary — provide on PATH or install into a conda env |
| RosettaLigand | ligand_docking | binary | no | no | source/apt binary — provide on PATH or install into a conda env |
| Rosetta InterfaceAnalyzer | binding_energy | binary | no | no | source/apt binary — provide on PATH or install into a conda env |
| PyRosetta | protein_protein_docking | pip | no | no | pip-installable Python package |
| HADDOCK | protein_protein_docking | web | no | no | web-only service — https://wenmr.science.uu.nl/haddock2.4 |
| HADDOCK3 | protein_protein_docking | conda | no | no | conda-forge / bioconda package |
| ClusPro | protein_protein_docking | web | no | no | web-only service — https://cluspro.bu.edu |
| MEGADOCK | protein_protein_docking | conda | no | no | conda-forge / bioconda package |
| ZDOCK | protein_protein_docking | conda | no | no | conda-forge / bioconda package |
| PatchDock | protein_protein_docking | binary | no | no | source/apt binary — provide on PATH or install into a conda env |
| FireDock | protein_protein_docking | binary | no | no | source/apt binary — provide on PATH or install into a conda env |
| LightDock | protein_protein_docking | conda | yes | yes | conda-forge / bioconda package |
| EquiDock | protein_protein_docking | repo | no | no | github.com/octavian-ganea/equidock_public (+weights) |
| AlphaFold-Multimer | ternary_complex_modeling | repo | no | no | DeepMind AlphaFold params (~2.3 TB DB / weights on request) |
| ColabFold | ternary_complex_modeling | binary | no | no | source/apt binary — provide on PATH or install into a conda env |
| GROMACS | molecular_dynamics | conda | yes | yes | conda-forge / bioconda package |
| OpenMM | molecular_dynamics | pip | yes | yes | pip-installable Python package |
| AMBER / AmberTools | molecular_dynamics | binary | yes | yes | source/apt binary — provide on PATH or install into a conda env |
| NAMD | molecular_dynamics | conda | no | no | conda-forge / bioconda package |
| CHARMM | molecular_dynamics | commercial | no | no | commercial/licensed — manual provisioning and licence required |
| Desmond | molecular_dynamics | commercial | no | no | commercial/licensed — manual provisioning and licence required |
| PLUMED | molecular_dynamics | binary | no | no | source/apt binary — provide on PATH or install into a conda env |
| gmx_MMPBSA | binding_energy | binary | yes | yes | source/apt binary — provide on PATH or install into a conda env |
| MMPBSA.py | binding_energy | binary | yes | yes | source/apt binary — provide on PATH or install into a conda env |
| Meeko | ligand_preparation | pip | yes | yes | pip-installable Python package |
| MGLTools | ligand_preparation | binary | no | no | source/apt binary — provide on PATH or install into a conda env |
| PDBFixer | structure_preparation | pip | yes | yes | pip-installable Python package |
| PropKa | structure_preparation | conda | yes | yes | conda-forge / bioconda package |
| PDB2PQR | structure_preparation | conda | yes | yes | conda-forge / bioconda package |
| OpenBabel | ligand_preparation | pip | yes | yes | pip-installable Python package |
| RDKit ETKDG | conformer_generation | pip | yes | yes | pip-installable Python package |
| CREST | conformer_generation | conda | no | no | conda-forge / bioconda package |
| xTB | quantum_chemistry | conda | no | no | conda-forge / bioconda package |
| MOPAC | quantum_chemistry | conda | no | no | conda-forge / bioconda package |
| ORCA | quantum_chemistry | binary | no | no | source/apt binary — provide on PATH or install into a conda env |
| Gaussian | quantum_chemistry | commercial | no | no | commercial/licensed — manual provisioning and licence required |
| OpenEye OMEGA | conformer_generation | commercial | no | no | commercial/licensed — manual provisioning and licence required |
| Schrodinger LigPrep | ligand_preparation | commercial | no | no | commercial/licensed — manual provisioning and licence required |
| Epik | ligand_preparation | commercial | no | no | commercial/licensed — manual provisioning and licence required |
| LinkInvent | linker_generation | repo | no | no | MolecularAI REINVENT4 LinkInvent (no PyPI distribution) |
| REINVENT | de_novo_generation | repo | no | no | github.com/MolecularAI/REINVENT4 (no PyPI distribution) |
| DeLinker | linker_generation | repo | no | no | github.com/oxpig/DeLinker (+checkpoint; no PyPI distribution) |
| DiffLinker | linker_generation | repo | no | no | github.com/igashov/DiffLinker (+checkpoint) |
| SyntaLinker | linker_generation | repo | no | no | github.com/kyo-t/DeepLigBuilder (+checkpoint) |
| CReM | de_novo_generation | pip | yes | yes | pip-installable Python package |
| mmpdb | fragmentation | conda | yes | yes | conda-forge / bioconda package |
| BRICS | fragmentation | pip | yes | yes | pip-installable Python package |
| RECAP | fragmentation | pip | yes | yes | pip-installable Python package |
| MolDQN | de_novo_generation | repo | no | no | github.com/google-research/google-research/mol_dqn |
| GuacaMol | de_novo_generation | pip | yes | yes | pip-installable Python package |
| MOSES | de_novo_generation | pip | no | no | pip-installable Python package |
| AiZynthFinder | retrosynthesis | pip | yes | yes | pip-installable Python package |
| ASKCOS | retrosynthesis | web | no | no | web-only service — https://askcos.mit.edu |
| Molecular Transformer | retrosynthesis | pip | no | no | pip-installable Python package |
| RDKit + OpenNMT workflow | retrosynthesis | pip | no | no | pip-installable Python package |
| IBM RXN | reaction_prediction | api | no | no | remote API — credentials required, no local install |
| RXNMapper | reaction_prediction | pip | yes | yes | pip-installable Python package |
| RDChiral | reaction_prediction | pip | yes | yes | pip-installable Python package |
| RAscore | synthetic_accessibility | repo | no | no | github.com/reymond-group/RAscore (no PyPI distribution) |
| SCScore | synthetic_accessibility | repo | no | no | github.com/connorcoley/scscore (no PyPI distribution) |
| ASKCOS Tree Builder | retrosynthesis | web | no | no | web-only service |
| SwissADME | admet_toxicity | web | no | no | web-only service — http://www.swissadme.ch |
| ADMETlab 3.0 | admet_toxicity | web | no | no | web-only service — https://admetlab3.scbdd.com |
| pkCSM | admet_toxicity | web | no | no | web-only service — https://biosig.lab.uq.edu.au/pkcsm |
| ProTox-II | admet_toxicity | web | no | no | web-only service — https://tox-new.charite.de/protox_II |
| DeepPurpose | admet_toxicity | repo | no | no | PyPI 0.1.5 pins numpy<2 — install in an isolated env (github.com/kexinhuang12345 |
| Therapeutics Data Commons | admet_toxicity | pip | yes | yes | pip-installable Python package |
| OpenADMET | admet_toxicity | api | no | no | remote API — credentials required, no local install |
| DeepPROTACs | protac_degradation_prediction | repo | no | no | github.com/FengleiShen/DeepPROTACs (checkpoint required) |
| PROTAC-STAN | protac_degradation_prediction | repo | no | no | PROTAC-STAN repo + trained weights |
| DegradeMaster | protac_degradation_prediction | repo | no | no | DegradeMaster repo + trained weights |
| Chemprop | molecular_ml | pip | yes | yes | pip-installable Python package |
| DeepChem | molecular_ml | pip | yes | yes | pip-installable Python package |
| GROVER | molecular_ml | repo | no | no | github.com/tencent-ailab/grover (+pretrained weights) |
| ChemBERTa | molecular_ml | repo | no | no | DeepChem/chemberta weights (HuggingFace) |
| MolFormer | molecular_ml | repo | no | no | IBM MolFormer weights (HuggingFace) |
| Uni-Mol | molecular_ml | repo | no | no | github.com/dptech-corp/Uni-Mol (+weights) |
| ESM-2 | protein_language_models | pip | yes | yes | pip-installable Python package |
| ProtT5 | protein_language_models | repo | no | no | Rostlab/prot_t5_xl weights (seq2seq PLM) |
| PubTator | literature_mining | web | no | no | web-only service — https://www.ncbi.nlm.nih.gov/research/pubtator3/ |
| SciSpacy | literature_mining | pip | yes | yes | pip-installable Python package |
| ChemDataExtractor | literature_mining | repo | no | no | DAWG build fails on py3.11; install via conda/py3.9 (github.com/cambridgeltl/che |
| OPSIN | literature_mining | binary | no | no | source/apt binary — provide on PATH or install into a conda env |
| NameRxn | literature_mining | commercial | no | no | commercial/licensed — manual provisioning and licence required |
| SureChEMBL | patent_mining | web | no | no | web-only service — https://www.surechembl.org |
| Lens.org | patent_mining | web | no | no | web-only service — https://www.lens.org |
| Google Patents | patent_mining | web | no | no | web-only service — https://patents.google.com |
| AlphaLISA/TR-FRET assay planner | assay_planning | metadata | no | no | metadata/planning entry — nothing to install |
| Proteome Discoverer / MaxQuant | proteomics | commercial | no | no | commercial/licensed — manual provisioning and licence required |
| Perseus | proteomics | conda | no | no | conda-forge / bioconda package |
| FragPipe | proteomics | conda | no | no | conda-forge / bioconda package |
| CellProfiler | image_analysis | pip | no | no | pip-installable Python package |
| KNIME | workflow_platforms | conda | no | no | conda-forge / bioconda package |
| Pipeline Pilot | workflow_platforms | commercial | no | no | commercial/licensed — manual provisioning and licence required |
| Galaxy | workflow_platforms | conda | no | no | conda-forge / bioconda package |

## 4. LLM-callable agent tools

| tool | kind | readiness | evidence | deterministic | ml | retrieved |
|---|---|---|---|---|---|---|
| deep_research | research | ready | RETRIEVED | False | False | True |
| search_europe_pmc | research | ready | RETRIEVED | False | False | True |
| search_pubmed | research | ready | RETRIEVED | False | False | True |
| verify_crossref | research | ready | RETRIEVED | False | False | True |
| retrieve_fulltext | research | ready | RETRIEVED | False | False | True |
| search_web | research | ready | RETRIEVED | False | False | True |
| resolve_target | target | ready | RETRIEVED | False | False | True |
| search_uniprot | target | ready | RETRIEVED | False | False | True |
| retrieve_target_binders | target | ready | RETRIEVED | False | False | True |
| select_e3_ligase | target | ready | HEURISTIC | True | False | False |
| retrieve_e3_evidence | target | ready | RETRIEVED | True | False | False |
| inspect_smiles | chemistry | ready | CALCULATED | True | False | False |
| search_pubchem | chemistry | ready | RETRIEVED | False | False | True |
| search_chembl | chemistry | ready | RETRIEVED | False | False | True |
| search_bindingdb | chemistry | ready | RETRIEVED | True | False | False |
| detect_exit_vectors | chemistry | ready | CALCULATED | True | False | False |
| generate_linkers | chemistry | ready | CALCULATED | True | False | False |
| construct_protac | chemistry | ready | CALCULATED | True | False | False |
| check_synthetic_feasibility | chemistry | ready | HEURISTIC | True | False | False |
| diagnose_capability | chemistry | ready | CALCULATED | True | False | False |
| list_capability_readiness | chemistry | ready | CALCULATED | True | False | False |
| list_scientific_capabilities | decision | ready | CALCULATED | True | False | False |
| run_scientific_capability | decision | ready | CALCULATED | True | False | False |
| retrieve_pdb | structure | ready | RETRIEVED | False | False | True |
| model_ternary_complex | structure | ready | STRUCTURAL SURROGATE | True | False | False |
| score_lysine_ubiquitination | structure | ready | STRUCTURAL SURROGATE | True | False | False |
| predict_cooperativity | structure | ready | STRUCTURAL SURROGATE | True | False | False |
| simulate_hook_effect | structure | ready | CALCULATED | True | False | False |
| predict_degradation | prediction | ready | ML PREDICTION | False | True | False |
| predict_cell_context | prediction | ready | ML PREDICTION | False | True | False |
| predict_admet | prediction | ready | ML PREDICTION | True | False | False |
| run_protacpilot_structural | workflow | ready | STRUCTURAL SURROGATE | False | False | False |
| rank_candidates | decision | ready | CALCULATED | True | False | False |
| build_candidate_dossier | decision | ready | CALCULATED | True | False | False |

## 5. Datasets (versioned by content hash)

`sha256:full` for files < 50 MB; `sha256:partial` = first+last 1 MB + size; `sha256:tree` = relative path + size fingerprint for directories.

| asset | domain | exists | size | rows | hash (short) | kind | version label |
|---|---|---|---|---|---|---|---|
| protacxtend/data/curated_targets.csv | targets | True | 394B | 3 | ace6f0cfc77f | sha256:full | curated |
| protacxtend/data/curated_warheads.csv | warheads | True | 910B | 6 | c05a35d53174 | sha256:full | curated |
| protacxtend/data/curated_e3_ligands.csv | E3 ligands | True | 51.5KB | 221 | 387a0063d821 | sha256:full | curated |
| protacxtend/data/curated_linkers.csv | linkers | True | 1.3KB | 12 | ffef7b2b7eea | sha256:full | curated |
| protacxtend/data/known_protac_smiles.csv | PROTACs | True | 309B | 3 | a3edf55b9a1a | sha256:full | curated |
| protacxtend/data/curated_exit_vector_map.csv | warheads | True | 924B | 5 | f735d65cc185 | sha256:full | curated |
| protacxtend/data/protacdb_local.csv | PROTACs | True | 461B | 3 | 065f0665f42f | sha256:full | PROTAC-DB 3.0 |
| protacxtend/data/protacpedia_local.csv | PROTACs | True | 331B | 2 | c837b4da2aad | sha256:full | PROTACpedia |
| protacxtend/data/drugbank_local.csv | drugs | True | 109B | 0 | bcded3e595d7 | sha256:full | DrugBank |
| protacxtend/data/cell_context_atlas.csv | cell context | True | 263B | 3 | cd2462854c15 | sha256:full | curated |
| protacxtend/data/cooperativity_calibration.csv | cooperativity | True | 151B | 0 | b8bc577070f8 | sha256:full | curated |
| protacxtend/data/hook_effect_calibration.csv | hook effect | True | 137B | 0 | e77a03f3516c | sha256:full | curated |
| protacxtend/data/benchmark/PROTAC-DB_3.0_protacs.xlsx | PROTACs | True | 6.0MB | 15502 | 4e3a7ecc74a2 | sha256:full | PROTAC-DB 3.0 |
| protacxtend/data/benchmark/chemprop_train.csv | degradation ML | True | 234.3KB | 1698 | d4fcece7de58 | sha256:full | derived |
| protacxtend/data/benchmark/chemprop_benchmark.csv | degradation ML | True | 8.2KB | 64 | b218d329da25 | sha256:full | derived |
| protacxtend/data/benchmark/chemprop_train_multitarget.csv | degradation ML | True | 158.8KB | 1126 | be81618819e5 | sha256:full | derived |
| protacxtend/data/benchmark/chemprop_cal.csv | degradation ML | True | 27.5KB | 200 | 3b40d1194689 | sha256:full | derived |
| protacxtend/data/benchmark/expression_context.csv | cell context | True | 566B | 7 | d221b5150df9 | sha256:full | derived |
| protacxtend/data/benchmark/e3_expression_evidence.csv | E3 expression | True | 2.1KB | 24 | 74bae7045f28 | sha256:full | curated |
| protacxtend/data/benchmark/protacdb_evidence_schema.csv | schema | True | 1.6KB | 10 | c3c9c8464ee7 | sha256:full | derived |
| data/tack/tack_dc50.parquet | degradation ML | True | 603.8KB | 4184 | 2893ce64fe1d | sha256:full | TACK |
| data/tack/tack_bin.parquet | degradation ML | True | 779.5KB | 6561 | 93a0b170de22 | sha256:full | TACK |
| protacxtend/data/tack/tack_dc50_model.joblib | model artifacts | True | 700.8KB |  | 30bdfcca0368 | sha256:full | TACK |
| protacxtend/data/tack/tack_dmax_model.joblib | model artifacts | True | 593.7KB |  | 985446971be5 | sha256:full | TACK |
| protacxtend/data/tack/tack_bin_model.joblib | model artifacts | True | 688.7KB |  | 898e59a0c387 | sha256:full | TACK |
| protacxtend/data/linkers/linker_smiles.txt | linkers | True | 5.1KB |  | 8ee51d27d81a | sha256:full | derived |
| protacxtend/data/linkers/linker_generator.pt | model artifacts | True | 691.3KB |  | 155819963596 | sha256:full | derived |
| protacxtend/data/case_study/brd4_vhl_6.csv | case study | True | 1.6KB | 6 | 220cc3d743f3 | sha256:full | curated |
| protacxtend/data/toolkit/Agent_Toolkit.xlsx | capability registry | True | 86.5KB | 21 | 1f9ab30c0e55 | sha256:full | curated |
| data/benchmark/PROTAC-DB_3.0_protacs.xlsx | PROTACs | True | 6.0MB | 15502 | 4e3a7ecc74a2 | sha256:full | PROTAC-DB 3.0 |
| data/ternary_benchmark_six.json | ternary benchmark | True | 2.1KB |  | da899635ebdc | sha256:full | curated |
| data/warheads/hmgb2_warhead_library.csv | warheads | True | 1.9KB | 15 | ce3b372b9b03 | sha256:full | curated |
| data/checkpoints/protacpilot.sqlite | memory / runs | True | 21.1MB |  | 5d543cbba093 | sha256:full | runtime |
| data/synglue | model artifacts | True | 98.1MB (dir) | 5 files | d5654556990c | sha256:tree | SynGlue |
| data/retrosynthesis/models | model artifacts | True | 965.9MB (dir) | 5 files | bbbda7688640 | sha256:tree | retrosynthesis |
| data/protac_repos/repos | external code | True | 6.1GB (dir) | 19161 files | 90a44eb82ca7 | sha256:tree | GitHub |
| data/synthesis_prediction/repos | external code | True | 64.6MB (dir) | 834 files | b6b896d570db | sha256:tree | GitHub |
| PROTAC-DB 3.0 | PROTACs | n/a |  |  |  |  | http://cadd.zju.edu.cn/protacdb/ |
| PROTACpedia | PROTACs | n/a |  |  |  |  | https://protacpedia.com/ |
| MagnetDB/MGDB/MolGlueDB | molecular glue | n/a |  |  |  |  | local export |
| TPDdb | TPD | n/a |  |  |  |  | https://db.idrblab.net/ttd/ |
| PROTAC-8K | PROTACs | n/a |  |  |  |  | local |
| PROTAC-PatentDB | patents | n/a |  |  |  |  | local |
| protacxtend/data/active_learning | unclassified | True |  |  |  |  |  |
| protacxtend/data/benchmark | unclassified | True |  |  |  |  |  |
| protacxtend/data/case_study | unclassified | True |  |  |  |  |  |
| protacxtend/data/linkers | unclassified | True |  |  |  |  |  |
| protacxtend/data/tack | unclassified | True |  |  |  |  |  |
| protacxtend/data/toolkit | unclassified | True |  |  |  |  |  |
| data/benchmark | unclassified | True |  |  |  |  |  |
| data/checkpoints | unclassified | True |  |  |  |  |  |
| data/linkers | unclassified | True |  |  |  |  |  |
| data/protac_repos | unclassified | True |  |  |  |  |  |
| data/research | unclassified | True |  |  |  |  |  |
| data/retrosynthesis | unclassified | True |  |  |  |  |  |
| data/synthesis_prediction | unclassified | True |  |  |  |  |  |
| data/tack | unclassified | True |  |  |  |  |  |
| data/toolkit | unclassified | True |  |  |  |  |  |
| data/warheads | unclassified | True |  |  |  |  |  |

## 6. Capability readiness

| capability | installed | installable | web | readiness | best candidate | version |
|---|---|---|---|---|---|---|
| admet_toxicity | 1 | 1 | 5 | ready | Therapeutics Data Commons | py:tdc installed |
| binding_energy | 2 | 0 | 0 | ready | gmx_MMPBSA | bin:gmx_MMPBSA |
| cheminformatics | 3 | 0 | 0 | ready | RDKit ETKDG | py:rdkit 2026.03.4 |
| conformer_generation | 1 | 1 | 0 | ready | RDKit ETKDG | py:rdkit 2026.03.4 |
| de_novo_generation | 2 | 3 | 0 | ready | CReM | py:crem 0.3.1 |
| degradation_prediction | 1 | 3 | 0 | ready | Chemprop | py:chemprop 2.3.1 |
| fragmentation | 3 | 0 | 0 | ready | BRICS | py:rdkit 2026.03.4 |
| image_analysis | 0 | 1 | 0 | installable | CellProfiler |  |
| ligand_docking | 3 | 5 | 0 | ready | AutoDock Vina | bin:vina AutoDock Vina v1.2.3 |
| ligand_preparation | 2 | 0 | 0 | ready | Meeko | py:meeko 0.7.1 |
| linker_generation | 1 | 5 | 0 | ready | CReM | py:crem 0.3.1 |
| literature_mining | 1 | 1 | 2 | ready | SciSpacy | py:scispacy 0.6.2 |
| molecular_dynamics | 3 | 1 | 0 | ready | OpenMM | py:openmm 8.6.1 |
| molecular_ml | 2 | 4 | 0 | ready | Chemprop | py:chemprop 2.3.1 |
| molecular_visualization | 2 | 0 | 1 | ready | NGLView | py:nglview 4.0.1 |
| patent_mining | 0 | 0 | 3 | web_only | SureChEMBL |  |
| protein_language_models | 1 | 1 | 0 | ready | ESM-2 | py:esm 2.0.0 |
| protein_protein_docking | 1 | 5 | 3 | ready | LightDock | bin:lightdock3.py |
| proteomics | 0 | 1 | 0 | installable | FragPipe |  |
| quantum_chemistry | 0 | 4 | 0 | installable | xTB |  |
| reaction_prediction | 2 | 0 | 1 | ready | RXNMapper | py:rxnmapper 0.4.3 |
| retrosynthesis | 1 | 2 | 2 | ready | AiZynthFinder | py:aizynthfinder 4.4.1 |
| smiles_validation | 2 | 0 | 0 | ready | RDKit ETKDG | py:rdkit 2026.03.4 |
| structure_preparation | 4 | 0 | 0 | ready | PDBFixer | py:pdbfixer 1.12.0 |
| synthetic_accessibility | 0 | 2 | 0 | installable | RAscore |  |
| ternary_complex_modeling | 0 | 3 | 2 | installable | PRosettaC |  |
| workflow_platforms | 0 | 0 | 1 | web_only | KNIME |  |

## 6b. Scientific backends (capability-first)

Free/local execution path per capability; restricted engines return LICENSE_REQUIRED. 20/27 capabilities ready.

| backend | licence | available | priority | best for |
|---|---|---|---|---|
| rdkit | open_source_permissive | True | 95 | admet, chemistry, conformer_generation |
| openbabel | open_source_copyleft | True | 40 |  |
| autodock_vina | open_source_permissive | True | 80 |  |
| consensus_docking | open_source_permissive | True | 99 | ligand_docking |
| gnina | open_source_permissive | True | 70 |  |
| diffdock | open_source_permissive | True | 85 |  |
| geometric_placement | open_source_permissive | True | 20 |  |
| lightdock | open_source_permissive | True | 90 | ppi_docking |
| geometric_orientation_search | open_source_permissive | True | 25 |  |
| geometry_fingerprint | open_source_permissive | True | 80 | interaction_fingerprint |
| rdkit_linker | open_source_permissive | True | 80 | linker_analysis |
| openmm | open_source_permissive | True | 95 | molecular_dynamics |
| mdanalysis | open_source_permissive | True | 80 | md_analysis |
| openmm_interaction | open_source_permissive | True | 90 | interaction_energy |
| binding_energy_hierarchy | open_source_permissive | True | 90 | binding_energy |
| pareto_nsga2 | open_source_permissive | True | 80 | candidate_ranking |
| pdbfixer_openmm | open_source_permissive | True | 90 | protein_preparation |
| pocket_geometry | open_source_permissive | True | 70 | pocket_detection |
| structure_retrieval | open_source_permissive | True | 60 | protein_structure |
| local_ternary_pipeline | open_source_permissive | True | 60 | ternary_docking |
| local_protac_scoring | open_source_permissive | True | 60 | protac_scoring |
| local_glue_ppi_delta | open_source_permissive | True | 60 | metabolite_ppi_scoring, molecular_glue_scoring |
| schrodinger_glide | commercial | False | 5 |  |
| schrodinger_prime | commercial | False | 5 |  |
| schrodinger_desmond | commercial | False | 5 |  |
| schrodinger_ligprep | commercial | False | 5 |  |
| gold_ccdc | commercial | False | 5 |  |
| moe | commercial | False | 5 |  |
| icm_pro | commercial | False | 5 |  |
| openeye_omega | commercial | False | 5 |  |
| gaussian | commercial | False | 5 |  |
| charmm | commercial | False | 5 |  |
| namerxn | commercial | False | 5 |  |
| pipeline_pilot | commercial | False | 5 |  |
| amber_commercial | commercial | False | 5 |  |
| rosetta | academic_only | False | 5 |  |
| cluspro | web_service | False | 1 |  |
| swissadme | web_service | False | 1 |  |
| admetlab3 | web_service | False | 1 |  |
| pkcsm | web_service | False | 1 |  |
| protox_ii | web_service | False | 1 |  |
| haddock_web | web_service | False | 1 |  |
| patchdock_web | web_service | False | 1 |  |
| ibm_rxn | web_service | False | 1 |  |
| openadmet_web | web_service | False | 1 |  |
| haddock_cns | academic_only | False | 2 |  |

## 7. Dependencies

The workbook `Dependencies` sheet contains **678** rows across groups: `runtime_requirements`, `pyproject_dependencies`, `optional:*`, `toolkit_installed`, and `environment_all` (every installed distribution).

| group | package | installed | declared |
|---|---|---|---|
| runtime_requirements | rdkit | 2026.3.4 | rdkit==2026.3.4 |
| runtime_requirements | numpy | 2.4.6 | numpy==2.4.6 |
| runtime_requirements | pandas | 2.3.3 | pandas==2.3.3 |
| runtime_requirements | scipy | 1.18.0 | scipy==1.17.1 |
| runtime_requirements | scikit-learn | 1.6.1 | scikit-learn==1.9.0 |
| runtime_requirements | torch | 2.10.0 | torch==2.6.0 |
| runtime_requirements | chemprop | 2.3.1 | chemprop==2.3.0 |
| runtime_requirements | joblib | 1.5.3 | joblib>=1.3 |
| runtime_requirements | openpyxl | 3.1.5 | openpyxl>=3.1 |
| runtime_requirements | langgraph | 1.2.2 | langgraph>=1.2 |
| runtime_requirements | langchain | 0.0.275 | langchain>=0.2 |
| runtime_requirements | langgraph-checkpoint-postgres |  | langgraph-checkpoint-postgres>=3.0 |
| runtime_requirements | fastapi | 0.136.3 | fastapi>=0.110 |
| runtime_requirements | uvicorn | 0.48.0 | uvicorn>=0.27 |
| runtime_requirements | streamlit | 1.57.0 | streamlit>=1.35 |
| runtime_requirements | pydantic | 2.11.7 | pydantic>=2.6 |
| runtime_requirements | ollama | 0.6.2 | ollama>=0.6 |
| runtime_requirements | openai | 0.27.8 | openai>=1.0 |
| runtime_requirements | anthropic |  | anthropic>=0.40 |
| runtime_requirements | google-generativeai |  | google-generativeai>=0.8 |
| runtime_requirements | psycopg |  | psycopg>=3.2 |
| runtime_requirements | psycopg-binary |  | psycopg-binary>=3.2 |
| runtime_requirements | redis |  | redis>=5.0 |
| runtime_requirements | requests | 2.32.3 | requests>=2.31 |
| runtime_requirements | beautifulsoup4 | 4.9.0 | beautifulsoup4>=4.12 |
| runtime_requirements | python-multipart | 0.0.29 | python-multipart>=0.0.9 |
| pyproject_dependencies | pandas | 2.3.3 | pandas>=2.0 |
| pyproject_dependencies | pydantic | 2.11.7 | pydantic>=2.6 |
| pyproject_dependencies | requests | 2.32.3 | requests>=2.31 |
| pyproject_dependencies | joblib | 1.5.3 | joblib>=1.3 |
| pyproject_dependencies | scikit-learn | 1.6.1 | scikit-learn>=1.2 |
| pyproject_dependencies | openpyxl | 3.1.5 | openpyxl>=3.1 |

## 8. How to regenerate

```bash
protacxtend toolkit --action truth          # XLSX + MD (this file)
protacxtend toolkit --action plan           # provisioning plan
protacxtend toolkit --action provision --mode install --categories molecular_ml
protacxtend toolkit --action verify         # functional smoke tests
python analysis/generate_inventory.py       # inventory + plots
```
