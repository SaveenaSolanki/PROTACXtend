# Search Instrumentation — Seeing What the Agents Explore

Companion to [`00-INDEX.md`](00-INDEX.md) and to
[`../converted/LEARNING_SCHEMA.md`](../converted/LEARNING_SCHEMA.md).

> **The premise.** A trace tells you what happened. It does not show you the search.
> To see the search you need *denominators* — what was considered, what was rejected and
> why, and what was never reached. Nearly all of it is already computed inside the pipeline
> and discarded before the report.

Four instruments. The first three are observational; the fourth drives exploration.

---

## Instrument 1 · Run funnel

**The single most informative view.** Candidates entering each node, surviving, and the
rejection-reason distribution for the rest.

It reveals the *shape* of a run. If 90% of candidates die at exit-vector detection, the run
never reached linker space at all — and a 192-combination linker scan was measuring almost
nothing. A ranked candidate table cannot show this; a funnel shows it immediately.

### Data sources — what exists today

| Node | Metric needed | Source | Status |
| --- | --- | --- | --- |
| 5 | binders retrieved / **true hit count** | API response totals | ⚠️ cap of 100 applied silently; true total not recorded |
| 6 | warheads considered / selected | seed DB + curated + retrieved | ⚠️ counts not emitted |
| 7 | E3 ligands available / selected | `curated_e3_ligands.csv` | ✅ static (8 ligands, 4 ligases) |
| 8 | atoms considered / vectors accepted | `detect_attachment_points` | ⚠️ `rationale` exists per accepted vector; rejected atoms not counted |
| 9 | linkers generated · scan combinations | `linker_scanner` result list | ✅ derivable |
| 10 | attempts / successful joins | **`construction_attempts`** | ✅ **retains failures already** |
| 11 | assembled → valid, **by rejection reason** | `validate_candidates` | ⚠️ knows why; does not report |
| 12–15 | predictions produced | prediction lists | ✅ derivable |
| 16 | ranked count, tier distribution | `ranking_results` | ✅ derivable |
| 17 | clusters formed | `diversity_clusters` | ✅ **cluster count is itself a finding** |
| 19 | generations run, new vs revisited | — | ❌ no generation tracking |
| 20 | poses passed / total, proxy score | P4ward output, proxy | ✅ e.g. `0/3600`, `8–16/3600` |
| 21 | final ranked | `final_ranked_candidates` | ✅ derivable |

**Roughly 70% is derivable today without touching agent logic.** Four real gaps: node 5's
true hit count, node 8's rejected-atom count, node 11's rejection reasons, node 19's
generation tracking.

### Schema

```sql
CREATE TABLE funnel_step (
  run_id            TEXT    NOT NULL,
  node              INTEGER NOT NULL,          -- 1..23
  generation        INTEGER NOT NULL DEFAULT 1,-- >1 for evolution-loop passes
  n_considered      INTEGER,                   -- NULL where no meaningful denominator
  n_in              INTEGER NOT NULL,
  n_out             INTEGER NOT NULL,
  rejections        JSONB,                     -- {reason_code: count}
  wall_ms           INTEGER,
  PRIMARY KEY (run_id, node, generation)
);
```

`rejections` keys must be drawn from the same closed `failure_reason` enum the learning
store uses — canonicalise once, at write time.

### Rendering — the HMGB2 / ICM run

Real values where the case study recorded them; `—` marks exactly what this instrument
would fill in:

```
node                        considered      in     out   died   top rejection
──────────────────────────────────────────────────────────────────────────────
05  get binders                      —     —      100      —    (capped, total unknown)
06  warheads                   485,336       —      —      —    —
08  exit vectors                     —      —      2*      —    —          *ICM: OH27, OH29
09  linkers                          —      —      12      —    —
    └ scan combos                  208     —      192      —    —          2 × 8 × 12
10  assemble                         —    192      —       —    —
11  validate                         —      —      —       —    —
20  ternary (OH27)               3,600  3,600      0   3,600    exit_vector_buried
20  ternary (A1_4COOH)           3,600  3,600   8–16   ~3,588   ternary_geometry_infeasible
    └ 16 linker variants             —      —      —       —    best 0.8% (C14-PEG5)
──────────────────────────────────────────────────────────────────────────────
```

The two node-20 rows are the entire recorded yield of the case study. Everything above them
is currently invisible.

---

## Instrument 2 · Coverage matrix

**What has been touched, and what the untouched remainder looks like.**

### The space

| Level | Size | Basis |
| --- | --- | --- |
| Warhead × E3 pairs | **56** | 7 curated warheads × 8 curated E3 ligands |
| × curated linkers | **728** | × 13 rows in `curated_linkers.csv` |
| × attachment combinations | **~11,600** | × ~16 (2 warhead points × 8 E3 points, ICM case) |
| Real space, **per pair** | **150,000+** | length × composition × rigidity × attachment × 2 ends |

### What the case study covered

- **192 of ~208** combinations for one pair (ICM + pomalidomide) — that sub-grid is ~92% dense
- **192 of ~11,600** across the curated space — **1.6%**
- **192 of 150,000+** within that one pair's real linker space — **~0.13%**

Dense in one cell, empty in the other fifty-five. **That is the finding**, and it is exactly
what a ranked candidate list conceals.

### Schema

