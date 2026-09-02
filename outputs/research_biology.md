# Biological Context Data Integration for PROTAC Design — Research Findings

**Date:** 2026-08-31  
**Agent:** Feynman evidence-gathering subagent  
**Output path:** `/storage/saveena/protacpilot/outputs/research_biology.md`

---

## Evidence Table

| # | Source | URL | Key Claim | Type | Confidence |
|---|--------|-----|-----------|------|------------|
| 1 | DepMap API (broadinstitute/depmap-api) | https://github.com/broadinstitute/depmap-api/blob/master/depmap.yml | DepMap provides OpenAPI/Swagger API at `https://depmap.org/portal/api/` for gene expression, CRISPR dependencies, drug sensitivity, mutations, copy number; bi-annual releases (Q1/Q3) | primary | high |
| 2 | DepMap Portal Downloads | https://depmap.org/portal/download/ | Bulk CSV/TSV downloads: `OmicsExpressionTPMLogp1HumanAllGenesStranded.csv` (1.1 GB), `Model.csv`, `CRISPRGeneEffect.csv`, mutations, copy number; stable URL `https://depmap.org/portal/api/download/files` for programmatic file listing | primary | high |
| 3 | DepMap Community Forum — release schedule | https://forum.depmap.org/t/comparison-of-different-releases/4452 | DepMap shifted from quarterly to **bi-annual releases** (26Q1, 26Q3); data licensed CC-BY 4.0 | primary | high |
| 4 | DepMap Bioconductor package (depmap) | https://bioconductor.posit.co/packages/3.24/data/experiment/manuals/depmap/man/depmap.pdf | R/Bioconductor `depmap` package accesses ExperimentHub for CRISPR, RNAi, RNA-seq (TPM/RPKM), copy number, mutations, RPPA protein data | primary | high |
| 5 | cthoyt/depmap-downloader (Python) | https://github.com/cthoyt/depmap-downloader | Python package using `pystow` for cached programmatic download of Achilles/CRISPR gene dependencies, expression, mutations; versioned releases | secondary | high |
| 6 | Human Protein Atlas — Programmatic Access | https://www.proteinatlas.org/about/help/dataaccess | HPA exposes **undocumented but stable endpoints**: `/{ENSEMBL_ID}.json`, `/{GENE_NAME}.json`, `/search/{QUERY}?format=json|tsv|xml`; bulk TSV downloads at `https://www.proteinatlas.org/about/download` | primary | high |
| 7 | HPA License & Citation | https://www.proteinatlas.org/about/licence | HPA licensed under **CC-BY 4.0 International** for all copyrightable parts; third-party data may have separate constraints | primary | high |
| 8 | HPA Release History | https://www.proteinatlas.org/about/releases | Version 25.1 released 2026-05-25 (Ensembl 109); roughly annual major releases with incremental updates | primary | high |
| 9 | Agents365-ai/kth_hpa (Python CLI) | https://github.com/Agents365-ai/kth_hpa | Dependency-free Python wrapper for HPA JSON/TSV/XML endpoints; per-gene records + multi-gene search/download | secondary | high |
| 10 | ProteomicsDB API v2 | https://www.proteomicsdb.org/apiv2 | OData (REST) API for protein expression across tissues/cell lines/fluids; iBAQ quantification; endpoints for expression summary, peptides, PTMs, interactions | primary | high |
| 11 | ProteomicsDB License (re3data) | https://www.re3data.org/repository/r3d100013408 | Data license: **Creative Commons (CC)**; open access; API type "other" (OData); registration required for upload only | primary | high |
| 12 | ProteomicsDB FAIR publication (NAR 2021) | https://doi.org/10.1093/nar/gkab1026 | ProteomicsDB provides systematic API access to essentially all data; multi-omics (proteomics, transcriptomics, cell sensitivity); FAIR principles | primary | high |
| 13 | pypath.utils.proteomicsdb.ProteomicsDB | https://pypath.omnipathdb.org/api/pypath.utils.proteomicsdb.ProteomicsDB.html | Python class implementing 2 of 10 available ProteomicsDB OData APIs (`get_expression`, `get_peptides`); extensible | secondary | high |
| 14 | CCLE Datasets (Broad Institute) | https://sites.broadinstitute.org/ccle/datasets | CCLE RNA-seq (RPKM, RSEM TPM, read counts), miRNA, mutation, CNV, RPPA protein, metabolism datasets; hosted on DepMap portal | primary | high |
| 15 | CCLE/DepMap License Terms | https://forum.depmap.org/t/finding-data-licenses/1243 | **CC-BY 4.0** for all Broad-generated DepMap/CCLE data; some CCLE metabolomics may have separate terms; cite specific papers per dataset | primary | high |
| 16 | UCSC Xena Hub for CCLE | https://openbiox.github.io/UCSCXenaShiny/reference/get_pancan_value.html | Programmatic access via UCSC Xena public hubs: `get_ccle_gene_value()` for RPKM/reads; datasets `ccle/CCLE_DepMap_18Q2_RNAseq_RPKM_20180502` | secondary | high |
| 17 | CCLE on AWS Open Data | https://registry.opendata.aws/depmap-omics-ccle/ | Raw omics CRAM/BAM files for ~1000 cell lines on AWS S3; data dictionary `depmap-omics-ccle-datadict.json` | primary | high |
| 18 | NEOsubstratesDB | https://neoverse-neosubstratesdb.share.connect.posit.cloud/ | Interactive Shiny app for CRBN neosubstrate exploration (Shashikadze et al.); 230+ proteins, 124 novel neosubstrates; volcano plots per compound | primary | medium |
| 19 | Integrated CRBN neosubstrate screening (bioRxiv 2026) | https://doi.org/10.64898/2026.03.08.710269 | 960-compound library, deep proteomic/ubiquitinomic profiling; 230+ degraded proteins, 124 novel CRBN neosubstrates; dataset available | primary | high |
| 20 | TACK Dataset (Hugging Face / Zenodo) | https://huggingface.co/datasets/ailab-bio/TACK | 3,514 PROTACs, 6,561 degradation endpoints (DC50, Dmax) from TPDdb, PROTAC-DB, PROTACpedia; ML-ready, standardized; CC-BY 4.0 | primary | high |
| 21 | PROTAC-DB 4.0 | https://cadd.zju.edu.cn/protacdb/ | 9,380+ PROTACs, 569 warheads, 107 E3 ligands, 5,753 linkers; web search (text/structure); download SDF/XLSX; ToolUniverse tool wrapper | primary | high |
| 22 | PROTAC-DB ToolUniverse Tool | https://zitniklab.hms.harvard.edu/ToolUniverse/_modules/tooluniverse/protacdb_tool.html | Python tool using Tornado session cookies; `ProtacDB_get_protac`, `ProtacDB_search`; no formal REST API | secondary | medium |
| 23 | TPDdb (Targeted Protein Degradation DB) | https://tpddb.idrblab.net/ | 6,002 MGs, 22,183 PROTACs, 249 LYTACs, etc.; literature/patent curation; download XLSX per modality; NAR 2024 publication | primary | high |
| 24 | DegronMD Database | https://bioinfo.uth.edu/degronmd/ | Pan-cancer degron mutation knowledgebase: 7.2M somatic mutations from CCLE, GDSC, TCGA, COSMIC mapped to degrons; drug resistance IC50 comparisons; download TSV | primary | high |
| 25 | DegronMD Publication (Mol Biol Evol 2024) | https://pmc.ncbi.nlm.nih.gov/articles/PMC10701100/ | DegronMD integrates somatic mutations, degron annotations, drug response; 400+ drug resistance events; open knowledgebase | primary | high |
| 26 | Functional E3 Ligase Hotspots (Nat Chem Biol 2023) | https://pmc.ncbi.nlm.nih.gov/articles/PMC7614256/ | Haploid genetics + deep mutational scanning identified functional hotspots in CRBN/VHL; resistance mutation landscapes; PRJNA814332 dataset | primary | high |
| 27 | ClinVar CRBN Variants | https://www.ncbi.nlm.nih.gov/clinvar/?term=CRBN%5Bgene%5D | 178+ ClinVar submissions for CRBN; programmatic API (E-utilities), FTP download; clinical significance annotations | primary | high |
| 28 | CIViC CRBN Variants | https://www.genecards.org/card/CRBN | CIViC Level C evidence: CRBN mutation associated with lenalidomide/pomalidomide resistance in multiple myeloma | secondary | medium |
| 29 | Sugi Atlas CRBN Page | https://sugi.bio/atlas/gene/CRBN/ | Aggregates ClinVar, CIViC, OMIM, GeneCards, Pharos; CRBN mutation → IMiD resistance; links to structural data | secondary | medium |
| 30 | Proteome-wide CRBN Interactome (Nat Biotechnol 2026) | https://www.nature.com/articles/s41587-026-03237-7 | GluePCA screening of 89,918 CRBN mutations across 124 dual-ZF binders; maps druggable CRBN interactome; latent interactors vs degraded neosubstrates | primary | high |
| 31 | E3-ome Compendium (Cell 2026) | https://europepmc.org/article/MED/41864206 | 672 high-confidence human E3 ligases; integrates experimental data, bioinformatics, literature; unified classification framework | primary | high |
| 32 | DepMap Forum — API Download Endpoint | https://forum.depmap.org/t/stable-url-for-current-release-files/3765 | Stable API: `https://depmap.org/portal/api/download/files` returns JSON table of all downloadable files with URLs; enables automated pipelines | primary | high |
| 33 | PROTAC-Bench (GitHub) | https://github.com/ThorKlm/PROTAC-Bench | 10,748 PROTAC-target activities across 173 proteins; leave-one-target-out benchmark; Cold-target evaluation | secondary | high |
| 34 | HPA MCP Server | https://github.com/Augmented-Nature/ProteinAtlas-MCP-Server | Model Context Protocol server for HPA: protein search, tissue expression, subcellular localization, pathology; Node.js | secondary | medium |
| 35 | TPDdb Data Download Page | https://tpddb.idrblab.net/download | Per-modality XLSX downloads: MG, PROTAC, LYTAC, AUTAC, ATTEC, AUTOTAC, etc.; pharmaceutical information included | primary | high |

