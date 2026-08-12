# DEEP RESEARCH TASK C — Making and validating a real PROTAC drug candidate
**Sub-question:** What does it actually take to make and validate a real PROTAC drug candidate, based on the current clinical pipeline and assay practice?
**Research date:** 2026-08-12 | **Status:** complete (all 5 sub-questions answered)

---

## Coverage Status

- **Q1 Clinical pipeline (Arvinas, Kymera, C4, others):** `done` — verified against FDA approval page, company press releases (Arvinas, Kymera, C4, Nurix, BMS), SEC 8-K, ClinicalTrials.gov.
- **Q2 E3 ligase landscape:** `done` — full-text read of the most recent dedicated review (Li et al., *Targets* 2025, MDPI) plus primary papers for SPOP, SKP1, FEM1B, DCAF15/16.
- **Q3 Validation assay stack:** `done` — ternary complex (SPR/BLI/ITC/AlphaScreen/native MS), HiBiT/immunoblot/DC50–Dmax/kinetics, TMT proteomics, ubiquitination, permeability, PK/PD, in vivo.
- **Q4 Failure modes:** `done` — hook effect, CRBN neosubstrate toxicity, off-target degradation, bRo5 oral PK, chemical (glutarimide) instability.
- **Q5 Wet-lab effort per candidate:** `done` — direct-to-biology throughput papers, E3-ligand validation workflow, IND-timeline case study (13 months PCC→IND, vendor-reported).
- **Not verified / blocked:** feynman alpha search required login (`alpha login`) and was unavailable — all sources came from `web_search` + `fetch_content`. Some med-chem "cycle time per chemist" figures are not published as hard numbers; what exists (throughput platforms, vendor IND timelines) is cited and labeled. Numbers inside the MDPI review's Table 1 are reported as read from the review, which in turn cites the primary papers.

---

## Evidence table

