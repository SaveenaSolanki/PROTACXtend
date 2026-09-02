# PROTAC Pipeline Coverage & Gap Analysis — "What does it take to make/solve a PROTAC, and are we covering it?"

_Deep research brief · 2026-08-12 · Evidence: `outputs/deepresearch_A.md` (pipeline literature), `outputs/deepresearch_B.md` (tool landscape + local inventory), `outputs/deepresearch_C.md` (clinical/assay reality). All claims below trace to numbered sources in those three briefs (A[n], B[n], C[n])._

---

## 1. The complete "make a PROTAC" pipeline (what the science requires)

A PROTAC = warhead (POI ligand) + linker + E3-ligase ligand, forming a ternary complex that routes the target to ubiquitin-mediated degradation [A1,A3]. The full pipeline, per the literature:

| # | Stage | What it requires (evidence-based) |
|---|---|---|
| 1 | **Target + E3 pair selection** | Degradable target (ligandable surface; "PROTACtable genome" [A19]); E3 chosen by expression profile (tumor-high/normal-low), ligandability, ternary compatibility — ideally tested before chemistry (RiPA proximity assay) [A18,A52,A55]; <2% of 600+ E3s engaged is the field's own bottleneck [A18] |
| 2 | **Warhead discovery** | Any validated binder (inhibitors, covalent, fragment, DEL, display) — promiscuous warheads can still give selective degraders via linker/orientation [A83] |
| 3 | **E3 ligand discovery** | Validated affinity + structure + drug-like profile + solvent-exposed exit vector; beyond CRBN/VHL: IAP, MDM2, KEAP1, DCAF15/16/11, RNF4/114, KLHL20, KLHDC2, FEM1B, FBXO22, GID4, AhR… [A12,A69,C23] |
| 4 | **Linker design** | No universal rules; length/composition/rigidity empirical per pair; PEG 54%/alkyl 31%; minimum length; rigidity↔permeability trade-offs [A13,A42] |
| 5 | **Ternary complex & cooperativity** | α (cooperativity), K_LPT, TC half-life — **these drive potency vs degradation rate** (Amgen: DC50/AUC ↔ K_LPT r=0.76–0.98; rate ↔ α; TC half-life MZ1≈130 s) [A5,A6] |
| 6 | **Degradation prediction** | DC50, Dmax, kinetics (kdeg); DC50 ∝ Kd_ternary / (E3 expression × k_ub) [A9,A11]; cellular ≠ biochemical [A5] |
| 7 | **ADMET/PK (bRo5)** | Permeability/chameleonicity (eHBD ≤ 2 "Rule-of-oral-PROTACs"), efflux, metabolism; PAMPA/Caco-2 poorly predictive for PROTACs [A20,A22] |
| 8 | **Synthesis** | Modular/click chemistry, building blocks, solid-phase; IMiD stability (glutarimide hydrolysis/epimerization) [A13,A48,C51-C54] |
| 9 | **Experimental validation** | Ternary biophysics (ITC/SPR/AlphaScreen/native MS) → ubiquitination → cellular degradation (HiBiT kinetics) → selectivity (TMT proteomics) → DMPK → PK/PD → in vivo [C33-C45] |
| 10 | **Databases/benchmarks** | PROTAC-DB 1/2/3.0 (1,662→3,270→9,380+ entries; v3 adds PK), ELiAH/UbiDash E3 atlases, PROTAC-8K benchmark [A15-A17,C53] |

**The clinical reality check (2026):** the modality is validated — **VEPPANU (vepdegestrant) became the first FDA-approved PROTAC on 2026-05-01** (ER+/HER2− ESR1m breast cancer; VERITAC-2 mPFS 5.0 vs 2.1 mo, HR 0.57) [C1-C6]; Kymera KT-621 (STAT6): Ph1b BroADen showed 94% skin/98% blood STAT6 degradation; Ph2b BROADEN2 enrollment complete, topline YE 2026 [C9,C10]; Nurix BTK degrader in registrational Ph3 [C18]; >40 TPD candidates in clinic; among 13 disclosed clinical PROTACs (mid-2024), 12 are CRBN-recruiting, 1 VHL [A73/C23].

---

## 2. Coverage matrix — ProtacPilot vs the pipeline

Legend: 🟢 stage covered / capability present and validated locally · 🟡 partial or degraded · 🔴 absent/stub or explicit boundary (semantics differ per row: stage coverage vs capability vs boundary — flagged where relevant)

