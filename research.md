# Deep Research Task D: Retraining/Validation Infrastructure for PROTAC Models

**Date:** 2026-08-31  
**Scope:** Infrastructure, tools, and practices for retraining, validation, and continuous improvement of PROTAC ML models

---

## Evidence Table

| # | Source | URL | Key Claim | Type | Confidence |
|---|--------|-----|-----------|------|------------|
| 1 | PROTAC-Bench GitHub | https://github.com/ThorKlm/PROTAC-Bench | Leave-one-target-out (LOTO) benchmark with 10,748 entries, 173 targets, 65 LOTO folds, 4 evaluation splits (LOTO, LOFO, cross-lab, temporal-prospective); pre-computed ADMET scores; canonical RF+Morgan baseline (0.668 AUROC); Croissant metadata with MLCommons RAI extension | primary | high |
| 2 | PROTAC-Bench paper (Klamt et al., 2025) | https://arxiv.org/abs/2605.11764 | Variance decomposition showing inter-laboratory measurement variance (0.124 AUROC) dominates random-CV-to-LOTO gap; 8 architectures plateau at ~0.67 LOTO AUROC; few-shot k=5 per-target retraining lifts to 0.705; Platt scaling recovers calibration (ECE 0.150→0.031); HPO (2000 trials) cannot break ceiling; scaffold splits don't isolate targets (99.6% target overlap) | primary | high |
| 3 | TACK GitHub | https://github.com/ribesstefano/TACK | Largest curated PROTAC dataset (3,514 PROTACs, 6,561 endpoints from TPDdb, PROTAC-DB, PROTACpedia); nested 5×5 cross-validation; scaffold-based splitting; Caruana's greedy forward ensemble selection; pre-trained ensembles for Dmax, DC50, binary on Hugging Face/Zenodo; uncertainty quantification via ensemble disagreement | primary | high |
| 4 | TACK paper (Ribes et al., 2026) | https://arxiv.org/abs/2605.19579 | Scaffold-based 5×5 CV + formal statistical testing (Friedman, Wilcoxon, Tukey HSD); regression (pDC50, Dmax) and binary classification; XGBoost + MLP architectures; ESM embeddings for proteins; Hugging Face dataset with multiple configs | primary | high |
| 5 | DeepPROTACs GitHub | https://github.com/Fenglei104/DeepPROTACs | Pocket graph CNN + BiLSTM over fragments; requires PDB structures for pockets; binary degradation prediction; single prediction script; web service at bailab.siais.shanghaitech.edu.cn | primary | high |
| 6 | PROTAC-STAN GitHub | https://github.com/PROTACs/PROTAC-STAN | Structure-informed deep ternary attention network; atom/molecule/property hierarchies; ESM-S structural protein embeddings; ternary attention over PROTAC, POI, E3; attention map visualization; PROTAC-fine dataset | primary | high |
| 7 | SE3-PROTACs GitHub | https://github.com/drugparadigm/SE3-protacs | SE(3)-Transformer for 3D molecular graphs from .mol2; ESM embeddings for proteins; equivariant to rotation/translation; binary prediction; pre-computed embedding script | primary | high |
| 8 | DegradeQuery paper (Xu et al., 2026) | https://arxiv.org/abs/2608.10595 | Counterfactual tuple pretraining on 7,134 unlabeled PROTAC-8K records; contrasts observed (molecule, target, E3) tuples vs. target/E3/both replacements; improves AUROC 0.9065 vs 0.8827 Sup; no pseudo-labels/teacher models; target-E3 group holdout shows heterogeneous gains | primary | high |
| 9 | PROTAC-Splitter paper (Ribes et al., 2025) | https://pmc.ncbi.nlm.nih.gov/articles/PMC12924545/ | 1.3M synthetic PROTAC dataset with substructure annotations; Transformer seq2seq (86% exact-match) + XGBoost graph model (100% validity/reassembly); Transformer-Δ fixing wrapper; hybrid inference strategy; AstraZeneca internal test set (2,256 PROTACs) | primary | high |
| 10 | TACK Hugging Face models | https://huggingface.co/ailab-bio/TACK-Model-Bin | Three model repos (Bin, DC50, Dmax) with model cards; ensemble predictors; linked to paper (arXiv:2605.19579); CC-BY-4.0 data, MIT code | primary | high |
| 11 | PROTAC-Bench Hugging Face dataset | https://huggingface.co/datasets/PROTAC-Bench/protac-bench | 10,748 entries; LOTO folds; ADMET cascade scores; evaluation scripts (baselines.py, evaluate.py); CC-BY-4.0 data, MIT code | primary | high |
| 12 | TACK Hugging Face dataset | https://huggingface.co/datasets/ailab-bio/TACK | Multi-config dataset (Dmax, DC50, multitask); standardized SMILES, protein annotations, experimental conditions; 5×5 CV splits | primary | high |
| 13 | Active learning for drug discovery (openadmet) | https://openadmet.ghost.io/model-take-the-wheel-active-learning-with-pec50-data/ | ChemProp + CheMeleon active learning loops for PXR/Mpro; 6 acquisition strategies; multi-fidelity cost-aware AL (moal); general small-molecule, not PROTAC-specific | secondary | medium |
| 14 | General MLOps tools (MLflow, Kubeflow, etc.) | https://mlflow.org/articles/automating-ai-model-registry-updates/ | Model registry, drift detection (PSI/KS), CI/CD pipelines, A/B testing, champion-challenger; no PROTAC-specific implementations found | secondary | medium |
| 15 | Validation split strategies (Ribes et al., 2024) | https://doi.org/10.1016/j.ailsci.2024.100104 | First LOTO evaluation for PROTACs; showed ~80% target overlap in random splits; LOTO drops AUROC to ~0.60; temporal splits considered | primary | high |

