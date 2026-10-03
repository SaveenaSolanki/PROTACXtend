# Vertical-slice closeout — COMPLETE (2026-09-25)

All workstreams executed and verified. See `outputs/CAPABILITY_DOSSIER.md` for the
six-element evidence contract (real input · trace · artifact · decision · output · failure)
for every claimed capability.

## Ledger status
- [x] W1 Node TUI intent routing — RESEARCH_INTENTS/CHAT_INTENTS registries; /design
      /investigate /reason /evidence /compare route to deterministic bridge handlers;
      bridge "investigate" research-contract routing; dist rebuilt; 61 node tests.
- [x] W2 Textual TUI — events sink (`events.capture_events`), `tui/engine.py` in-process
      executor (monkeypatch-immune), `app.py` real routing (simulation removed), honest
      stages; 26 pytest.
- [x] W3 BRD4×CRBN e2e — run `brd4_crbn_vslice_v1` (180→150 valid; 150 predicted+calculated;
      verdict DESIGN BRIEF ONLY, verified=0); independent RDKit structure validation
      (150 unique InChIKeys, component cores 150/150); persistent bundle (17 files + MANIFEST).
- [x] W4 Matched-case adjudication — 6 attempted / 9 abstained; KNOW-09 1.0, Know-01 0.5,
      KNOW-07 0.0, KNOW-10 0.33, DISCOVER-06/DESIGN-04 rubric→expert; mean 0.306, Wilson95
      [0.097, 0.70]; gold PENDING_HUMAN preserved.
- [x] W5 Capability dossier — `outputs/CAPABILITY_DOSSIER.md`.

## Extra hardening found during closure (all verified green)
- api.py: /design with unresolvable target → clarification_needed (before engine); resume
  bypasses the gate. E3 never blocks; explicit E3 honored (VHL probe: 100% VHL candidates).
- test_run_quarantine.py: direct `server.emit` assignment leak fixed (monkeypatch).
- design_tui_workflow_bridge.resume test fixed by the resume-bypass gate.
- bridge_regression design E3 tests updated from the stale plan-only contract to the
  executed-design contract (executed_design=True + E3-on-candidates assertions).
- events.py: `capture_events` sink; emit hardened; bridge subprocess protocol unchanged.

## Final green results
- Node TUI: 61/61.
- pytest (slice + textual TUI + bridge regression + quarantine + design bridge +
  plan dialogue + explanation): 49 + 26 + 44 + … (all included suites pass).
- Real bridge protocol driver: 24/24 (incl. the 226 s full design engine trace).

## Registered issues (not fixed; new evidence)
G1 chat slow-tool hang · G2 retrieve_pdb misses 5T35 · G3 demo-over-DOI E3 ligand ranking ·
G4 multi-E3 panels unsupported · G5 cell_atlas = local seed priors only.
Details + evidence paths: `outputs/CAPABILITY_DOSSIER.md` (cross-cutting failure matrix).