| Stage | Required (lit) | ProtacPilot now | Verdict |
|---|---|---|---|
| 1a Target resolution | UniProt/ChEMBL/PDB lookups | 🟢 Live ChEMBL target resolve + binder retrieval (90 BRD4 binders in 9 s, normalized nM/pIC50 — per changelog 2026-08-08; not re-executed this research run) | Covered |
| 1b E3 selection | 600+ E3s; expression-aware choice | 🟢 **19 E3 groups in the built library** (117 data rows across 20 raw groups in e3_ligand.csv; aggregation collapses IAP family rows): MDM2/Nutlin, KEAP1/KI-696, RNF114/Nimbolide, DCAF15, KLHL20/BTR2000…); 🟡 expression table curated (CRBN/VHL/cIAP1/MDM2), not live ELiAH/UbiDash/GTEx | **Partial → gap: tissue-aware E3 choice** |
| 2 Warhead | binders → warheads | 🟢 binder→warhead fallback + user SMILES validation; 🟡 no covalent/DEL/fragment screens (out of scope computationally) | Covered (design-side) |
| 3 E3 ligands | validated + exit vector | 🟢 library with DOI/UniProt/activity provenance; 🟡 tool-compound caveat (many are not drug-optimized [C23]); attachment point approximate | Covered w/ caveat |
| 4 Linker | empirical length/composition | 🟢 curated panel + rule-based + **fragment-combination generator** (64 diverse, RDKit-validated) + strain proxy + bounded repair; 🔴 no generative (RL/diffusion/LM) linker model wired | **Partial → gap: generative design** |
| 5 Ternary & cooperativity | α, K_LPT, TC half-life, BSA-based ranking | 🟢 3-method ensemble (geometric proxy + P4ward + SE3-PROTACs) with consensus + human gate; 🟡 no α/K_LPT/TC-half-life prediction (only plausibility scores); PRosettaC/DeepTernary not wired | **Partial → gap: cooperativity/kinetics** |
| 6 Degradation | DC50/Dmax/kdeg | 🟢 trained Chemprop ensemble (ρ=0.783 on a 64-molecule scaffold-split holdout of PROTAC-DB 3.0, heterogeneous assay labels, log-DC50; conformal coverage 92.2% vs 90% target — calibration, not accuracy) + SynGlue transformer fallback; 🟡 kinetics (kdeg) not modeled; Zhao DC50 model not implemented | **Core covered; kinetics gap** |
| 7 ADMET/PK | bRo5 permeability, chameleonicity | 🟢 ADMET-AI (106 endpoints) + rules; 🔴 no chameleonicity/eHBD/EPSA prediction (Chamelogk-class), no permeability model tuned for PROTACs | **Partial → gap: bRo5 oral-PK** |
| 8 Synthesis | route planning | 🟢 AiZynthFinder MCTS (real routes; aspirin→1-step ZINC) + RAscore proxy; 🟡 container RAscore-only | Covered |
| 9 Experimental | assays | 🔴 **none** (inherent boundary — computational platform); 🟡 we can output an experiment request spec | **Gap: wet-lab (by design)** |
| 10 Data | PROTAC-DB 3.0 | 🟢 15,502-row xlsx in-repo (PROTAC-DB 3.0 count-method variant of the paper's ~9,380 entries), benchmark-excluded training splits | Covered |
| Orchestration | agentic, auditable | 🟢 LangGraph + real nodes + AgentRunRecord + human gates + 6/6 e2e | Covered |
| Clinical/PK-PD | hook models, QSP | 🔴 no PK/PD modeling | Gap (out of core scope) |

**Honest stub list (from deepresearch_B Part 2):** `exit_vector_detection` graph node = not_run stub; supervisor/safety graph nodes = passthrough lambdas (real logic lives in the LLM layer); 20+ cloned upstream repos = metadata-only wrappers; BindingDB live API not implemented (local TSV only); P4ward SMILES constructor = placeholder (real construction in RDKit toolbox); heuristic fallbacks are labelled.

---

## 3. The gaps that matter most (prioritized)

1. **Cooperativity & kinetics (stage 5)** — the literature says α and TC half-life drive degradation rate [A5,A6]; we predict only plausibility. **Fix (re-scoped after review):** (a) add a **K_LPT-rank BSA proxy** (computed protein–protein + protein–PROTAC buried surface area from existing P4ward/SE3 poses), labeled honestly: the Amgen BSA↔K_LPT ρ=−0.8 comes from N=3 compounds in ONE SMARCA2–VHL system with near-native, MD-relaxed models — a within-series ranking aid, NOT a general score, and it predicts affinity, not rate; **α (cooperativity) is not currently predictable and must not be claimed** [A5]. (b) Do NOT wire PRosettaC as the 4th method on the current evidence: the Sci Rep 2025 benchmark gave AF3 sequence-only inputs (no ligand), PRosettaC failed 11/36 systems, ΔDockQ was modest (+0.11), and Rosetta energy cannot rank its own outputs without ground-truth structures [B19]. Preferred: DeepTernary (end-to-end, released weights) or a PROTACable Stage-IV-style score, gated behind an interface-aware pose filter; add an effort table (binaries/weights/GPU) before any new ensemble member — this is not a 'code-only' change.
2. **Generative de novo design (stage 4)** — curated+fragment linkers only. **Fix:** wire a generative linker model (Link-INVENT [B38], AIMLinker [B40], or the SynGlue generative path already cloned locally [B36]) — with a stated budget: SynGlue's grover_fixed.pt is 409 MB (not committable), weights/training + an evaluation protocol are required; this is a weeks-scale milestone, not code-only.
3. **CRBN-neosubstrate & off-target degradation risk (NEW, from review)** — ~90% of clinical PROTACs recruit CRBN, which degrades neosubstrates (IKZF1/Aiolos, GSPT1, CK1α, SALL4) → hematotoxicity; IMiD scaffolds and promiscuous warheads amplify off-target degradation [A23,A37,C51,C53,C56]. **Fix (low effort, high value):** knowledge-based risk flag in the E3 node — E3-ligand identity + warhead similarity vs known neosubstrate/off-target lists — before any CRBN-based recommendation is finalized.
4. **bRo5 oral-PK (stage 7)** — the #1 clinical failure mode after efficacy [A46,A60]. **Fix:** add chameleonicity descriptors (eHBD proxy via RDKit conformers or Chamelogk [B56]), permeability flag for PROTAC-size molecules.
5. **Tissue-aware E3 selection (stage 1b)** — curated table only. **Fix:** wire ELiAH [A54]/UbiDash [A53] expression data (or a GTEx-derived static snapshot) into the E3-context engine.
6. **Degradation kinetics (stage 6)** — implement the Zhao model (DC50 ∝ Kd_ternary/(E3·k_ub)) using our predictions + expression [A11].
7. **Wet-lab boundary** — define an "experiment request card" (HiBiT kinetics + ternary SPR + TMT proteomics protocol spec) as the platform's handoff artifact to a lab [C33-C45].
8. **Field-level gap (not ours):** no PROTAC-specific hERG datasets exist publicly [A-residual]; treat as regulatory-panel input.

---

## 4. Bottom line

**On the computational design side: ProtacPilot covers ~7 of 10 stages with real, verified tools** (target/binder, E3 library now 19 groups, linker enumeration, ternary ensemble, trained degradation, ADMET-AI, retrosynthesis, agentic orchestration + audit trail) — the only PROTAC-specific agentic platform found in this survey with evidence of real tool execution (small comparator set; not an external benchmark) [B8-finding]. **Not yet covered:** (1) cooperativity/kinetic ternary prediction, (2) generative de novo design, (3) bRo5 chameleonicity/PK prediction, (4) live tissue-aware E3 atlases, (5) degradation kinetics, (6) any wet-lab validation (inherent boundary — the platform is a design engine, not a lab). **Recommended milestone order (feasibility-ordered):** (1) K_LPT-rank BSA proxy (with its within-series caveats) + the neosubstrate/off-target risk flag — cheap, code-mostly, clinically relevant; (2) tissue-aware E3 static snapshot (GTEx-derived median expression per E3, tumor-vs-normal) — bypasses API keys [A54]; (3) Zhao degradation-kinetics model (DC50 ∝ Kd_ternary/(E3·k_ub)) — closed-form on existing outputs [A11]; (4) generative linker model, costed; (5) bRo5 chameleonicity; (6) experiment-request card (which also documents the PK-PD/hook-model handoff [C43,C44] and the resistance-aware E3/CRBN assessment [A33,A85] as deliberate out-of-scope boundaries).

---

## Provenance

- `outputs/deepresearch_A.md` — pipeline literature (86+ sources; Burslem & Crews Cell 2020, Amgen Nat Commun 2023, linker reviews, PROTAC-DB papers, E3 landscape).
- `outputs/deepresearch_B.md` — tool landscape (83 sources; DeepPROTACs, P4ward, SE3-PROTACs, PRosettaC, DeepTernary, PROTACable, TERNIFY, SynGlue, Link-INVENT, ADMET-AI, AiZynthFinder…) + local real-vs-stub inventory from repo files.
- `outputs/deepresearch_C.md` — clinical/assay reality (61 sources; FDA/Arvinas/Kymera/C4/Nurix, E3 ligand tables, assay stack, failure modes).
- Verifier + reviewer passes: pending (next step).
