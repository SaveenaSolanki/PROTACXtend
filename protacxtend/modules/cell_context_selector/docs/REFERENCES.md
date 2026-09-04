# References — Module 5

Primary sources used in the module:

1. **PROTAC-Degradation-DB (labels + cell context)**
   PROTAC-Degradation-Predictor companion dataset: "Predicting PROTAC
   degradation activity with machine learning" (arXiv:2406.02637). The curated
   database file `PROTAC-Degradation-DB.csv` ships in the project's verified
   research clone (`data/protac_repos/repos/PROTAC-Degradation-Predictor/`,
   also used for this project's G6 reproduction). 2,141 rows; per-row cell
   type, DC50, Dmax, DOI provenance (PROTAC-DB + PROTAC-Pedia entries). The
   paper's `is_active()` AND rule (pDC50>=6.0, Dmax>=60) is the documented
   derivation we recompute for the binary view.

2. **DepMap Public 24Q4** — model/sample metadata (`Model.csv`, figshare file
   51065297) and transcriptomics
   `OmicsExpressionProteinCodingGenesTPMLogp1.csv` (figshare file 51065489).
   Cached under `outputs/omics_cache/` (gitignored); the small extracted
   cell-line × gene matrix is committed under `data/cell_context_expression.csv`
   with provenance in `data/omics_provenance.json`. DepMap (CCLE) is the
   expression-context descriptor source. No DepMap 24Q4 quantitative-proteomics
   matrix exists → proteomics leg unavailable.

3. **Module 4 (featurizer reuse)** — protacxtend/modules/degradation_ml
   (RDKit descriptors + ECFP4 + entity encoders; documented in Module 4 docs).

4. Context biology priors (used to choose the gene panel):
   - CRL/ubiquitin machinery in PROTAC pharmacology reviews (e.g., 60-gene
     panel spanning CRBN/VHL complexes, DDB1/CUL4/RBX1, E2s UBE2D/G/R/N/M/F,
     proteasome, DUBs, ABC transporters).
   - Existing in-repo curated expression priors
     (`data/benchmark/e3_expression_evidence.csv`, `expression_context.csv`)
     consulted for sanity but not used as model features (per-line coverage
     too small).

5. Degradation DB underlying entries: PROTAC-DB and PROTAC-Pedia (as compiled
   by the source paper; 231 unique DOIs retained per row in the curated CSV).
