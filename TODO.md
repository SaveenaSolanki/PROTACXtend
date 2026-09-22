# PROTACXtend — Remediation & Benchmark TODO

Status legend: `[x]` done · `[~]` partial · `[ ]` not started · `[!]` blocked

Last updated: 2026-09-22 (session 3)

---

## P0 — do now

- [~] **Commit or discard the 89 modified / 129 untracked files deliberately**
  - [x] Stale `.ipynb_checkpoints/` discarded
  - [x] Parser, execution modes, benchmark engine committed (see git log)
  - [ ] Triage remaining pre-existing modified/untracked artifacts (outputs runs)
- [~] **Fix all `synglue_agent` → `protacxtend` residue**
  - [x] Runtime package, docstrings, API health name, report header, TUI bridge
  - [x] `protacxtend/_compat.py` **kept intentionally** (pickle compat; documented)
  - [ ] Historical markdown/audit docs still mention the old name (documentation only)
- [x] **Fix Dockerfile broken package path** — installs the package (`pip install .[api,ui]`), `.dockerignore` rewritten
- [x] **Fix TUI setup path** — Node `tui/README.md` added; Python TUI CSS + JSON data now packaged
- [x] **Fix target/entity parser** — `protacxtend/nlp/entity_extraction.py`
- [x] **Create parser validation suite** — 125 prompts, ≥98% gate (100% measured)
- [x] **Remove scientific-mode fixtures** — `protacxtend/runtime/modes.py` (DEMO/TEST/SCIENTIFIC)
- [x] **Consolidate two agent stacks**
  - [x] Canonical stack (`protacxtend/canonical/`) is the single control plane
  - [x] `run_protacpilot` routes through canonical → typed `TherapeuticStrategy`
  - [x] New `protacxtend strategy` CLI surface; legacy `agentic` documented as deprecated
- [x] **Implement typed `TherapeuticStrategy`** — `protacxtend/canonical/schemas.py`
- [x] **Implement typed `EvidenceItem`** — enriched (direction, entity, claim, strength, date, provenance) + duplicate dataclass fields removed
- [x] **Implement typed `ToolRun`** — `protacxtend/results/schema.py`
- [x] **Implement `RunManifest`** — `protacxtend/canonical/schemas.py`, emitted by `strategy` CLI
- [x] **Make 50 benchmark tasks genuinely scorable** — 48 frozen tasks graded via derived overlay; `SCORABLE_MANIFEST.json` = 48/48 scorable, 29 flagged for expert review
- [x] **Implement scoring engine** — `benchmark_runner/grader.py` (exact, categorical, ranked, numeric, set, constraint, rubric, causal_graph, trajectory)
- [~] **Run 50-task PROTACXtend-only pilot**
  - [x] Runner implemented: `scripts/run_benchmark_pilot.py`
  - [x] Offline smoke: 48/48 tasks graded (mean 0.885)
  - [~] One real deterministic task executed (KNOW-01, 239 s) — engine is design-only; KNOW/REASON need the matched retrieval/LLM path (P1)
  - [ ] Full 48-task executed run

## P1 — benchmark readiness

- [ ] Add failure taxonomy
- [ ] Add retry/fallback/abstention policy
- [ ] Build EvidenceCritic
- [ ] Build MechanismCritic
- [ ] Build ReproducibilityCritic
- [ ] Make all tool versions/provenance explicit
- [~] Replace fixture defaults in all 34 agent tools
  - [x] `run_agent_tool` + executor + registry fail closed in SCIENTIFIC mode
  - [ ] Audit each of the 34 adapters for residual internal defaults
- [ ] Decide what to do with the 115 non-executable tools
- [ ] Add matched-tool registry
- [ ] Implement Biomni adapter
- [ ] Implement TPD comparator adapter
- [ ] Implement LLM baseline
- [ ] Implement retrieval-only baseline
- [ ] Implement tool-only baseline
- [ ] Run 50-task baseline comparison

## P2 — publication experiments

- [ ] Scale gold benchmark to 500
- [ ] Run native-system comparison
- [ ] Run matched-tool comparison
- [ ] Run 100-task TPD-depth challenge
- [ ] Run L1–L7 analysis
- [ ] Run failure-recovery challenge
- [ ] Run 5× repeated reproducibility experiment
- [ ] Create 10 temporal pilot cases
- [ ] Scale temporal challenge to 50
- [ ] Run PROTACXtend ablations
- [ ] Conduct blinded expert evaluation
- [ ] Calculate confidence intervals/statistics
- [ ] Generate final figures

## P3 — release

- [ ] Harden `shell=True`
- [ ] Replace unsafe pickle loading
- [ ] Add sandboxed scientific Python execution
- [ ] Finalize Docker/HPC/offline deployment
- [ ] Freeze benchmark release
- [ ] Produce benchmark manifests
- [ ] Produce model/tool cards
- [ ] Publish reproducibility instructions

---

## Progress log

- **Session 3 (this one):** created tracker; fixed residue, Dockerfile, TUI packaging,
  typed `EvidenceItem`/`ToolRun`; added `strategy` CLI; built the benchmark scoring
  engine, derived scoring overlays, scorable manifest, and the pilot runner
  (offline smoke 48/48 graded).
- **Session 2:** removed production fixture defaults; added DEMO/TEST/SCIENTIFIC modes.
- **Session 1:** replaced positional parser with entity-extraction layer; 125-prompt
  validation suite at 100% target accuracy.

### Key commands

```bash
python scripts/evaluate_parser.py                 # parser gate (≥98%)
python scripts/build_scorable_manifest.py         # refresh benchmark scorable manifest
python scripts/derive_scoring_criteria.py         # regenerate scoring overlays
python scripts/run_benchmark_pilot.py --offline-smoke
python scripts/run_benchmark_pilot.py --limit 3 --capability DESIGN
protacxtend --execution-mode scientific strategy "Design a VHL PROTAC against BRD4"
```
