# PROTACXtend Environments

Two conda environments are the canonical compute layers for PROTACXtend.

| Env | Python | Path | Purpose |
|-----|--------|------|---------|
| **`protacpilot`** | 3.11.15 | `/home/saveenas/miniconda3/envs/protacpilot` | **Primary env** — full toolkit: chem, ML, agents, degradation, GROVER |
| **`torchdrug310`** | 3.10.20 | `/home/saveenas/miniconda3/envs/torchdrug310` | torchdrug 0.2.1 (requires Python <3.11, torch 2.1.2) |

## Activate

```bash
conda activate protacpilot        # primary
conda activate torchdrug310       # torchdrug only
```

## `protacpilot` — installed stack (verified 2026-08-01)

### Chemistry / descriptors
| Package | Version | Notes |
|---------|---------|-------|
| rdkit | 2026.03.4 | pip build (conda 2025.09.5 was replaced by pip during mordredcommunity reinstall) |
| openbabel | 3.1.0 | conda-forge |
| datamol | 0.12.5 | |
| mordred (mordredcommunity) | 2.0.7 | provides `mordred` import, 1613 2D descriptors, numpy-2 compatible |
| padelpy | 0.1.17 | needs Java at runtime |
| meeko | 0.7.1 | Vina ligand prep |

### ML / deep learning
| Package | Version | Notes |
|---------|---------|-------|
| torch | 2.6.0+cu126 | **pinned for dgl 2.5.0 graphbolt compatibility**; CUDA works on RTX 5000 |
| pytorch-lightning | 2.6.5 | |
| torch_geometric | 2.8.0.post1 | |
| deepchem | 2.8.0 | needs transformers<5 (pinned 4.57.6) |
| chemprop | 2.3.0 | D-MPNN for degradation — CLI: `chemprop train` |
| dgl | 2.5.0 | from `https://data.dgl.ai/wheels/torch-2.6/repo.html` |
| esm (fair-esm) | 2.0.0 | protein embeddings |
| xgboost | 3.2.0 | |
| scikit-learn | 1.9.0 | |
| catboost | 1.2.10 | |
| optuna | 4.9.0 | |
| ray | 2.56.1 | |

### MD / structure
| Package | Version | Notes |
|---------|---------|-------|
| mdtraj | 1.11.1 | conda-forge, needs numpy>=2 (satisfied: 2.4.6) |
| prody | 2.6.1 | |
| MDAnalysis | 2.10.0 | |
| gemmi | 0.7.5 | meeko dependency |

### Visualization
| Package | Version | Notes |
|---------|---------|-------|
| py3Dmol | 2.5.5 | |
| nglview | 4.0.1 | |
| matplotlib / seaborn | 3.10.9 / 0.13.2 | |

### Agents / orchestration
| Package | Version | Notes |
|---------|---------|-------|
| langgraph | 1.2.10 | StateGraph, interrupt, Command verified |
| langchain | 1.3.14 | |
| fastapi | 0.141.1 | |
| streamlit | 1.60.0 | |
| mlflow | 3.15.0 | |
| wandb | 0.28.1 | needs `wandb login` |
| gradio | 6.22.0 | |

### RAG / vector / workflow infrastructure
| Package | Version | Notes |
|---------|---------|-------|
| llama-index | 0.14.23 | `llama_index.core` verified |
| qdrant-client | 1.18.0 | client; server optional |
| chromadb | 1.5.9 | embedded |
| duckdb | 1.5.5 | |
| psycopg | 3.3.4 | needs Postgres server |
| redis | 8.1.0 | client; server optional |
| celery | 5.6.3 | needs broker |
| prefect | 3.8.1 | |
| snakemake | 9.24.0 | |
| nextflow | 24.10.6 | conda/bioconda, Java |

### Core
numpy 2.4.6, pandas 2.3.3, scipy 1.17.1, biopython 1.87, openpyxl 3.1.5, tqdm, requests, pytest 9.1.1, joblib 1.5.3

### Key version pins (do not bump casually)
- `torch==2.6.0+cu126` — dgl 2.5.0 graphbolt is compiled for torch 2.6; torch 2.13 breaks dgl (`libgraphbolt_pytorch_2.13.0.so` missing)
- `transformers<5` — deepchem 2.8.0 imports `HuggingFaceModel` from `deepchem.models.torch_models`, broken on transformers 5.x
- `huggingface-hub<1.0` — transformers 4.57.6 requires it (llama-index bumps hub to 1.x; pin back after installing llama-index)
- `numpy>=2` — mdtraj 1.11.1 requires numpy~=2.0 (use mordredcommunity, not original mordred 1.2.0, which pins numpy==1.*)
- `torchdata==0.9.0` — only version with `torchdata.datapipes` (dgl dependency); torchdata ≥0.10 removed it

## `torchdrug310` — torchdrug env

torchdrug 0.2.1 requires Python <3.11 (hard `Requires-Python` check) and a torch ≤2.1-era
toolchain for compiled ops. The env was built with:

```bash
conda create -n torchdrug310 python=3.10 -y
pip install torch==2.1.2 torchvision==0.16.2 --index-url https://download.pytorch.org/whl/cu121
pip install torch-scatter torch-sparse torch-cluster torch-spline-conv \
    -f https://data.pyg.org/whl/torch-2.1.0+cu121.html
pip install torchdrug --no-build-isolation
pip install "numpy<2" "setuptools<81" torch_geometric ninja
```

### Quirks resolved
- `setuptools<81` — setuptools 83 removed `pkg_resources` which torch 2.1.2's `cpp_extension` imports
- `numpy<2` — torch 2.1.2 compiled against numpy 1.x
- ninja lexicographic-version bug — torch's `verify_ninja_availability` compares `'1.13.0' >= '1.8.2'` as strings (fails);
  patched via `sitecustomize.py` in the env's site-packages
- Compiled ops built once into `TORCH_EXTENSIONS_DIR=/tmp/torch_extensions_td*` (nvcc at `/usr/bin/nvcc`)

### Verified working
- `torchdrug 0.2.1` import, `Molecule.from_smiles`, `Graph.pack`, CUDA True
- GIN forward reaches compiled `message_and_aggregate` (dtype quirk in test code, library ops load fine)

## GROVER + SynGlue (works in both envs)

SynGlue models live at `/storage/saveena/protacpilot/SynGlue_Py/models/` and are independent of conda env.
GROVER feature extraction needs `descriptastorus` (installed in `protacpilot`; in base it was pip-installed earlier).
The GROVER `torch.load` patch (`weights_only=False`) lives in
`SynGlue_Py/repos/grover/grover/util/utils.py` — applies in any env.

## Reproduce

```bash
bash scripts/setup_protacpilot_env.sh
```

## Run the test suite in the new env

```bash
conda activate protacpilot
cd /storage/saveena/protacpilot
python -m pytest synglue_agent/agents/test_ternary_stage.py \
                synglue_agent/tests/test_synglue_degradation.py -q
# 24 passed (verified 2026-08-01)
```
