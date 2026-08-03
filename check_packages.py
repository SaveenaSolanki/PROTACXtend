# check_packages.py

import importlib.util
import subprocess
import sys
from pathlib import Path

PACKAGES = {
    # Chemistry / molecular
    "rdkit": "rdkit",
    "openbabel": "openbabel",
    "datamol": "datamol",
    "mordred": "mordred",
    "padelpy": "padelpy",

    # Deep learning / molecular ML
    "deepchem": "deepchem",
    "molfeat": "molfeat",
    "torch": "torch",
    "pytorch-lightning": "pytorch_lightning",
    "dgl": "dgl",
    "torch-geometric": "torch_geometric",
    "torchdrug": "torchdrug",
    "transformers": "transformers",
    "fair-esm": "esm",

    # Bio / structure / MD
    "biopython": "Bio",
    "MDAnalysis": "MDAnalysis",
    "mdtraj": "mdtraj",
    "prody": "prody",
    "py3Dmol": "py3Dmol",
    "nglview": "nglview",

    # ML / optimization / tracking
    "scikit-learn": "sklearn",
    "xgboost": "xgboost",
    "catboost": "catboost",
    "optuna": "optuna",
    "ray[tune]": "ray",
    "mlflow": "mlflow",
    "wandb": "wandb",

    # Apps / APIs / agents
    "fastapi": "fastapi",
    "streamlit": "streamlit",
    "gradio": "gradio",
    "langgraph": "langgraph",
    "langchain": "langchain",
    "llama-index": "llama_index",

    # Vector DB / memory
    "qdrant-client": "qdrant_client",
    "faiss-cpu": "faiss",
    "chromadb": "chromadb",

    # Database / storage / workers
    "duckdb": "duckdb",
    "psycopg": "psycopg",
    "redis": "redis",
    "celery": "celery",
    "prefect": "prefect",

    # Workflow systems
    "snakemake": "snakemake",
    "nextflow": None,  # command-line tool, checked separately
}

COMMANDS = {
    "nextflow": "nextflow",
}


def check_python_import(import_name: str) -> bool:
    return importlib.util.find_spec(import_name) is not None


def check_command(command: str) -> bool:
    try:
        result = subprocess.run(
            ["which", command],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return result.returncode == 0
    except Exception:
        return False


def get_version(import_name: str):
    try:
        module = __import__(import_name)
        return getattr(module, "__version__", "version_unknown")
    except Exception:
        return "version_unavailable"


installed = []
missing = []

print("\n==============================")
print("SynGlue Package Status Checker")
print("==============================\n")

for package_name, import_name in PACKAGES.items():
    if import_name is None:
        command = COMMANDS.get(package_name)
        ok = check_command(command)
        version = "command_available" if ok else "-"
    else:
        ok = check_python_import(import_name)
        version = get_version(import_name) if ok else "-"

    if ok:
        installed.append(package_name)
        print(f"[OK]      {package_name:<22} import/command={import_name or COMMANDS.get(package_name):<20} version={version}")
    else:
        missing.append(package_name)
        print(f"[MISSING] {package_name:<22} import/command={import_name or COMMANDS.get(package_name):<20}")

print("\n==============================")
print(f"Installed: {len(installed)}")
print(f"Missing:   {len(missing)}")
print("==============================\n")

if missing:
    Path("missing_packages.txt").write_text("\n".join(missing) + "\n")
    print("Missing packages written to: missing_packages.txt\n")

    print("Suggested pip install command:")
    print("pip install " + " ".join(missing))
else:
    print("All packages are installed.")