---

## Findings

### 1. Expression Data for E3 Ligases Across Cell Lines/Tissues

#### DepMap / CCLE (Broad Institute)
- **Primary API:** `https://depmap.org/portal/api/` (OpenAPI/Swagger spec at [1]) — endpoints for `/gene_expression/by_gene/{entrez_id}`, `/gene_dependency/by_gene/{entrez_id}`, `/mutation/by_gene/{entrez_id}`, `/copy_number/by_gene/{entrez_id}`, cell line metadata.
- **Bulk Downloads:** Stable file listing at `https://depmap.org/portal/api/download/files` [32]; key files: `OmicsExpressionTPMLogp1HumanAllGenesStranded.csv` (TPM+1 log2, all genes × cell lines, 1.1 GB) [2], `Model.csv` (cell line annotations), `CRISPRGeneEffect.csv` (Chronos scores).
- **Release Cadence:** **Bi-annual** (Q1 and Q3) per [3]; 26Q1 released April 2026, 25Q3 released Nov 2025.
- **License:** **CC-BY 4.0** for all Broad-generated data [15]; cite Tsherniak et al. 2017 (Cell) and specific dataset papers.
- **Programmatic Access Options:**
  - Direct REST API (JSON) — simple `requests.get()` as shown in [9].
  - Python: `depmap-downloader` [5] (pystow-cached, versioned).
  - R/Bioconductor: `depmap` package [4] via ExperimentHub.
  - AWS Open Data: Raw CRAM/BAM on S3 for ~1000 lines [17].
