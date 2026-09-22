# Gap-completion data curation & analysis

Scripts to reproduce the three data-backed capability completions. Run from the
repository root with the project environment.

```bash
# 1. E3 expression/context atlas — Human Protein Atlas (RNA + protein IHC + MS)
python scripts/gap_completion/curate_e3_hpa.py
#    -> protacxtend/modules/e3_opportunity/data/hpa_tissue_{rna,protein_ihc,protein_ms}.csv
#    -> .../hpa_tissue_provenance.json      (raw JSON cached in outputs/omics_cache/hpa/)

# 2. BRD/BET ligand + domain selectivity evidence
python scripts/gap_completion/curate_brd_bet.py
#    -> protacxtend/modules/brd_bet_intelligence/data/brd_bet_ligand_evidence.csv
#    -> .../brd_bet_domain_summary.csv, .../brd_bet_bd1_bd2_pairs.csv
#    -> .../brd_bet_provenance.json

# 3. Ternary cooperativity records + calibration
python scripts/gap_completion/curate_cooperativity.py
python -m protacxtend.modules.cooperativity_alpha_predictor.calibration
#    -> .../cooperativity_alpha_predictor/data/cooperativity_records.csv
#    -> .../cooperativity_provenance.json, .../calibration_report.json

# 4. Validation tables + 7 publication figures (600-dpi PNG + PDF)
python scripts/gap_completion/validate_and_figures.py
#    -> outputs/gap_completion/{tables,figures}/ and validation_summary.json
```

All external values are cached under `outputs/omics_cache/`; re-running is
offline-stable. Provenance JSON files record the source, retrieval time and
columns. No value is fabricated or imputed.

Tests:

```bash
python -m pytest \
  protacxtend/modules/brd_bet_intelligence/tests \
  protacxtend/modules/e3_opportunity/tests \
  protacxtend/modules/cooperativity_alpha_predictor/tests \
  protacxtend/tests/test_evaluate_protac_candidate.py -q
```