| # | Source | URL | Key claim | Type | Confidence |
|---|--------|-----|-----------|------|------------|
| 1 | FDA (approval page) | https://www.fda.gov/drugs/resources-information-approved-drugs/fda-approves-vepdegestrant-er-positive-her2-negative-esr1-mutated-advanced-or-metastatic-breast | On May 1, 2026 FDA approved vepdegestrant (Veppanu, Arvinas Operations), a heterobifunctional protein degrader, for ER+/HER2−, ESR1-mutated advanced/metastatic breast cancer after ≥1 line endocrine therapy | primary | high |
| 2 | Arvinas press release | https://ir.arvinas.com/news-releases/news-release-details/arvinas-announces-fda-approval-veppanu-vepdegestrant-treatment | VEPPANU is the "first-and-only FDA-approved PROTAC"; approval before PDUFA date (June 5, 2026); Arvinas + Pfizer | primary (self-reported) | high |
| 3 | Reuters | https://www.reuters.com/business/healthcare-pharmaceuticals/us-fda-approves-pfizer-arvinas-breast-cancer-drug-2026-05-01/ | FDA approved Pfizer/Arvinas' breast cancer drug branded Veppanu for ESR1-mutated ER+/HER2− advanced disease | secondary | high |
| 4 | SEC Form 8-K (Arvinas) | https://www.sec.gov/Archives/edgar/data/1655759/000162828026029210/arvn-20260501.htm | Confirms May 1, 2026 approval; indication restricted to ESR1m detected by FDA-authorized test | primary | high |
| 5 | CancerNetwork (ASCO 2025 coverage) | https://www.cancernetwork.com/view/vepdegestrant-outperforms-fulvestrant-in-pfs-for-esr1-mutant-advanced-breast-cancer | VERITAC-2 (NCT05654623): ESR1m mPFS 5.0 vs 2.1 mo (HR 0.57, P<0.001); all-comer BICR HR 0.83 (P=0.07); CBR 42.1% vs 20.2%; ORR 18.6% vs 4.0%; neutropenia 12% vs 5% | secondary (ASCO LBA1000) | high |
| 6 | NEJM (Hamilton et al.) | https://www.nejm.org/doi/full/10.1056/NEJMoa2505725 | Phase 3 VERITAC-2 design: 200 mg QD vepdegestrant vs fulvestrant, 1:1, ESR1-stratified | primary | high |
| 7 | Arvinas pipeline page | https://www.arvinas.com/research-and-development/pipeline/ | Luxdegalutamide (ARV-766, AR degrader) licensed to Novartis, Phase 2; ARV-102 (LRRK2) Ph1; ARV-393 (BCL6) Ph1; ARV-806 (KRAS G12D); ARV-027; 2026 Rigel license deal for VEPPANU | primary (self-reported) | high |
| 8 | Arvinas Q4 2025 results | https://ir.arvinas.com/news-releases/news-release-details/arvinas-reports-fourth-quarter-and-full-year-2025-financial | 2026 data readouts from ARV-102, ARV-806, ARV-393; ARV-102 Ph1 PD data at AP/PD conf March 2026 | primary (self-reported) | high |
| 9 | Kymera Q2 2026 results | https://investors.kymeratx.com/news-releases/news-release-details/kymera-therapeutics-announces-second-quarter-2026-financial | KT-621 (STAT6) Ph2b BROADEN2 (AD) enrollment complete ~6 mo early, data YE 2026; Ph3 AD start mid-2027; BREADTH (asthma) data late 2027; KT-579 (IRF5) Ph1 HV ongoing, data 4Q26 | primary (self-reported) | high |
| 10 | Kymera AAD 2026 PR (KT-621) | https://investors.kymeratx.com/news-releases/news-release-details/kymera-therapeutics-presents-kt-621-broaden-data-late-breaking | BroADen Ph1b (n=22): 28 days QD; median STAT6 degradation 94% skin / 98% blood; TARC −74%; mean EASI −63%; EASI-75 29%; vIGA-AD 0/1 19%; itch NRS −40%; well tolerated | primary (self-reported) | high |
| 11 | ClinicalTrials.gov KT-579 | https://clinicaltrials.gov/study/NCT07412288 | KT-579 first-in-human Ph1 SAD/MAD in healthy adults; recruiting since 2026-02-23; IRF5 (per sponsor) | primary | high |
| 12 | Kymera pipeline page | https://www.kymeratx.com/science-innovation/pipeline/ | KT-474→KT-485 (SAR447971) IRAK4 degraders with Sanofi; KT-621 STAT6; KT-579 IRF5; oncology KT-333 (STAT3)/KT-253 (MDM2) advanced with partner support | primary (self-reported) | high |
| 13 | Kymera Q1 2025 results | https://investors.kymeratx.com/news-releases/news-release-details/kymera-therapeutics-announces-first-quarter-2025-financial | KT-474/SAR444656 Ph2b HS+AD with Sanofi; $20M milestone Apr 2025; KT-295 (TYK2) not advanced to clinic | primary (self-reported) | high |
| 14 | C4 Therapeutics pipeline | https://c4therapeutics.com/our-pipeline/ | Cemsidomide (IKZF1/3 MonoDAC) Ph1/2; CFT8919 (EGFR L858R) Ph1 NSCLC with Betta; CFT1946 (BRAF V600) Ph1 not advanced beyond | primary (self-reported) | high |
| 15 | ClinicalTrials.gov CFT1946 | https://clinicaltrials.gov/study/NCT05668585 | Ph1 CFT1946 monotherapy + combo BRAF V600 solid tumors; 89 enrolled; completed Nov 5, 2025 | primary | high |
| 16 | C4 Q1 2025 results | https://ir.c4therapeutics.com/news-releases/news-release-details/c4-therapeutics-reports-first-quarter-2025-financial-results-and | Cemsidomide dose escalation complete (640 mg BID); FDA feedback for next phase; CFT1946 Ph1 dose escalation complete | primary (self-reported) | high |
| 17 | C4 MOMENTUM PR | https://ir.c4therapeutics.com/news-releases/news-release-details/c4-therapeutics-announces-first-patient-dosed-phase-2-momentum | First patient dosed Ph2 MOMENTUM: cemsidomide + dex in R/R multiple myeloma; enrollment complete Q1 2027 | primary (self-reported) | high |
| 18 | ClinicalTrials.gov NX-5948 | https://clinicaltrials.gov/study/NCT07516093 | Nurix bexobrutideg (NX-5948) vs pirtobrutinib, Ph3 DAYBreak CLL-306, R/R CLL/SLL; first patient enrolled (registrational) | primary | high |
| 19 | ClinicalTrials.gov NX-2127 | https://clinicaltrials.gov/study/NCT04830137 | NX-2127 Ph1a/1b R/R B-cell malignancies (BTK degrader) | primary | high |
| 20 | BMS press release (iberdomide) | https://news.bms.com/news/details/2026/U-S--Food-and-Drug-Administration-Accepts-Bristol-Myers-Squibbs-New-Drug-Application-for-Iberdomide-in-Patients-with-Relapsed-or-Refractory-Multiple-Myeloma/default.aspx | FDA accepted iberdomide NDA (CELMoD molecular glue), Breakthrough + Priority Review, PDUFA Aug 17, 2026 | primary (self-reported) | high |
| 21 | EMA EU-IN Horizon Scanning Report (TPD) | https://www.ema.europa.eu/en/documents/report/targeted-protein-degradation-eu-horizon-scanning-report_en.pdf | First PROTAC approved; >40 TPD candidates in clinical development, predominantly oncology | primary (regulator) | high |
| 22 | Beacon Intelligence TPD 2025 Landscape Review | https://www.beacon-intelligence.com/landscape-reviews/tpd-2025-landscape-review/ | 215 degrader assets active in clinic (2025); most assets preclinical | secondary (vendor) | medium |
| 23 | Li et al., "The Expanding E3 Ligase-Ligand Landscape for PROTAC Technology", Targets 2025, 3, 30 (MDPI) | https://www.mdpi.com/2813-3137/3/4/30 | Full-text read. ~600–700 human E3s; clinic dominated by CRBN/VHL/MDM2/IAP quartet; details ligands + DC50/Dmax for RNF4, RNF114, DCAF16, DCAF15, DCAF11, DCAF1, AhR, KEAP1, FEM1B, KLHL20, KLHDC2, FBXO22, GID4 | review (peer-reviewed) | high |
| 24 | Ishida & Ciulli-style "E3 ligase guide" (Cell Chem. Biol. via ScienceDirect) | https://www.sciencedirect.com/science/article/pii/S2451945621001574 | CRBN is one of ~100 exchangeable substrate adaptors of modular CRL4-type E3s; bivalent PROTACs tether E3 ligand + target warhead | review | high |
| 25 | E3 ligase deconvolution review, J. Med. Chem. 2024 | https://pubs.acs.org/doi/abs/10.1021/acs.jmedchem.4c00723 | Lack of ligandable E3 ligases is a major issue in TPD; reviews deconvolution approaches | review | high |
| 26 | Li et al., DCAF15 in vivo PROTAC, Signal Transduct. Target. Ther. 2020 | https://www.nature.com/articles/s41392-020-00245-0 | DCAF15-based BRD4 degrader DP1 (E7820 + JQ1) works in vitro and in vivo | primary | high |
| 27 | DCAF16 binder discovery (J. Med. Chem. 2025) | https://pubmed.ncbi.nlm.nih.gov/39882752/ | DCAF16 binders enabling TPD via proteasome/autophagy | primary | medium |
| 28 | Lucas et al., DCAF15 ligand optimization, J. Med. Chem. 2024 | https://pubs.acs.org/doi/abs/10.1021/acs.jmedchem.3c02136 | 53 nM DCAF15 ligand (compound 24) made; only one conjugated PROTAC degraded BRD4 and it was DCAF15-independent — warning against assuming glue ligand ⇒ functional warhead | primary | high |
| 29 | SPOP bridged PROTAC, J. Med. Chem. 2025 | https://doi.org/10.1021/acs.jmedchem.5c00295 | First SPOP-recruiting PROTAC MS479 (bridged strategy) proof-of-concept | primary | medium |
| 30 | Henning et al., covalent FEM1B recruiter, JACS 2022 (PMC) | https://pmc.ncbi.nlm.nih.gov/articles/PMC8928484/ | EN106 covalently targets FEM1B C186; NJH-1-106 degrades BRD4 (DC50 250 nM, Dmax 94%); only a small number of recruiters available for >600 E3s | primary | high |
| 31 | SKP1 exploitation (J. Med. Chem. 2024) | https://pubmed.ncbi.nlm.nih.gov/38305738/ | Core CRL adaptor SKP1 exploited for TPD (SKPIN1-type recruiters) | primary | medium |
| 32 | Farrell et al., KLHL20, Genes Dev. 2022 | https://genesdev.cshlp.org/content/36/17-18/1031.long | Synthetic macrocyclic KLHL20 ligand BTR2000 validated; BTR2003 degrades BET proteins | primary | high |
| 33 | JoVE protocol: ternary complex biophysics | https://www.jove.com/t/65718/the-development-application-biophysical-assays-for-evaluating-ternary | SPR, BLI, ITC protocols for PROTAC ternary complex formation (VHL + CRBN) | primary (protocol) | high |
| 34 | Native MS of BCL-xL PROTAC, Chem. Sci. 2026 | https://pubs.rsc.org/en/content/articlehtml/2026/sc/d5sc07400b | Native mass spectrometry maps ternary complex efficiency and dissociation pathways; selectivity vs BCL-2 | primary | high |
| 35 | Assays & technologies for PROTACs, Future Med. Chem. 2020 | https://www.tandfonline.com/doi/full/10.4155/fmc-2020-0073 | Three-body equilibria; binary + ternary SAR; TR-FRET/SPR/AlphaScreen-type proximity assays | review | high |
| 36 | Revvity AlphaLISA PROTAC application note | https://resources.revvity.com/pdfs/pbr-alphalisa-protac.pdf | AlphaLISA proximity assay setup for E3-ligand–target ternary complex detection with multiple readouts | primary (vendor protocol) | high |
| 37 | Comparative analysis of biophysical proximity methods | https://www.sciencedirect.com/science/article/abs/pii/S030441652300096X | Comparative assessment of methods for monitoring protein-proximity induction in degrader development | review | high |
| 38 | Riching et al., ACS Chem. Biol. 2019 | https://pubs.acs.org/doi/full/10.1021/acschembio.8b00692 | Quantitative live-cell kinetic degradation + mechanistic profiling of PROTAC MoA (HiBiT/NanoLuc) | primary | high |
| 39 | Promega AN331 (HiBiT application note) | https://www.promega.com/-/media/files/resources/application-notes/nanobret/an331.pdf | Kinetically detect/quantitate PROTAC-induced degradation of endogenous HiBiT-tagged targets; DC50/Dmax & kinetics | primary (vendor protocol) | high |
| 40 | E3 ligase ligand validation workflow, J. Med. Chem. (PMC) | https://pmc.ncbi.nlm.nih.gov/articles/PMC11851430/ | Six-step workflow: design/synthesis → DSF + Kinobeads → NanoBRET cell penetration/engagement → degradation → kinome-wide selectivity by MS-based quantitative proteomics | primary | high |
| 41 | In vitro pull-down ternary assay | https://pubmed.ncbi.nlm.nih.gov/34432242/ | E3:PROTAC:substrate pull-down assay to triage effective PROTACs and confirm MoA | primary (protocol) | high |
| 42 | LifeSensors PROTAC ubiquitination assays | https://lifesensors.com/protac-ubiquitination-assays/ | Reconstituted in vitro ubiquitination (E1/E2/E3 + ubiquitin) measures productive ubiquitin transfer that proximity assays cannot | primary (vendor) | medium |
| 43 | PK/PD modeling of targeted protein degraders (review, 2025) | https://www.sciencedirect.com/science/article/pii/S1359644625000248 | E-max must be adapted into dedicated hook models; hook effect frequently observed in vitro but widely disregarded in vivo because relevant concentrations rarely reached in animals | review | high |
| 44 | Mechanistic PD modeling framework, Pharmaceutics 2023 | https://www.mdpi.com/1999-4923/15/1/195 | Model links biochemical ternary parameters → degradation; hook model relates degradation to concentration/time; PK/PD metrics for discovery | primary | high |
| 45 | Kinetic modeling of PROTAC degradation, ChemMedChem 2023 | https://chemistry-europe.onlinelibrary.wiley.com/doi/abs/10.1002/cmdc.202300530 | DC50 depends on ternary-complex Kd, E3 expression level, and effective ubiquitination rate | primary | medium |
| 46 | Physicochemical determinants of oral absorption (J. Med. Chem. 2023) | https://pubmed.ncbi.nlm.nih.gov/37279490/ | Large rat PO/IV dataset of PROTACs estimating fraction absorbed; bRo5 determinants of oral absorption | primary | high |
| 47 | ADME/DMPK perspective on PROTACs | https://www.sciencedirect.com/science/article/abs/pii/S1359644620302932 | PROTACs sit in bRo5 space; ADME data scarce; permeability/metabolic stability are key optimization axes | review | high |
| 48 | "Property-based optimisation of PROTACs", RSC Med. Chem. 2025 (PMC) | https://pmc.ncbi.nlm.nih.gov/articles/PMC11561549/ | Clinical PROTACs analyzed through physicochemical-property lens; component-by-component optimization for oral bioavailability; med-chem guidance | review | high |
| 49 | Direct-to-biology PROTAC platform, ACS Med. Chem. Lett. 2022 | https://pubmed.ncbi.nlm.nih.gov/35859867/ | D2B platform synthesizes large linker analog sets without purification; measures permeability + degradation in 4 cell assays; linker SAR throughput | primary | high |
| 50 | Linker design in PROTACs, J. Med. Chem. 2021 | https://pubs.acs.org/doi/abs/10.1021/acs.jmedchem.1c00482 | Linker length/composition SAR is empirical bottleneck; four synthetic-throughput strategies reviewed | review | high |
| 51 | Phenyl-glutarimides as alternative CRBN binders (PMC) | https://pmc.ncbi.nlm.nih.gov/articles/PMC8648984/ | IMiDs and IMiD-based PROTACs hydrolyze rapidly in cell media; phenyl-glutarimides are more stable CRBN ligands | primary | high |
| 52 | Linker attachment points vs stability (PMC) | https://pmc.ncbi.nlm.nih.gov/articles/PMC8591746/ | Linker attachment-point choice changes hydrolytic/metabolic stability of IMiD-containing PROTACs | primary | high |
| 53 | Dihydrouracil CRBN ligand, Nat. Commun. 2026 | https://www.nature.com/articles/s41467-026-70663-1 | IMiD scaffolds in PROTACs can inadvertently degrade IKZF1/IKZF3 neosubstrates (hematotoxicity); configurational instability (glutarimide epimerization) complicates manufacture; dihydrouracil ligand mitigates both | primary | high |
| 54 | Beilstein: cryptic impurity in pomalidomide-PEG PROTACs | https://beilstein-journals.org/bjoc/content/pdf/1860-5397-21-28.pdf | SNAr synthesis of IMiD-PEG PROTACs generates competing acyl-substitution impurity | primary | medium |
| 55 | GSPT1 molecular glue on-target toxicity (bioRxiv 2026) | https://www.biorxiv.org/content/10.64898/2026.02.14.705470v1.full-text | GSPT1 MGDs (e.g., CC-90009) caused on-target toxicity; species differences in CRBN (thalidomide teratogenic in humans, not rodents) hinder toxicity prediction | preprint | medium |
| 56 | Neosubstrate degradation trends (J. Med. Chem./PMC) | https://pubmed.ncbi.nlm.nih.gov/38170610/ | CRBN neosubstrates: Aiolos, Ikaros, GSPT1, CK1α, SALL4; selectivity vs neosubstrates is a central design problem | review | high |
| 57 | WuXi STA case study: PROTAC PCC→IND in 13 months | https://sta.wuxiapptec.com/resources/case-study-a-protac-molecule-from-pcc-to-ind-submission-in-13-months/ | Vendor case study: PROTAC API from PCC to IND filing in 13 months; complex synthesis with toxic intermediates | secondary (vendor) | medium |
| 58 | Nanomole-scale array PROTAC synthesis (PMC) | https://pmc.ncbi.nlm.nih.gov/articles/PMC10726452/ | Parallel nanomole-scale synthesis platform to accelerate empirical linker/exit-vector SAR | primary | high |
| 59 | Extended PD responses after single dose (ACS Med. Chem. Lett./PMC) | https://pmc.ncbi.nlm.nih.gov/articles/PMC7083851/ | PROTAC catalytic MoA can give PD responses that outlast drug exposure; supports intermittent dosing | primary | high |
| 60 | Tissue distribution/retention of VHL PROTAC (Commun. Med. 2024) | https://www.nature.com/articles/s43856-024-00505-y | QWBA + tissue excision PK in rats/mice; tissue distribution and retention drive efficacy of rapidly cleared degraders; BDC rats for clearance pathways | primary | high |
| 61 | Intramolecular bivalent glues (Nature 2024, IBG1) | https://www.nature.com/articles/s41586-024-07089-6 | DCAF15-recruiting degrader IBG1; aryl-sulfonamide E3 ligands for PROTACs have had limited success — context for DCAF15 | primary | high |

