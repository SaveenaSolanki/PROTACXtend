# PROTAC Pipeline Coverage & Gap Analysis — "What does it take to make/solve a PROTAC, and are we covering it?"

_Deep research brief · 2026-08-12 · Evidence: `outputs/deepresearch_A.md` (pipeline literature), `outputs/deepresearch_B.md` (tool landscape + local inventory), `outputs/deepresearch_C.md` (clinical/assay reality). All claims below carry inline citations to the unified Sources list (each entry maps to a numbered source in one of the three briefs; URLs spot-verified by the verifier pass where marked)._

---

## 1. The complete "make a PROTAC" pipeline (what the science requires)

A PROTAC = warhead (POI ligand) + linker + E3-ligase ligand, forming a ternary complex that routes the target to ubiquitin-mediated degradation [1,2]. The full pipeline, per the literature:

| # | Stage | What it requires (evidence-based) |
|---|---|---|
| 1 | **Target + E3 pair selection** | Degradable target (ligandable surface; "PROTACtable genome" [3]); E3 chosen by expression profile (tumor-high/normal-low), ligandability, ternary compatibility — ideally tested before chemistry (RiPA proximity assay) [4,5,6]; <2% of 600+ E3s engaged is the field's own bottleneck [4] |
| 2 | **Warhead discovery** | Any validated binder (inhibitors, covalent, fragment, DEL, display) — promiscuous warheads can still give selective degraders via linker/orientation [7] |
| 3 | **E3 ligand discovery** | Validated affinity + structure + drug-like profile + solvent-exposed exit vector; beyond CRBN/VHL: IAP, MDM2, KEAP1, DCAF15/16/11, RNF4/114, KLHL20, KLHDC2, FEM1B, FBXO22, GID4, AhR… [8,9,10] |
| 4 | **Linker design** | No universal rules; length/composition/rigidity empirical per pair; PEG 54%/alkyl 31%; minimum length; rigidity↔permeability trade-offs [11,12] |
| 5 | **Ternary complex & cooperativity** | α (cooperativity), K_LPT, TC half-life — **these drive potency vs degradation rate** (Amgen: DC50/AUC ↔ K_LPT r=0.76–0.98; rate ↔ α; TC half-life MZ1≈130 s) [13,14] |
| 6 | **Degradation prediction** | DC50, Dmax, kinetics (kdeg); DC50 ∝ Kd_ternary / (E3 expression × k_ub) [15,16]; cellular ≠ biochemical [13] |
| 7 | **ADMET/PK (bRo5)** | Permeability/chameleonicity (eHBD ≤ 2 "Rule-of-oral-PROTACs"), efflux, metabolism; PAMPA/Caco-2 poorly predictive for PROTACs [17,18] |
| 8 | **Synthesis** | Modular/click chemistry, building blocks, solid-phase; IMiD stability (glutarimide hydrolysis/epimerization) [11,19,20,21,22,23] |
| 9 | **Experimental validation** | Ternary biophysics (ITC/SPR/AlphaScreen/native MS) → ubiquitination → cellular degradation (HiBiT kinetics) → selectivity (TMT proteomics) → DMPK → PK/PD → in vivo [24–34] |
| 10 | **Databases/benchmarks** | PROTAC-DB 1/2/3.0 (1,662→3,270→9,380+ entries; v3 adds PK), ELiAH/UbiDash E3 atlases, PROTAC-8K benchmark [35,36,37,38,39,40,41] |

**The clinical reality check (2026):** the modality is validated — **VEPPANU (vepdegestrant) became the first FDA-approved PROTAC on 2026-05-01** (ER+/HER2− ESR1m breast cancer; VERITAC-2 mPFS 5.0 vs 2.1 mo, HR 0.57) [42–48]; Kymera KT-621 (STAT6) in Ph2b with 94% skin/98% blood STAT6 degradation [48,49]; Nurix BTK degrader in registrational Ph3 [50]; >40 TPD candidates in clinic [51], ~90% CRBN-recruiting among disclosed clinical PROTACs (12 of 13 as of mid-2024) [52].

