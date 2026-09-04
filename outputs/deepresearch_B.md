# DEEP RESEARCH TASK B — Computational PROTAC Tool Landscape (2020–2026) + Local ProtacPilot Inventory

*Evidence-gathering subagent output. Date: 2026-08-12. Working dir: /storage/saveena/protacpilot*

---

## Coverage Status

- **Checked directly (primary):** Local repo files read in full or in part: `ASSET_MANIFEST.md`, `RELEASE_CLOSURE_REPORT.md`, `CHANGELOG.md` (full), `protacxtend/agents/real_nodes.py` (full), `protacxtend/tools/p4ward_wrapper.py` (full), plus headers of `ternary_ensemble.py`, `synglue_degradation.py`, `chemprop_degradation.py` (referenced), `e3_context_engine.py`, `admet_integration.py`, `retrosynthesis.py`, `docking_pipeline.py`, `online_ligand_miner.py`, `protac_repo_tool_wrappers.py`, `tool_status.py`; directory listings of `protacxtend/tools/` (76 tool modules) and `protacxtend/agents/`; `data/protac_repos/repos/` (29 cloned repos); `git status`/`git log`. External tools: verified via GitHub repos, papers (abstracts/fulltext where open), and official docs found by web search. Every entry in the evidence table has a direct URL.
- **Not checked:** I did not re-run the local test suite (parent asked for an inventory, not verification runs); I did not read every one of the 76 tool modules end-to-end; paywalled full texts (JCIM/JMC) were assessed from abstract + GitHub + secondary benchmark sources only. Claims about external tool internals beyond what a README/abstract states are marked as inferences.
- **Could not complete:** nothing in the assigned scope was silently skipped; deep verification of local live-network behavior (ChEMBL/PubChem calls) was not re-executed — status taken from CHANGELOG/RELEASE records.

---

## Part 1 — External tool landscape by pipeline stage

### 1.1 Degradation predictors (DC50/Dmax/class)

- **DeepPROTACs** — deep neural network that predicts degradation capacity from the structures of the target pocket, E3 ligase pocket, ligand, and linker (input includes pocket PDBs + SMILES fragments). Trained on PROTAC-DB-derived data; published Nat Commun 13:7133 (2022). Code at Fenglei104/DeepPROTACs; public web server at bailab.siais.shanghaitech.edu.cn/services/deepprotacs/ [1][2][3].
- **PROTAC-STAN** — structure-informed deep ternary attention network for *interpretable* degradation prediction (first structure-aware + explainable approach per repo); Adv. Sci. 2025, DOI 10.1002/advs.202508138; official code with Colab demo [4][5][6].
- **DegradeMaster** — semi-supervised E(3)-equivariant GNN predictor with memory-based pseudo-labeling and mutual-attention pooling; bioRxiv 2025; released with the **PROTAC-8K** benchmark dataset (620 high-activity + 7,900+ low-activity entries curated from PROTAC-DB 3.0) on Zenodo [7][8][9].
- **SE(3)-PROTACs** — geometric deep learning (SE(3)-equivariant transformer + ESM embeddings) predicting degradation from ternary complex geometry; Brief. Bioinform. 2023, DOI 10.1093/bib/bbag228; code at drugparadigm/SE3-protacs (also used for ternary scoring) [10][11].
- **PROTAC-Degradation-Predictor** (ribesstefano) — ML predictor of degradation activity (Jupyter Notebook repo; companion paper in Comput. Struct. Biotechnol. J. 2024) [12].
- **ProtacPilot local analog:** trained Chemprop D-MPNN ensemble (see Part 2) outperforms heuristic ranking ρ 0.42→0.78 on PROTAC-DB 3.0 holdout (local claim) [13].

### 1.2 Ternary complex modeling

- **P4ward** — fully automated, open-source Python pipeline for PROTAC ternary complex modeling from two binary complexes + PROTAC 2D structures; integrates MEGADOCK (PPI docking), RxDock (linker scoring), RDKit, BioPython; outputs ranked complexes, lysine accessibility, CRL models; paper J. Chem. Inf. Model. 2025, DOI 10.1021/acs.jcim.5c00614 [14][15].
- **PROTAC-Model** — integrative FRODOCK-based protocol + RosettaDock refinement to predict Target–PROTAC–E3 ternary complexes (J. Med. Chem. 2021, DOI 10.1021/acs.jmedchem.1c01576); code at gaoqiweng/PROTAC-Model (Python 2.7-era; needs ADFRsuite, Vina, FRODOCK, Rosetta) [16][17].
- **PRosettaC** — Rosetta-based modeling of PROTAC-mediated ternary complexes; takes E3 + POI PDBs plus E3-ligand/POI-ligand SDFs; LondonLab repo [18]. A 2025 Sci. Rep. benchmark (36 crystallographic ternary complexes, DockQ) reports **PRosettaC outperforms AlphaFold3** for ternary modeling [19].
- **DeepTernary** — end-to-end SE(3)-equivariant deep learning approach for ternary complex prediction (Nat. Commun. 2025, DOI 10.1038/s41467-025-61272-5); code with predict.py, released ternary PDBs and training data [20][21].
- **PROTACable** — end-to-end in-silico toolkit: Stage I warhead docking/elaboration, Stage II POI–E3 docking + pose filtering, Stage III linker ligation + pose filtering, Stage IV SE(3)-transformer score prediction (JCIM 2024, DOI 10.1021/acs.jcim.3c01878) [22][23].
- **TERNIFY** — efficient sampling of PROTAC-induced ternary complexes (C++; bioRxiv 2024.10.30.619573) [24][25].
- **PROflow** — iterative refinement model for PROTAC ternary complexes from protein–protein docking simplification (arXiv 2405.06654) [26].
- **PROTACFold** — toolkit analyzing/predicting PROTAC structures via AlphaFold3 and Boltz-1 (GitHub) [27]. Independent evaluation of AF3/Boltz-1 for PROTAC ternary prediction: Digital Discovery 2025 [28].
- **MEGA-PROTAC** — MEGADOCK-based ternary complex modeling with linker screening (Sci. Rep. 2024, s41598-024-83558-2) [29].
- **karanicolaslab/PROTAC_ternary** — protein–protein docking (ZDOCK-era protocol) + linker-conformer screening for ternary ensembles [30].
- **PRODE (PROTAC-Design-Evaluator)** — protein–protein docking-based design evaluator (PMC10955709) [31].
- **Benchmarks:** "Benchmarking methods for PROTAC ternary complex structure prediction" (JCIM 2024, DOI 10.1021/acs.jcim.4c00426; data at ERovers/PROTAC_ternary_complex_benchmark) and "Benchmarking of PROTAC docking and virtual screening tools" (bioRxiv 2023.08.30.555318) [32][33][34].

### 1.3 Generative design (PROTACs, linkers, molecular glues)

