# Getting Started with PROTACXtend

This guide will walk you through setting up **PROTACXtend** on your system, installing required dependencies, and executing your first AI-guided PROTAC design workflow.

---

## 📋 Prerequisites

- **OS**: Linux (Ubuntu 20.04+ recommended) or macOS
- **Python**: 3.9, 3.10, or 3.11
- **Conda / Mamba**: Recommended for RDKit and PyTorch package isolation
- **Optional**: Docker / Singularity (for full P4ward ternary complex 3D docking runs)

---

## ⚡ Quick Installation

### Option 1: Install from GitHub (Recommended)

Clone the canonical repository (Ahuja Lab organization home):

```bash
# Clone the repository
git clone https://github.com/the-ahuja-lab/PROTACXtend.git
cd PROTACXtend

# Create a virtual environment
conda create -n protacxtend python=3.10 -y
conda activate protacxtend

# Install key chemistry & machine learning dependencies
pip install -r requirements.txt

# Install PROTACXtend in editable mode (PyPI publishing is on the roadmap)
pip install -e .
```

### Option 1b: Docker

```bash
docker build -t protacxtend https://github.com/the-ahuja-lab/PROTACXtend.git
```

### Option 2: Repository-Local CLI Execution (No Installation Required)

If you are working inside the workspace directory, you can run the executable wrapper immediately:

```bash
cd /storage/saveena/protacpilot
./PROTACXtend --help
# Or lowercase alias
./protacxtend status
```

---

## 🧪 Verifying the Environment

Run the self-diagnostic check to ensure all chemistry modules, RDKit sanitization routines, and agent tools are correctly initialized:

```bash
protacxtend status
```

Example output:
```text
PROTACXtend System Diagnostic [v0.3.0]
--------------------------------------
Python Version   : 3.10.12
RDKit Version    : 2023.09.1 [OK]
Chemprop Engine  : Active [OK]
P4ward Docker    : Ready [OK]
ChEMBL Lookup    : Connected [OK]
Status           : All 23 workflow nodes operational.
```

Test molecular sanitization with a sample SMILES:
```bash
protacxtend validate --smiles "O=C1NC(=O)C(N2C(=O)c3ccccc3C2=O)CC1"
```

---

## 🚀 Running Your First Workflow

### 1. Interactive CLI Command
Design PROTACs targeting BRD4 with CRBN E3 ligase:
```bash
protacxtend design "Design CRBN PROTAC candidates targeting BRD4 degradation"
```

### 2. Launching the Local Workbench UI
Launch the interactive science workbench interface:
```bash
protacxtend serve
```
Open your web browser at `http://localhost:8501`.

### 3. REST API Server Mode
Start the FastAPI REST backend for programmatic API calls:
```bash
python -m uvicorn protacxtend.backend.api_routes:get_app --factory --host 0.0.0.0 --port 8001
```

Send a POST request to design PROTAC candidates:
```bash
curl -X POST "http://localhost:8001/design" \
  -H "Content-Type: application/json" \
  -d '{"request": "Design 16 PROTACs for HMGB2 with ICM warhead and CRBN E3"}'
```

---

## 📂 Next Steps

- Explore the complete **[Architecture Guide](file:///storage/saveena/protacpilot/documentation/ARCHITECTURE.md)** to understand the 23-node agentic workflow graph.
- Learn about slash commands in **[Workflows & Slash Commands](file:///storage/saveena/protacpilot/documentation/WORKFLOWS.md)**.
- Set up your GitHub collaboration environment in **[GitHub Setup](file:///storage/saveena/protacpilot/documentation/GITHUB_AND_COLLABORATION.md)**.