---

## Findings

### 1. Published PROTAC Model Retraining Pipelines with Code

**PROTAC-Bench (Klamt et al., 2025)** [1, 2] provides the most complete retraining/evaluation infrastructure:
- **Repository:** `ThorKlm/PROTAC-Bench` with `reproduce.sh` regenerating all canonical results (~2-3 hours on 16-core CPU)
- **Baselines:** `rf_morgan.py` (anchor 0.668 AUROC), `dm_loto.py` (DegradeMaster), `gnn_baselines.py`, `chemprop_hpo.py`, `xgboost_morgan.py`
- **Full-stack pipeline:** `signals/warhead_transfer.py`, `signals/admet_cascade.py`, `signals/fewshot.py`, `signals/full_stack.py` implementing the 4-factor factorial (Morgan M, Warhead W, ADMET A, Few-shot K)
- **HPO infrastructure:** 21-dimensional search space, 2000 Optuna trials, multi-seed validation (5 seeds), functional ANOVA variance attribution
- **Robustness checks:** `robustness/` for cross-source, non-kinase, cross-E3, temporal evaluations

**TACK (Ribes et al., 2026)** [3, 4] provides a production-grade training framework:
- **Nested 5×5 cross-validation** with scaffold-based splits to prevent leakage
- **Caruana's greedy forward ensemble selection** with uncertainty quantification
- **Config-driven training:** YAML configs in `configs/data/` and `configs/models/` for data featurization (Morgan, ESM, text, countvec) and model architectures (MLP, XGBoost, BERT)
- **Pre-trained ensembles** on Hugging Face (`ailab-bio/TACK-Model-Bin`, `TACK-Model-DC50`, `TACK-Model-Dmax`) and Zenodo [10]
- **Cache system:** Pre-computed embeddings (ESM protein, sentence-transformer cell lines, Morgan fingerprints, RDKit descriptors) separated from model checkpoints
- **EnsemblePredictor API** for inference with pre-fitted scalers/encoders

**DeepPROTACs (Li et al., 2022)** [5] – Original pipeline:
- Requires PDB structures for ligase/target pockets + ligand SMILES + linker
- Pocket extraction via `prepare_data.ipynb` → feature extraction via `prepare_data.py`
- Graph CNN over pockets + BiLSTM over fragment SMILES
- Single prediction script for new complexes

