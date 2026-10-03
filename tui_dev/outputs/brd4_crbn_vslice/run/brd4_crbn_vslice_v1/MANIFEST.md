# Vertical-slice evidence bundle — BRD4 × CRBN (run `brd4_crbn_vslice_v1`)

Generated 2026-09-25 · surface: the REAL TUI bridge (`python -m protacxtend.tui_bridge.server`,
JSONL protocol) and the REAL deterministic engine (`run_protacpilot`, capability=DESIGN),
never a mock.

## Input
```
/design Design a CRBN-recruiting PROTAC for BRD4
```

## Executed tool trace (selected)
- `run_protacpilot(request, mode="deterministic", config={run_id, record_run, capability:"DESIGN"})`
  — trace: `trace.jsonl` (run_start → tool_call → run_end) + bridge events in
  `traces/bridge_trace.jsonl` (24/24 protocol checks pass).
- Independent RDKit revalidation pass: `tui_dev/scripts/validate_candidates.py`.

## Scientific decisions (with evidence files)
1. **Target resolution**: BRD4 → O60885 (Homo sapiens) — `run.json`/strategy; investigate handler
   reports `known_binder_count=120`, `measured_precedent_rows=65` (per-E3: CRBN 26, VHL 32,
   FEM1B 7) — `outputs/workflows/investigate/*_evidence.json`, `stage_timeline.json`.
2. **Design executed**: 180 assembled → 150 RDKit-valid → 150 predicted/calculated scored →
   150 ranked. `candidate_evidence.json/.csv`, `candidates.csv` (150×26 from candidates.parquet).
3. **Candidate-structure validation (independent)**: 150/150 parse OK, 150/150 canonical
   round-trip, 150 unique InChIKeys (0 duplicates), 150/150 component cores present
   (warhead / E3-ligand / linker; attachment dummies stripped), 34 candidates carry
   stereocenters. `structure_validation.json/.csv`.
4. **Honest stage states**:
   - degradation: **predicted** (TACK-style DC50/Dmax; model_version tack-style-v1; per-row
     model_confidence 0.25; never measured in this run).
   - ternary_coordinates: **unevaluated** — no validated coordinate backend/DockQ benchmark.
   - synthesis_route: **unevaluated** — no retrosynthetic route execution.
   - nomination gate: **gated** — candidates are hypotheses for review, not validated degraders.
5. **Verdict**: `verdict.json` — **DESIGN BRIEF ONLY**; scientific_result=false; reasons:
   "candidates lack verified component/attachment provenance"; counts:
   target_resolved=true, candidates_valid=150, **candidates_verified=0**, candidates_ranked=150.
6. **Top ranked (predicted)**: SGA-214601f354c0 (score 0.771, pDC50 21.64 nM,
   Dmax 97.4%, warhead `BRD4_demo_quinazoline_like`, linker ALKYL6); all top-6 carry
   `low_degradation_model_confidence`/`high_hook_effect_risk`/proxy-cooperativity flags and
   use DEMO-named components — none are source-backed measured binders.

## Failure / unavailable behavior demonstrated
- Live binder sources unavailable in this run → engine REPLAYED cached real prior live-API
  records (urls + fetched_at in run.json warnings) and fell back to curated/demo components —
  flagged in warnings; verdict drops candidates_verified to 0 (no fabrication).
- Unknown command `/bogus` → typed `error` event (bridge trace).
- Chat free text with local LLM (qwen2.5:7b) → chat_answer (kind=answer); single-token
  recognized target → deterministic target card (never LLM identification).

## Files (this directory)
run.json · summary.json · trace.jsonl · evidence.jsonl · decisions.jsonl · report.md ·
verdict.json · therapeutic_strategy.json · pareto_front.csv · candidates.csv ·
stage_timeline.json · candidate_evidence.json/.csv · evidence_graph.json ·
resume_state.json · structure_validation.json/.csv

## Provenance note
`evidence.jsonl` contains the engine evidence ledger (1 row: 100 binders rejected as
empty-placeholder before scoring); claim-level evidence for the 150 candidates lives in
`evidence_graph.json` (degradation claims, kind=computed, tool=
deterministic_design_engine.degradation_prediction) — ML predictions are never labelled
measured anywhere in the bundle.