---

## 2. Coverage matrix — ProtacPilot vs the pipeline

Legend: 🟢 real/validated locally · 🟡 partial or degraded · 🔴 absent/stub

| Stage | Required (lit) | ProtacPilot now | Verdict |
|---|---|---|---|
| 1a Target resolution | UniProt/ChEMBL/PDB lookups | 🟢 Live ChEMBL target resolve + binder retrieval (90 BRD4 binders, 9 s, normalized nM/pIC50) [53] | Covered |
| 1b E3 selection | 600+ E3s; expression-aware choice | 🟢 **19 E3 groups** (114 cited ligands [54,55]: MDM2/Nutlin, KEAP1/KI-696, RNF114/Nimbolide, DCAF15, KLHL20/BTR2000…); 🟡 expression table curated (CRBN/VHL/cIAP1/MDM2) [56], not live ELiAH/UbiDash/GTEx [39,38] | **Partial → gap: tissue-aware E3 choice** |
| 2 Warhead | binders → warheads | 🟢 binder→warhead fallback + user SMILES validation [53]; 🟡 no covalent/DEL/fragment screens (out of scope computationally) [57] | Covered (design-side) |
| 3 E3 ligands | validated + exit vector | 🟢 library with DOI/UniProt/activity provenance [55]; 🟡 tool-compound caveat (many are not drug-optimized [10]); attachment point approximate | Covered w/ caveat |
| 4 Linker | empirical length/composition | 🟢 curated panel + rule-based + **fragment-combination generator** (64 diverse, RDKit-validated) [53] + strain proxy + bounded repair; 🔴 no generative (RL/diffusion/LM) linker model wired [57] | **Partial → gap: generative design** |
| 5 Ternary & cooperativity | α, K_LPT, TC half-life, BSA-based ranking | 🟢 3-method ensemble (geometric proxy + P4ward + SE3-PROTACs) with consensus + human gate [58,56]; 🟡 no α/K_LPT/TC-half-life prediction (only plausibility scores) [57]; PRosettaC/DeepTernary not wired [57] | **Partial → gap: cooperativity/kinetics** |
| 6 Degradation | DC50/Dmax/kdeg | 🟢 trained Chemprop ensemble (ρ=0.783, conformal 92.2%) [56] + SynGlue transformer fallback [59]; 🟡 kinetics (kdeg) not modeled; Zhao DC50 model not implemented [16] | **Core covered; kinetics gap** |
| 7 ADMET/PK | bRo5 permeability, chameleonicity | 🟢 ADMET-AI (106 endpoints) [60,61] + rules; 🔴 no chameleonicity/eHBD/EPSA prediction (Chamelogk-class [62,63]), no permeability model tuned for PROTACs | **Partial → gap: bRo5 oral-PK** |
| 8 Synthesis | route planning | 🟢 AiZynthFinder MCTS (real routes; aspirin→1-step ZINC) [64,65,66,56] + RAscore proxy; 🟡 container RAscore-only [56] | Covered |
| 9 Experimental | assays | 🔴 **none** (inherent boundary — computational platform); 🟡 experiment-request spec = *proposed handoff artifact, not yet implemented in the briefs' inventory* (content would follow the assay stack [24–34]) | **Gap: wet-lab (by design)** |
| 10 Data | PROTAC-DB 3.0 | 🟢 15,502-row xlsx in-repo, benchmark-excluded training splits [67,68,56] | Covered |
| Orchestration | agentic, auditable | 🟢 LangGraph + real nodes + AgentRunRecord + human gates + 6/6 e2e [53] | Covered |
| Clinical/PK-PD | hook models, QSP | 🔴 no PK/PD modeling (absent from the local inventory in the tool brief) | Gap (out of core scope) |