- **SynGlue** — generative-AI platform (fragment-based + data-driven + structure-guided) for PROTACs and multi-target molecules; GROVER embeddings per component → multi-task transformer → RF heads; the-ahuja-lab/SynGlue; bioRxiv 2025.08.28.672835 [35][36].
- **PROTAC-RL** — deep reinforcement-learning generative model for rational PROTAC design in low-resource settings (Nat. Mach. Intell. 2022, s42256-022-00527-y) [37].
- **Link-INVENT** — REINVENT extension for fragment linking/scaffold hopping/PROTAC linker generation with RL (Digital Discovery 2023, D2DD00115B) [38].
- **ShapeLinker** — shape-conditioned de novo linker design (RL + attention-based point-cloud alignment; arXiv 2306.08166) [39].
- **AIMLinker** — deep encoder-decoder for fragment linker prediction for PROTAC design (JCIM 2023, DOI 10.1021/acs.jcim.2c01287; PROTAC-DB+ZINC training) [40][41].
- **DiffPROTACs** — diffusion-based PROTAC/linker generator (2024, PMID 39101502) [42].
- **LM-PROTAC** — language-model-driven PROTAC generation with structure+property dual constraints (arXiv 2412.09661) [43].
- **ProLinker-Generator** — PROTAC linker generation via transfer + reinforcement learning (Appl. Sci. 2025, 15(10):5616) [44].
- **Protac-invent** — 3D-based generative PROTAC linker design with RL built on REINVENT/DockStream [45].
- **protacSpace** — graph-based generative model proposing novel PROTAC-like molecules (arXiv 2211.02660) [46].
- **DeepDegradome** — structure-aware DL framework for PROTAC *and ligand* generation against targets lacking defined binding sites (2025, PMID 41818153) [47].
- **Cloned-but-unconnected locally:** ProtacGPT (generative PROTAC GPT-style model), protacSpace, Protac-invent, PROTAC-RL, AIMLinker (see Part 2) [45][46][37][40].

### 1.4 Docking (warhead, E3 ligand, full PROTAC)

- No dedicated "PROTAC docking" engine dominates; the field uses warhead docking (Vina/Glide-type), protein–protein docking (MEGADOCK/FRODOCK/ZDOCK/LightDock/RosettaDock) and PROTAC-conformer-constrained docking inside pipelines: PROTACable Stage I–III [23], PROTAC-Model [17], P4ward [14], MEGA-PROTAC [29], karanicolaslab/PROTAC_ternary [30], PRODE [31]. Benchmark evidence: PROTAC docking/virtual-screening benchmark (bioRxiv 2023) [34]; ternary-structure benchmark (JCIM 2024) [32].
- **PROTACability** — rational prediction of PROTAC-compatible ligase–target interfaces via restraint-based LightDock + energy rescoring + SASA-distance filtering (Nextflow pipeline available) [48][49].

### 1.5 E3 ligase ligand tools/datasets

- No mature standalone "E3-ligand design" tool was found; E3 ligand *libraries/datasets* are the workhorses: **PROTAC-DB** hosts downloadable E3 ligand collections (SDF/XLSX) [50][51]; SynGlue ships `e3_ligand.csv` (118 rows with Uniprot, IC50/EC50/Kd, article DOI, ChEMBL/BindingDB/PubChem IDs) [36][52]; PROTAC-DB 3.0 reports 107 E3 ligands within 9,380 entries [8][51]. Structure-based E3 ligand *discovery* is typically done with standard docking tools against CRBN/VHL/other ligase pockets (inference, no single named tool found). ProtacPilot locally built a 114-row/19-E3-group library from SynGlue's `e3_ligand.csv` [52].

### 1.6 ADMET-for-bRo5

- **ADMET-AI** — Chemprop(-RDKit) models trained on 41 TDC ADMET datasets (v2: 106+ endpoints); CLI/Python/web; MIT; widely used for large libraries incl. PROTAC-size molecules [53][54][55].
- **Chamelogk** — chromatographic chameleonicity quantifier to design orally bioavailable bRo5 drugs (JMC 2023, DOI 10.1021/acs.jmedchem.3c00823) [56].
- **Chameleonicity methodology** — environment-dependent conformer ensembles (MD in explicit solvent) predicting EPSA/polarity and H-bond donor exposure for bRo5 (ChemMedChem 2021); EPSA-to-TPSA ratio (ETR) + explainable ML for chameleonicity hot spots (2025) [57][58].
- **Conformer sampling for bRo5:** CREST (GFN-xTB-based conformer–rotamer ensemble sampling, open source) [59]; CONFORGE high-quality conformer generation [60].
- **Property-based oral-PROTAC optimization reviews:** RSC Med. Chem. 2025 (tailored ADME approach for heterobifunctional degraders) [61]; PubMed 37279490 (physicochemical determinants of oral absorption, rat IV/PO dataset) [62]; "Property-based optimisation of PROTACs" (RSC Med. Chem. 2025) [63]; Designing Soluble PROTACs (Drug Discov. Today 2023) [64]. Clinical context: of 13 disclosed clinical PROTACs (~July 2024), 12 engage CRBN, one (DT-2216) VHL [63].

### 1.7 Retrosynthesis

- **AiZynthFinder** — open-source retrosynthetic planning via neural-network-guided Monte-Carlo tree search to purchasable precursors; multiple search algorithms (MCTS, Retro*), filter policies, scoring framework; J. Cheminform. 2020 (10.1186/s13321-020-00472-1) and 4.0 update 2024 (10.1186/s13321-024-00860-x); models from figshare/Zenodo (USPTO policy/templates, ZINC stock) [65][66][67].

### 1.8 Agentic / automated design platforms

- **ProtacPilot** (local, this repo) — the most complete *PROTAC-specific* agentic platform found in this survey (see Part 2).
- **FROGENT** — end-to-end full-process drug design agent using LLM + Model Context Protocol to integrate biochemical databases and tool libraries (arXiv 2508.10760) [68].
- **Tippy** — multi-agent framework (Supervisor/Molecule/Lab/Analysis/Report + safety guardrail) for the DMTA cycle (arXiv 2507.09023) [69].
- **MADD** — Multi-Agent Drug Discovery Orchestra (LLM multi-agent virtual screening; EMNLP Findings 2025) [70].
- **LLM agent for modular drug-discovery task execution** — LLM-driven framework for retrieval, RAG Q&A, molecular generation, multi-property prediction, refinement, 3D structure generation (arXiv 2507.02925) [71].
- **PROTAC Design Agent** (mdbabumiamssm skills repo) — SKILL.md-style agent spec integrating ternary prediction, linker optimization, ADMET modeling; production-category listing, Dec 2025 [72].
- **SynGlue itself** is described as an AI-driven "designer" platform (bioRxiv 2025) [35].

### 1.9 Key databases

