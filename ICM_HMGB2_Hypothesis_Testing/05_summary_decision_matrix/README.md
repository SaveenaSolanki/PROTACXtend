# 05_summary_decision_matrix — Hypothesis Decision Framework

## Decision Matrix

| Hypothesis | Computational Evidence Needed | Supported? | Next Action |
|------------|------------------------------|------------|-------------|
| **H1: PROTAC fails due to bad exit vector** | HMGB2 binding ✅, ternary geometry poor ✅ | **YES** ✅ | Redesign warhead (ICM analog or new scaffold). Linker optimization alone cannot rescue. |
| **H2: Ring-modified ICM can rescue PROTAC** | Improved binding + better linker handle | **NOT TESTED** | Design 15–25 ICM analogs, dock to HMGB2, screen for exit vector. Synthesize top candidate. |
| **H3: ICM is CRBN molecular glue** | Stable HMGB2–ICM–CRBN ternary | **NO** ❌ | Do CRBN KO / MG132 / ubiquitin assay to rule out definitively. Low prior from docking data. |
| **H4: ICM degradation is CRBN-independent** | No CRBN ternary, alternative degradation plausible | **NOT TESTED** | If cellular degradation observed but CRBN-independent, screen alternative E3s and degradation pathways. |

## Summary of Computational Findings

| Metric | H1 (PROTAC) | H2 (Analog) | H3 (Glue) | H4 (Other) |
|--------|-------------|-------------|------------|------------|
| Status | ✅ COMPLETE | ⏳ Proposed | ✅ COMPLETE | ⏳ Proposed |
| ICM-HMGB2 binding | Confirmed | Needs testing | Confirmed | Confirmed |
| Exit vector | ❌ Buried (both OH groups) | Needs testing | Not needed | Not needed |
| CRBN interface | ❌ Linker can't bridge | Needs testing | ⚠️ HMGB2-CRBN interface exists, but ICM not involved | Needs testing |
| Lysine accessibility | 40/40 within 60 Å | 40/40 within 60 Å | 40/40 within 60 Å | 40/40 within 60 Å |
| Ternary stability | ❌ 0/3600 passes | Needs testing | ❌ ICM contributes 0 contacts | Needs testing |
| **Verdict** | **SUPPORTED** | **Pending** | **REJECTED** | **Pending** |

## Recommended Action Plan

### Priority 1: Report H1 (completed, robust)
The PROTAC failure analysis is complete and defensible. The data package includes:
- 3600 P4ward poses → 0 passed linker filter
- 16 alternative linkers tested → best is 0.8% pass rate (C14-PEG5)
- Exit vector analysis: both OH groups point into HMGB2 (100°–105° from CRBN)
- ICM burial visualization: all 29 atoms within 3–6 Å of protein surface

### Priority 2: Cellular experiment for H3 (3 days, ~$500)
The fastest way to resolve the molecular glue question:
```
Treat cells with ICM (0.1, 1, 5 μM) ± MG132 ± CRBN siRNA
Blot for HMGB2 at 24 h
If HMGB2 drops → degradation is real
If MG132 rescues → proteasomal
If CRBN siRNA rescues → CRBN-dependent
```

### Priority 3: H2 or H4 depending on H3 result
- **If H3 positive (CRBN-dependent):** Optimize ICM as a glue (analogs with better CRBN recruitment)
- **If H3 negative (CRBN-independent):** Pursue H2 (ICM analog for PROTAC) or H4 (alternative mechanism)

## Files in this directory

| File | Status | Description |
|------|--------|-------------|
| `hypothesis_score_table.xlsx` | 🔶 Not yet created | Structured scores for each hypothesis |
| `final_decision_tree.pptx` | 🔶 Not yet created | Decision tree for next steps |
| `manuscript_ready_summary.docx` | 🔶 Not yet created | Summary for publication |