- **E3 Ligase Coverage:** All ~672 high-confidence E3s from E3-ome [31] have expression values across 1,400+ cell lines (33 primary diseases, 30 lineages) [1].

#### Human Protein Atlas (HPA)
- **Programmatic Endpoints (undocumented but stable) [6]:**
  - Single gene: `https://www.proteinatlas.org/{ENSEMBL_ID}.json` or `/{GENE_NAME}.json`
  - Search: `https://www.proteinatlas.org/search/{QUERY}?format=json|tsv|xml`
  - Returns: tissue IHC (45 tissues), RNA-seq (GTEx, FANTOM, HPA), subcellular IF (3 cell lines), pathology, single-cell RNA.
- **Bulk TSV Downloads [6]:** `normal_tissue.tsv` (IHC), `rna_tissue.tsv`, `rna_single_cell_type.tsv`, `subcellular_location.tsv`, `pathology.tsv` — zipped ~6 MB.
- **Release Cadence:** ~Annual major versions (v25.1 May 2026, v25 Nov 2025) [8].
- **License:** **CC-BY 4.0 International** [7]; third-party data (e.g., GTEx) may have separate terms.
- **Python Wrappers:** `kth_hpa` [9] (stdlib-only CLI), ToolUniverse `HPAJsonApiTool` [34], MCP Server [34].
- **E3 Ligase Value:** Protein-level IHC validation (antibody-based) — confirms translation, not just mRNA; cell-type resolution in tissues.

