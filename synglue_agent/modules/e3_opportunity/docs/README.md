# Module 6 — Novel E3 Ligase Opportunity Engine

`rank_e3_ligases(poi, cell_line=None, tissue=None, disease=None, warhead=None,
poi_structure=None, top_k=10)` ranks candidate E3 ligases for PROTAC
development across **independent, evidence-gated axes** — never by expression
alone. See SPEC.md, VALIDATION.md, LIMITATIONS.md, REFERENCES.md.

```python
from synglue_agent.modules.e3_opportunity import rank_e3_ligases
out = rank_e3_ligases("BRD4", cell_line="K562", top_k=10)
for c in out["candidates"]:
    print(c["rank"], c["e3_gene"], c["verdict"], c["overall_rank_score"])
```

## What is evaluated per candidate
cell-context expression (E3 + adaptor + POI, DepMap 24Q4 percentiles) ·
subcellular compatibility (UniProt) · recruiter tractability (DOI-cited
library; demo ligands excluded) · biological precedent (curated measured
rows) · structural availability (ternary feasibility stays **UNKNOWN** without
ternary data) · lysine opportunity (only when a POI structure is supplied) ·
selectivity opportunity · per-axis OOD/uncertainty flags.

## Verdict semantics (hard rules)
- **SUPPORTED** — direct measured precedent for this POI in the curated
  dataset AND strong multi-axis evidence.
- **PROMISING** — a chemical handle (cited recruiter) or usage signal with
  decent evidence coverage; never expression-only.
- **EXPLORATORY** — partial positive signal (e.g., high expression in context
  alone); recommended next test explains what evidence is missing.
- **INSUFFICIENT EVIDENCE** — no usable evidence (incl. unresolved POI).

Low E3 expression (<20th percentile) caps the verdict at EXPLORATORY.
`structural_feasibility` is always None unless a resolved/docked ternary
complex is supplied — no mechanistic claim is fabricated.

## Files
`e3_catalog.py` (30-E3 catalog, families/adaptors/curated facts) ·
`dataset.py` (recruiters + retrospective pairs) · `context.py` (expression) ·
`localization.py` (UniProt) · `recruiters.py` · `structure.py` · `lysines.py`
· `selectivity.py` · `features.py` · `models.py` (grouped benchmark,
baselines, ablations) · `rank.py` (scoring/verdicts) · `uncertainty.py` ·
`predict.py` (`rank_e3_ligases`) · `schemas.py` · tests/ · docs/ ·
artifacts/benchmark_results.json. Agent tool: `run_e3_opportunity`.

## Run
```
python -m pytest synglue_agent/modules/e3_opportunity/tests/ -q   # 17 tests
python -c "from synglue_agent.modules.e3_opportunity import rank_e3_ligases; \
import json; print(json.dumps(rank_e3_ligases('BTK', cell_line='K562',
top_k=5), indent=1, default=str)[:2000])"
```

## Data honesty
All expression/recruiter/precedent values are measured or DOI-cited; every
absence is reported as absence. A retrospective benchmark (VALIDATION.md)
shows expression-only is at chance (AUROC 0.49) and gates every claim.
