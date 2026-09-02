# References — Module 6 (E3 opportunity engine)

1. **PROTAC degradation labels / precedent (retrospective pairs)**
   PROTAC-Degradation-DB and the paper's machine-learning companion
   (arXiv:2406.02637); project research clone under
   `data/protac_repos/repos/PROTAC-Degradation-Predictor/` (already used for
   G6 reproduction). Curated in-repo by Module 5
   (`modules/cell_context_selector/dataset.py`); 231 source DOIs retained.
2. **E3 ligand / recruiter library (DOI-cited rows)**
   `protacxtend/data/curated_e3_ligands.csv` (107 cited rows; CRBN,
   VHL, DCAF1/11/15/16, FBXO22, FEM1B, IAP/cIAP1/XIAP, KEAP1, KLHDC2, KLHL20,
   MDM2, RNF114, RNF4, UBR1). Original registry: `SynGlue_Py/data/e3_ligand.csv`.
   Example citations carried in the table (pomalidomide/lenalidomide
   10.1038/nature13527; VHL ligands 10.1021/jacs.8b05807, 10.1021/jm5011258;
   DCAF15 ligand 10.1126/science.aal3755; cIAP1 ligand 10.1016/j.bmcl.2014.09.022).
3. **Expression context** — DepMap Public 24Q4: `Model.csv` (figshare
   51065297) and `OmicsExpressionProteinCodingGenesTPMLogp1.csv` (figshare
   51065489); cached under `outputs/omics_cache/`. Module 5 documents the
   extraction pipeline and mapping (137/180 mapped lines).
4. **Subcellular localization** — UniProtKB/Swiss-Prot (human, reviewed),
   SUBCELLULAR LOCATION comments, fetched 2026-09-02 via
   `rest.uniprot.org/uniprotkb/search` (gene_exact + organism 9606); cached
   offline in `data/uniprot_localization.csv` (78 genes).
5. **Curated ternary/complex PDB facts** — CRBN-DDB1 4CI2, BRD4-CRBN 6BN7,
   VHL-ElonginBC 4W9O, BRD4-VHL 5T35 (retained from the project's E3-context
   engine evidence tables, `tools/e3_context_engine.py`).
6. **Resistance notes** (curated, documented) — CRBN loss/mutation under IMiD
   selection in multiple myeloma; VHL loss-of-function in clear-cell RCC.
7. **Static-geometry/SASA machinery** — Module 2
   (`lysine_ubiquitination_feasibility`, Shrake-Rupley 1973 numeric SASA);
   reused for the surface-lysine census when a POI structure is provided.
8. **E3 catalog families/modes** — standard ubiquitin-system classification
   (RING/CRL/HECT/RBR/U-box/IAP) as commonly applied in PROTAC reviews; the
   catalog itself is a project-curated table (see e3_catalog.py docstring).
