# ProtacXtend Experimental Study — Phase 0 package

**Study id:** `PROTACXTEND-STUDY/1.0.0`
**Status:** Phase 0 complete. **Phase 1 pilot NOT started** — awaiting approval of
`03_EXPERIMENTAL_DESIGN.md`.

## Read in order

1. [`00_REPOSITORY_FREEZE.md`](00_REPOSITORY_FREEZE.md) — git commit, dirty state,
   environment, model, packages, backends, hardware, date.
2. [`01_SYSTEM_AUDIT.md`](01_SYSTEM_AUDIT.md) — what is actually implemented
   (parser, planner, graph, agents, tools, capabilities, retrieval, evidence,
   state, fallback, persistence, synthesis) and the hypothesis→component map.
3. [`02_BENCHMARK_AUDIT.md`](02_BENCHMARK_AUDIT.md) — exact counts, distributions,
   gold/adjudication status and scorable-readiness of every benchmark asset.
4. [`03_EXPERIMENTAL_DESIGN.md`](03_EXPERIMENTAL_DESIGN.md) — the 12-part
   pre-execution design (H1–H6, matrix, metrics, grading, statistics, figures,
   schemas, cost, risks, go/no-go, first commands).

## Headline Phase 0 findings

- **48** authored governed benchmark cases exist; **0/48** independently
  adjudicated. **1000** `benchmark500` question-bank tasks exist; **0/1000**
  gold-curated. **500** `tpdeval` design slots exist; **0** authored.
- **No scored aggregate exists for any system on any benchmark** — confirmed on
  disk and by `tpdeval/docs/03_VERDICT.md`.
- System architecture is real and ablatable; the scientific claim is currently
  `NOT TESTED`.
- Blocking gate for correctness endpoints: **gold curation + adjudication**.
- Blocking gate for H2: **S1/S2 adapters must be built** (LLM+RAG, LLM+flat-tools)
  so the tool set is matched to S3.

## Next action

Review `03_EXPERIMENTAL_DESIGN.md`. On approval, run only the **Phase 1 pilot**
commands in §12 of that document, then produce `PILOT_REVIEW.md` against the §11
go/no-go checklist before any Phase 2 run.