---

## Findings

### 1. Clinical pipeline status (as of Aug 2026)

**VEPPANU (vepdegestrant / ARV-471) is the first FDA-approved PROTAC.** Approved May 1, 2026 (ahead of the June 5 PDUFA date) for ER+/HER2−, ESR1-mutated advanced or metastatic breast cancer with progression after ≥1 line of endocrine-based therapy, detected by an FDA-authorized test [1][2][4]. The pivotal basis is VERITAC-2 (NCT05654623): 200 mg QD oral vepdegestrant vs IM fulvestrant [6]. In the ESR1-mutated population, median PFS was 5.0 vs 2.1 months (HR 0.57; 95% CI 0.42–0.77; P<0.001), 6-month PFS 45.2% vs 22.7%, CBR 42.1% vs 20.2%, ORR 18.6% vs 4.0%; in the all-comer population the BICR PFS HR was 0.83 (P=0.07) — i.e., benefit was driven by the ESR1m subgroup [5]. Safety: any-grade TEAEs 87% vs 81%, grade ≥3 23% vs 18%, TEAE discontinuation only 3% (vs 1% fulvestrant); notable CRBN-relevant hematologic signal: neutropenia 12% vs 5% [5]. Arvinas/Pfizer licensed VEPPANU rights to Rigel Pharmaceuticals in 2026 [7]. E3: CRBN (vepdegestrant is a CRBN-recruiting ER degrader; the MDPI review notes vepdegestrant met its primary endpoint and "regulatory submissions have been filed" — see [23], citing the JMC NDA article).

