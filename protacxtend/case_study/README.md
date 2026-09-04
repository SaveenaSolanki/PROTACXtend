# BRD4–VHL Six-PROTAC Prospective Case Study

Classification decision: the six BRD4–VHL PROTAC workflow is a
**prospective case study**, not a benchmark.

## Why prospective case study

- The repository contains **no measured potency (DC50/Dmax) data** for these
  six molecules — only structural descriptions and published SAR principles.
- Six molecules are therefore **never used as benchmark ground truth**.
- Benchmark ground truth requires outcome-derived measurements with
  citations; none exist here (see `benchmark/README.md` ground-truth policy).

## Workflow & commands

```
/run brd4-vhl-case-study          # preferred command
/run brd4-vhl-benchmark           # backward-compatible alias (kept)
/compare <six-protac-file>        # e.g. examples/brd4_vhl_6.csv
/compare                          # bundled blinded dataset
```

Phases: KNOW (load blinded candidates) → REASON (score retrieved structural
fields + calculated RDKit properties) → DESIGN (strengths/liabilities) →
DISCOVER (predicted ranking).

Evidence kinds are kept strictly separate:

| kind | meaning here |
|------|--------------|
| measured   | none — no experiment has been run |
| retrieved  | fields read from the blinded dataset (linker, junction, VHL-ligand status …) |
| calculated | RDKit descriptors computed for warhead/VHL-ligand SMILES |
| predicted  | structural-score potency bands |
| missing    | measured potency explicitly absent |

## Blinding

- Input (`examples/brd4_vhl_6.csv`) contains **no outcome-derived ranking**
  column. Any ranking information produced by prior analysis was removed
  from blinded inputs.
- The predicted ranking produced here is provisional. **The final ranking
  will be locked before any wet-lab outcome is accessed**, so it cannot be
  tuned to a known answer.

## Implementation

- Engine: `protacxtend/case_study/brd4_vhl_six.py`
- Tests: `tests/test_brd4_vhl_case_study.py`
- Datasets: `examples/brd4_vhl_6.csv`, `tui/examples/brd4_vhl_6.csv`
- TUI dispatch: `/run` route + `/compare` in `tui/src/app.ts`
