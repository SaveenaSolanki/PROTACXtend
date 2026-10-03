# PROTACXtend Toolkit — Source of Truth

_Generated 2026-09-30T18:17:03.359727+00:00_

This document and the sibling workbook `analysis/inventory/PROTACXtend_Toolkit_Truth.xlsx` are the single source of truth for **what the toolkit contains and at exactly which version**.

## 1. Headline counts

| metric | value |
|---|---|
| toolkit_tools | 115 |
| tools_installed | 44 |
| tools_callable | 44 |
| tools_installable | 47 |
| tools_commercial | 13 |
| tools_web_only | 13 |
| tools_repo_required | 21 |
| agent_tools | 44 |
| agent_tools_ready | 44 |
| datasets | 73 |
| datasets_present | 67 |
| capabilities | 27 |
| capabilities_ready | 23 |

## 2. Installed & callable tools (with exact version)

| tool | category | version | provider env | method |
|---|---|---|---|---|
| PyMOL | molecular_visualization | File "<string>", line 1, in <module> | protac-mega-protac:/home/saveenas/miniconda3/envs/pp/envs/protac-mega-protac/bin/pymol | binary |
| NGLView | molecular_visualization | 4.0.1 | protacpilot | pip |
| AutoDock Vina | ligand_docking | AutoDock Vina v1.2.3 | PATH:/usr/bin/vina | conda |
| AutoDock4 | ligand_docking | AutoDock 4.2.6 | PATH:/usr/bin/autodock4 | binary |
| Smina | ligand_docking | bin:smina | docking:/home/saveenas/.protacxtend/envs/docking/bin/smina | conda |
| GNINA | ligand_docking | bin:gnina | docking:/home/saveenas/.protacxtend/envs/docking/bin/gnina | conda |
| rDock | ligand_docking | bin:rbdock | docking:/home/saveenas/.protacxtend/envs/docking/bin/rbdock | conda |
| HADDOCK3 | protein_protein_docking | bin:haddock3 | toolkit:/home/saveenas/.protacxtend/envs/toolkit/bin/haddock3 | conda |
| LightDock | protein_protein_docking | bin:lightdock3.py | ppi:/home/saveenas/.protacxtend/envs/ppi/bin/lightdock3.py | conda |
| ColabFold | ternary_complex_modeling | bin:colabfold_batch | toolkit:/home/saveenas/.protacxtend/envs/toolkit/bin/colabfold_batch | binary |
| GROMACS | molecular_dynamics | bin:gmx | gromacs:/home/saveenas/.protacxtend/envs/gromacs/bin/gmx | conda |
| OpenMM | molecular_dynamics | 8.6.1 | protacpilot | pip |
| AMBER / AmberTools | molecular_dynamics | bin:sander | gromacs:/home/saveenas/.protacxtend/envs/gromacs/bin/sander | binary |
| PLUMED | molecular_dynamics | bin:plumed | qc:/home/saveenas/.protacxtend/envs/qc/bin/plumed | binary |
| gmx_MMPBSA | binding_energy | bin:gmx_MMPBSA | gromacs:/home/saveenas/.protacxtend/envs/gromacs/bin/gmx_MMPBSA | binary |
| MMPBSA.py | binding_energy | bin:MMPBSA.py | gromacs:/home/saveenas/.protacxtend/envs/gromacs/bin/MMPBSA.py | binary |
| Meeko | ligand_preparation | 0.7.1 | current | pip |
| PDBFixer | structure_preparation | 1.12.0 | protacpilot | pip |
| PropKa | structure_preparation | propka3 3.5.1 | protacpilot:/home/saveenas/miniconda3/envs/protacpilot/bin/propka3 | conda |
| PDB2PQR | structure_preparation | pdb2pqr 3.7.1 | protacpilot:/home/saveenas/miniconda3/envs/protacpilot/bin/pdb2pqr | conda |
| OpenBabel | ligand_preparation | 3.1.0 | PATH:/usr/local/bin/babel | pip |
| RDKit ETKDG | conformer_generation | 2026.03.4 | current | pip |
| CREST | conformer_generation | bin:crest | qc:/home/saveenas/.protacxtend/envs/qc/bin/crest | conda |
| xTB | quantum_chemistry | bin:xtb | qc:/home/saveenas/.protacxtend/envs/qc/bin/xtb | conda |
| MOPAC | quantum_chemistry | bin:mopac | qc:/home/saveenas/.protacxtend/envs/qc/bin/mopac | conda |
| CReM | de_novo_generation | 0.3.1 | protacpilot | pip |
| mmpdb | fragmentation | mmpdb, version 3.1.4 | protacpilot:/home/saveenas/miniconda3/envs/protacpilot/bin/mmpdb | conda |
| BRICS | fragmentation | 2026.03.4 | current | pip |
| RECAP | fragmentation | 2026.03.4 | current | pip |
| GuacaMol | de_novo_generation | 0.5.5 | protacpilot | pip |
| MOSES | de_novo_generation | py:moses 0.10.0 | toolkit | pip |
| AiZynthFinder | retrosynthesis | 4.4.1 | protacpilot | pip |
| Molecular Transformer | retrosynthesis | py:onmt installed | toolkit | pip |
| RDKit + OpenNMT workflow | retrosynthesis | py:rdkit 2026.3.4 | toolkit | pip |
| RXNMapper | reaction_prediction | 0.4.3 | protacpilot | pip |
| RDChiral | reaction_prediction | 1.1.0 | protacpilot | pip |
| DeepPurpose | admet_toxicity | py:DeepPurpose 0.1.5 | toolkit | repo |
| Therapeutics Data Commons | admet_toxicity | installed | protacpilot | pip |
| Chemprop | molecular_ml | 2.3.1 | current | pip |
| DeepChem | molecular_ml | 2.8.0 | protacpilot | pip |
| ESM-2 | protein_language_models | 2.0.0 | current | pip |
| SciSpacy | literature_mining | 0.6.2 | toolkit-venv | pip |
| Perseus | proteomics | bin:Perseus | md:/home/saveenas/.protacxtend/envs/md/bin/perseus | conda |
| FragPipe | proteomics | bin:fragpipe | md:/home/saveenas/.protacxtend/envs/md/bin/fragpipe | conda |

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
| Smina | ligand_docking | conda | yes | yes | conda-forge / bioconda package |
| GNINA | ligand_docking | conda | yes | yes | conda-forge / bioconda package |
| rDock | ligand_docking | conda | yes | yes | conda-forge / bioconda package |
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
| HADDOCK3 | protein_protein_docking | conda | yes | yes | conda-forge / bioconda package |
| ClusPro | protein_protein_docking | web | no | no | web-only service — https://cluspro.bu.edu |
| MEGADOCK | protein_protein_docking | conda | no | no | conda-forge / bioconda package |
| ZDOCK | protein_protein_docking | conda | no | no | conda-forge / bioconda package |
| PatchDock | protein_protein_docking | binary | no | no | source/apt binary — provide on PATH or install into a conda env |
| FireDock | protein_protein_docking | binary | no | no | source/apt binary — provide on PATH or install into a conda env |
| LightDock | protein_protein_docking | conda | yes | yes | conda-forge / bioconda package |
| EquiDock | protein_protein_docking | repo | no | no | github.com/octavian-ganea/equidock_public (+weights) |
| AlphaFold-Multimer | ternary_complex_modeling | repo | no | no | DeepMind AlphaFold params (~2.3 TB DB / weights on request) |
| ColabFold | ternary_complex_modeling | binary | yes | yes | source/apt binary — provide on PATH or install into a conda env |
| GROMACS | molecular_dynamics | conda | yes | yes | conda-forge / bioconda package |
| OpenMM | molecular_dynamics | pip | yes | yes | pip-installable Python package |
| AMBER / AmberTools | molecular_dynamics | binary | yes | yes | source/apt binary — provide on PATH or install into a conda env |
| NAMD | molecular_dynamics | conda | no | no | conda-forge / bioconda package |
| CHARMM | molecular_dynamics | commercial | no | no | commercial/licensed — manual provisioning and licence required |
| Desmond | molecular_dynamics | commercial | no | no | commercial/licensed — manual provisioning and licence required |
| PLUMED | molecular_dynamics | binary | yes | yes | source/apt binary — provide on PATH or install into a conda env |
| gmx_MMPBSA | binding_energy | binary | yes | yes | source/apt binary — provide on PATH or install into a conda env |
| MMPBSA.py | binding_energy | binary | yes | yes | source/apt binary — provide on PATH or install into a conda env |
| Meeko | ligand_preparation | pip | yes | yes | pip-installable Python package |
| MGLTools | ligand_preparation | binary | no | no | source/apt binary — provide on PATH or install into a conda env |
| PDBFixer | structure_preparation | pip | yes | yes | pip-installable Python package |
| PropKa | structure_preparation | conda | yes | yes | conda-forge / bioconda package |
| PDB2PQR | structure_preparation | conda | yes | yes | conda-forge / bioconda package |
| OpenBabel | ligand_preparation | pip | yes | yes | pip-installable Python package |
| RDKit ETKDG | conformer_generation | pip | yes | yes | pip-installable Python package |
| CREST | conformer_generation | conda | yes | yes | conda-forge / bioconda package |
| xTB | quantum_chemistry | conda | yes | yes | conda-forge / bioconda package |
| MOPAC | quantum_chemistry | conda | yes | yes | conda-forge / bioconda package |
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
| MOSES | de_novo_generation | pip | yes | yes | pip-installable Python package |
| AiZynthFinder | retrosynthesis | pip | yes | yes | pip-installable Python package |
| ASKCOS | retrosynthesis | web | no | no | web-only service — https://askcos.mit.edu |
| Molecular Transformer | retrosynthesis | pip | yes | yes | pip-installable Python package |
| RDKit + OpenNMT workflow | retrosynthesis | pip | yes | yes | pip-installable Python package |
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
| DeepPurpose | admet_toxicity | repo | yes | yes | PyPI 0.1.5 pins numpy<2 — install in an isolated env (github.com/kexinhuang12345 |
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
| Perseus | proteomics | conda | yes | yes | conda-forge / bioconda package |
| FragPipe | proteomics | conda | yes | yes | conda-forge / bioconda package |
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
| predict_protac_activity | prediction | ready | ML PREDICTION | False | True | False |
| predict_deepprotacs | prediction | ready | ML PREDICTION | False | True | False |
| predict_protac_stan | prediction | ready | ML PREDICTION | False | True | False |
| split_protac_bellerophon | chemistry | ready | CALCULATED | True | False | False |
| sample_ternary_ternify | structure | ready | STRUCTURAL SURROGATE | True | False | False |
| predict_se3_protacs | prediction | ready | ML PREDICTION | False | True | False |
| run_degradomap_experiment | decision | ready | CALCULATED | True | False | False |
| assign_e3_mechanism | target | ready | CALCULATED | True | False | False |
| inspect_repo_assets | decision | ready | CALCULATED | True | False | False |
| list_repo_tools | decision | ready | CALCULATED | True | False | False |
| run_protacpilot_structural | workflow | ready | STRUCTURAL SURROGATE | False | False | False |
| rank_candidates | decision | ready | CALCULATED | True | False | False |
| build_candidate_dossier | decision | ready | CALCULATED | True | False | False |

## 5. Datasets (versioned by content hash)

`sha256:full` for files < 50 MB; `sha256:partial` = first+last 1 MB + size; `sha256:tree` = relative path + size fingerprint for directories.

| asset | domain | exists | size | rows | hash (short) | kind | version label |
|---|---|---|---|---|---|---|---|
| protacxtend/data/curated_targets.csv | targets | True | 791B | 8 |  |  | curated |
| protacxtend/data/curated_warheads.csv | warheads | True | 910B | 6 |  |  | curated |
| protacxtend/data/curated_e3_ligands.csv | E3 ligands | True | 21.8KB | 95 |  |  | curated |
| protacxtend/data/curated_linkers.csv | linkers | True | 1.3KB | 12 |  |  | curated |
| protacxtend/data/known_protac_smiles.csv | PROTACs | True | 309B | 3 |  |  | curated |
| protacxtend/data/curated_exit_vector_map.csv | warheads | True | 924B | 5 |  |  | curated |
| protacxtend/data/protacdb_local.csv | PROTACs | True | 461B | 3 |  |  | PROTAC-DB 3.0 |
| protacxtend/data/protacpedia_local.csv | PROTACs | True | 331B | 2 |  |  | PROTACpedia |
| protacxtend/data/drugbank_local.csv | drugs | True | 109B | 0 |  |  | DrugBank |
| protacxtend/data/cell_context_atlas.csv | cell context | True | 263B | 3 |  |  | curated |
| protacxtend/data/cooperativity_calibration.csv | cooperativity | True | 151B | 0 |  |  | curated |
| protacxtend/data/hook_effect_calibration.csv | hook effect | True | 137B | 0 |  |  | curated |
| protacxtend/data/benchmark/PROTAC-DB_3.0_protacs.xlsx | PROTACs | True | 6.0MB | 15502 |  |  | PROTAC-DB 3.0 |
| protacxtend/data/benchmark/chemprop_train.csv | degradation ML | True | 234.3KB | 1698 |  |  | derived |
| protacxtend/data/benchmark/chemprop_benchmark.csv | degradation ML | True | 8.2KB | 64 |  |  | derived |
| protacxtend/data/benchmark/chemprop_train_multitarget.csv | degradation ML | True | 158.8KB | 1126 |  |  | derived |
| protacxtend/data/benchmark/chemprop_cal.csv | degradation ML | True | 27.5KB | 200 |  |  | derived |
| protacxtend/data/benchmark/expression_context.csv | cell context | True | 566B | 7 |  |  | derived |
| protacxtend/data/benchmark/e3_expression_evidence.csv | E3 expression | True | 2.1KB | 24 |  |  | curated |
| protacxtend/data/benchmark/protacdb_evidence_schema.csv | schema | True | 1.6KB | 10 |  |  | derived |
| data/tack/tack_dc50.parquet | degradation ML | True | 603.8KB | 4184 |  |  | TACK |
| data/tack/tack_bin.parquet | degradation ML | True | 779.5KB | 6561 |  |  | TACK |
| protacxtend/data/tack/tack_dc50_model.joblib | model artifacts | True | 700.8KB |  |  |  | TACK |
| protacxtend/data/tack/tack_dmax_model.joblib | model artifacts | True | 593.7KB |  |  |  | TACK |
| protacxtend/data/tack/tack_bin_model.joblib | model artifacts | True | 688.7KB |  |  |  | TACK |
| protacxtend/data/linkers/linker_smiles.txt | linkers | True | 5.1KB |  |  |  | derived |
| protacxtend/data/linkers/linker_generator.pt | model artifacts | True | 691.3KB |  |  |  | derived |
| protacxtend/data/case_study/brd4_vhl_6.csv | case study | True | 1.6KB | 6 |  |  | curated |
| protacxtend/data/toolkit/Agent_Toolkit.xlsx | capability registry | True | 86.5KB | 21 |  |  | curated |
| data/benchmark/PROTAC-DB_3.0_protacs.xlsx | PROTACs | True | 6.0MB | 15502 |  |  | PROTAC-DB 3.0 |
| data/ternary_benchmark_six.json | ternary benchmark | True | 2.1KB |  |  |  | curated |
| data/warheads/hmgb2_warhead_library.csv | warheads | True | 1.9KB | 15 |  |  | curated |
| data/checkpoints/protacpilot.sqlite | memory / runs | True | 21.1MB |  |  |  | runtime |
| data/synglue | model artifacts | True | 98.1MB (dir) | 5 files | d5654556990c | sha256:tree | SynGlue |
| data/retrosynthesis/models | model artifacts | True | 965.9MB (dir) | 5 files | bbbda7688640 | sha256:tree | retrosynthesis |
| data/protac_repos/repos | external code | True | 6.3GB (dir) | 19202 files | a4244cee3e32 | sha256:tree | GitHub |
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
| protacxtend/data/parser_validation_set.json | unclassified | True | 12.1KB |  |  |  |  |
| protacxtend/data/planning_notes.json | unclassified | True | 1.3KB |  |  |  |  |
| protacxtend/data/tack | unclassified | True |  |  |  |  |  |
| protacxtend/data/therapeutics | unclassified | True |  |  |  |  |  |
| protacxtend/data/toolkit | unclassified | True |  |  |  |  |  |
| protacxtend/data/verified_components.json | unclassified | True | 12.2KB |  |  |  |  |
| data/benchmark | unclassified | True |  |  |  |  |  |
| data/checkpoints | unclassified | True |  |  |  |  |  |
| data/definite_ligase_list_medvar2016.csv | unclassified | True | 98.6KB | 377 |  |  |  |
| data/e3_catalog_sources.json | unclassified | True | 1.4KB |  |  |  |  |
| data/e3_catalog_v2.csv | unclassified | True | 146.4KB | 800 |  |  |  |
| data/e3_catalog_v2_enriched.csv | unclassified | True | 152.4KB | 800 |  |  |  |
| data/e3_cell_context_stats.csv | unclassified | True | 226.2KB | 601 |  |  |  |
| data/e3_ligome_202508_systems.csv | unclassified | True | 389.3KB | 728 |  |  |  |
| data/evidence_snapshots | unclassified | True |  |  |  |  |  |
| data/linkers | unclassified | True |  |  |  |  |  |
| data/live_cache | unclassified | True |  |  |  |  |  |
| data/protac_repos | unclassified | True |  |  |  |  |  |
| data/request_cache | unclassified | True |  |  |  |  |  |
| data/research | unclassified | True |  |  |  |  |  |
| data/retrosynthesis | unclassified | True |  |  |  |  |  |
| data/synthesis_prediction | unclassified | True |  |  |  |  |  |
| data/tack | unclassified | True |  |  |  |  |  |
| data/toolkit | unclassified | True |  |  |  |  |  |
| data/uniprot | unclassified | True |  |  |  |  |  |
| data/warheads | unclassified | True |  |  |  |  |  |

## 6. Capability readiness

| capability | installed | installable | web | readiness | best candidate | version |
|---|---|---|---|---|---|---|
| admet_toxicity | 2 | 0 | 5 | ready | DeepPurpose | py:DeepPurpose 0.1.5 |
| binding_energy | 2 | 0 | 0 | ready | gmx_MMPBSA | bin:gmx_MMPBSA |
| cheminformatics | 3 | 0 | 0 | ready | RDKit ETKDG | py:rdkit 2026.03.4 |
| conformer_generation | 2 | 0 | 0 | ready | RDKit ETKDG | py:rdkit 2026.03.4 |
| de_novo_generation | 3 | 2 | 0 | ready | CReM | py:crem 0.3.1 |
| degradation_prediction | 1 | 3 | 0 | ready | Chemprop | py:chemprop 2.3.1 |
| fragmentation | 3 | 0 | 0 | ready | BRICS | py:rdkit 2026.3.4 |
| image_analysis | 0 | 1 | 0 | installable | CellProfiler |  |
| ligand_docking | 5 | 3 | 0 | ready | AutoDock Vina | bin:vina AutoDock Vina v1.2.3 |
| ligand_preparation | 2 | 0 | 0 | ready | Meeko | py:meeko 0.7.1 |
| linker_generation | 1 | 5 | 0 | ready | CReM | py:crem 0.3.1 |
| literature_mining | 1 | 1 | 2 | ready | SciSpacy | py:scispacy 0.6.2 |
| molecular_dynamics | 4 | 1 | 0 | ready | OpenMM | py:openmm 8.6.1 |
| molecular_ml | 2 | 4 | 0 | ready | Chemprop | py:chemprop 2.3.1 |
| molecular_visualization | 2 | 0 | 1 | ready | NGLView | py:nglview 4.0.1 |
| patent_mining | 0 | 0 | 3 | web_only | SureChEMBL |  |
| protein_language_models | 1 | 1 | 0 | ready | ESM-2 | py:esm installed |
| protein_protein_docking | 2 | 4 | 3 | ready | HADDOCK3 | bin:haddock3 |
| proteomics | 2 | 0 | 0 | ready | FragPipe | bin:fragpipe |
| quantum_chemistry | 3 | 1 | 0 | ready | xTB | bin:xtb |
| reaction_prediction | 2 | 0 | 1 | ready | RXNMapper | py:rxnmapper 0.4.3 |
| retrosynthesis | 3 | 0 | 2 | ready | AiZynthFinder | py:aizynthfinder 4.4.1 |
| smiles_validation | 2 | 0 | 0 | ready | RDKit ETKDG | py:rdkit 2026.03.4 |
| structure_preparation | 4 | 0 | 0 | ready | PDBFixer | py:pdbfixer 1.12.0 |
| synthetic_accessibility | 0 | 2 | 0 | installable | RAscore |  |
| ternary_complex_modeling | 2 | 2 | 2 | ready | HADDOCK3 | bin:haddock3 |
| workflow_platforms | 0 | 0 | 1 | web_only | KNIME |  |

## 6b. Scientific backends (capability-first)

Free/local execution path per capability; restricted engines return LICENSE_REQUIRED. 23/27 capabilities ready.

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

The workbook `Dependencies` sheet contains **703** rows across groups: `runtime_requirements`, `pyproject_dependencies`, `optional:*`, `toolkit_installed`, and `environment_all` (every installed distribution).

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
