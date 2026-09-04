# NP-HARD PROBLEM MAP → AGENT DESIGN — making PROTACXtend the best PROTAC-design agent

**Internal plan & design doc — NOT for public presentation until each claim's gate is closed.**
Maps the 11 NP-hard PROTAC-design problems to: (A) what PROTACXtend **actually** has today
(code-verified 2026-09-03 — several rows in the draft table were wrong), (B) the agent
search strategy that attacks each problem, and (C) the design + definition-of-done to claim
"handled" honestly.

Companion docs: `CODE_REPORT_2026-09-02.md` (what was built) · `TECHNICAL_COHERENCE_REVIEW.md`
(review checklist) · `config/scientific_status.yaml` + `protacxtend/modules/PROTACXTEND_MODULE_BUILD.md`
(status gates) · `protacxtend/modules/FOLLOW_UP_TASKS.md` (open items).

---

## 1. Corrected status map (draft table vs verified reality)

| # | Problem | Draft said | **Verified today (file → state)** | Gap that remains |
|---|---|---|---|---|
| 1 | Linker optimization | Partial (scan+score) | `tools/linker_scanner.py` scan/geometry + `tools/generative_linker.py` **char-GRU trained on PROTAC-DB linkers** (`data/linkers/linker_generator.pt`) + curated 241 + rule-based + `linker_scoring.py` + evolution `propose_linker_replacement` | **No global optimizer** (BO/MCTS over the 150K space) — sampled, not optimized |
| 2 | E3 sparsity (4/600) | Partial (nominal scoring) | **Module 6 built**: 30-gene catalog × 8 evidence axes → SUPPORTED/PROMISING/EXPLORATORY/INSUFFICIENT (`e3_opportunity/rank.py`); recruiter selection in agents/E3 | **No de novo ligand design** for the ~596 others; verdicts report-gated |
| 3 | Ternary 3-body | Built | `tools/p4ward_wrapper.py` (Docker/local, batch, parses **lysine accessibility**) + `ternary_feasibility.py` SE(3) proxy; gated by `select_expensive_modeling_finalists` (node 24) | P4ward 24h/case → only top-N get it; proxy not validated vs crystal data at scale |
| 4 | Cooperativity α | Not built | **Module 3 built (surrogate)**: `cooperativity_alpha_predictor/{features,models}.py` — grouped harness **constant/ridge/RF/XGB/GP ready**; explicit "NOT a trained α predictor" | **Experimental-α dataset missing** → learned α prediction data-gated (curation task, not code) |
| 5 | Lysine proximity | Not built | **Module 2 built**: `lysine_ubiquitination_feasibility/` static-geometry scorer (SASA, ≤13 Å distance, approach angle, occlusion, ensemble productive fraction); P4ward output parser also returns lysine accessibility | **Real-PDB benchmark pending** (synthetic fixtures only today) |
| 6 | De novo PPI interface | Partial (proxy only) | geometric proxy only (`ternary_feasibility.py`) | **True interface design not built** (e.g., diffusion/energy-based generation) |
| 7 | Hook effect | Not built | **Module 1 built + VALIDATED BASELINE**: `hook_effect_modeler/core.py` three-body mass-action equilibrium (Douglass-2013 form), hook onset/severity/window, MC uncertainty; node `predict_hook_effect` (27) + CLI `dose` | Equilibrium only — **no kinetics**; not yet used as the dose-objective inside ranking |
| 8 | bRo5 Pareto | Built (descriptors) | `tools/admet_predictors.py` (hERG/AMES/DILI/CYP/Pgp/solubility/**permeability_proxy**) + `tools/pareto_ranking.py` (non-dominated sort + crowding) + `rank_candidates` | Proxy permeability (no trained permeation model); Pareto currently a **composite + front**, not explicit 3-obj interactive |
| 9 | Proteotype selectivity | Not built | **Module 5 built**: cell-context pDC50, transcriptomic (DepMap 24Q4), leg D R² 0.605 vs 0.513, 16 tests | **Proteotype leg pending** (needs quantitative proteomics matrix, not in 24Q4); unseen-line transfer not claimed |
| 10 | Stereochemistry | Built | `stereochemistry_engine.py` (detect/enumerate/assemble) + node `expand_stereoisomers` | Search doubles per center — needs **orthogonal-design pruning**, not enumeration alone at 4+ centers |
| 11 | Sparse sampling | Partial (similarity) | `novelty_checker.py` (Tanimoto vs curated known-PROTAC set) + curated DBs (PROTAC-DB 3.0, PROTACpedia); AD checks + grouped OOD splits in M4/M5 | ML extrapolation honestly bounded; needs **active acquisition + DB refresh loop** |

**Bottom line:** of the 11, we already have real machinery for 10 (all but #6), but every row has an
honest gap between "has a module" and "solves the NP-hard problem optimally". The agent design below
closes those gaps in phases.

---

## 2. Agent architecture to attack the 11 problems (what exists → what to add)

The 31-node governed graph is already a **tiered search agent** (tier = cost of evaluation):

```
Tier 0  CONSTRAINTS      parse_user_request · create_design_plan · safety_precheck          (nodes 1–4)
Tier 1  CHEAP SAMPLING   curated + rule + char-GRU generative linkers (74-method)           (nodes 10)
Tier 2  CHEAP FILTERS    RDKit validate · ADMET risk · novelty · applicability domain        (nodes 12–17)
Tier 3  FAST MODELS      degradation M4 · cell-context M5 · hook M1 (analytic) · lysine M2   (nodes 14,19)
        + FAST SURROGATES coop M3 feasibility · ternary SE(3) geometric proxy
Tier 4  EXPENSIVE EVAL   P4ward ternary (gated to finalists) + structure-backed M2/M3        (node 24→25–27)
Tier 5  DECISION         initial/final Pareto ranking · diversity clustering · evolution     (nodes 20–22, 28)
        + reflection critic + report + memory
Tier 6  LEARNING         active-learning_update node (CLI-only today) → Module-7 BO loop      (node 29)
```

Mapping problem → strategy the agent applies (all within one run via nodes 1–31):

| # | Problem | Strategy (now) | Strategy (design target) |
|---|---|---|---|
| 1 Linker | sampled design + replace-repair evolution | **surrogate-guided Bayesian optimization** over linker space (acquire on M4/pDC50 + geometry), M7 loop |
| 2 E3 | catalog + evidence verdicts | + **de novo E3-ligand design module** (warp/glue chemotypes from known warheads; only for verdict-flagged E3s) |
| 3 Ternary | gated P4ward (≤ top-N) + SE(3) proxy rank | + proxy calibration on crystal ternary set; learn when P4ward is worth 24 h |
| 4 α | feasibility surrogate | + curated binary/ternary Kd dataset → grouped ML α predictor (M3 v2) |
| 5 Lysine | static-geometry scorer | + real-PDB benchmark → calibrated filter + ensemble rotamer sampling |
| 6 PPI | proxy only | + **interface-generation track** (energy/diffusion priors) — new module M8 (long-horizon) |
| 7 Hook | analytic equilibrium | + **multiobjective dose-objective** (DC50 + Dmax + hook-margin + window) inside final ranking |
| 8 bRo5 | descriptor risk + Pareto | + trained permeability ML; explicit Pareto front export + decision weights |
| 9 Proteotype | transcriptomic M5 | + proteomics leg (when matrix available) → M5 v2 |
| 10 Stereo | enumerate | + **orthogonal-design pruning** (pick centers with best exit-vector/variance gain; cap enumeration) |
| 11 Sparse | Tanimoto + OOD gates | + active acquisition (M7) selects next experiments; DB refresh pipeline |

---

## 3. Design per problem — build order with definition-of-done

### P-A. Surrogate-guided linker + dose optimizer (closes #1, #7, partially #8, #10)
- **Module:** M7 "Active learning / experiment selection" (planned) → first deliverable: multiobjective **Bayesian/evolutionary optimizer** over (linker, stereoisomer, dose) with acquisition combining M4-pDC50, M5-context, M1 hook margin, ADMET constraints, novelty, synthetic feasibility.
- **Wiring:** new optimizer tool `tools/search/bo_optimizer.py` called from `active_learning_update` (node 29) and the CLI `/learn`; existing `ParetoResult`/`non_dominated_sort`/`crowding_distance` reused; evolution agent operators reused as the mutator for a (µ+λ) inner loop.
- **Definition of done:** on a 3-target benchmark, the optimizer finds ≥ top-10% pDC50 designs with **fewer than 5%** of the naive-scan evaluations; hook-margin Pareto front exported; reproducible run artifacts.
- **Claim gate:** "optimized linker search" only after benchmark; today's claim stays "73/74-method sampled design".

### P-B. E3 space expansion (#2) — Module 6 audit then de novo ligand track
- Close the **Module-6 status-report audit** (unblocks public claim of the catalog engine; M7 start gate).
- Design track: `e3_ligand_design` module: for verdict-flagged ligase E3s, scaffold-hop known recruiter chemotypes (lenalidomide/thalidomide/VHL/HIAP/IMiD warhead space) toward E3 pockets from PDB/AlphaFold; score by the same 8-axis evidence + docking proxy.
- **DoD:** ≥1 non-canonical E3 with a designed recruiter passing RDKit + ADMET + docking proxy; documented in `docs/CLAIMS.md` style with evidence tags.
- **Claim gate:** nothing about novel E3 ligands until then (Module 6 remains report-gated).

### P-C. Structure layer trust (#3, #5, #6)
- **Curate real-PDB ternary benchmark** (Gadd BRD4–MZ1–VHL; Bondeson-2018-style series; lysine/E2 distance ground truth) → calibrate M2 (lysine) and the SE(3) proxy (ternary) → publish "structural surrogate, PDB-calibrated" instead of "synthetic-fixture" (closes the main M2/M3 limitation).
- **DoD:** M2 + proxy AUROC/AUC vs curated poses reported on held-out PDBs; P4ward cost model ("when is 24 h worth it") in `select_expensive_modeling_finalists`.
- #6 de novo PPI: long-horizon module M8 (after M7) — internal spec only for now; no public claim.

### P-D. α prediction (#4) — data, not code
- Curation task: binary+ternary Kd pairs from SI tables (Follow-up task 2) → run the **ready grouped harness** (constant/ridge/RF/XGB/GP) → only then flip M3 to "trained α predictor, grouped-validated".

### P-E. bRo5 & Pareto polish (#8)
- Trained permeability surrogate (or honest proxy) + explicit **interactive Pareto** (potency × permeability × solubility × synthetic feasibility) with weights documented per run; `dose` objective added (P-A).

### P-F. Proteotype leg (#9)
- Acquire quantitative proteomics matrix (DepMap/CCLE when published) → M5 v2 leg E → only then "proteotype-aware".

### P-G. Sparse-sampling honesty loop (#11)
- DB refresh utility + active-acquisition tie-in (M7) so novelty/prior space stays current; keep OOD/AD gates — ML never extrapolates silently.

---

## 4. Sequencing

| Phase | Ships | Problems touched | Status today |
|---|---|---|---|
| P0 | Module-6 status-report audit (blocker for M7 + E3 claims) | #2 | **DONE 2026-09-03** (`e3_opportunity/docs/AUDIT.md` — APPROVED; config claimable-PARTIAL) |
| P1 | M7 optimizer v1 (BO + µλ evolution on dose/linker subset), wired to `/learn` + node 29 | #1 #7 #10 #11 | **DONE v1.0.0 2026-09-03** (`modules/active_learning`, 16 tests; synthetic-validated; exp loop pending) |
| P2 | Real-PDB benchmark for M2 + SE(3) proxy calibration | #3 #5 | data task |
| P3 | α dataset curation → M3 v2 grouped ML | #4 | data task |
| P4 | E3 de-novo ligand design module | #2 | not started |
| P5 | Proteomics leg (M5 v2) · trained permeability · PPI module spec (M8) | #8 #9 #6 | data/wait |

Nothing in P1–P5 is claimable until its DoD and its `config/scientific_status.yaml` row flip `public_claim: true`.

---

## 5. What must NOT go public yet (guard list)

1. "Solves linker optimization" → today: *sampled* design, no optimizer.
2. E3 verdicts (SUPPORTED/PROMISING) as validated → report-gated.
3. "Lysine/ternary validated on real structures" → synthetic fixtures only; real-PDB pending.
4. "α prediction" / "cooperativity model" → data-gated surrogate.
5. "Proteotype-aware" → transcriptomic only.
6. "Active learning / experiment selection" → CLI surface only (PARTIAL).
7. Live site URL → Pages not deployed (admin action).
8. Any metric (R² 0.605, AUROC .93) without its grouped-split regime and limitation in the same frame.

*Rule for every public sentence: status must trace to `config/scientific_status.yaml`; every number needs its validation regime in the same frame; every module needs its limitation next to it.*
