#!/usr/bin/env bash
# ============================================================================
# ProtacPilot environment setup — reproducible build
# Creates `protacpilot` (primary) and `torchdrug310` (torchdrug) conda envs.
# Verified on: Linux, conda 26.1.1, NVIDIA RTX 5000 Ada (CUDA 13 driver)
# ============================================================================
set -euo pipefail

ENV_NAME=${1:-protacpilot}
PYTHON_VER=3.11

echo "==> Creating conda env: $ENV_NAME (python $PYTHON_VER)"
conda create -n "$ENV_NAME" "python=$PYTHON_VER" -y

PIP="$HOME/miniconda3/envs/$ENV_NAME/bin/pip"
PY="$HOME/miniconda3/envs/$ENV_NAME/bin/python"

echo "==> conda-forge packages (rdkit, openbabel, mdtraj)"
conda install -n "$ENV_NAME" -c conda-forge rdkit openbabel mdtraj -y

echo "==> torch 2.6.0+cu126 (pinned for dgl graphbolt compatibility)"
"$PIP" install torch==2.6.0 torchvision==0.21.0 --index-url https://download.pytorch.org/whl/cu126

echo "==> Missing-toolkit packages (the 17 from Agent_Toolkit audit)"
"$PIP" install datamol molfeat prody py3Dmol nglview catboost mlflow wandb padelpy fair-esm
"$PIP" install chemprop torchdata==0.9.0
"$PIP" install dgl -f https://data.dgl.ai/wheels/torch-2.6/repo.html
"$PIP" install deepchem "transformers<5"
"$PIP" install --force-reinstall mordredcommunity   # provides `mordred`, numpy-2 compatible
"$PIP" install xgboost gemmi

echo "==> Core toolchain (agents, orchestration, MD, viz)"
"$PIP" install langgraph langchain fastapi streamlit optuna ray \
        torch_geometric faiss-cpu meeko MDAnalysis biopython openpyxl \
        tqdm requests pytest

echo "==> Fix numpy (mdtraj 1.11.1 needs numpy>=2)"
"$PIP" install "numpy>=2.0"

echo "==> Verify"
"$PY" -c "
import warnings; warnings.filterwarnings('ignore')
import numpy as np, rdkit, openbabel, mdtraj, datamol, molfeat, prody, py3Dmol
import nglview, catboost, mlflow, wandb, padelpy, esm, deepchem, dgl, chemprop
import torch, sklearn, xgboost, mordred, langgraph, torch_geometric, meeko
from rdkit import Chem
assert Chem.MolFromSmiles('CC(=O)Oc1ccccc1C(=O)O') is not None
assert torch.cuda.is_available(), 'CUDA not available'
print('ALL PACKAGES VERIFIED in $ENV_NAME ✅')
print('torch', torch.__version__, '| dgl', dgl.__version__, '| chemprop', chemprop.__version__)
print('deepchem', deepchem.__version__, '| sklearn', sklearn.__version__, '| numpy', np.__version__)
"

# ---------------------------------------------------------------------------
# torchdrug env (Python 3.10 + torch 2.1.2, REQUIRED for torchdrug)
# ---------------------------------------------------------------------------
echo
echo "==> Creating torchdrug env: torchdrug310"
conda create -n torchdrug310 python=3.10 -y
TD_PIP="$HOME/miniconda3/envs/torchdrug310/bin/pip"
TD_PY="$HOME/miniconda3/envs/torchdrug310/bin/python"

"$TD_PIP" install torch==2.1.2 torchvision==0.16.2 --index-url https://download.pytorch.org/whl/cu121
"$TD_PIP" install torch-scatter torch-sparse torch-cluster torch-spline-conv \
    -f https://data.pyg.org/whl/torch-2.1.0+cu121.html
"$TD_PIP" install torchdrug --no-build-isolation
"$TD_PIP" install "numpy<2" "setuptools<81" torch_geometric ninja

# Patch torch's lexicographic ninja version check (ninja>=1.10 vs '1.8.2')
SITE_DIR=$("$TD_PY" -c "import site; print(site.getsitepackages()[0])")
cat > "$SITE_DIR/sitecustomize.py" << 'SITEEOF'
try:
    import torch.utils.cpp_extension as cpp
    def _patched():
        try:
            import ninja
            v = tuple(int(p) for p in ninja.__version__.split('.')[:2])
            if v >= (1, 8):
                return True
        except Exception:
            pass
        raise RuntimeError("Ninja is required to load C++ extensions")
    cpp.verify_ninja_availability = _patched
except Exception:
    pass
SITEEOF

"$TD_PY" -c "
import warnings; warnings.filterwarnings('ignore')
import torch, torchdrug
from torchdrug import data
mol = data.Molecule.from_smiles('CCO')
assert mol.num_node > 0
assert torch.cuda.is_available()
print('torchdrug', torchdrug.__version__, 'verified in torchdrug310 ✅')
"

echo
echo "Done. Activate with: conda activate $ENV_NAME"
echo "torchdrug with:       conda activate torchdrug310"
