# Phase 2 Manual Review List

The repositories below should not be installed yet without human review of licenses, dependency files, README instructions, resource needs, and any scripts that could launch training, docking, notebooks, or GPU workloads.

## DeepPROTACs

- GitHub: https://github.com/Fenglei104/DeepPROTACs
- Local path: `data/protac_repos/repos/DeepPROTACs`
- Detected files: README.md, LICENSE
- Priority: Medium
- Reason: README install hints: 3. Prepare the environment. Here we export our anaconda environment as the file "env.yaml". You can use the command: | conda env create -f env.yaml | conda activate DeepPROTACs | to get the same environment. Also, we use an RTX3090 to accelerate our | Besides, we highly recommond to install openbabel (2.3.2) (https://openbabel.org/wiki/Main_Page) and preprocess the mol2 files. | apt install openbabel; no standard dependency files detected; dataset/notebook or benchmark-style repository likely

## PROTAC-Model

- GitHub: https://github.com/gaoqiweng/PROTAC-Model
- Local path: `data/protac_repos/repos/PROTAC-Model`
- Detected files: none
- Priority: Manual
- Reason: README.md not detected; no standard dependency files detected

## PROTACFold

- GitHub: https://github.com/NilsDunlop/PROTACFold
- Local path: `data/protac_repos/repos/PROTACFold`
- Detected files: requirements.txt, README.md, LICENSE
- Priority: Manual
- Reason: README install hints: - [Installation](#installation) | - [AlphaFold 3 Setup (Docker Recommended)](#alphafold-3-setup-docker-recommended) | - [Manual Installation](#manual-installation) | ## Installation | - Docker (recommended for AlphaFold 3 setup) | ### AlphaFold 3 Setup (Docker Recommended); heavy docking/GPU/training/ternary-complex keywords detected

## PROTACable

- GitHub: https://github.com/giaguaro/PROTACable
- Local path: `data/protac_repos/repos/PROTACable`
- Detected files: README.md, LICENSE
- Priority: Medium
- Reason: README install hints: - [Requirements](#requirements) | - [Installation](#installation) | The concept of an end-to-end in silico pipeline is quite enticing. You may only find it in biotech specialized for this type of task. Now we offer this to the public as an accessible package. Yes, you can now design and validate in silico your PROTACs with limited knowledge of PROTACs. And you can do it affordably and at a high quality similar to high-end companies. This is the culmination of 3 years of dedicated work. | #### ***We kindly ask you that if you find this pipeline useful to cite us appropriately.*** | Architecture of the PROTACable pipeline. | ## Requirements; no standard dependency files detected

## Protac-invent

- GitHub: https://github.com/jidushanbojue/Protac-invent
- Local path: `data/protac_repos/repos/Protac-invent`
- Detected files: Dockerfile, README.md, LICENSE
- Priority: Manual
- Reason: README install hints: Installation | 1. Install [Conda](https://conda.io/projects/conda/en/latest/index.html) | 3. Open a shell, and go to the repository and create the Conda environment: | $ conda env create -f reinvent.yml | 4. Activate the environment: | $ conda activate reinvent.v3.2; Dockerfile detected; review Docker context before building; heavy docking/GPU/training/ternary-complex keywords detected

## PROTAC_ternary

- GitHub: https://github.com/karanicolaslab/PROTAC_ternary
- Local path: `data/protac_repos/repos/PROTAC_ternary`
- Detected files: README.md, LICENSE
- Priority: Manual
- Reason: README install hints: The `-extra_res_fa ligand1.params ligand2_params` will be the same as the initial docking submission at the beginning of the pipeline; heavy docking/GPU/training/ternary-complex keywords detected; no standard dependency files detected

## ProTACT

- GitHub: https://github.com/doheejin/ProTACT
- Local path: `data/protac_repos/repos/ProTACT`
- Detected files: README.md, LICENSE
- Priority: Medium
- Reason: README install hints: ## Package Requirements | Install below packages in your virtual environment before running the code.; no standard dependency files detected

## PROTAC-STAN

- GitHub: https://github.com/PROTACs/PROTAC-STAN
- Local path: `data/protac_repos/repos/PROTAC-STAN`
- Detected files: README.md, LICENSE
- Priority: Manual
- Reason: README install hints: We provide PROTAC-STAN running demo through a Jupyter notebook `demo.ipynb`. Note it is based on a small demo dataset of PROTAC-fine. This demo only takes about 5 minutes to complete the whole pipeline. For running PROTAC-STAN on the full dataset, we advise GPU ram >= 8GB and CPU ram >= 16GB. | ## System requirements | The full requirements are provided in `protac-stan.yml` | ## Installation guide | It normally takes about 10 minutes to install on a normal desktop computer (based on your network). | 1. Create Conda environment; heavy docking/GPU/training/ternary-complex keywords detected; no standard dependency files detected; dataset/notebook or benchmark-style repository likely

## PROTACability

- GitHub: https://github.com/GilbertoPPereira/PROTACability
- Local path: `data/protac_repos/repos/PROTACability`
- Detected files: README.md
- Priority: Manual
- Reason: no standard dependency files detected

## AIMLinker

- GitHub: https://github.com/AnHorn/AIMLinker
- Local path: `data/protac_repos/repos/AIMLinker`
- Detected files: README.md
- Priority: Manual
- Reason: no standard dependency files detected

## MEGA-PROTAC

- GitHub: https://github.com/yauz3/MEGA-PROTAC
- Local path: `data/protac_repos/repos/MEGA-PROTAC`
- Detected files: environment.yml, requirements.txt, README.md
- Priority: Manual
- Reason: README install hints: <h1> MEGA PROTAC: PROTAC-Mediated Ternary Complex Formation Pipeline based on MEGADOCK with Sequential Filtering integrated with Rank Aggregation. </h1> | **Pre-installation:** | *1*- MEGA DOCK Installation: | Before proceeding with the installation, ensure that MEGA DOCK is installed on your system. It is highly recommended to follow the original documentation provided by the developers for detailed instructions: | Please refer to their documentation to install MEGA DOCK correctly before continuing with this project. | HINT: megadock and megadock-gpu should be in the folder. Otherwise, the MEGA PROTAC won't work because of failure installation for MEGADOCK.; heavy docking/GPU/training/ternary-complex keywords detected

## SynGlue

- GitHub: https://github.com/the-ahuja-lab/SynGlue
- Local path: `data/protac_repos/repos/SynGlue`
- Detected files: README.md, LICENSE.txt
- Priority: Medium
- Reason: README install hints: <img src="https://img.shields.io/conda/vn/conda-forge/YOUR_PACKAGE"> | # Installation | ### 📦 Install API Client | pip install synglue requests | * Integration into automated drug discovery pipelines | pip install requests; no standard dependency files detected; dataset/notebook or benchmark-style repository likely

## PROTAC-Model_benchmark

- GitHub: https://github.com/gaoqiweng/PROTAC-Model_benchmark
- Local path: `data/protac_repos/repos/PROTAC-Model_benchmark`
- Detected files: README.md
- Priority: Low
- Reason: no standard dependency files detected; dataset/notebook or benchmark-style repository likely

## SE3-protacs

- GitHub: https://github.com/drugparadigm/SE3-protacs
- Local path: `data/protac_repos/repos/SE3-protacs`
- Detected files: environment.yml, README.md
- Priority: Manual
- Reason: README install hints: ## ⚙️ Installation | conda env create -f environment.yml | conda activate se3protacs; heavy docking/GPU/training/ternary-complex keywords detected

## science-paper-protac-conformer-generator-2025

- GitHub: https://github.com/ccdc-opensource/science-paper-protac-conformer-generator-2025
- Local path: `data/protac_repos/repos/science-paper-protac-conformer-generator-2025`
- Detected files: README.md
- Priority: Manual
- Reason: README install hints: ## Dependencies & Requirements | ## Installation | Ensure a working CSD Python API environment. No separate package installation is required beyond dependencies already provided with the API.; heavy docking/GPU/training/ternary-complex keywords detected; no standard dependency files detected

## PROTAC-shotgun

- GitHub: https://github.com/zhao-fuqiang/PROTAC-shotgun
- Local path: `data/protac_repos/repos/PROTAC-shotgun`
- Detected files: README.md, LICENSE
- Priority: Manual
- Reason: README install hints: The code of DSDP is modified to use the input coordinates as the initial guess for conformation sampling. You can find the instructions for installment of DSDP from https://github.com/PKUGaoGroup/DSDP. | The code of ColabDock is also modified to use the input coordinates as the initial guess for conformation sampling. The output from each iteration is saved, and the second stage (prediction stage) of ColabDock is not run. You can find the instructions for installment of ColabDock from https://github.com/JeffSHF/ColabDock.; heavy docking/GPU/training/ternary-complex keywords detected; no standard dependency files detected; dataset/notebook or benchmark-style repository likely

## PROTAC_descriptors

- GitHub: https://github.com/cancer-nanomedicine-lab/PROTAC_descriptors
- Local path: `data/protac_repos/repos/PROTAC_descriptors`
- Detected files: none
- Priority: Manual
- Reason: README.md not detected; no standard dependency files detected; dataset/notebook or benchmark-style repository likely

## computational-PROTAC-development

- GitHub: https://github.com/leezx/computational-PROTAC-development
- Local path: `data/protac_repos/repos/computational-PROTAC-development`
- Detected files: README.md, LICENSE
- Priority: Manual
- Reason: no standard dependency files detected

## PROTAC

- GitHub: https://github.com/yugyeong0609/PROTAC
- Local path: `data/protac_repos/repos/PROTAC`
- Detected files: README.md
- Priority: Manual
- Reason: no standard dependency files detected

## ProtacDatabase

- GitHub: https://github.com/wxfsd/ProtacDatabase
- Local path: `data/protac_repos/repos/ProtacDatabase`
- Detected files: README.md, LICENSE
- Priority: Low
- Reason: no standard dependency files detected; dataset/notebook or benchmark-style repository likely

## degradomap

- GitHub: https://github.com/crisprking/degradomap
- Local path: `data/protac_repos/repos/degradomap`
- Detected files: pyproject.toml, README.md, LICENSE
- Priority: Manual
- Reason: README install hints: - Full pipeline (UniProt → AlphaFold → DepMap → feature matrix → LOO classifier) | ## Install | pip install -e . | ## Run the pipeline; heavy docking/GPU/training/ternary-complex keywords detected; dataset/notebook or benchmark-style repository likely