**Honest stub list (from deepresearch_B Part 2):** `exit_vector_detection` graph node = not_run stub [69]; supervisor/safety graph nodes = passthrough lambdas (real logic lives in the LLM layer) [69]; 20+ cloned upstream repos = metadata-only wrappers [57]; BindingDB live API not implemented (local TSV only) [71]; P4ward SMILES constructor = placeholder (real construction in RDKit toolbox) [70]; heuristic fallbacks are labelled [70,58].

---

## 3. The gaps that matter most (prioritized)

1. **Cooperativity & kinetics (stage 5)** — the literature says α and TC half-life drive degradation rate [13,14]; we predict only plausibility. **Fix:** (a) add a computed-BSA/α proxy to the ternary node (Amgen: BSA ↔ K_LPT ρ=−0.8 [13]); (b) wire PRosettaC (benchmarked > AlphaFold3 on DockQ [72]) or DeepTernary [73] as a 4th ensemble method.
2. **Generative de novo design (stage 4)** — curated+fragment linkers only. **Fix:** wire a generative linker model: Link-INVENT [74], AIMLinker [75], or the SynGlue generative path already cloned locally [76]; RL/diffusion options exist [77,78].
3. **bRo5 oral-PK (stage 7)** — the #1 clinical failure mode after efficacy [79,80]. **Fix:** add chameleonicity descriptors (eHBD proxy via RDKit conformers or Chamelogk [62]), permeability flag for PROTAC-size molecules.
4. **Tissue-aware E3 selection (stage 1b)** — curated table only. **Fix:** wire ELiAH [39]/UbiDash [38] expression data (or a GTEx-derived static snapshot) into the E3-context engine.
5. **Degradation kinetics (stage 6)** — implement the Zhao model (DC50 ∝ Kd_ternary/(E3·k_ub)) using our predictions + expression [16].
6. **Wet-lab boundary** — define an "experiment request card" (HiBiT kinetics + ternary SPR + TMT proteomics protocol spec) as the platform's handoff artifact to a lab [24–34].
7. **Field-level gap (not ours):** no PROTAC-specific hERG datasets exist publicly — flagged as a residual coverage gap in the pipeline literature brief [81]; treat as regulatory-panel input.

---

## 4. Bottom line

**On the computational design side: ProtacPilot covers ~7 of 10 stages with real, verified tools** (target/binder, E3 library now 19 groups [55], linker enumeration, ternary ensemble, trained degradation, ADMET-AI, retrosynthesis, agentic orchestration + audit trail) — the most complete PROTAC-specific agentic coverage found in the tool survey [87; adjacent general drug-design agents: 82–86]. **Not yet covered:** (1) cooperativity/kinetic ternary prediction, (2) generative de novo design, (3) bRo5 chameleonicity/PK prediction, (4) live tissue-aware E3 atlases, (5) degradation kinetics, (6) any wet-lab validation (inherent boundary — the platform is a design engine, not a lab). **Recommended next milestone:** close gaps 1–2 first (ternary α-proxy + one generative linker model) — they are the highest-leverage, code-only additions; then gap 4 via a GTEx/ELiAH snapshot; document gap 6 as the explicit handoff protocol.

---

## Provenance

- `outputs/deepresearch_A.md` — pipeline literature (86+ sources; Burslem & Crews Cell 2020, Amgen Nat Commun 2023, linker reviews, PROTAC-DB papers, E3 landscape).
- `outputs/deepresearch_B.md` — tool landscape (83 sources; DeepPROTACs, P4ward, SE3-PROTACs, PRosettaC, DeepTernary, PROTACable, TERNIFY, SynGlue, Link-INVENT, ADMET-AI, AiZynthFinder…) + local real-vs-stub inventory from repo files.
- `outputs/deepresearch_C.md` — clinical/assay reality (61 sources; FDA/Arvinas/Kymera/C4/Nurix, E3 ligand tables, assay stack, failure modes).
- Verifier pass (2026-08-12): every inline citation mapped to a numbered evidence-table entry in the three briefs; 10 load-bearing URLs fetched and confirmed live (FDA approval page, Arvinas PR, Kymera KT-621 AAD PR, Amgen Nat Commun 2023, PRosettaC-vs-AF3 Sci Rep, PROTAC-DB, EMA TPD report, Scott J Med Chem 2024, LondonLab/PRosettaC, MDPI Targets 2025); local quantitative claims re-verified against `RELEASE_CLOSURE_REPORT.md`, `CHANGELOG.md`, and `SynGlue_Py/data/e3_ligand.csv`.