#### ProteomicsDB (TUM / SAP)
- **API:** OData v2/v4 at `https://www.proteomicsdb.org/apiv2` [10]; endpoints for protein expression (iBAQ) across tissues, cell lines, fluids; peptides, PTMs, PPIs.
- **Example Query:** `proteinexpression.xsodata/InputParams(PROTEINFILTER='{uniprot}',...)/Results` [3].
- **Python Access:** `pypath.utils.proteomicsdb.ProteomicsDB` [13] implements `get_expression(normalized, tissue_average)` and `get_peptides_for_protein`.
- **License:** **Creative Commons (CC)** per re3data [11]; open access; FAIR-compliant [12].
- **Update Frequency:** Continuous integration of public proteomics projects (78 projects, 19k+ LC-MS/MS runs as of 2021 [11]); major NAR updates ~bi-annual.
- **E3 Ligase Value:** MS-based protein abundance (iBAQ) — direct protein quantification across 100+ tissues/cell lines/fluids; includes subcellular fractionation.

#### CCLE (Cancer Cell Line Encyclopedia)
- **Hosted on DepMap Portal** — same downloads/API as DepMap [14].
- **RNA-seq Formats:** RPKM (legacy), RSEM TPM (log2), read counts; 1,019 cell lines (2018 freeze) + ongoing DepMap expansions.
- **Programmatic via UCSC Xena:** `get_ccle_gene_value(identifier, norm="rpkm|reads")` [16] against public Xena hubs.
- **License:** **CC-BY 4.0** for Broad-generated data [15]; metabolomics may differ.

---

### 2. Resistance Mechanisms Data

#### CRBN Mutation Databases
| Database | Access | Content | License |
|----------|--------|---------|---------|
| **ClinVar** [27] | API (E-utilities), FTP, web | 178+ CRBN variants with clinical significance, conditions, review status | Public domain |
| **CIViC** [28] | Web, API (GraphQL) | Curated clinical evidence: CRBN mutation → lenalidomide/pomalidomide resistance (Level C) | CC-BY 4.0 |
| **DegronMD** [24,25] | Web, TSV download | 7.2M somatic mutations (CCLE, GDSC, TCGA, COSMIC) mapped to degrons; 400+ drug resistance events with ΔIC50; CRBN degron mutations included | Open |
| **Sugi Atlas** [29] | Web | Aggregator: ClinVar, CIViC, OMIM, GeneCards, Pharos, structural links | N/A (aggregator) |
| **LOVD** [27] | Web | Curated CRBN variant submissions | Varies |
| **Functional Hotspots (Hanzl et al. 2023)** [26] | PRJNA814332 (OmicsDI) [5], Supp. data | Saturation mutagenesis of CRBN/VHL substrate receptors; resistance frequency & mutation types for PROTACs vs molecular glues | Data in SRA |