- **PROTAC-DB** (Zhejiang Univ., cadd.zju.edu.cn/protacdb) — public degrader database: PROTACs, warheads, E3 ligands, linkers, molecular glues, XTACs; DC50/Dmax, binding, cellular activities; v3.0 ~9,380–15,502 entries depending on count method (3.0 paper: NAR 2025) [50][51][8]. ProtacPilot uses the 15,502-row PROTAC-DB 3.0 xlsx locally [13].
- **PROTAC-8K** (Zenodo) — supervised DegradeMaster benchmark set from PROTAC-DB 3.0 [9].

---

## Part 2 — Local ProtacPilot inventory: what runs for real vs stub

Sources for this section: `ASSET_MANIFEST.md` [73], `RELEASE_CLOSURE_REPORT.md` [13], `CHANGELOG.md` [74], `real_nodes.py` [75], `p4ward_wrapper.py` [76], `ternary_ensemble.py` [77], `synglue_degradation.py` [78], `protac_repo_tool_wrappers.py` [79], tools directory listing [80].

### 2.1 Runs for real (verified by code read + release/changelog records)

| Local capability | Implementation | Status evidence |
|---|---|---|
| Degradation endpoint (DC50+Dmax+class) | Chemprop D-MPNN: 3-member conformal-calibrated ensemble (`chemprop_cal_ensemble_seed{0,1,2}`) + multi-target model (`chemprop_multitarget`), trained on PROTAC-DB 3.0 (1,698/1,126 rows, scaffold split) | Real trained models committed in-repo; container run produced DC50=33.9 nM, Dmax=80% [13][73] |
| SynGlue degradation fallback | GROVER 4,800-dim embeddings per component → multi-task transformer (9M params, in-repo) → RF heads | Real when `grover_fixed.pt` present (409 MB, not committable → bootstrap); else labelled fallback to chemprop→heuristic [73][78] |
| Ternary ensemble (≥2 independent methods) | geometric proxy + P4ward (Docker/local) + SE3-PROTACs (pretrained weights + ESM2-t6_8M) with staged escalation, consensus, human gate | Real; HMGB2-ICM run surfaced genuine proxy-vs-SE3 disagreement → AMBIGUOUS → human gate [13][74][77] |
| P4ward wrapper | Full config generation (MEGADOCK 3,600/162,000 poses, RxDock scoring, lysine accessibility, CRL filter), Docker `paulajlr/p4ward` or local mode, batch/multi-linker screening, failure diagnosis | Real wrapper; HMGB2 linker campaign ran 5 P4ward run dirs (16 linkers × 3,600 MegaDock poses) [74][76] |
| SE3-PROTACs score | `se3_protacs_score()` loads `SE(3)-PROTACs.pt` (cloned repo + bootstrap) + ESM embeddings | Real when weights present; `weights_missing` error surfaced gracefully otherwise [77][73] |
| Retrosynthesis | RAscore prescreen + AiZynthFinder MCTS route search (USPTO ONNX stereo policy + templates + ZINC stock, 738 MB), route-quality + routing (feasible/repairable/human) | Real on host (verified aspirin → 1-step purchasable route; real PROTAC → honest human_required); container runs RAscore/SAScore-only (aizynthfinder omitted, numpy<2 conflict) [13][74][73] |
| ADMET | ADMET-AI 2.0.1 (106 endpoints) via isolated venv subprocess + adme-py rules + OpenADMET imports; composite penalty 0.50·AMES+0.30·DILI+0.20·hERG | Real (ADMET-AI verified live per changelog 2026-08-08) [74][81] |
| E3-context engine | Deterministic evidence scoring (expression/colocalization/ligand/structural/resistance) with per-component refs; CRBN-vs-VHL verbatim requirement verified | Real (8 tests) [13][82] |
| E3 ligand library | 114 rows / 19 E3 groups (cIAP1/2, XIAP, MDM2, DCAF*, KEAP1, RNF4/114/126, KLHL20, KLHDC2, FEM1B, FBXO22, AhR, SKP1, UBR + CRBN/VHL) generated from SynGlue `e3_ligand.csv` (118 rows with DOI/UniProt/activity provenance) | Real local data + builder script; e2e MDM2-recruiting scenario passes [74][52] |
| Warhead/binder retrieval | Live ChEMBL target search + /activity (normalized nM/pIC50), local fallback; BindingDB key-gated (local TSV loader only) | Live ChEMBL verified (90 BRD4 binders in 9s) [74]; BindingDB live API **not implemented** [83] |
| Construction/validation | RDKit BRICS/RECAP constructor + fragment-combination linkers (64-linker generator) + SMILES validation | Real [74][75] |
| Novelty | Local Morgan similarity + live PubChem PUG-View patent cross-ref | Live verified (aspirin → 14 patents) [74] |
| Ranking | NSGA-II Pareto on [logDC50, dmax_inv, admet, synthesis, ternary] | Real (7 tests) [74] |
| LLM layer | Ollama gpt-oss:20b (host 11435), 6 roles, schema-enforced, deterministic validators, provider-agnostic gateway (openai/openrouter/anthropic/google/ollama) | Live 17/17 case bank, 0 safety violations [13][74] |
| Agentic runtime | LangGraph StateGraph, PostgresSaver checkpointer, redis/sqlite job queue, per-run trace.jsonl, 3-store memory, docker-compose stack | Boot-tested end-to-end; 20 checkpoints persisted; e2e 6/6 scenarios [13][74] |

### 2.2 Stub / degraded / not-connected (honest list)

- **`exit_vector_detection` node** in `real_nodes.py` is explicitly a stub: returns `{"exit_vectors": [], "evidence": {"exit_vector": {"status": "not_run"}}}` [75]. (The standalone `exit_vector_detector.py` tool exists but is not wired into this graph node.)
- **`supervisor` and `safety` nodes** in `real_nodes.py` are lambda passthroughs (`status: ok`) — LLM supervisor/safety logic lives in the separate `llm/` layer, not in these graph nodes [75].
- **29 cloned repos in `data/protac_repos/repos/`** (DeepPROTACs, PROTAC-Model, PRosettaC→(`PROTAC`?), PROTACable, PROTAC-STAN, SE3-protacs, SynGlue, TERNIFY, MEGA-PROTAC, PROTACFold, ProtacGPT, protacSpace, Protac-invent, PROTAC-RL, AIMLinker, degradomap, PROTAC-Splitter, Bellerophon, PROTACability, PRODE, etc.): most are **metadata/status-only** — `protac_repo_tool_wrappers.py` marks heavy workflows (MEGA-PROTAC, PROTACFold, SE3-protacs, TERNIFY modeling, PROTAC-Degradation-Predictor inference, Machine-Learning-for-Predicting-Targeted-Protein-Degradation, ProtacGPT, protacSpace, Bellerophon) as **manual-only / not connected**; safe capabilities only (CSV loaders, example catalogs, input validation) [79]. Only SE3-protacs (via `ternary_ensemble.py`) and SynGlue models are actually executed.
- **P4ward `_construct_protac_smiles`** is a documented placeholder (SMILES string concatenation) — real construction happens in the RDKit toolbox instead [76].
- **P4ward `discover_synglue_models`/`predict_degradation_with_model`** fall back to a heuristic MW/TPSA/RotB scorer when no trained model is found (labelled `heuristic_proxy`) [76].
- **Container degradation:** aizynthfinder omitted in the container image (RAscore-only retrosynthesis) [13]; SE3 weights and grover_fixed.pt require bootstrap/retrain (documented degradation table in ASSET_MANIFEST) [73].
- **Cellular context** is curated (literature/CCLE-derived), not live DepMap/Open Targets/COSMIC (no API keys) [13].
- **Historical note:** before 2026-08-11 the agentic runtime defaulted to `_default_stub_agents()` (stub candidates); the E2E milestone re-wired the graph to `real_nodes.py` — this is fixed and regression-tested [74].