```sql
CREATE TABLE coverage_cell (
  warhead_inchikey  TEXT NOT NULL,
  e3_inchikey       TEXT NOT NULL,
  linker_id         TEXT NOT NULL,
  wh_attach_idx     INTEGER NOT NULL,
  e3_attach_idx     INTEGER NOT NULL,
  n_evaluated       INTEGER NOT NULL DEFAULT 0,
  best_pass_rate    REAL,                      -- from node 20; NULL if never reached
  best_proxy_score  REAL,
  last_run_id       TEXT,
  last_seen         TIMESTAMPTZ,
  PRIMARY KEY (warhead_inchikey, e3_inchikey, linker_id, wh_attach_idx, e3_attach_idx)
);
```

**Key on InChIKey, never on name** — `canonicalize_smiles` and `_stable_id` already exist in
the toolbox. This table is what answers *"have we already tried this combination?"*, which
is the query that prevents repeating a $5K–$50K, 2–6 week evaluation.

Render as a heatmap: warhead rows × E3 columns, cell shade = `n_evaluated`, cell value =
`max(best_pass_rate)`. Drill into a cell for the linker × attachment sub-grid.

---

## Instrument 3 · Loop trajectory

**Is the evolution loop exploring, or churning?**

Per generation of nodes 10 ↔ 19:

```sql
CREATE TABLE loop_generation (
  run_id          TEXT    NOT NULL,
  generation      INTEGER NOT NULL,
  n_produced      INTEGER NOT NULL,
  n_novel         INTEGER NOT NULL,   -- unseen InChIKey vs all prior generations
  best_score      REAL,
  mean_score      REAL,
  operator_counts JSONB,              -- {mutation: n, recombination: n}
  PRIMARY KEY (run_id, generation)
);
```

Plot `n_novel / n_produced` against generation. A curve decaying toward zero means the GA
has converged — or is revisiting. That single ratio answers the unbounded-loop risk flagged
in [`19-EvolutionRefinementAgent.md`](19-EvolutionRefinementAgent.md) as a number rather
than a worry, and it supplies the convergence criterion the loop currently lacks.

**Prerequisite:** a persistent seen-set keyed on canonical InChIKey. It does not exist yet.

---

## Instrument 4 · Counterfactual sweep — the active instrument

The first three observe. This one explores.

The cheap path runs in under a second, so a sweep is affordable: hold everything fixed,
vary one axis, and plot the response.

```jsonc
{
  "sweep_id": "swp_004",
  "hold": { "warhead": "A1_4COOH", "e3_ligand": "pomalidomide",
            "wh_attach": "N-phenyl", "e3_attach": 8 },
  "vary":  { "axis": "linker_length_atoms", "range": [8, 16], "class": "PEG" },
  "measure": ["proxy_score", "p4ward_pass_rate"]
}
```

This is precisely what the case study did by hand — 16 linker variants, best 0.8% at
C14-PEG5 — and it is the experiment the project's own headline finding demands: three atoms
of linker length flips the degraded target from p38α to p38δ. A system that knows this and
does not sweep length systematically is not using its own most important result.

**Sweep axes worth standardising:** linker length, linker class (PEG / alkyl / rigid),
warhead attachment point, E3 attachment point, E3 ligase (all 4).

Store each sweep as a run of `coverage_cell` writes plus a response curve. The curve — not
the individual points — is what gets promoted into a principle.

---

## Implementation order

Ranked by value per unit of effort. Nothing here is blocked on data or new science.

| # | Change | Touches | Effort |
| --- | --- | --- | --- |
| 1 | Emit `funnel_step` from data already in state | node 22 / post-run | Small |
| 2 | Report node 11 rejection reasons | [`11-CandidateValidationAgent`](11-CandidateValidationAgent.md) | Small |
| 3 | Record node 5 true hit count before the 100-cap | [`05-TargetBinderRetrievalAgent`](05-TargetBinderRetrievalAgent.md) | Small |
| 4 | Backfill `coverage_cell` from the 192-combo scan | post-run | Small |
| 5 | Count rejected atoms at node 8 | [`08-ExitVectorDetectionAgent`](08-ExitVectorDetectionAgent.md) | Small |
| 6 | Generation tracking + InChIKey seen-set | [`19-EvolutionRefinementAgent`](19-EvolutionRefinementAgent.md) | Medium |
| 7 | Sweep runner over the existing scanner | [`09-LinkerGenerationAgent`](09-LinkerGenerationAgent.md) | Medium |

Items 1–5 are mostly *reporting what is already computed* — the recurring theme across all
22 agent files.

---

## Relationship to the learning store

These tables are **observations** in the sense of `LEARNING_SCHEMA.md`: one episode,
deterministic, typed, high volume. They are not principles.

- A `funnel_step` row with a dominant rejection reason **is** a structured learning record —
  same `problem_type` and `failure_reason` enums, `evidence_refs` pointing at the node and
  trace index.
- A `coverage_cell` with a measured `best_pass_rate` is the component-compatibility learning
  class, and the highest-volume one you have.
- A sweep response curve is the natural input to pattern extraction — and, later, the
  training set for the surrogate model that objective **O-5g** (active learning) needs.

**One discipline carries over unchanged:** grade on geometry and validity only. Populating
`best_pass_rate` from node 12's heuristic rather than from measured pose counts would make
the coverage matrix a record of what the placeholder believes, and every downstream
conclusion would inherit it.

**Dependency:** `best_pass_rate` is only trustworthy once objective **O-4** runs P4ward and
the proxy is calibrated against it. Until then, populate `best_proxy_score` and leave
`best_pass_rate` null rather than substituting an uncalibrated number.