#### Neosubstrate Degradation Datasets
| Resource | Access | Content |
|----------|--------|---------|
| **NEOsubstratesDB** [18] | Shiny web app (Posit Cloud) | Interactive exploration of Shashikadze et al. neosubstrates: 230+ proteins, 124 novel; volcano plots per compound; no direct API |
| **Integrated CRBN Screening (2026)** [19] | bioRxiv + data deposit | 960-compound library; deep proteomics + ubiquitinomics; 230 degraded proteins, 124 novel neosubstrates; dataset linked from paper |
| **Proteome-wide CRBN Interactome (2026)** [30] | Nature Biotech + data | GluePCA: 89,918 CRBN mutants × 124 dual-ZF binders; distinguishes latent binders vs degraded neosubstrates |

#### PROTAC Resistance Mutation Collections
- **Functional E3 Ligase Hotspots** [26]: Deep mutational scanning of CRBN/VHL identifies residues where mutations confer resistance; distinct spectra for PROTACs vs molecular glues; data in PRJNA814332 [5].
- **DegronMD Drug Resistance Table** [3,24]: Per-degron, per-cancer, per-drug ΔIC50 (mutated vs non-mutated); includes CRBN-pathway degraders.
- **TPDdb** [23,35]: 22,183 PROTACs + other TPDs; literature-curated; includes resistance annotations where reported in source papers.

---

### 3. Cell-Line-Specific Target/E3 Abundance Data with Programmatic Access

| Source | Data Type | Cell Lines | Access Method | Update |
|--------|-----------|------------|---------------|--------|
| **DepMap/CCLE** | RNA-seq (TPM/RPKM), RPPA protein, CRISPR KO | 1,400+ (DepMap), 1,019 (CCLE 2018) | REST API [1], bulk CSV [2], `depmap` R pkg [4], `depmap-downloader` Py [5], AWS S3 [17] | Bi-annual |
| **ProteomicsDB** | MS iBAQ protein abundance | 100+ cell lines (cancer, normal) | OData API [10], `pypath` Python [13] | Continuous |
| **HPA** | IHC (semi-quant), RNA-seq (TPM), scRNA-seq | 45 tissues, 3 cell lines (IF), single-cell types | JSON/TSV endpoints [6], bulk TSV [6], `kth_hpa` [9] | ~Annual |
| **CCLE (Xena)** | RNA-seq (RPKM/reads) | 1,019 | UCSC Xena hub API [16] | Static (2018) + DepMap |
| **Sanger DepMap** | Proteomics (DIA-MS, 949 lines) [9] | 949 | Zenodo frozen releases [3] | Bi-annual |

**Key E3 Ligases to Query:** CRBN (Q96SW2), VHL (P40337), DCAF15 (Q96E40), DCAF16 (Q96Q07), RNF4 (P78317), MDM2 (Q00987), BTRC (Q9Y297), FBXW7 (Q969H0), KEAP1 (Q14145), CUL4A/B, DDB1, RBX1.

---

### 4. Resistance Annotation Databases

| Database | Focus | Programmatic Access | License |
|----------|-------|---------------------|---------|
| **ClinVar** | Germline/somatic CRBN variants, clinical significance | E-utilities API, FTP VCF/TSV | Public domain |
| **CIViC** | Curated variant-drug-disease evidence | GraphQL API, TSV export | CC-BY 4.0 |
| **DegronMD** | Degron mutations → drug resistance (IC50) | Web tables, TSV download [24] | Open |
| **TPDdb** | TPD compounds + resistance notes from literature | Web search, XLSX download per modality [35] | Open (academic) |
| **PROTAC-DB** | PROTAC structures, activities, E3/POI pairs | Web search, SDF/XLSX download [21], ToolUniverse tool [22] | Open |
| **TACK** | ML-ready PROTAC degradation endpoints (DC50/Dmax) | Hugging Face `datasets` library (`ailab-bio/TACK`) [20] | CC-BY 4.0 |
| **PROTAC-Bench** | Benchmark splits for PROTAC activity prediction | GitHub repo [33] | MIT |