### 2.3 Gap analysis vs external landscape (inference)

- Not wrapped locally: DeepPROTACs model, PROTAC-Model, PRosettaC, DeepTernary, TERNIFY modeling, PROTAC-STAN, DegradeMaster/PROTAC-8K, Link-INVENT/ShapeLinker/DiffPROTACs/LM-PROTAC generative linkers (only curated+fragment linkers are used), Chamelogk/ETR chameleonicity (ADMET-AI only), CREST/CONFORGE conformer sampling.
- Local coverage is strongest on: degradation (trained chemprop+SynGlue), ternary (proxy+P4ward+SE3), retrosynthesis (AiZynthFinder), ADMET (ADMET-AI), E3 context/library, agentic orchestration. Weakest: generative de novo linker/whole-molecule design (no RL/diffusion/transformer generative model wired), docking (Vina pipeline present but no live-verified run in changelog), molecular glue design (none).

---

## Evidence table

| # | Source | URL | Key claim | Type | Confidence |
|---|--------|-----|-----------|------|------------|
| 1 | DeepPROTACs paper (Nat Commun 2022) | https://www.nature.com/articles/s41467-022-34807-3 | DL targeted degradation predictor from target/E3 pocket + ligand/linker structures; trained on PROTAC-DB data | primary | high |
| 2 | DeepPROTACs GitHub | https://github.com/Fenglei104/DeepPROTACs | Reproduces Nat Commun 2022 experiments; web service at bailab.siais.shanghaitech.edu.cn/services/deepprotacs/ | primary (code) | high |
| 3 | DeepPROTACs PMC | https://pmc.ncbi.nlm.nih.gov/articles/PMC9681730/ | Full text of Nat Commun 2022 paper | primary | high |
| 4 | PROTAC-STAN GitHub | https://github.com/PROTACs/PROTAC-STAN | Interpretable structure-informed deep ternary attention network; Adv. Sci. 2025 (10.1002/advs.202508138) | primary (code) | high |
| 5 | PROTAC-STAN paper (Adv Sci) DOI | https://doi.org/10.1002/advs.202508138 | First structure-informed + interpretable PROTAC degradation model | primary | medium (via repo + abstract) |
| 6 | PROTAC-STAN PMC | https://pmc.ncbi.nlm.nih.gov/articles/PMC12713099/ | Peer-reviewed full text | primary | high |
| 7 | DegradeMaster GitHub | https://github.com/ABILiLab/DegradeMaster | Semi-supervised E(3)-equivariant GNN degradation predictor; trains/evaluates on PROTAC-8K | primary (code) | high |
| 8 | DegradeMaster bioRxiv | https://www.biorxiv.org/content/10.1101/2025.02.03.636343v1 | Method + PROTAC-DB 3.0 curation (9,380 entries, 569 warheads, 107 E3 ligands, 5,753 linkers) | primary | high |
| 9 | PROTAC-8K dataset (Zenodo) | https://zenodo.org/records/14728925 | Supervised benchmark set from PROTAC-DB 3.0 (620 high-activity etc.) | primary (data) | high |
| 10 | SE(3)-PROTACs paper (Brief Bioinform 2023) | https://www.ovid.com/journals/brbio/fulltext/10.1093/bib/bbag228~se3-protacs-geometric-deep-learning-for-protac-degradation | Geometric DL for PROTAC degradation prediction from ternary structure; code at github.com/drugparadigm/SE3-protacs | primary | high |
| 11 | drugparadigm/SE3-protacs (via ASSET_MANIFEST + paper) | https://github.com/drugparadigm/SE3-protacs | Repo + pretrained SE(3)-PROTACs.pt (referenced by both the paper and local manifest) | primary | medium (repo URL not directly fetched; confirmed in paper text + manifest) |
| 12 | ribesstefano/PROTAC-Degradation-Predictor | https://github.com/ribesstefano/PROTAC-Degradation-Predictor | ML degradation-activity predictor; companion CSBJ 2024 paper | primary (code) | medium |
| 13 | RELEASE_CLOSURE_REPORT.md (local) | /storage/saveena/protacpilot/RELEASE_CLOSURE_REPORT.md | Local benchmark: chemprop ρ=0.758→0.783 vs heuristic 0.42; 293 tests; container boot-test results | self-reported (primary local) | high (local artifact) |
| 14 | P4ward GitHub | https://github.com/SKTeamLab/P4ward | Automated PROTAC ternary complex modeling from binary complexes + PROTAC 2D; MEGADOCK+RxDock | primary (code) | high |
| 15 | P4ward paper DOI | https://doi.org/10.1021/acs.jcim.5c00614 | J. Chem. Inf. Model. 2025, 65(16), 8806–8818 (cited in local wrapper) | primary | medium (not fetched directly) |
| 16 | PROTAC-Model paper (JMC 2021) | https://pubs.acs.org/doi/full/10.1021/acs.jmedchem.1c01576 | FRODOCK + RosettaDock integrative ternary modeling | primary | medium (abstract-level) |
| 17 | gaoqiweng/PROTAC-Model | https://github.com/gaoqiweng/PROTAC-Model | Code + dependency list (Python 2.7, ADFRsuite, Vina, FRODOCK, Rosetta) | primary (code) | high |
| 18 | LondonLab/PRosettaC | https://github.com/LondonLab/PRosettaC | Rosetta-based PROTAC ternary modeling; E3/POI PDB + ligand SDFs | primary (code) | high |
| 19 | PRosettaC vs AlphaFold3 (Sci Rep 2025) | https://www.nature.com/articles/s41598-025-21502-8 | Benchmark of 36 crystallographic ternary complexes; PRosettaC outperforms AF3 on DockQ | primary | high |
| 20 | DeepTernary paper (Nat Commun 2025) | https://www.nature.com/articles/s41467-025-61272-5 | End-to-end SE(3)-equivariant ternary complex prediction for TPD | primary | high |
| 21 | youqingxiaozhua/DeepTernary | https://github.com/youqingxiaozhua/DeepTernary | Code, predict.py, ternary PDBs, preprocessed training data | primary (code) | high |
| 22 | PROTACable paper (JCIM 2024) | https://pubs.acs.org/doi/10.1021/acs.jcim.3c01878 | End-to-end de novo PROTAC design pipeline (docking→SE(3) score) | primary | medium (abstract-level) |
| 23 | giaguaro/PROTACable | https://github.com/giaguaro/PROTACable | 4-stage pipeline implementation (docking, POI-E3 docking, linker ligation, SE(3) scoring) | primary (code) | high |
| 24 | TERNIFY preprint | https://www.biorxiv.org/content/10.1101/2024.10.30.619573v1 | Efficient sampling of PROTAC-induced ternary complexes | primary | high |
| 25 | WIMNZhao/TERNIFY | https://github.com/WIMNZhao/TERNIFY | C++ implementation + example data | primary (code) | medium |
| 26 | PROflow (arXiv 2405.06654) | https://arxiv.org/html/2405.06654v1 | Iterative refinement for PROTAC ternary prediction | primary | medium |
| 27 | NilsDunlop/PROTACFold | https://github.com/NilsDunlop/PROTACFold/ | AF3/Boltz-1 toolkit for PROTAC ternary structure prediction/analysis | primary (code) | medium |
| 28 | AF3 & Boltz-1 PROTAC ternary (Digital Discovery 2025) | https://pubs.rsc.org/en/content/articlehtml/2025/dd/d5dd00300h | Assessment of AF3/Boltz-1 for ligand-mediated ternary complexes | primary | medium |
| 29 | MEGA-PROTAC (Sci Rep 2024) | https://www.nature.com/articles/s41598-024-83558-2 | MEGADOCK-based ternary modeling + linker screening | primary | medium |
| 30 | karanicolaslab/PROTAC_ternary | https://github.com/karanicolaslab/PROTAC_ternary | PPI docking + linker-conformer screening for ternary ensembles | primary (code) | medium |
| 31 | PRODE (PMC10955709) | https://pmc.ncbi.nlm.nih.gov/articles/PMC10955709/ | PROTAC-Design-Evaluator: protein-protein docking-based design evaluation | primary | medium |
| 32 | Ternary benchmark (JCIM 2024) | https://pubs.acs.org/doi/10.1021/acs.jcim.4c00426 | Benchmarks ternary complex structure prediction methods | primary | medium (abstract-level) |
| 33 | ERovers/PROTAC_ternary_complex_benchmark | https://github.com/ERovers/PROTAC_ternary_complex_benchmark | Benchmark protocols + data (JCIM 2024) | primary (code) | high |
| 34 | PROTAC docking/VS benchmark (bioRxiv 2023) | https://www.biorxiv.org/content/10.1101/2023.08.30.555318v1 | Compares PROTAC design/screening methods | primary | medium |
| 35 | SynGlue paper (bioRxiv 2025) | https://www.biorxiv.org/content/10.1101/2025.08.28.672835v1 | Modular generative AI platform for multi-target therapeutics/PROTACs | primary | high |
| 36 | the-ahuja-lab/SynGlue | https://github.com/the-ahuja-lab/SynGlue | Python toolkit: generation/analysis/optimization of PROTACs & multitarget molecules | primary (code) | high |
| 37 | PROTAC-RL (Nat Mach Intell 2022) | https://www.nature.com/articles/s42256-022-00527-y | Deep RL generative model for rational PROTAC design | primary | medium (abstract-level) |
| 38 | Link-INVENT (Digital Discovery 2023) | https://pubs.rsc.org/en/content/articlehtml/2023/dd/d2dd00115b | REINVENT extension: RL generative linker design incl. PROTACs | primary | high |
| 39 | ShapeLinker (arXiv 2306.08166) | https://arxiv.org/html/2306.08166 | Shape-conditioned de novo PROTAC linker design via RL | primary | medium |
| 40 | AIMLinker paper (JCIM 2023) | https://pubs.acs.org/doi/10.1021/acs.jcim.2c01287 | Deep encoder-decoder fragment linker prediction for PROTACs | primary | medium (abstract-level) |
| 41 | AnHorn/AIMLinker | https://github.com/AnHorn/AIMLinker | Code + data (PROTAC-DB+ZINC training set) | primary (code) | high |
| 42 | DiffPROTACs (PMID 39101502) | https://pubmed.ncbi.nlm.nih.gov/39101502/ | Diffusion-based generator for PROTACs/linkers | primary | medium (abstract-level) |
| 43 | LM-PROTAC (arXiv 2412.09661) | https://doi.org/10.48550/arxiv.2412.09661 | Language-model PROTAC generation with structure+property constraints | primary | medium |
| 44 | ProLinker-Generator (Appl Sci 2025) | https://www.mdpi.com/2076-3417/15/10/5616 | PROTAC linker generation via transfer+RL | primary | medium |
| 45 | jidushanbojue/Protac-invent | https://github.com/jidushanbojue/Protac-invent | 3D-based generative PROTAC linker design (REINVENT/DockStream-based) | primary (code) | medium |
| 46 | protacSpace (arXiv 2211.02660) | https://arxiv.org/pdf/2211.02660 | Graph-based generative model for PROTAC-like molecules | primary | medium |
| 47 | DeepDegradome (PMID 41818153) | https://pubmed.ncbi.nlm.nih.gov/41818153/ | Structure-aware framework for PROTAC+ligand generation | primary | medium (abstract-level) |
| 48 | GilbertoPPereira/PROTACability | https://github.com/GilbertoPPereira/PROTACability | Prediction of PROTAC-compatible ligase-target interfaces (LightDock-based) | primary (code) | medium |
| 49 | Romumrn/PROTAC_pipeline | https://github.com/Romumrn/PROTAC_pipeline | Nextflow wrapper of the PROTACability pipeline | primary (code) | medium |
| 50 | PROTAC-DB | https://cadd.zju.edu.cn/protacdb/about | Public degrader DB (PROTACs, warheads, E3 ligands, linkers, glues, XTACs; DC50/Dmax etc.) | primary (database) | high |
| 51 | PROTAC-DB 3.0 paper (PMC) | https://pmc.ncbi.nlm.nih.gov/articles/PMC11701630/ | Updated database description | primary | high |
| 52 | e3_ligand.csv (local, from SynGlue) | /storage/saveena/protacpilot/SynGlue_Py/data/e3_ligand.csv | 118-row E3 ligand table (Uniprot, activity, article DOI, ChEMBL/BindingDB/PubChem); local library builder | primary (local data) | high |
| 53 | ADMET-AI GitHub | https://github.com/swansonk14/admet_ai | Chemprop models on 41 TDC ADMET datasets; CLI/Python/web | primary (code) | high |
| 54 | ADMET-AI paper (PMC10793392) | https://pmc.ncbi.nlm.nih.gov/articles/PMC10793392/ | ADMET-AI platform for large-scale library evaluation | primary | high |
| 55 | admet-ai v2.0.1 (PyPI) | https://pypi.org/project/admet-ai/ | v2 Chemprop models, 106 endpoints (version used locally) | primary | high |
| 56 | Chamelogk (JMC 2023) | https://pubs.acs.org/doi/full/10.1021/acs.jmedchem.3c00823 | Chromatographic chameleonicity quantifier for bRo5 design | primary | medium (abstract-level) |
| 57 | Chameleonic efficiency prediction (ChemMedChem 2021) | https://chemistry-europe.onlinelibrary.wiley.com/doi/10.1002/cmdc.202100306 | MD-based prediction of EPSA/polarity + HBD exposure for bRo5 | primary | medium |
| 58 | ETR + explainable ML chameleonicity (PMID 40367343) | https://pubmed.ncbi.nlm.nih.gov/40367343/ | EPSA-to-TPSA ratio hot-spot ML for bRo5 oral absorption | primary | medium (abstract-level) |
| 59 | CREST (crest-lab/crest) | https://github.com/crest-lab/crest | Conformer–Rotamer Ensemble Sampling Tool (GFN-xTB) for bRo5 conformers | primary (code) | high |
| 60 | CONFORGE (PMID 37624145) | https://pubmed.ncbi.nlm.nih.gov/37624145/ | High-quality conformer generation | primary | medium (abstract-level) |
| 61 | bRo5 ADME of degraders (RSC Med Chem 2025) | https://pubs.rsc.org/en/content/articlelanding/2025/md/d4md00854e | Tailored ADME/DMPK approach for heterobifunctional degraders | primary | medium |
| 62 | Oral absorption determinants (PMID 37279490) | https://pubmed.ncbi.nlm.nih.gov/37279490/ | Rat IV/PO dataset → determinants of oral absorption for PROTACs | primary | medium (abstract-level) |
| 63 | Property-based optimisation of PROTACs (RSC Med Chem 2025) | https://pmc.ncbi.nlm.nih.gov/articles/PMC11561549/ | 13 disclosed clinical PROTACs; 12 CRBN, 1 VHL (DT-2216); property analysis | primary | high |
| 64 | Designing Soluble PROTACs (Drug Discov Today 2023) | https://www.sciencedirect.com/org/science/article/pii/S1520480422007165 | Solubility strategies/guidelines for bRo5 PROTACs | primary | medium |
| 65 | AiZynthFinder v1 (J Cheminform 2020) | https://link.springer.com/article/10.1186/s13321-020-00472-1 | Neural-network-guided MCTS retrosynthesis to purchasable precursors | primary | high |
| 66 | AiZynthFinder 4.0 (J Cheminform 2024) | https://link.springer.com/article/10.1186/s13321-024-00860-x | Filters, one-step model support, scoring framework, new search algorithms | primary | high |
| 67 | MolecularAI/aizynthfinder | https://github.com/MolecularAI/aizynthfinder | Open-source tool + model downloads (figshare/Zenodo) | primary (code) | high |
| 68 | FROGENT (arXiv 2508.10760) | https://arxiv.org/html/2508.10760v1 | End-to-end full-process drug design agent (LLM + MCP) | primary | medium |
| 69 | Tippy (arXiv 2507.09023) | https://arxiv.org/html/2507.09023 | Multi-agent DMTA laboratory automation framework | primary | medium |
| 70 | MADD (EMNLP Findings 2025) | https://aclanthology.org/2025.findings-emnlp.367/ | Multi-agent LLM drug discovery orchestra | primary | medium |
| 71 | LLM agent modular drug discovery (arXiv 2507.02925) | https://arxiv.org/html/2507.02925v3 | LLM agent for retrieval/generation/prediction/3D structure tasks | primary | medium |
| 72 | PROTAC Design Agent (SKILL.md) | https://github.com/mdbabumiamssm/LLMs-Universal-Life-Science-and-Clinical-Skills-/tree/main/Skills/Generative_Drug_Design/PROTAC_Design_Agent | Production-listed agent skill spec for PROTAC design (Dec 2025) | secondary | low |
| 73 | ASSET_MANIFEST.md (local) | /storage/saveena/protacpilot/ASSET_MANIFEST.md | Asset provenance: figshare/Zenodo AiZynth models, SE3 clone, in-repo models, degradation table | self-reported (primary local) | high |
| 74 | CHANGELOG.md (local) | /storage/saveena/protacpilot/CHANGELOG.md | Full implementation history (2026-07-06 → 2026-08-12), incl. real-vs-stub fixes | self-reported (primary local) | high |
| 75 | real_nodes.py (local) | /storage/saveena/protacpilot/protacxtend/agents/real_nodes.py | Graph node wiring; exit_vector_detection = not_run stub; supervisor/safety lambdas | primary (local code) | high |
| 76 | p4ward_wrapper.py (local) | /storage/saveena/protacpilot/protacxtend/tools/p4ward_wrapper.py | Real P4ward wrapper; placeholder SMILES constructor; heuristic model fallback | primary (local code) | high |
| 77 | ternary_ensemble.py (local) | /storage/saveena/protacpilot/protacxtend/tools/ternary_ensemble.py | Staged escalation proxy→P4ward→SE3; SE3 weights-missing graceful error | primary (local code) | high |
| 78 | synglue_degradation.py (local) | /storage/saveena/protacpilot/protacxtend/tools/synglue_degradation.py | GROVER→transformer→RF architecture; model locations | primary (local code) | high |
| 79 | protac_repo_tool_wrappers.py (local) | /storage/saveena/protacpilot/protacxtend/tools/protac_repo_tool_wrappers.py | Cloned repos are metadata-only/manual-only; safe capabilities only | primary (local code) | high |
| 80 | protacxtend/tools/ directory (local) | /storage/saveena/protacpilot/protacxtend/tools/ | 76 tool modules (chemprop_degradation, admet_integration, e3_context_engine, docking_pipeline, retrosynthesis, ternary_ensemble, etc.) | primary (local) | high |
| 81 | admet_integration.py (local) | /storage/saveena/protacpilot/protacxtend/tools/admet_integration.py | ADMET-AI isolated-venv subprocess + adme-py + OpenADMET | primary (local code) | high |
| 82 | e3_context_engine.py (local) | /storage/saveena/protacpilot/protacxtend/tools/e3_context_engine.py | Deterministic evidence-based E3 selection components + refs | primary (local code) | high |
| 83 | protac_component_wrappers.py (local) | /storage/saveena/protacpilot/protacxtend/tools/protac_component_wrappers.py | "BindingDB live API was not implemented; local TSV loader is the supported backend" | primary (local code) | high |