**PROTAC-STAN (Chen et al., 2025)** [6] – Ternary attention framework:
- `main.py` training on PROTAC-fine dataset (enriched PROTAC-DB 2.0)
- ESM-S structural embeddings + ternary attention
- `inference.py` for custom data with attention map visualization
- Colab demo available

**SE3-PROTACs** [7] – Equivariant 3D approach:
- `.mol2` → 3D molecular graphs; ESM protein embeddings
- `pre_compute_emb.py` → `main.py` training
- `casestudy.py` for single-sample inference

**DegradeQuery (Xu et al., 2026)** [8] – Counterfactual tuple pretraining:
- Uses unlabeled PROTAC-8K records (7,134 tuples) for self-supervision
- Contrastive loss: observed (molecule, target, E3) vs. counterfactual replacements
- Fine-tunes on 1,502 labeled records; achieves 0.9065 AUROC on official split
- No pseudo-labels, teacher models, or ensembles

**PROTAC-Splitter (Ribes et al., 2025)** [9] – Substructure decomposition:
- 1.3M synthetic PROTACs with warhead/linker/E3 annotations
- Two models: Transformer seq2seq (ChemBERTa init) + XGBoost graph classifier
- Transformer-Δ fixing wrapper for hallucination correction
- Hybrid inference: Transformer-Δ → fallback to XGBoost on validity failure

### 2. Active Learning / Active Learning Loops for PROTAC Optimization

**No PROTAC-specific active learning implementations were found.** The literature contains:
- General drug discovery AL frameworks (openadmet) using ChemProp/CheMeleon for PXR/Mpro targets [13]
- Multi-fidelity cost-aware AL (`moal`) for choosing assays + compounds [13]
- Multi-objective ligand optimization for binding affinities [13]
- Policy-based AL for molecular identification [initial search]

**Gap:** No published work applies active learning specifically to PROTAC degradation prediction (which compound-target-E3 experiment to run next). The PROTAC context adds complexity: the acquisition function must consider the ternary (molecule, target, E3) space, not just molecule-property pairs. DegradeQuery's counterfactual tuple pretraining [8] implicitly learns which target-E3 contexts a molecule appears in, but doesn't implement an acquisition strategy.

### 3. Model Validation Frameworks for PROTACs

**Cross-validation strategies implemented:**

| Strategy | PROTAC-Bench [1, 2] | TACK [3, 4] | DegradeQuery [8] | DeepPROTACs [5] |
|----------|---------------------|-------------|------------------|-----------------|
| Random CV | Referenced (0.902 pooled) | Not primary | Official split | 0.847 reported |
| Scaffold CV | Tested: 0.897 AUROC, 99.6% target overlap → rejected | **Primary: scaffold-based 5×5 CV** | Scaffold holdout tested | Not used |
| Leave-One-Target-Out (LOTO) | **Canonical: 65 folds, macro AUROC 0.668** | Not used | Target-E3 group holdout (10 splits) | Not used |
| Leave-One-Family-Out (LOFO) | 61 targets, 0.616 AUROC | Not used | Not used | Not used |
| Temporal-prospective | Pre-2023 train / 2024 test: 0.561 (RF) → 0.674 (full-stack) | Not used | Not used | Not used |
| Cross-laboratory | 36 targets, 3+ pubs/target: cascade 0.802→0.678→0.653 | Not used | Not used | Not used |
| Target-E3 group holdout | Not defined | Not used | **10 independent 20% holdouts** | Not used |
| Few-shot per-target | k=5/25/50/100 stratified retraining | Not used | K=2/4/8 support examples | Not used |

**Key validation findings [2]:**
- Scaffold splits **do not isolate targets** (99.6% of test compounds share target with training; 88/173 targets in all 5 folds) → LOTO adopted as canonical
- Random CV (pooled 0.902) vs LOTO (macro 0.668) gap = 0.234 AUROC, largely due to 80% target overlap in random splits [15]
- Inter-laboratory variance bounds the LOTO ceiling at 0.124 AUROC (cross-lab cascade: random-CV 0.802 → cross-lab 0.678 → LOTO 0.653)
- Few-shot k=5 per-target retraining + ADMET lifts 65-target LOTO from 0.668 → 0.705
- Platt scaling recovers calibration: ECE 0.150 → 0.031 (below 0.05 threshold)
- HPO (2000 trials) rank-1 single-seed (0.764) regresses to 0.603±0.012 under 5-seed validation (0.161 regression = selection bias)