---

## Sources

1. Burslem GM, Crews CM. Proteolysis-Targeting Chimeras as Therapeutics and Tools for Biological Discovery. Cell 2020;181(1):102–114. https://pubmed.ncbi.nlm.nih.gov/31955850/
2. Békés M, Langley DR, Crews CM. PROTAC targeted protein degraders: the past is prologue. Nat Rev Drug Discov 2022;21:181–200. https://www.nature.com/articles/s41573-021-00371-6
3. Schneider M, et al. The PROTACtable genome. Nat Rev Drug Discov 2021;20:789–797. https://www.nature.com/articles/s41573-021-00245-x
4. Zhao L, et al. Expanding PROTACtable genome universe of E3 ligases. Nat Commun 2023;14:6509. https://www.nature.com/articles/s41467-023-42233-2
5. Identification of suitable target/E3 ligase pairs for PROTAC development using a rapamycin-induced proximity assay (RiPA). eLife 2025. https://elifesciences.org/articles/98450
6. Clinical considerations for the design of PROTACs in cancer. Mol Cancer 2022;21:71. https://link.springer.com/article/10.1186/s12943-022-01535-7
7. Smith BE, et al. Differential PROTAC substrate specificity dictated by orientation of recruited E3 ligase. Nat Commun 2019;10:131. https://pubmed.ncbi.nlm.nih.gov/30631068/
8. Ishida T, Ciulli A. E3 Ligase Ligands for PROTACs: How They Were Found and How to Discover New Ones. SLAS Discov 2021;26(4):484–502. https://pmc.ncbi.nlm.nih.gov/articles/PMC8013866/
9. E3 Ligases Meet Their Match: Fragment-Based Approaches to Discover New E3 Ligands and to Unravel E3 Biology. J Med Chem 2022. https://pubs.acs.org/doi/full/10.1021/acs.jmedchem.2c01882
10. Li Z, et al. The Expanding E3 Ligase-Ligand Landscape for PROTAC Technology. Targets 2025;3(4):30. https://www.mdpi.com/2813-3137/3/4/30 *(URL fetched — live)*
11. Troup RI, Fallan C, Baud MGJ. Current strategies for the design of PROTAC linkers: a critical review. Explor Target Anti-tumor Ther 2020;1:273–312. https://pmc.ncbi.nlm.nih.gov/articles/PMC9400730/
12. Linker-Dependent Folding Rationalizes PROTAC Cell Permeability. J Med Chem 2022. https://pubs.acs.org/doi/full/10.1021/acs.jmedchem.2c00877
13. Wurz RP, et al. (Amgen). Affinity and cooperativity modulate ternary complex formation to drive targeted protein degradation. Nat Commun 2023;14:4177. https://www.nature.com/articles/s41467-023-39904-5 *(URL fetched — live; r=0.76–0.98, α-rate r=0.67/0.99, MZ1 t1/2≈130 s, BSA ρ=−0.8, α=12.8 / AU-15330 α=2 all confirmed in full text)*
14. Roy MJ, et al. SPR-Measured Dissociation Kinetics of PROTAC Ternary Complexes Influence Target Degradation Rate. ACS Chem Biol 2019;14:361–368. https://pubmed.ncbi.nlm.nih.gov/30721025/
15. Riching KM, et al. Quantitative Live-Cell Kinetic Degradation and Mechanistic Profiling of PROTAC Mode of Action. ACS Chem Biol 2018;13:2758–2770. https://pubs.acs.org/doi/full/10.1021/acschembio.8b00692
16. Zhao H. Kinetic Modeling of PROTAC-Induced Protein Degradation. ChemMedChem 2023;18(24):e202300530. https://pubmed.ncbi.nlm.nih.gov/37905604/
17. Scott JS, et al. Structural and Physicochemical Features of Oral PROTACs. J Med Chem 2024;67(15):13106–13116 (eHBD ≤ 2; "Rule-of-oral-PROTACs"). https://pubmed.ncbi.nlm.nih.gov/39078401/ *(URL fetched — live)*
18. In vitro and in vivo ADME of heterobifunctional degraders: a tailored approach to optimize DMPK properties of PROTACs. RSC Med Chem 2025. https://pubs.rsc.org/en/content/articlelanding/2025/md/d4md00854e
19. Wurz RP, et al. A "Click Chemistry Platform" for the rapid synthesis of bispecific molecules for inducing protein degradation. J Med Chem 2018;61:453–461. https://pubs.acs.org/doi/10.1021/acs.jmedchem.6b01781
20. Min J, et al. Phenyl-Glutarimides: Alternative Cereblon Binders for the Design of PROTACs. https://pmc.ncbi.nlm.nih.gov/articles/PMC8648984/
21. Influence of Linker Attachment Points on the Stability and Activity of IMiD-Containing PROTACs. https://pmc.ncbi.nlm.nih.gov/articles/PMC8591746/
22. A dihydrouracil CRBN ligand mitigates IMiD associated safety liabilities in heterobifunctional targeted protein degraders. Nat Commun 2026. https://www.nature.com/articles/s41467-026-70663-1
23. Identification and removal of a cryptic impurity in pomalidomide-PEG based PROTACs. Beilstein J Org Chem 2025. https://beilstein-journals.org/bjoc/content/pdf/1860-5397-21-28.pdf
24. JoVE 65718 — Biophysical assays for evaluating ternary complex formation induced by PROTACs. https://www.jove.com/t/65718/the-development-application-biophysical-assays-for-evaluating-ternary
25. Unveiling BCL-xL-specific PROTAC efficiency and dissociation pathways using native mass spectrometry. Chem Sci 2026. https://pubs.rsc.org/en/content/articlehtml/2026/sc/d5sc07400b
26. Assays and Technologies for Developing Proteolysis Targeting Chimera Degraders. Future Med Chem 2020. https://www.tandfonline.com/doi/full/10.4155/fmc-2020-0073
27. Revvity — AlphaLISA PROTAC application note. https://resources.revvity.com/pdfs/pbr-alphalisa-protac.pdf
28. Comparative analysis of biophysical methods for monitoring protein proximity induction in degrader development. https://www.sciencedirect.com/science/article/abs/pii/S030441652300096X
29. Promega AN331 — Kinetically Detecting and Quantitating PROTAC-Induced Degradation of Endogenous HiBiT-Tagged Target Proteins. https://www.promega.com/-/media/files/resources/application-notes/nanobret/an331.pdf
30. Workflow for E3 Ligase Ligand Validation for PROTAC Development (six-step: synthesis → DSF/Kinobeads → NanoBRET → degradation → MS proteomics). https://pmc.ncbi.nlm.nih.gov/articles/PMC11851430/
31. An In Vitro Pull-down Assay of the E3 Ligase:PROTAC:Substrate Ternary Complex to Identify Effective PROTACs. https://pubmed.ncbi.nlm.nih.gov/34432242/
32. LifeSensors — PROTAC ubiquitination assays. https://lifesensors.com/protac-ubiquitination-assays/
33. PK/PD modeling of targeted protein degraders (hook models). Drug Discov Today 2025. https://www.sciencedirect.com/science/article/pii/S1359644625000248
34. A Mechanistic Pharmacodynamic Modeling Framework for PROTACs. Pharmaceutics 2023;15(1):195. https://www.mdpi.com/1999-4923/15/1/195
35. Weng G, et al. PROTAC-DB 2.0. Nucleic Acids Res 2023;51(D1) (3,270 PROTACs). https://pmc.ncbi.nlm.nih.gov/articles/PMC9825472/
36. Ge J, et al. PROTAC-DB 3.0 with extended pharmacokinetic parameters. Nucleic Acids Res 2025;53(D1):D1510–D1515. https://pubmed.ncbi.nlm.nih.gov/39225044/
37. Weng G, et al. PROTAC-DB 1.0. Nucleic Acids Res 2021;49:D1381–D1387 (1,662 PROTACs). https://pubmed.ncbi.nlm.nih.gov/33010159/
38. UbiDash: A UPS proteomic atlas for tissue-aware degrader design. Cell Death Differ 2026. https://www.nature.com/articles/s41418-026-01791-w
39. ELiAH — E3 Ligase Atlas of Human (web resource). https://www.eliahdb.org/
40. DegradeMaster — bioRxiv 2025 (PROTAC-DB 3.0 curation: 9,380 entries). https://www.biorxiv.org/content/10.1101/2025.02.03.636343v1
41. PROTAC-8K benchmark dataset. Zenodo. https://zenodo.org/records/14728925
42. FDA — "FDA approves vepdegestrant for ER-positive, HER2-negative, ESR1-mutated advanced or metastatic breast cancer" (May 1, 2026). https://www.fda.gov/drugs/resources-information-approved-drugs/fda-approves-vepdegestrant-er-positive-her2-negative-esr1-mutated-advanced-or-metastatic-breast *(URL fetched — live; mPFS 5 vs 2.1 mo, HR 0.57 confirmed)*
43. Arvinas — "Arvinas Announces FDA Approval of VEPPANU (vepdegestrant)…" (first-and-only FDA-approved PROTAC; ahead of June 5, 2026 PDUFA). https://ir.arvinas.com/news-releases/news-release-details/arvinas-announces-fda-approval-veppanu-vepdegestrant-treatment *(URL fetched — live)*
44. Reuters — "US FDA approves Pfizer, Arvinas' breast cancer drug." https://www.reuters.com/business/healthcare-pharmaceuticals/us-fda-approves-pfizer-arvinas-breast-cancer-drug-2026-05-01/
45. SEC EDGAR — Arvinas Form 8-K (arvn-20260501). https://www.sec.gov/Archives/edgar/data/1655759/000162828026029210/arvn-20260501.htm
46. CancerNetwork — Vepdegestrant outperforms fulvestrant in PFS for ESR1-mutant advanced breast cancer (VERITAC-2; mPFS 5.0 vs 2.1 mo, HR 0.57). https://www.cancernetwork.com/view/vepdegestrant-outperforms-fulvestrant-in-pfs-for-esr1-mutant-advanced-breast-cancer
47. Hamilton E, et al. Vepdegestrant, a PROTAC Estrogen Receptor Degrader, in Advanced Breast Cancer. NEJM (VERITAC-2 design). https://www.nejm.org/doi/full/10.1056/NEJMoa2505725
48. Kymera — Q2 2026 financial results (KT-621 Ph2b BROADEN2 enrollment complete; data YE 2026). https://investors.kymeratx.com/news-releases/news-release-details/kymera-therapeutics-announces-second-quarter-2026-financial
49. Kymera — KT-621 BroADen data at AAD 2026 (median STAT6 degradation 94% skin / 98% blood; TARC −74%; EASI −63%). https://investors.kymeratx.com/news-releases/news-release-details/kymera-therapeutics-presents-kt-621-broaden-data-late-breaking *(URL fetched — live)*
50. ClinicalTrials.gov — NCT07516093 (NX-5948 bexobrutideg, registrational Ph3 DAYBreak CLL-306). https://clinicaltrials.gov/study/NCT07516093
51. EMA — "Targeted Protein Degradation (TPD) — EU-IN Horizon scanning report" ("first PROTAC has recently received FDA approval and more than 40 TPD candidates are currently in clinical development, predominantly in oncology"). https://www.ema.europa.eu/en/documents/report/targeted-protein-degradation-eu-horizon-scanning-report_en.pdf *(URL fetched — live)*
52. Property-based optimisation of PROTACs. RSC Med Chem 2025 (13 disclosed clinical PROTACs ~July 2024: 12 CRBN, 1 VHL/DT-2216). https://pmc.ncbi.nlm.nih.gov/articles/PMC11561549/
53. ProtacPilot CHANGELOG.md (local artifact: ChEMBL live 90 BRD4 binders in 9s; 64-linker generator; LangGraph e2e 6/6; aspirin→1-step route). /storage/saveena/protacpilot/CHANGELOG.md *(re-verified locally)*
54. ProtacPilot E3 ligand library status per release records (114 rows / 19 E3 groups). /storage/saveena/protacpilot/RELEASE_CLOSURE_REPORT.md (per brief B §2.1; raw CSV = 117 rows — see residual note)
55. ProtacPilot SynGlue_Py/data/e3_ligand.csv (local artifact: 118-line table, DOI/UniProt/activity provenance; contains Nutlin, KI-696, Nimbolide, BTR2000). /storage/saveena/protacpilot/SynGlue_Py/data/e3_ligand.csv *(re-verified locally)*
56. ProtacPilot RELEASE_CLOSURE_REPORT.md (local artifact: chemprop ρ=0.758→0.783 vs heuristic 0.42; 92.2% conformal coverage; 15,502-row PROTAC-DB 3.0 xlsx; DC50=33.9 nM/Dmax=80% container run; 293 tests). /storage/saveena/protacpilot/RELEASE_CLOSURE_REPORT.md *(re-verified locally)*
57. ProtacPilot protacxtend/tools/protac_repo_tool_wrappers.py (cloned repos are metadata-only/manual-only; no generative linker model wired). /storage/saveena/protacpilot/protacxtend/tools/protac_repo_tool_wrappers.py
58. ProtacPilot protacxtend/tools/ternary_ensemble.py (staged proxy→P4ward→SE3 escalation; SE3 weights-missing graceful error; heuristic fallback). /storage/saveena/protacpilot/protacxtend/tools/ternary_ensemble.py
59. ProtacPilot protacxtend/tools/synglue_degradation.py (GROVER→transformer→RF architecture). /storage/saveena/protacpilot/protacxtend/tools/synglue_degradation.py
60. admet-ai v2.0.1 — PyPI (Chemprop models, 106 endpoints). https://pypi.org/project/admet-ai/
61. ProtacPilot protacxtend/tools/admet_integration.py (ADMET-AI isolated-venv subprocess + adme-py + OpenADMET). /storage/saveena/protacpilot/protacxtend/tools/admet_integration.py
62. Chamelogk — chromatographic chameleonicity quantifier for bRo5. J Med Chem 2023. https://pubs.acs.org/doi/full/10.1021/acs.jmedchem.3c00823
63. Prediction of Chameleonic Efficiency (EPSA/polarity + HBD exposure). ChemMedChem 2021. https://chemistry-europe.onlinelibrary.wiley.com/doi/10.1002/cmdc.202100306
64. AiZynthFinder — neural-network-guided MCTS retrosynthesis. J Cheminform 2020. https://link.springer.com/article/10.1186/s13321-020-00472-1
65. AiZynthFinder 4.0. J Cheminform 2024. https://link.springer.com/article/10.1186/s13321-024-00860-x
66. MolecularAI/aizynthfinder (GitHub). https://github.com/MolecularAI/aizynthfinder
67. PROTAC-DB (web database). https://cadd.zju.edu.cn/protacdb/about *(URL fetched — live; PK parameters Tmax/T1/2/Cmax/AUC/Vz/Vss/CL/MRT/bioavailability confirmed)*
68. PROTAC-DB 3.0 — PMC11701630. https://pmc.ncbi.nlm.nih.gov/articles/PMC11701630/
69. ProtacPilot protacxtend/agents/real_nodes.py (exit_vector_detection = not_run stub; supervisor/safety lambdas). /storage/saveena/protacpilot/protacxtend/agents/real_nodes.py
70. ProtacPilot protacxtend/tools/p4ward_wrapper.py (placeholder SMILES constructor; heuristic model fallback). /storage/saveena/protacpilot/protacxtend/tools/p4ward_wrapper.py
71. ProtacPilot protacxtend/tools/protac_component_wrappers.py ("BindingDB live API was not implemented; local TSV loader is the supported backend"). /storage/saveena/protacpilot/protacxtend/tools/protac_component_wrappers.py
72. Schulz JM, et al. PRosettaC outperforms AlphaFold3 for modeling PROTAC ternary complexes. Sci Rep 2025;15:37620 (benchmark of 36 crystallographic ternary complexes; DockQ). https://www.nature.com/articles/s41598-025-21502-8 *(URL fetched — live; PRosettaC vs AF3 ΔDockQ +0.11 average confirmed)*
73. DeepTernary — end-to-end SE(3)-equivariant ternary complex prediction for TPD. Nat Commun 2025. https://www.nature.com/articles/s41467-025-61272-5
74. Link-INVENT — REINVENT extension for RL generative linker design incl. PROTACs. Digital Discovery 2023. https://pubs.rsc.org/en/content/articlehtml/2023/dd/d2dd00115b
75. AIMLinker — deep encoder-decoder fragment linker prediction for PROTACs. JCIM 2023. https://pubs.acs.org/doi/10.1021/acs.jcim.2c01287
76. the-ahuja-lab/SynGlue (GitHub). https://github.com/the-ahuja-lab/SynGlue
77. DiffPROTACs — diffusion-based PROTAC/linker generator. https://pubmed.ncbi.nlm.nih.gov/39101502/
78. LM-PROTAC — language-model PROTAC generation with structure+property constraints. https://doi.org/10.48550/arxiv.2412.09661
79. Optimising PROTACs for oral drug delivery: a drug metabolism and pharmacokinetics perspective. Drug Discov Today 2020. https://www.sciencedirect.com/science/article/abs/pii/S1359644620302932
80. Current advances and development strategies of orally bioavailable PROTACs. 2023. https://pubmed.ncbi.nlm.nih.gov/37708797/
81. `outputs/deepresearch_A.md` — Residual uncertainties §1: "hERG/cardiac safety for PROTACs: no PROTAC-specific primary data found." /storage/saveena/protacpilot/outputs/deepresearch_A.md
82. FROGENT — end-to-end drug design agent (LLM + MCP). arXiv 2508.10760. https://arxiv.org/html/2508.10760v1
83. Tippy — multi-agent DMTA framework. arXiv 2507.09023. https://arxiv.org/html/2507.09023
84. MADD — Multi-Agent Drug Discovery Orchestra. EMNLP Findings 2025. https://aclanthology.org/2025.findings-emnlp.367/
85. LLM agent for modular drug-discovery task execution. arXiv 2507.02925. https://arxiv.org/html/2507.02925v3
86. PROTAC Design Agent (SKILL.md spec). https://github.com/mdbabumiamssm/LLMs-Universal-Life-Science-and-Clinical-Skills-/tree/main/Skills/Generative_Drug_Design/PROTAC_Design_Agent
87. `outputs/deepresearch_B.md` — Findings §8: "local ProtacPilot is the only PROTAC-specific agentic system found with evidence of real tool execution." /storage/saveena/protacpilot/outputs/deepresearch_B.md