---

## Findings (summary)

1. **Degradation prediction is the most mature stage.** DeepPROTACs (2022) [1][2], PROTAC-STAN (2025) [4][5][6], DegradeMaster + PROTAC-8K (2025) [7][8][9], SE(3)-PROTACs (2023) [10][11] and PROTAC-Degradation-Predictor [12] all provide usable code; PROTAC-DB 3.0 [50][51] is the shared training substrate. Local ProtacPilot ships its own trained Chemprop ensemble on the same substrate with published-in-repo benchmarks (ρ≈0.78; 92.2% conformal coverage) [13].
2. **Ternary complex modeling is crowded and still contested.** At least 10 independent methods: P4ward [14][15], PROTAC-Model [16][17], PRosettaC [18][19], DeepTernary [20][21], PROTACable [22][23], TERNIFY [24][25], PROflow [26], PROTACFold/AF3-Boltz-1 [27][28], MEGA-PROTAC [29], karanicolaslab/PROTAC_ternary [30], PRODE [31]. Two independent 2024-25 benchmarks exist [32][33][34]; the PRosettaC-vs-AF3 study found PRosettaC superior on DockQ [19]. No single tool is ground truth — the local repo's 3-method ensemble (proxy/P4ward/SE3) with consensus + human gate [77][13] is a reasonable design response to that uncertainty (inference).
3. **Generative design splits into whole-molecule (SynGlue, PROTAC-RL, DiffPROTACs, LM-PROTAC, protacSpace, DeepDegradome) and linker-specific (Link-INVENT, ShapeLinker, AIMLinker, ProLinker-Generator, Protac-invent) approaches** [35][36][37][38][39][40][41][42][43][44][45][46][47]. This is the local repo's biggest gap: it generates linkers by curated/fragment combination only [74][75], with no RL/diffusion/LM generative model wired in.
4. **Docking is infrastructure, not a standalone tool category** — warhead docking (Vina-class), PPI docking (MEGADOCK/FRODOCK/LightDock/ZDOCK), and PROTAC-conformer-constrained scoring are embedded in the pipelines above [23][17][14][29][30][31][48][49]. Local Vina pipeline exists but no live run is recorded in the changelog [80][74].
5. **E3 ligand "tools" are really datasets** (PROTAC-DB E3 ligands [50][51], SynGlue e3_ligand.csv [52]) plus docking-against-pockets workflows; the local 114-row/19-group library built from e3_ligand.csv is comparable to what the literature uses [74][52].
6. **ADMET for bRo5 is a review+descriptor field**: ADMET-AI for general prediction [53][54][55], chameleonicity quantifiers (Chamelogk [56], MD-based EPSA/HBD prediction [57], ETR/ML [58]), conformer tools (CREST [59], CONFORGE [60]), and property-optimization guidance for oral degraders [61][62][63][64]. Local coverage = ADMET-AI + adme-py rules only; no chameleonicity module [81].
7. **Retrosynthesis = AiZynthFinder** (MCTS + USPTO policy + ZINC stock; v1 2020, v4 2024) [65][66][67]; local integration is real on host, RAscore-proxy in container [13][74].
8. **Agentic platforms are emerging but PROTAC-specific ones are rare**: local ProtacPilot is the only PROTAC-specific agentic system found with evidence of real tool execution; general drug-design agents (FROGENT, Tippy, MADD, LLM modular agents) are adjacent [68][69][70][71]; a PROTAC Design Agent skill exists as a spec [72].
9. **Honest local status** (from code + records): real = chemprop/SynGlue degradation, ternary ensemble (proxy+P4ward+SE3), AiZynthFinder, ADMET-AI, E3 context/library, ChEMBL/PubChem live lookups, NSGA-II, LLM layer, LangGraph runtime, container stack [13][73][74]. Stub/not-wired = exit_vector_detection graph node [75], supervisor/safety lambdas in the graph [75], 20+ cloned repos (metadata-only) [79], P4ward placeholder SMILES constructor [76], heuristic fallbacks [76][77], BindingDB live API [83].