### 4. PROTAC-Specific MLOps Tools

**No PROTAC-specific MLOps tools exist.** The ecosystem uses general-purpose infrastructure:

| Component | Tools Used / Referenced | PROTAC-Specific? |
|-----------|------------------------|------------------|
| Experiment tracking | Not explicitly used in PROTAC repos; MLflow referenced in general MLOps [14] | No |
| Model registry | Hugging Face Model Hub (TACK models, PROTAC-Bench dataset) | Partial (HF Hub) |
| Drift detection | PSI/KS for feature drift, prediction drift, concept drift [14] | No |
| A/B testing / Champion-challenger | `9shrey/cicd-retraining-pipeline`, `Emmimal/ml-retraining-pipeline` [14] | No |
| Model cards | TACK models on HF have model cards (README.md with metadata) [10] | Partial (HF standard) |
| CI/CD / Reproducibility | `reproduce.sh` scripts (PROTAC-Bench, TACK); Croissant metadata (PROTAC-Bench) | Partial |
| Data versioning | Datasets on Hugging Face + Zenodo with DOIs | Partial |
| Pipeline orchestration | Not used; manual `reproduce.sh` / `python scripts/train_models.py` | No |

**Hugging Face serves as de facto model registry** for TACK [10, 11, 12] and PROTAC-Bench [1, 11] with:
- Model cards (README.md with YAML metadata)
- Dataset cards with Croissant/RAI metadata (PROTAC-Bench)
- Versioned datasets (TACK configs: Dmax, DC50, multitask)
- Linked paper DOI (arXiv:2605.19579)

### 5. Public PROTAC Benchmark Suites with Standardized Splits

| Benchmark | Size | Targets | Splits | Key Features | Access |
|-----------|------|---------|--------|--------------|--------|
| **PROTAC-Bench** [1, 2, 11] | 10,748 entries | 173 (65 LOTO-eligible) | LOTO (65), LOFO (61), Cross-lab (36), Temporal | Binary label (DC50<1μM ∨ Dmax>50%); ADMET cascade (7 props); Croissant 1.0 + RAI; 10 canonical seeds | HF: `ThorKl/protac-bench` (CC-BY-4.0); GitHub MIT |
| **TACK** [3, 4, 12] | 3,514 PROTACs, 6,561 endpoints | Multiple POIs/E3s | Nested 5×5 scaffold CV; multiple configs (bin-fp, bin-cell_text, etc.) | Continuous DC50/Dmax + binary; ESM/protein embeddings; ensemble selection; pre-trained models | HF: `ailab-bio/TACK`; Zenodo models |
| **PROTAC-8K** (DegradeMaster) [8] | 8,636 tuples | 332 targets | Official split (1,502 labeled / 7,134 unlabeled) | Tuple-rich (100% molecule/target/E3 IDs); label-sparse (17% labeled) | Referenced in DegradeQuery/DegradeMaster |
| **PROTAC-DB 3.0** [2] | 6,111 | 442 | None standardized | Activity + PK parameters | CC-BY-4.0 |
| **TPDdb** [2] | 22,183 | 580 | None (only 10 LOTO-evaluable) | Comprehensive but patent-enumerated | CC-BY-NC-4.0 |
| **PROTAC-PatentDB** [2] | 63,136 | 252 | None | Patent compounds, few assays | CC-BY-NC-ND-4.0 |

**PROTAC-Bench is the only benchmark with:**
- Multiple standardized evaluation splits (4 primary + robustness)
- Pre-computed fold assignments (JSON files)
- Evaluation scripts (`evaluate.py`, `baselines.py`)
- Measurement-variance decomposition framework
- Croissant metadata with MLCommons RAI compliance

### 6. Model Cards for PROTAC Models