**Arvinas remainder:** luxdegalutamide (ARV-766), an oral AR PROTAC licensed to Novartis in 2024, in Phase 2 (and earlier-stage prostate cancer studies); ARV-102 (LRRK2, Parkinson's/PSP) Phase 1 with data presented March 2026; ARV-393 (BCL6, NHL) Phase 1 with 2026 data; ARV-806 (KRAS G12D) and ARV-027 earlier stage [7][8].

**Kymera (immunology-focused):** KT-621, an oral STAT6 degrader, is the lead — Phase 1b BroADen (n=22, moderate-severe AD, 28 days QD) showed median STAT6 degradation of 94% in skin and 98% in blood at 100/200 mg, median TARC −74%, mean EASI −63%, EASI-75 29%, vIGA-AD 0/1 19%, peak-pruritus NRS −40%, POEM −9 points, well tolerated [10]. Phase 2b BROADEN2 (AD) enrollment completed ~6 months early with topline data expected YE 2026; Phase 3 AD planned mid-2027; BREADTH (asthma) Ph2b data late 2027 [9]. KT-579 (IRF5) is in a Phase 1 first-in-human SAD/MAD study in healthy volunteers (NCT07412288, recruiting since Feb 2026) with data expected 4Q26 [9][11]. Sanofi-partnered IRAK4 program: KT-474/SAR444656 in Ph2b (HS and AD), with second-generation KT-485 (SAR447971) prioritized by Sanofi [12][13]. Oncology (KT-333 STAT3, KT-253 MDM2) advanced only with partner support; KT-295 (TYK2) was not advanced into the clinic [12][13]. E3s used by Kymera candidates are CRBN-based (heterobifunctional degraders; KT-621/KT-579 are oral small-molecule degraders) — the company describes all as degraders; ligase identity for KT-621/KT-579 is CRBN per Kymera disclosures (not independently verified here; labeled as inference from company materials).

**C4 Therapeutics:** cemsidomide — an oral IKZF1/3 molecular-glue degrader (MonoDAC) — completed Phase 1 dose escalation (640 mg BID) and has now dosed its first patient in the Phase 2 MOMENTUM trial (cemsidomide + dexamethasone, R/R multiple myeloma) [14][16][17]. CFT8919 (EGFR L858R degrader, NSCLC) is in Phase 1 with Betta Pharmaceuticals [14]. CFT1946 (BRAF V600) completed Phase 1 (NCT05668585, n=89) and C4T stated it will not advance beyond Phase 1 [14][15].

**Others:** Nurix's bexobrutideg (NX-5948), a BTK degrader, entered a registrational Phase 3 (DAYBreak CLL-306, vs pirtobrutinib, R/R CLL/SLL; NCT07516093), with updated Phase 1a/b data reported June 2026 [18]; NX-2127 remains in Phase 1a/1b [19]. On the molecular-glue side, BMS's iberdomide NDA was accepted with Priority Review (PDUFA Aug 17, 2026) and mezigdomide is in Phase 3 for R/R myeloma [20]. Scale: the EMA EU-IN horizon-scanning report counts >40 TPD candidates in clinical development, predominantly oncology [21]; Beacon's 2025 landscape counted 215 degrader assets active in the clinic [22] (vendor estimate — medium confidence).

**Bottom line for Q1:** the modality is validated end-to-end (approval → launch), the current clinic is ~90% CRBN-recruiting heterobifunctional PROTACs + IKZF1/3 molecular glues, and the next waves (STAT6, IRF5, BTK, LRRK2, BCL6, KRAS G12D, EGFR L858R) are in Ph1–Ph3.

### 2. The E3 ligase landscape (600+ human E3s; which have validated ligands)

The human genome encodes an estimated 600–700 E3 ligases, but clinical and most preclinical PROTAC work has been dominated by four: **CRBN, VHL, MDM2, and the IAP family (cIAP1/2)** [23][24]. Beyond the canonical quartet, a 2025 review (full-text read here) tabulates validated ligand–E3 pairs with measured degradation metrics [23]:

| E3 | Validated ligand (type) | Example PROTAC (target) | Reported DC50 / Dmax | Proof |
|----|------------------------|-------------------------|----------------------|-------|
| RNF4 | TRH 1-23 → CCW16 (covalent) | CCW 28-3 (BRD4) | — | ABPP-discovered; proteasome- and RNF4-dependent [23] |
| RNF114 | Nimbolide (covalent, C8); EN219 acrylamide (IC50 470 nM) | XH2, BT1 (BRD4/BCR-ABL); ML 2-14 (BRD4) | BRD4 long 36 nM / short 14 nM (ML 2-14) | Nomura lab; selectivity over other BETs by proteomics [23] |
| DCAF16 | KB02 chloroacetamide (covalent, C177/C179) | KB02-SLF (FKBP12), KB02-JQ1 (BRD4), C8 (PARP2), A4 (CDK4/6) | PARP2: 2 µM/>92%; CDK4 6.5 µM, CDK6 8 µM | 10–40% DCAF16 occupancy suffices; nuclear-restricted; washout-resistant [23][27] |
| DCAF15 | E7820/aryl sulfonamides; cryo-EM-optimized 53 nM ligand (compd 24) | DP1 (BRD4); IBG1 (intramolecular bivalent glue) | DP1: 10.8 µM/98% | In vivo degradation shown (STTT 2020) [23][26][28][61]; **caveat:** potent DCAF15 glue ligand gave only one degrader that was DCAF15-independent [28] |
| DCAF11 | Chloroacetamide 21-SLF (C460); alkenyl oxindoles (covalent) | 21-SLF (FKBP12), 21-ARL (AR); HL435, L134 (BRD4); FF2039 (pan-HDAC) | HL435 11.9/21.9 nM; L134 7.36 nM/>98% | CRISPRi-validated CRL4DCAF11 dependence [23] |
| DCAF1 | Noncovalent binder; OICR-8268 | DBr-1 (BRD9), DBt-10 (BTK), OICR-41114 (WDR5) | WDR5: 40 nM/49% | Overcomes CRBN/VHL degrader resistance [23] |
| AhR | β-NF, ITE (noncovalent) | β-NF-ATRA (CRABP1/2), β-NF-JQ1 (BRDs) | — | AhR-dependent, UPS-mediated [23] |
| KEAP1 | CDDO (bardoxolone, covalent); KEAP1-L-OEt (noncovalent, prodrug); piperlongumine (covalent) | CDDO-JQ1 (BRD4); MS83 (BRD4/BRD3); 955 (CDK9, DC50 9 nM), 819 (EML4-ALK) | MS83 sustained kinetics vs dBET1 | Proteasome + NEDD8 (CUL3) dependence confirmed [23] |
| FEM1B | EN106 (covalent, C186) | NJH-1-106 (BRD4), NJH-2-142 (BCR-ABL) | 250 nM / 94% | FEM1B-FNIP1 biology exploited [23][30] |
| KLHL20 | BTR2000 (synthetic macrocycle) | BTR2003 (BRD2/3/4) | 46/87/777 nM | Structure-guided (PDB 6GY5); macrocycle outperformed linear [23][32] |
| KLHDC2 | KDRLKZ-1/2; SJ46418-type C-degron mimics | K2-B4-3e/5e (BRD4), K2-AR-1 (AR), SJ46421 (BRD3) | 66 nM/62%; 6.2 nM/93% | Prodrugs solve permeability of acidic degron mimics [23] |
| FBXO22 | Electrophilic ligand (C227/C228) | 22-SLF (FKBP12), 22-JQ1 (BRD4), 22-TAE (EML4-ALK) | FKBP12: 0.5 µM/89% | CRISPRa screen-identified [23] |
| GID4 | PFI-7 (noncovalent) | NEP108, NEP162 (BRD4), NEP168 (ERα), NEP202 (SMARCA2) | 3.8 µM; 1.2–1.6 µM | Ternary crystal structures (8X7G/8X7H); xenograft efficacy [23] |
| SPOP | Bridged-PROTAC strategy | MS479 (proof-of-concept) | — | First SPOP recruitment [29] |
| SKP1 | SKPIN1-type adaptor recruiters | — | — | Core CRL adaptor exploited for TPD [31] |

Key structural context: CRBN is one of ~100 exchangeable substrate adaptors of modular CRL4-type E3 complexes (CUL4A/B + RBX1 + DDB1) [24]. The review's limitations section is directly relevant to practice: most of these new ligands are **tool compounds, not yet optimized for oral bioavailability or metabolic stability**, and most novel-E3 systems lack rigorous in vivo validation [23]. Inference: for a drug candidate, CRBN or VHL remain the default choices; the expanded toolbox is the answer to resistance, tissue selectivity, and subcellular (e.g., nuclear) targeting.

### 3. Validation assay stack (what is actually measured, in order)

**Step 0 — binary binding & E3 ligand validation.** A published industry/academic workflow for E3 ligand validation runs six steps: design/synthesis → mapping ligandable space with DSF and Kinobeads → cell penetration + cellular target engagement by NanoBRET → degradation assays → kinome-wide selectivity by MS-based quantitative proteomics [40]. For promiscuous warheads, kinome-wide degradation profiling drastically reduces synthesis burden [40].

**Ternary complex formation (biophysics):** SPR, biolayer interferometry (BLI), and ITC are the workhorse methods, with published protocols for both VHL- and CRBN-recruiting PROTACs measuring ternary kinetics/thermodynamics and cooperativity (α) [33]. Proximity assays such as AlphaScreen/AlphaLISA (Revvity) give higher-throughput ternary detection [35][36][37]; a 2023 comparative review covers method trade-offs [37]. Native mass spectrometry now resolves ternary complex stoichiometry, efficiency, and dissociation pathways — e.g., a BCL-xL/BCL-2 dual degrader was characterized by native MS with distinct complex architectures explaining selectivity [34]. In vitro pull-down of the E3:PROTAC:substrate complex is a simple orthogonal confirmation [41]. Note the assay hierarchy: ternary formation is necessary but not sufficient — "current PROTAC discovery heavily relies on monitoring ternary complex formation using biophysical/biochemical approaches... that does not monitor true function" [42].

**Ubiquitination (functional proof):** reconstituted in vitro ubiquitination with E1 + E2 + E3 + ubiquitin (LifeSensors-type kits) measures whether the ternary complex is productive (ubiquitin transfer onto the POI) [42]. Crystal structures of ternary complexes (VHL/753b/BCL-xL etc.) plus mutagenesis confirm the interfacial contacts [23][34].

**Degradation (cellular):** the standard cellular readouts are (i) immunoblot, (ii) HiBiT-tagged (NanoLuc split) live-cell kinetic assays on endogenous knock-in lines giving DC50, Dmax, and degradation kinetics in real time [38][39], (iii) end-point quantitation for screening [39]. Mechanistic controls are mandatory: proteasome inhibitor (bortezomib/MG132), NEDD8 inhibitor (MLN4924), E1 inhibitor (MLN7243), E3-ligase knockout/competition, and inactive negative controls [23]. Metrics to report: DC50 (concentration for 50% degradation), Dmax (maximal degradation), kinetics (t1/2 of degradation, resynthesis rate) [38][39]; kinetic modeling shows DC50 depends on ternary Kd, E3 expression level, and effective ubiquitination rate [45].

**Selectivity:** TMT-based quantitative (whole-proteome or kinome-enriched) proteomics after compound treatment identifies off-target degradation [40]; this is how BRD4-selective degraders (e.g., RNF114-based, over other BET proteins) were confirmed [23]. Expected practice: 2+ concentrations, matched vehicle and inactive enantiomer/negative controls, and a resynthesis window.

**ADME/DMPK:** PROTACs live in beyond-Rule-of-5 (bRo5) space, so permeability (PAMPA, Caco-2/MDCK, parallel artificial membrane) and metabolic stability (microsomal/hepatocyte intrinsic clearance) are primary optimization axes [46][47][48]. Direct-to-biology platforms now measure permeability and degradation in parallel across large linker arrays [49].

**PK/PD and in vivo efficacy:** mechanistic PK/PD models (hook models adapted from E-max) convert in vitro DC50/Dmax into predictions of in vivo degradation time-course [43][44]. In vivo practice includes: QWBA/tissue-excision distribution studies showing tissue retention drives efficacy for rapidly cleared degraders [60]; single-dose PD that outlasts exposure (supports intermittent dosing) [59]; xenograft tumor regression with target knockdown confirmation (e.g., STAT3 degrader achieving complete regression [23], SMARCA2 degrader in SMARCA4-mutant NSCLC [23-cited literature]); degradation-duration and recovery measurements after dosing stop [44].

### 4. Key failure modes

1. **Hook effect.** At high PROTAC concentrations, binary E3 and binary POI complexes outcompete the ternary complex, producing a bell-shaped dose–response. Dedicated "hook models" are required for PK/PD fitting because ordinary E-max fails [43][44]. Practically, the hook effect is frequently observed in vitro but "widely disregarded in vivo because the relevant concentrations are only rarely reached in animal studies" [43] — still, it sets an upper bound on tolerated doses and matters for IV-to-PO bridging.
2. **Ternary-mediated / neosubstrate toxicity.** CRBN-recruiting molecules degrade CRBN neosubstrates (IKZF1/Aiolos, GSPT1, CK1α, SALL4) [56]. IMiD scaffolds embedded in PROTACs can inadvertently degrade IKZF1/3, causing hematotoxicity [53]; GSPT1 molecular glues (CC-90009) showed on-target toxicity in the clinic, and species differences in CRBN (thalidomide teratogenic in humans, not rodents) make preclinical toxicity prediction unreliable [55]. Mitigations in the literature: alternative CRBN ligands (phenyl-glutarimides, dihydrouracil) that retain target degradation while sparing neosubstrates [51][53]. On-target, off-tissue toxicity from ubiquitous CRBN/VHL expression is also a stated driver for tissue-restricted E3 selection [23].
3. **Off-target degradation.** Degraders can eliminate proteins beyond the POI (warhead promiscuity + neosubstrate effects + E3-dependent bystander degradation). Detection requires TMT quantitative proteomics [40]; the DCAF15 case (potent ligand, only one degrader, DCAF15-independent) is a documented example of an apparent "hit" failing rigorous mechanism-of-action proof [28]. Acquired resistance via mutations in E3-complex components is an additional late failure mode [23][25].
4. **Poor oral PK of bRo5 molecules.** PROTACs exceed Rule-of-5 property space; fraction-absorbed datasets from rat PO/IV studies show oral absorption is the key hurdle, with permeability and solubility co-limiting [46][47]. Med-chem guidance: optimize each component (warhead, linker, E3 ligand) separately, watch TPSA/rotatable bonds/H-bond donors, use prodrugs for acidic moieties (e.g., KEAP1 ester prodrug MS83, KLHDC2 prodrugs) [23][48].
5. **Chemical stability.** IMiD glutarimide rings hydrolyze rapidly in aqueous media and buffers, degrading potency in assays and complicating formulation [51][52]; the glutarimide stereocenter epimerizes (configurational instability), adding manufacturing/analytical burden [53]; a common pomalidomide-PEG SNAr route generates a cryptic acyl-substitution impurity [54]. Linker attachment point modulates both metabolic and hydrolytic stability [52].

### 5. Wet-lab effort per candidate (typical med-chem cycle)

There is no single published "hours-per-compound" figure; the field's own documentation is about **throughput engineering** because PROTAC SAR is inherently empirical (three bodies, linker length/composition/exit vector) [50]. Concrete anchors:

- **Linker SAR is the bottleneck.** Empirically exploring linker length/composition dominates cycle time; four published synthetic strategies (convergent routes, solid-phase, late-stage diversification) exist to raise throughput [50].
- **Direct-to-biology (D2B):** preparing unpurified linker analog sets and testing them directly in four cell-based assays (degradation + permeability) collapses the design–make–test cycle [49].
- **Parallel nanomole-scale synthesis** platforms produce arrays of PROTACs for rapid empirical SAR [58].
- **E3-ligand validation consumes a dedicated workflow** (6 steps, above) before a novel ligase can be used [40].
- **Vendor-reported IND timeline:** WuXi STA case study — a PROTAC candidate went from PCC (preclinical candidate confirmation) to IND submission in **13 months**, highlighting that modern CMC/process chemistry can compress the back half; the same case notes complexity from highly toxic intermediates [57] (vendor claim, medium confidence).
- **Per-assay costs of the validation stack:** the Q3 assay cascade (biophysics → ubiquitination → HiBiT kinetics → TMT proteomics → DMPK → PK/PD → in vivo) is the standard gauntlet a candidate passes before IND; each cycle is typically run on series (10s–100s of compounds) rather than singles.

**Inference (labeled):** for a single medicinal-chemistry cycle (one linker/warhead variant set), the practical expectation from the cited literature is weeks-to-months of synthesis + the full cellular cascade (HiBiT kinetics, immunoblot confirmation, mechanism controls), with whole-program lead optimization to a clinical candidate running roughly 1.5–3 years (13-month PCC→IND being an aggressive, vendor-reported best case [57]). Note: no source in this set gives a reproducible "compounds-per-chemist-per-year" number; that figure should be treated as unverified.

---

## Sources

1. FDA — "FDA approves vepdegestrant for ER-positive, HER2-negative, ESR1-mutated advanced or metastatic breast cancer" — https://www.fda.gov/drugs/resources-information-approved-drugs/fda-approves-vepdegestrant-er-positive-her2-negative-esr1-mutated-advanced-or-metastatic-breast
2. Arvinas — "Arvinas Announces FDA Approval of VEPPANU (vepdegestrant)..." — https://ir.arvinas.com/news-releases/news-release-details/arvinas-announces-fda-approval-veppanu-vepdegestrant-treatment
3. Reuters — "US FDA approves Pfizer, Arvinas' breast cancer drug" — https://www.reuters.com/business/healthcare-pharmaceuticals/us-fda-approves-pfizer-arvinas-breast-cancer-drug-2026-05-01/
4. SEC EDGAR — Arvinas Form 8-K (arvn-20260501) — https://www.sec.gov/Archives/edgar/data/1655759/000162828026029210/arvn-20260501.htm
5. CancerNetwork — "Vepdegestrant Outperforms Fulvestrant in PFS for ESR1-Mutant Advanced Breast Cancer" (ASCO LBA1000) — https://www.cancernetwork.com/view/vepdegestrant-outperforms-fulvestrant-in-pfs-for-esr1-mutant-advanced-breast-cancer
6. NEJM — Hamilton E, et al. "Vepdegestrant, a PROTAC Estrogen Receptor Degrader, in Advanced Breast Cancer" — https://www.nejm.org/doi/full/10.1056/NEJMoa2505725
7. Arvinas — Pipeline — https://www.arvinas.com/research-and-development/pipeline/
8. Arvinas — Q4 2025 financial results — https://ir.arvinas.com/news-releases/news-release-details/arvinas-reports-fourth-quarter-and-full-year-2025-financial
9. Kymera — Q2 2026 financial results — https://investors.kymeratx.com/news-releases/news-release-details/kymera-therapeutics-announces-second-quarter-2026-financial
10. Kymera — KT-621 BroADen data at AAD 2026 — https://investors.kymeratx.com/news-releases/news-release-details/kymera-therapeutics-presents-kt-621-broaden-data-late-breaking
11. ClinicalTrials.gov — NCT07412288 (KT-579) — https://clinicaltrials.gov/study/NCT07412288
12. Kymera — Pipeline — https://www.kymeratx.com/science-innovation/pipeline/
13. Kymera — Q1 2025 financial results — https://investors.kymeratx.com/news-releases/news-release-details/kymera-therapeutics-announces-first-quarter-2025-financial
14. C4 Therapeutics — Our Pipeline — https://c4therapeutics.com/our-pipeline/
15. ClinicalTrials.gov — NCT05668585 (CFT1946) — https://clinicaltrials.gov/study/NCT05668585
16. C4 Therapeutics — Q1 2025 results — https://ir.c4therapeutics.com/news-releases/news-release-details/c4-therapeutics-reports-first-quarter-2025-financial-results-and
17. C4 Therapeutics — Cemsidomide MOMENTUM Ph2 first patient dosed — https://ir.c4therapeutics.com/news-releases/news-release-details/c4-therapeutics-announces-first-patient-dosed-phase-2-momentum
18. ClinicalTrials.gov — NCT07516093 (NX-5948 DAYBreak CLL-306) — https://clinicaltrials.gov/study/NCT07516093
19. ClinicalTrials.gov — NCT04830137 (NX-2127) — https://clinicaltrials.gov/study/NCT04830137
20. BMS — FDA accepts iberdomide NDA — https://news.bms.com/news/details/2026/U-S--Food-and-Drug-Administration-Accepts-Bristol-Myers-Squibbs-New-Drug-Application-for-Iberdomide-in-Patients-with-Relapsed-or-Refractory-Multiple-Myeloma/default.aspx
21. EMA — "Targeted Protein Degradation (TPD) — EU-IN Horizon scanning report" — https://www.ema.europa.eu/en/documents/report/targeted-protein-degradation-eu-horizon-scanning-report_en.pdf
22. Beacon Intelligence — "TPD 2025 Landscape Review" — https://www.beacon-intelligence.com/landscape-reviews/tpd-2025-landscape-review/
23. Li Z, Huang X, Zhao X, Zhang Y, Li P. "The Expanding E3 Ligase-Ligand Landscape for PROTAC Technology." Targets 2025, 3(4), 30 — https://www.mdpi.com/2813-3137/3/4/30
24. "An E3 ligase guide to the galaxy of small-molecule-induced protein degradation" (Cell Chem Biol series) — https://www.sciencedirect.com/science/article/pii/S2451945621001574
25. "Targeted Protein Degradation: Current and Emerging Approaches for E3 Ligase Deconvolution" J. Med. Chem. 2024 — https://pubs.acs.org/doi/abs/10.1021/acs.jmedchem.4c00723
26. Li L, et al. "In vivo target protein degradation induced by PROTACs based on E3 ligase DCAF15." Signal Transduct. Target. Ther. 2020 — https://www.nature.com/articles/s41392-020-00245-0
27. "Discovery of DCAF16 Binders for Targeted Protein Degradation" — https://pubmed.ncbi.nlm.nih.gov/39882752/
28. Lucas SCC, et al. "Optimization of Potent Ligands for the E3 Ligase DCAF15..." J. Med. Chem. 2024 — https://pubs.acs.org/doi/abs/10.1021/acs.jmedchem.3c02136
29. "Harnessing the SPOP E3 Ubiquitin Ligase via a Bridged PROTAC Strategy" J. Med. Chem. 2025 — https://doi.org/10.1021/acs.jmedchem.5c00295
30. Henning NJ, et al. "Discovery of a Covalent FEM1B Recruiter for Targeted Protein Degradation Applications." JACS 2022 — https://pmc.ncbi.nlm.nih.gov/articles/PMC8928484/
31. "Exploiting the Cullin E3 Ligase Adaptor Protein SKP1 for Targeted Protein Degradation" — https://pubmed.ncbi.nlm.nih.gov/38305738/
32. Farrell BM, et al. "A synthetic KLHL20 ligand to validate CUL3KLHL20 as a potent E3 ligase for targeted protein degradation." Genes Dev. 2022 — https://genesdev.cshlp.org/content/36/17-18/1031.long
33. JoVE 65718 — "The Development and Application of Biophysical Assays for Evaluating Ternary Complex Formation Induced by PROTACs" — https://www.jove.com/t/65718/the-development-application-biophysical-assays-for-evaluating-ternary
34. "Unveiling BCL-xL-specific PROTAC efficiency and dissociation pathways using native mass spectrometry." Chem. Sci. 2026 — https://pubs.rsc.org/en/content/articlehtml/2026/sc/d5sc07400b
35. "Assays and Technologies for Developing Proteolysis Targeting Chimera Degraders" Future Med. Chem. 2020 — https://www.tandfonline.com/doi/full/10.4155/fmc-2020-0073
36. Revvity — AlphaLISA PROTAC application note — https://resources.revvity.com/pdfs/pbr-alphalisa-protac.pdf
37. "Comparative analysis of biophysical methods for monitoring protein proximity induction in the development of small molecule degraders" — https://www.sciencedirect.com/science/article/abs/pii/S030441652300096X
38. Riching KM, et al. "Quantitative Live-Cell Kinetic Degradation and Mechanistic Profiling of PROTAC Mode of Action." ACS Chem. Biol. 2019 — https://pubs.acs.org/doi/full/10.1021/acschembio.8b00692
39. Promega AN331 — "Kinetically Detecting and Quantitating PROTAC-Induced Degradation of Endogenous HiBiT-Tagged Target Proteins" — https://www.promega.com/-/media/files/resources/application-notes/nanobret/an331.pdf
40. "Workflow for E3 Ligase Ligand Validation for PROTAC Development" (PMC11851430) — https://pmc.ncbi.nlm.nih.gov/articles/PMC11851430/
41. "An In Vitro Pull-down Assay of the E3 Ligase:PROTAC:Substrate Ternary Complex to Identify Effective PROTACs" — https://pubmed.ncbi.nlm.nih.gov/34432242/
42. LifeSensors — PROTAC ubiquitination assays — https://lifesensors.com/protac-ubiquitination-assays/
43. "PK/PD modeling of targeted protein degraders" Drug Discov. Today 2025 — https://www.sciencedirect.com/science/article/pii/S1359644625000248
44. "A Mechanistic Pharmacodynamic Modeling Framework for the Assessment and Optimization of Proteolysis Targeting Chimeras (PROTACs)" Pharmaceutics 2023 — https://www.mdpi.com/1999-4923/15/1/195
45. "Kinetic Modeling of PROTAC-Induced Protein Degradation" ChemMedChem 2023 — https://chemistry-europe.onlinelibrary.wiley.com/doi/abs/10.1002/cmdc.202300530
46. "Physicochemical Property Determinants of Oral Absorption for PROTAC Protein Degraders" J. Med. Chem. 2023 — https://pubmed.ncbi.nlm.nih.gov/37279490/
47. "Optimising proteolysis-targeting chimeras (PROTACs) for oral drug delivery: a drug metabolism and pharmacokinetics perspective" — https://www.sciencedirect.com/science/article/abs/pii/S1359644620302932
48. "Property-based optimisation of PROTACs" RSC Med. Chem. 2025 — https://pmc.ncbi.nlm.nih.gov/articles/PMC11561549/
49. "Direct-to-Biology Accelerates PROTAC Synthesis and the Evaluation of Linker Effects on Permeability and Degradation" — https://pubmed.ncbi.nlm.nih.gov/35859867/
50. "Unraveling the Role of Linker Design in Proteolysis Targeting Chimeras" J. Med. Chem. 2021 — https://pubs.acs.org/doi/abs/10.1021/acs.jmedchem.1c00482
51. Min J, et al. "Phenyl-Glutarimides: Alternative Cereblon Binders for the Design of PROTACs" — https://pmc.ncbi.nlm.nih.gov/articles/PMC8648984/
52. "Influence of Linker Attachment Points on the Stability and Activity of IMiD-Containing PROTACs" — https://pmc.ncbi.nlm.nih.gov/articles/PMC8591746/
53. "A dihydrouracil CRBN ligand mitigates IMiD associated safety liabilities in heterobifunctional targeted protein degrader" Nat. Commun. 2026 — https://www.nature.com/articles/s41467-026-70663-1
54. "Identification and removal of a cryptic impurity in pomalidomide-PEG based PROTAC" Beilstein J. Org. Chem. 2025 — https://beilstein-journals.org/bjoc/content/pdf/1860-5397-21-28.pdf
55. "On-target toxicity of GSPT1 molecular glue degraders in mice" bioRxiv 2026 — https://www.biorxiv.org/content/10.64898/2026.02.14.705470v1.full-text
56. "Trends in Neosubstrate Degradation by Cereblon-Based Molecular Glues..." — https://pubmed.ncbi.nlm.nih.gov/38170610/
57. WuXi STA — "Case Study: A PROTAC Molecule from PCC to IND Submission in 13 Months" — https://sta.wuxiapptec.com/resources/case-study-a-protac-molecule-from-pcc-to-ind-submission-in-13-months/
58. "Rapid PROTAC Discovery Platform: Nanomole-Scale Array Synthesis" — https://pmc.ncbi.nlm.nih.gov/articles/PMC10726452/
59. "Extended pharmacodynamic responses observed upon PROTAC treatment" — https://pmc.ncbi.nlm.nih.gov/articles/PMC7083851/
60. "Tissue distribution and retention drives efficacy of rapidly cleared VHL-PROTACs" Commun. Med. 2024 — https://www.nature.com/articles/s43856-024-00505-y
61. "Targeted protein degradation via intramolecular bivalent glues" Nature 2024 (IBG1/DCAF15) — https://www.nature.com/articles/s41586-024-07089-6

---

## Notes on verification status
- Directly read (full text): [23] (MDPI E3 review, entire text incl. Table 1), [10] (Kymera AAD PR, entire), [5] (CancerNetwork VERITAC-2, entire), [30]-adjacent abstracts for FEM1B, plus abstracts/snippets for all others.
- Read as search-result snippets + provider page content: FDA [1], Arvinas PR [2], Kymera Q2'26 [9], C4 pipeline [14], BMS [20], Nurix [18][19], EMA [21].
- Not independently verified: Kymera's E3 ligase identity for KT-621/KT-579 (CRBN, per company materials — labeled inference); Beacon asset counts [22] (vendor); WuXi STA 13-month timeline [57] (vendor case study).