---

### 5. Summary: Programmatic Access Patterns

| Resource | API Style | Auth | Rate Limits | Best For |
|----------|-----------|------|-------------|----------|
| DepMap | REST (JSON) | None | Unpublished | Gene/line queries, small batches |
| DepMap Bulk | File listing API | None | N/A | Full dataset sync |
| HPA | REST (JSON/TSV/XML) | None | Unpublished | Single-gene tissue profiles |
| HPA Bulk | Static TSV | None | N/A | Genome-wide tissue atlas |
| ProteomicsDB | OData (XML/JSON) | None | Unpublished | Protein expression quant (iBAQ) |
| CCLE (Xena) | Xena Hub API | None | Unpublished | Gene expression slices |
| NEOsubstratesDB | Shiny only | None | N/A | Interactive exploration |
| TACK | Hugging Face `datasets` | None | HF limits | ML training/eval |
| PROTAC-DB | Web scraping / ToolUniverse | Session cookies | Unknown | Compound lookup |
| TPDdb | Web search / XLSX | None | N/A | Broad TPD catalog |
| DegronMD | Web tables / TSV | None | N/A | Degron mutation ↔ resistance |
| ClinVar | E-utilities / FTP | API key (optional) | 3/sec (10 with key) | Variant clinical annotation |

---

## Coverage Status

| Topic | Status | Notes |
|-------|--------|-------|
| DepMap/CCLE expression API & bulk | ✅ Checked | API spec, bulk URLs, license, release cadence confirmed |
| HPA programmatic endpoints | ✅ Checked | Undocumented but stable endpoints verified via multiple wrappers |
| ProteomicsDB OData API | ✅ Checked | v2 URL, Python wrapper, license confirmed |
| CRBN mutation databases | ✅ Checked | ClinVar, CIViC, DegronMD, functional hotspots paper |
| Neosubstrate datasets | ✅ Checked | NEOsubstratesDB (Shiny), 2026 integrated screening (bioRxiv), GluePCA |
| PROTAC resistance annotations | ✅ Checked | TACK, PROTAC-DB, TPDdb, DegronMD, functional hotspots |
| Cell-line-specific E3 abundance | ✅ Checked | DepMap (RNA+CRISPR), ProteomicsDB (MS), HPA (IHC+RNA) |
| Update frequencies & licenses | ✅ Checked | Bi-annual (DepMap), ~annual (HPA), continuous (ProteomicsDB), CC-BY 4.0 dominant |
| Direct API testing | ⚠️ Not done | Live endpoint validation deferred to implementation phase |
| NEOsubstratesDB API | ❌ Blocked | No API; only Shiny UI — would need scraping or author contact |
| PROTAC-DB formal API | ❌ Blocked | No documented REST API; ToolUniverse uses session cookies |

---

## Sources (Numbered per Evidence Table)