---

## Sources

1. Li F, Hu Q, Zhang X et al. DeepPROTACs — Nat Commun 2022 — https://www.nature.com/articles/s41467-022-34807-3
2. Fenglei104/DeepPROTACs — https://github.com/Fenglei104/DeepPROTACs
3. DeepPROTACs — PMC9681730 — https://pmc.ncbi.nlm.nih.gov/articles/PMC9681730/
4. PROTACs/PROTAC-STAN — https://github.com/PROTACs/PROTAC-STAN
5. PROTAC-STAN — Adv Sci 2025 — https://doi.org/10.1002/advs.202508138
6. PROTAC-STAN — PMC12713099 — https://pmc.ncbi.nlm.nih.gov/articles/PMC12713099/
7. ABILiLab/DegradeMaster — https://github.com/ABILiLab/DegradeMaster
8. DegradeMaster — bioRxiv 2025 — https://www.biorxiv.org/content/10.1101/2025.02.03.636343v1
9. PROTAC-8K — Zenodo — https://zenodo.org/records/14728925
10. SE(3)-PROTACs — Brief Bioinform 2023 — https://www.ovid.com/journals/brbio/fulltext/10.1093/bib/bbag228~se3-protacs-geometric-deep-learning-for-protac-degradation
11. drugparadigm/SE3-protacs — https://github.com/drugparadigm/SE3-protacs
12. ribesstefano/PROTAC-Degradation-Predictor — https://github.com/ribesstefano/PROTAC-Degradation-Predictor
13. ProtacPilot RELEASE_CLOSURE_REPORT.md — /storage/saveena/protacpilot/RELEASE_CLOSURE_REPORT.md
14. SKTeamLab/P4ward — https://github.com/SKTeamLab/P4ward
15. P4ward — JCIM 2025 — https://doi.org/10.1021/acs.jcim.5c00614
16. PROTAC-Model — JMC 2021 — https://pubs.acs.org/doi/full/10.1021/acs.jmedchem.1c01576
17. gaoqiweng/PROTAC-Model — https://github.com/gaoqiweng/PROTAC-Model
18. LondonLab/PRosettaC — https://github.com/LondonLab/PRosettaC
19. PRosettaC outperforms AlphaFold3 — Sci Rep 2025 — https://www.nature.com/articles/s41598-025-21502-8
20. DeepTernary — Nat Commun 2025 — https://www.nature.com/articles/s41467-025-61272-5
21. youqingxiaozhua/DeepTernary — https://github.com/youqingxiaozhua/DeepTernary
22. PROTACable — JCIM 2024 — https://pubs.acs.org/doi/10.1021/acs.jcim.3c01878
23. giaguaro/PROTACable — https://github.com/giaguaro/PROTACable/
24. TERNIFY — bioRxiv 2024 — https://www.biorxiv.org/content/10.1101/2024.10.30.619573v1
25. WIMNZhao/TERNIFY — https://github.com/WIMNZhao/TERNIFY
26. PROflow — arXiv 2405.06654 — https://arxiv.org/html/2405.06654v1
27. NilsDunlop/PROTACFold — https://github.com/NilsDunlop/PROTACFold/
28. AF3 & Boltz-1 PROTAC ternary — Digital Discovery 2025 — https://pubs.rsc.org/en/content/articlehtml/2025/dd/d5dd00300h
29. MEGA-PROTAC — Sci Rep 2024 — https://www.nature.com/articles/s41598-024-83558-2
30. karanicolaslab/PROTAC_ternary — https://github.com/karanicolaslab/PROTAC_ternary
31. PRODE — PMC10955709 — https://pmc.ncbi.nlm.nih.gov/articles/PMC10955709/
32. Benchmarking methods for PROTAC ternary complex structure prediction — JCIM 2024 — https://pubs.acs.org/doi/10.1021/acs.jcim.4c00426
33. ERovers/PROTAC_ternary_complex_benchmark — https://github.com/ERovers/PROTAC_ternary_complex_benchmark
34. Benchmarking of PROTAC docking and virtual screening tools — bioRxiv 2023 — https://www.biorxiv.org/content/10.1101/2023.08.30.555318v1
35. SynGlue — bioRxiv 2025 — https://www.biorxiv.org/content/10.1101/2025.08.28.672835v1
36. the-ahuja-lab/SynGlue — https://github.com/the-ahuja-lab/SynGlue
37. PROTAC-RL — Nat Mach Intell 2022 — https://www.nature.com/articles/s42256-022-00527-y
38. Link-INVENT — Digital Discovery 2023 — https://pubs.rsc.org/en/content/articlehtml/2023/dd/d2dd00115b
39. ShapeLinker — arXiv 2306.08166 — https://arxiv.org/html/2306.08166
40. AIMLinker — JCIM 2023 — https://pubs.acs.org/doi/10.1021/acs.jcim.2c01287
41. AnHorn/AIMLinker — https://github.com/AnHorn/AIMLinker
42. DiffPROTACs — PMID 39101502 — https://pubmed.ncbi.nlm.nih.gov/39101502/
43. LM-PROTAC — arXiv 2412.09661 — https://doi.org/10.48550/arxiv.2412.09661
44. ProLinker-Generator — Appl Sci 2025 — https://www.mdpi.com/2076-3417/15/10/5616
45. jidushanbojue/Protac-invent — https://github.com/jidushanbojue/Protac-invent
46. protacSpace — arXiv 2211.02660 — https://arxiv.org/pdf/2211.02660
47. DeepDegradome — PMID 41818153 — https://pubmed.ncbi.nlm.nih.gov/41818153/
48. GilbertoPPereira/PROTACability — https://github.com/GilbertoPPereira/PROTACability
49. Romumrn/PROTAC_pipeline — https://github.com/Romumrn/PROTAC_pipeline
50. PROTAC-DB — https://cadd.zju.edu.cn/protacdb/about
51. PROTAC-DB 3.0 — PMC11701630 — https://pmc.ncbi.nlm.nih.gov/articles/PMC11701630/
52. ProtacPilot SynGlue_Py/data/e3_ligand.csv — /storage/saveena/protacpilot/SynGlue_Py/data/e3_ligand.csv
53. swansonk14/admet_ai — https://github.com/swansonk14/admet_ai
54. ADMET-AI — PMC10793392 — https://pmc.ncbi.nlm.nih.gov/articles/PMC10793392/
55. admet-ai v2.0.1 — PyPI — https://pypi.org/project/admet-ai/
56. Chamelogk — JMC 2023 — https://pubs.acs.org/doi/full/10.1021/acs.jmedchem.3c00823
57. Prediction of Chameleonic Efficiency — ChemMedChem 2021 — https://chemistry-europe.onlinelibrary.wiley.com/doi/10.1002/cmdc.202100306
58. Explainable ML for ETR and Drug Chameleonicity — PMID 40367343 — https://pubmed.ncbi.nlm.nih.gov/40367343/
59. crest-lab/crest — https://github.com/crest-lab/crest
60. CONFORGE — PMID 37624145 — https://pubmed.ncbi.nlm.nih.gov/37624145/
61. In vitro and in vivo ADME of heterobifunctional degraders — RSC Med Chem 2025 — https://pubs.rsc.org/en/content/articlelanding/2025/md/d4md00854e
62. Physicochemical Property Determinants of Oral Absorption — PMID 37279490 — https://pubmed.ncbi.nlm.nih.gov/37279490/
63. Property-based optimisation of PROTACs — PMC11561549 — https://pmc.ncbi.nlm.nih.gov/articles/PMC11561549/
64. Designing Soluble PROTACs — Drug Discov Today 2023 — https://www.sciencedirect.com/org/science/article/pii/S1520480422007165
65. AiZynthFinder — J Cheminform 2020 — https://link.springer.com/article/10.1186/s13321-020-00472-1
66. AiZynthFinder 4.0 — J Cheminform 2024 — https://link.springer.com/article/10.1186/s13321-024-00860-x
67. MolecularAI/aizynthfinder — https://github.com/MolecularAI/aizynthfinder
68. FROGENT — arXiv 2508.10760 — https://arxiv.org/html/2508.10760v1
69. Tippy — arXiv 2507.09023 — https://arxiv.org/html/2507.09023
70. MADD — EMNLP Findings 2025 — https://aclanthology.org/2025.findings-emnlp.367/
71. LLM Agent for Modular Task Execution in Drug Discovery — arXiv 2507.02925 — https://arxiv.org/html/2507.02925v3
72. PROTAC Design Agent (SKILL) — https://github.com/mdbabumiamssm/LLMs-Universal-Life-Science-and-Clinical-Skills-/tree/main/Skills/Generative_Drug_Design/PROTAC_Design_Agent
73. ProtacPilot ASSET_MANIFEST.md — /storage/saveena/protacpilot/ASSET_MANIFEST.md
74. ProtacPilot CHANGELOG.md — /storage/saveena/protacpilot/CHANGELOG.md
75. ProtacPilot protacxtend/agents/real_nodes.py — /storage/saveena/protacpilot/protacxtend/agents/real_nodes.py
76. ProtacPilot protacxtend/tools/p4ward_wrapper.py — /storage/saveena/protacpilot/protacxtend/tools/p4ward_wrapper.py
77. ProtacPilot protacxtend/tools/ternary_ensemble.py — /storage/saveena/protacpilot/protacxtend/tools/ternary_ensemble.py
78. ProtacPilot protacxtend/tools/synglue_degradation.py — /storage/saveena/protacpilot/protacxtend/tools/synglue_degradation.py
79. ProtacPilot protacxtend/tools/protac_repo_tool_wrappers.py — /storage/saveena/protacpilot/protacxtend/tools/protac_repo_tool_wrappers.py
80. ProtacPilot protacxtend/tools/ (directory) — /storage/saveena/protacpilot/protacxtend/tools/
81. ProtacPilot protacxtend/tools/admet_integration.py — /storage/saveena/protacpilot/protacxtend/tools/admet_integration.py
82. ProtacPilot protacxtend/tools/e3_context_engine.py — /storage/saveena/protacpilot/protacxtend/tools/e3_context_engine.py
83. ProtacPilot protacxtend/tools/protac_component_wrappers.py — /storage/saveena/protacpilot/protacxtend/tools/protac_component_wrappers.py

---

*End of deepresearch_B.md. Evidence table: 83 entries. External landscape: 9 stages. Local inventory: real-vs-stub tables in Part 2.*
