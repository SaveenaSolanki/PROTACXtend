# SOTA (State-of-the-Art) Tools Integration

## Setup Instructions

### 1. AI Scientist (Sakana AI)
```bash
cd SOTA/ai_scientist
git clone https://github.com/SakanaAI/AI-Scientist.git .
conda create -n ai_scientist python=3.11 -y
conda activate ai_scientist
pip install -r requirements.txt
```

### 2. BioMiner (jiaxianyan)
```bash
cd SOTA/biomini
git clone https://github.com/jiaxianyan/BioMiner.git .
conda create -n biominer python=3.11 -y
conda activate biominer
pip install -r requirements.txt
```

### 3. Robin (Future-House)
```bash
cd SOTA/robin
git clone https://github.com/Future-House/robin.git .
conda create -n robin python=3.12 -y
conda activate robin
pip install -r requirements.txt
```

## PROTAC Ranking Prompt

Use this prompt with any SOTA tool:
```
Rank these 6 BRD4-VHL PROTACs from most to least potent using only their structures.
Explain the mechanistic reason for each rank.

Molecule    Canonical SMILES    Formula
Molecule 1    COc1cc2c(cc1c1c(C)onc1C)cc(c(=O)n2Cc1ccccn1)C(=O)NCCOCCOCCOCC(=O)N[C@@H](C(C)(C)C)C(=O)N1C[C@@H](C[C@H]1C(=O)N[C@H](c1ccc(cc1)c1scnc1C)C)O    C53H64N8O11S
Molecule 2    COc1cc2c(cc1c1c(C)onc1C)cc(c(=O)n2Cc1ccccn1)CNCCOCCOCCOCC(=O)N[C@@H](C(C)(C)C)C(=O)N1C[C@@H](C[C@H]1C(=O)NCc1ccc(cc1)c1scnc1C)O    C52H64N8O10S
Molecule 3    COc1cc2c(cc1c1c(C)onc1C)cc(c(=O)n2Cc1ccccn1)C(=O)NCCCCCCCCOCC(=O)N[C@@H](C(C)(C)C)C(=O)N1C[C@@H](C[C@H]1C(=O)N[C@H](c1ccc(cc1)c1scnc1C)C)O    C55H68N8O9S
Molecule 4    COc1cc2c(cc1c1c(C)onc1C)cc(c(=O)n2Cc1ccccn1)C(=O)NCCCCCCCCCCCOCC(=O)N[C@@H](C(C)(C)C)C(=O)N1C[C@@H](C[C@H]1C(=O)N[C@H](c1ccc(cc1)c1scnc1C)C)O    C58H74N8O9S
Molecule 5    COc1cc2c(cc1c1c(C)onc1C)cc(c(=O)n2Cc1ccccn1)c1cnn(c1)CCOCCOCCOCC(=O)N[C@@H](C(C)(C)C)C(=O)N1C[C@@H](C[C@H]1C(=O)N[C@H](c1ccc(cc1)c1scnc1C)C)O    C55H65N9O10S
Molecule 6    COc1cc2c(cc1c1c(C)onc1C)cc(c(=O)n2Cc1ccccn1)C(=O)N1CCC(CC1)OCCOCCOCC(=O)N[C@@H](C(C)(C)C)C(=O)N1C[C@@H](C[C@H]1C(=O)N[C@H](c1ccc(cc1)c1scnc1C)C)O    C56H68N8O11S
```

## Outputs

- `outputs/capabilities/capabilities_full.csv` - All 24K+ capabilities
- `outputs/capabilities/capabilities_clustered.csv` - Functional clusters
- `outputs/capabilities/hierarchy.json` - Hierarchical structure
- `outputs/capabilities/capability_graph.md` - Mermaid dependency graph
- `outputs/capabilities/word_cloud.html` - Keyword visualization
- `outputs/capabilities/coverage_diff.html` - Coverage analysis
- `outputs/capabilities/domain_distribution.html` - Domain chart