**TACK models on Hugging Face** [10] have model cards:
- `ailab-bio/TACK-Model-Bin` – Binary degradation (DC50<100nM & Dmax>80%)
- `ailab-bio/TACK-Model-DC50` – DC50 regression ensemble
- `ailab-bio/TACK-Model-Dmax` – Dmax regression ensemble
- `ailab-bio/TACK-ensembles` – Combined ensemble artifacts

Each follows HF model card convention (README.md with YAML frontmatter linking to paper, dataset, metrics).

**PROTAC-Bench dataset** [11] has a comprehensive dataset card with:
- Dataset description, structure, splits, baseline results table
- Known biases (kinase-dominated, E3 imbalance, publication bias)
- Citation format, license (CC-BY-4.0)

**Gap:** No model cards for DeepPROTACs, PROTAC-STAN, SE3-PROTACs, DegradeQuery, or DegradeMaster on public registries. Models are distributed as `.pt`/`.ckpt` files in GitHub repos or Zenodo without standardized documentation.

---

## Coverage Status

| Area | Status | Notes |
|------|--------|-------|
| Retraining pipelines (code) | ✅ **Checked** | 6 major repos analyzed (PROTAC-Bench, TACK, DeepPROTACs, PROTAC-STAN, SE3-PROTACs, PROTAC-Splitter) |
| Active learning for PROTACs | ❌ **Blocked** | No PROTAC-specific AL found; only general small-molecule AL |
| Validation frameworks | ✅ **Checked** | Comprehensive split strategies documented across 4 benchmarks |
| PROTAC-specific MLOps | ❌ **Blocked** | Only general MLOps tools; HF Hub used as de facto registry |
| Benchmark suites | ✅ **Checked** | 3 major benchmarks (PROTAC-Bench, TACK, PROTAC-8K) with splits characterized |
| Model cards | 🟡 **Partial** | TACK models have HF cards; others lack standardized cards |

---

## Sources

1. ThorKlm/PROTAC-Bench — https://github.com/ThorKlm/PROTAC-Bench
2. Klamt et al., "Decomposing the Generalization Gap in PROTAC Activity Prediction" — https://arxiv.org/abs/2605.11764
3. ribesstefano/TACK — https://github.com/ribesstefano/TACK
4. Ribes et al., "TACK: A Statistical Evaluation of Degradation Activity" — https://arxiv.org/abs/2605.19579
5. Fenglei104/DeepPROTACs — https://github.com/Fenglei104/DeepPROTACs
6. PROTACs/PROTAC-STAN — https://github.com/PROTACs/PROTAC-STAN
7. drugparadigm/SE3-protacs — https://github.com/drugparadigm/SE3-protacs
8. Xu et al., "DegradeQuery: Counterfactual Tuple Pretraining" — https://arxiv.org/abs/2608.10595
9. Ribes et al., "PROTAC-Splitter" — https://pmc.ncbi.nlm.nih.gov/articles/PMC12924545/
10. ailab-bio/TACK-Model-Bin — https://huggingface.co/ailab-bio/TACK-Model-Bin
11. PROTAC-Bench/protac-bench — https://huggingface.co/datasets/PROTAC-Bench/protac-bench
12. ailab-bio/TACK dataset — https://huggingface.co/datasets/ailab-bio/TACK
13. openadmet active learning — https://openadmet.ghost.io/model-take-the-wheel-active-learning-with-pec50-data/
14. MLflow MLOps articles — https://mlflow.org/articles/automating-ai-model-registry-updates/
15. Ribes et al., "Modeling PROTAC degradation activity with ML" — https://doi.org/10.1016/j.ailsci.2024.100104

---

## Summary for Parent

Found comprehensive retraining/validation infrastructure for PROTAC models centered on two benchmark ecosystems: **PROTAC-Bench** (LOTO-focused, variance-decomposition, few-shot calibration) and **TACK** (scaffold 5×5 CV, ensemble selection, pre-trained HF models). Six open-source model repos provide reproducible pipelines. **Critical gaps:** no PROTAC-specific active learning, no PROTAC MLOps tools beyond HF Hub, and most models lack standardized model cards.