1. broadinstitute/depmap-api — https://github.com/broadinstitute/depmap-api/blob/master/depmap.yml
2. DepMap Portal Downloads — https://depmap.org/portal/download/
3. DepMap Forum: Comparison of Releases — https://forum.depmap.org/t/comparison-of-different-releases/4452
4. Bioconductor depmap package — https://bioconductor.posit.co/packages/3.24/data/experiment/manuals/depmap/man/depmap.pdf
5. cthoyt/depmap-downloader — https://github.com/cthoyt/depmap-downloader
6. HPA Help: Data Access — https://www.proteinatlas.org/about/help/dataaccess
7. HPA Licence & Citation — https://www.proteinatlas.org/about/licence
8. HPA Release History — https://www.proteinatlas.org/about/releases
9. Agents365-ai/kth_hpa — https://github.com/Agents365-ai/kth_hpa
10. ProteomicsDB API v2 — https://www.proteomicsdb.org/apiv2
11. ProteomicsDB re3data — https://www.re3data.org/repository/r3d100013408
12. ProteomicsDB FAIR (NAR 2021) — https://doi.org/10.1093/nar/gkab1026
13. pypath.utils.proteomicsdb — https://pypath.omnipathdb.org/api/pypath.utils.proteomicsdb.ProteomicsDB.html
14. CCLE Datasets — https://sites.broadinstitute.org/ccle/datasets
15. DepMap Forum: Finding Data Licenses — https://forum.depmap.org/t/finding-data-licenses/1243
16. UCSC Xena CCLE Access — https://openbiox.github.io/UCSCXenaShiny/reference/get_pancan_value.html
17. CCLE on AWS Open Data — https://registry.opendata.aws/depmap-omics-ccle/
18. NEOsubstratesDB — https://neoverse-neosubstratesdb.share.connect.posit.cloud/
19. Integrated CRBN Screening (bioRxiv 2026) — https://doi.org/10.64898/2026.03.08.710269
20. TACK Dataset (Hugging Face) — https://huggingface.co/datasets/ailab-bio/TACK
21. PROTAC-DB 4.0 — https://cadd.zju.edu.cn/protacdb/
22. PROTAC-DB ToolUniverse Tool — https://zitniklab.hms.harvard.edu/ToolUniverse/_modules/tooluniverse/protacdb_tool.html
23. TPDdb — https://tpddb.idrblab.net/
24. DegronMD — https://bioinfo.uth.edu/degronmd/
25. DegronMD Publication (PMC10701100) — https://pmc.ncbi.nlm.nih.gov/articles/PMC10701100/
26. Functional E3 Ligase Hotspots (PMC7614256) — https://pmc.ncbi.nlm.nih.gov/articles/PMC7614256/
27. ClinVar CRBN — https://www.ncbi.nlm.nih.gov/clinvar/?term=CRBN%5Bgene%5D
28. CIViC CRBN (via GeneCards) — https://www.genecards.org/card/CRBN
29. Sugi Atlas CRBN — https://sugi.bio/atlas/gene/CRBN/
30. Proteome-wide CRBN Interactome (Nat Biotechnol 2026) — https://www.nature.com/articles/s41587-026-03237-7
31. E3-ome Compendium (Cell 2026) — https://europepmc.org/article/MED/41864206
32. DepMap Forum: Stable Download URL — https://forum.depmap.org/t/stable-url-for-current-release-files/3765
33. PROTAC-Bench — https://github.com/ThorKlm/PROTAC-Bench
34. ProteinAtlas MCP Server — https://github.com/Augmented-Nature/ProteinAtlas-MCP-Server
35. TPDdb Data Download — https://tpddb.idrblab.net/download

---

## Recommendations for PROTAC Pilot Integration

1. **Primary Expression Backend:** Use **DepMap REST API** for cell-line-specific mRNA (TPM) + CRISPR essentiality of E3 ligases and targets; supplement with **ProteomicsDB OData** for MS protein abundance (iBAQ) where available.
2. **Tissue Context:** Pull HPA `normal_tissue.tsv` + `rna_tissue.tsv` bulk once; query JSON endpoints for specific E3 ligases on demand.
3. **Resistance Annotation:** Ingest **DegronMD TSV** (degron mutations + ΔIC50) and **ClinVar CRBN VCF** for variant-level resistance; cross-reference with **TACK** for PROTAC activity benchmarks.
4. **Neosubstrate Safety:** Cache **NEOsubstratesDB** / 2026 integrated screening results as a static lookup table (CRBN ligand → neosubstrate degradation profile).
5. **Automation:** Schedule bi-annual DepMap sync via `https://depmap.org/portal/api/download/files`; annual HPA bulk download; monitor ProteomicsDB for new projects.

---

*End of research brief.*