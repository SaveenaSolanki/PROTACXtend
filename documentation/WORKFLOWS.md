# PROTACXtend Workflows & Slash Commands

PROTACXtend provides intuitive slash commands and natural-language workflows through the CLI, REST API, and local Feynman science workbench.

---

## ⚡ Slash Commands Overview

| Command | Action | Key Parameters | Output |
| :--- | :--- | :--- | :--- |
| `/design` | Full end-to-end PROTAC discovery pipeline | `--target`, `--e3`, `--num-candidates` | Pareto-ranked PROTAC candidate table + markdown report |
| `/predict` | Predict $DC_{50}$, $D_{\max}$, and degradation class | `--smiles`, `--target`, `--cell-line` | Quantitative degradation metrics and confidence interval |
| `/dock` | Run ternary complex modeling & docking | `--smiles`, `--target-pdb`, `--e3-pdb` | 3D complex structure + SE(3) geometric feasibility score |
| `/admet` | Evaluate safety, toxicity, & drug-likeness | `--smiles` | ADMET radar scores (hERG, AMES, BBB, Lipinski/Veber) |
| `/audit` | Audit reasoning chain and claim evidence | `--session-id` | Step-by-step decision log & evidence verification matrix |
| `/replicate` | Replicate benchmark experiments | `--dataset`, `--model` | Reproducibility report & metric validation |

---

## 🧪 Detailed Workflow Examples

### 1. `/design` — End-to-End Candidate Generation

Run a complete design run targeting BRD4 degradation with CRBN E3 ligase:

```bash
protacxtend design \
  --target "BRD4" \
  --e3 "CRBN" \
  --warhead "pomalidomide" \
  --num-candidates 16 \
  --output ./results/brd4_run.json
```

**What happens inside**:
1. UniProt and ChEMBL lookup for BRD4 binders.
2. Attachment point detection on warhead and pomalidomide.
3. Generative linker design (rigid vs flexible chains).
4. Chemprop $DC_{50}$ prediction and SE(3) ternary complex check.
5. Multi-objective Pareto ranking and CSV/JSON output.

---

### 2. `/predict` — Degradation Prediction for Existing SMILES

Evaluate a candidate molecule:

```bash
protacxtend predict \
  --smiles "CC1=C(C=C(C=C1)NC(=O)C2=CC=C(C=C2)CN3CCN(CC3)C)C4=NC=CN4" \
  --target "BRD4" \
  --cell-line "HeLa"
```

**Output**:
```json
{
  "smiles": "CC1=C(C=C(C=C1)...",
  "dc50_nm": 14.2,
  "dmax_percent": 88.5,
  "degradation_class": "High Degrader",
  "confidence": 0.91,
  "hERG_risk": "Low"
}
```

---

### 3. `/dock` — Ternary Complex Simulation

Perform 3D docking simulation for target-PROTAC-E3 ternary complex:

```bash
protacxtend dock \
  --smiles "<PROTAC_SMILES>" \
  --target-pdb "3U5L" \
  --e3-pdb "4CIW"
```

Generates PDB coordinates of the predicted ternary ensemble along with interface contact residue mapping.

---

### 4. `/admet` — ADMET Risk Profiling

Perform comprehensive ADMET profiling:

```bash
protacxtend admet --smiles "<PROTAC_SMILES>"
```

Returns Lipinski Rule-of-5 compliance, Veber rotatable bond count, topological polar surface area (TPSA), hERG affinity risk, and AMES mutagenicity assessment.

---

### 5. `/audit` — Feynman Decision Trace Audit

Audit a completed design session to review reasoning provenance:

```bash
protacxtend audit --session-id "session_20260731_1542"
```

Outputs the exact sequence of 23 agent decisions, tool parameters, and threshold evaluations.
