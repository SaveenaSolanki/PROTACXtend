# tui_dev lab notebook — vertical-slice closeout

## 2026-09-25 — W2–W5 COMPLETE: slice closed, all evidence on disk

- **W2 Textual TUI (real engine)**: `events.capture_events` in-process sink
  (`tui_bridge/events.py`); new `protacxtend/tui/engine.py` executor (cwd pinned,
  monkeypatch-immune, plan/design/investigate/reason/evidence/run/chat via the same
  bridge handlers as the Node TUI); `app.py` rewritten — fake 23-node sleep simulation
  REMOVED, Input bar added, real stage statuses (executed/unevaluated/failed) rendered,
  honest `unevaluated stages: ternary_coordinates, synthesis_route` lines.
  tests/test_tui_slice_routing.py: 11 tests incl. one REAL design engine run → 26 passed
  with test_protacxtend_tui.
- **W3 BRD4×CRBN e2e**: canonical run `brd4_crbn_vslice_v1` (135.8 s): 180 assembled →
  150 valid → 150 predicted/calculated → 150 ranked; verdict DESIGN BRIEF ONLY,
  candidates_verified=0; bundle (17 files + MANIFEST.md) at
  `outputs/brd4_crbn_vslice/run/brd4_crbn_vslice_v1/`. Independent RDKit validation:
  150/150 parse+round-trip, 150 unique InChIKeys, component cores 150/150, 34 stereocenter-
  bearing, 0 verified provenance. Two validator bugs found & fixed en route: InChIKey API
  moved in RDKit 2026.03 (`rdkit.Chem.inchi`); fragment substructure requires dummy handling.
- **W4 adjudication**: `scripts/adjudicate_slice.py` → 6 attempted (KNOW-01/07/09/10,
  DISCOVER-06, DESIGN-04) + 9 documented abstentions. Machinery (LLM-free grader, frozen
  GT): KNOW-09 1.0 exact; KNOW-01 0.5; KNOW-07 0.0; KNOW-10 0.33; DISCOVER-06/DESIGN-04
  0.0 rubric → requires_expert_review. Mean 0.306, correct 2/6, Wilson95 [0.097,0.70],
  empty baselines all 0.0. Gold stays AWAITING_EXPERT_REVIEW. Registered findings
  (G1–G5): chat slow-tool hang; retrieve_pdb misses 5T35; demo-over-DOI E3 ranking;
  multi-E3 panel unsupported; cell_atlas = seed priors.
- **Extra fixes during closure**: api.py design unknown-target → clarification_needed
  (resume bypasses); explicit-E3 honored probe (VHL → 100% VHL candidates incl.
  DOI-backed VHL_ligand_4); test_run_quarantine `server.emit` leak fixed;
  bridge_regression design-E3 tests updated to the executed-design contract.
- **Final green**: node 61/61; pytest suites 49+26+44; bridge protocol driver 24/24 on the
  final re-run (226 s); chat answered (kind=answer) after warm-up.

## 2026-09-25 — W1 done: real-TUI intent routing fixed

- **Bridge intent-routing fix** (`protacxtend/tui_bridge/server.py`): `investigate` with a plain
  request now runs the deterministic research contract (`run_command("investigate")`); the
  plan-task executor stays behind explicit task ids (`/investigate T0`). Before the fix, bridge
  `investigate` hit `handle_investigate` with `task_id=""` → `investigate_answer kind=error
  "unknown task ''"` — /investigate <query> could never run the research workflow.
- **Node TUI** (`tui/src/commands.ts`, `tui/src/app.ts`): new `RESEARCH_INTENTS` /
  `CHAT_INTENTS` registries (single source used by dispatcher AND tests). `/design`,
  `/investigate`, `/reason`, `/evidence <q>`, `/compare <molecules>` now route to their
  deterministic bridge handlers and render a `research_answer` / `diagnosis_answer` panel with
  executed-vs-unevaluated stages, evidence gates, candidate table, persisted artifacts and
  resume command. `/ask`, `/explain` stay chat; `/explain run_<id>` reads the persisted run via
  bridge `explain`. dist rebuilt; 61 node tests pass (adds 4 intent-routing tests).
- **Real-protocol verification** (`tui_dev/scripts/drive_bridge.py`): spawned the actual bridge
  server, sent 10 real commands (status, /plan, /design BRD4×CRBN, /investigate, /reason,
  /evidence, /compare, chat BRD4, /bogus, chat free text) → **24/24 checks pass**.
  Trace: `outputs/brd4_crbn_vslice/traces/bridge_trace.jsonl` (18 events, 119.8s).
  Highlights: design → executed_design=True, 150 candidate rows, ternary/synthesis
  unevaluated, degradation predicted, engine run record persisted at
  `outputs/runs/design_5ba22e5d9d/`; investigate → BRD4/O60885 + 65 measured precedent rows
  + per-E3 breakdown (CRBN 26, VHL 32, FEM1B 7); unknown command → typed error.

## Next
- W2 Textual TUI: events.py sink + tui/engine.py in-process executor + app.py real routing
  (kill the fake 23-node sleep simulation; honest stages).
- W3 canonical BRD4×CRBN run (fixed run_id `brd4_crbn_vslice_v1`) + independent
  candidate-structure validation (RDKit parse/canonical/InChIKey/formula/components) +
  evidence bundle into `outputs/brd4_crbn_vslice/run/`.
- W4 matched-case adjudication (48 gold; strict matched = 32 per recon).
- W5 capability dossier.