# ProtacXtend Experimental Study — presentation

**Deck:** `PROTACXTEND_STUDY_DECK.pptx` — 39 slides, 16:9, **20 embedded figures**, speaker notes on every slide.
**Figures:** `figures/` — 18 figures, each as PNG (400 dpi) + PDF + SVG vector.
**Rebuild:**
```bash
python study/make_figures.py        # real figures from repo data
python study/build_presentation.py  # the deck
```

## Figure provenance (honesty labels are printed on the slides)

**REAL — computed from files on disk**
| Figure | Source |
|---|---|
| `f06_architecture` | source audit (counts) |
| `f07_module_scale` | source tree (LOC/files) |
| `f01_benchmark_inventory` | benchmark + benchmark500 + sota/eval |
| `f02_governed_composition` | `benchmark/ground_truth/*.json` |
| `f03_b500_domains`, `f04_b500_difficulty` | `benchmark500/cases/*.jsonl` |
| `f05_capability_readiness` | `config/capability_backend_crosswalk.yaml` |
| `f08_closed48_outcomes` | `benchmark_results/closed48/.../results_table.csv` (n=144) |
| `f09_closed48_latency`, `f10_closed48_evidence` | same real run |
| `f11_trace_events` | 458 `outputs/runs/*/trace.jsonl` |
| `f12_node_waterfall` | `outputs/runs/trace_test/trace.jsonl` |

**DESIGN / ESTIMATE** — `f13_experiment_matrix`, `f14_cost`, `f15_traceability`,
`f16_workflow_g012`, `f17_failure_matrix`, `f18_metric_hierarchy`.

## Slide map

| # | Slide | Type |
|---|---|---|
| 1 | Title | hero (2 real figs) |
| 2 | Executive summary | 6 metric cards |
| 3 | Agenda | list |
| 4 | The question | framing |
| 5 | **Part 1 — What we audited** | section |
| 6 | Architecture as implemented | fig `f06` |
| 7 | A real codebase | fig `f07` |
| 8 | Endpoint hierarchy | fig `f18` |
| 9 | Benchmark exists, gold does not | fig `f01` |
| 10 | 48 governed cases | fig `f02` |
| 11 | 16 domains / ~500 tasks | fig `f03` |
| 12 | Difficulty skew | fig `f04` |
| 13 | 11 blocked capabilities | fig `f05` |
| 14 | **Part 2 — Real execution evidence** | section |
| 15 | Auditable traces | fig `f11` |
| 16 | 48×3-arm run — outcomes | fig `f08` |
| 17 | Latency by arm | fig `f09` |
| 18 | Evidence depth by arm | fig `f10` |
| 19 | Per-node timing | fig `f12` |
| 20 | What it proves / does not | two-column |
| 21 | **Part 3 — The experiment** | section |
| 22 | H1–H6 | table |
| 23 | S0–S3 + fairness manifest | table |
| 24 | Experimental matrix | fig `f13` |
| 25 | Traceability | fig `f15` |
| 26 | Metric definitions | table |
| 27 | Grading ladder | 9-stage |
| 28 | Statistics plan | table |
| 29 | **Part 4 — End-to-end & safety** | section |
| 30 | G0–G12 workflow | fig `f16` |
| 31 | Failure injection | fig `f17` |
| 32 | Causal ablation | table |
| 33 | Reproducibility | 6 cards |
| 34 | Benefit / cost | fig `f14` |
| 35 | Risks | table |
| 36 | Go / no-go | two-column |
| 37 | Falsification | list |
| 38 | Roadmap | phases |
| 39 | Closing | hero |

## 30-second narrative

> ProtacXtend is a genuine TPD agent (34-node graph, 15 specialists, ~30 tools,
> 11/27 capabilities blocked). The audit shows the benchmark has **no curated
> gold** (0/48 adjudicated, 0/1000 curated) and the **S1/S2 baselines are not
> built**, so correctness endpoints are gated and H2 is currently unanswerable.
> A real 48×3-arm run already shows typed abstention behaviour. The design fixes
> endpoints, grading, statistics, figures and falsification conditions in
> advance. Next step: the Phase 1 pilot.

## Presenting

- Slides 6–13 are the audit; 15–20 are real evidence; 22–28 are the method.
- Decision slides: 2 (summary), 9 (gold blocker), 23 (S2 baseline), 36 (gates).
- Export to PDF from PowerPoint/Keynote for distribution.
