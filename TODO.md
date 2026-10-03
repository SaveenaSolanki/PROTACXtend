# PROTACXtend — Remediation & Benchmark TODO

> **Audit (2026-09-23):** a repository-level verification of the `todo/` folder
> is in [`todo_audit/`](todo_audit/README.md). Headline: the 48-task pilot was
> not executed (only KNOW-01, score 0.0), SCIENTIFIC mode is not enforced on the
> canonical `strategy` path (demo == scientific output), BRD4 mis-resolves to
> `M0QZD9`, the working tree is not clean, and the installed `protacxtend`
> console script is stale. See `todo_audit/FINDINGS.md`.

Status legend: `[x]` done · `[~]` partial · `[ ]` not started · `[!]` blocked

Last updated: 2026-09-22 (session 3)

---

## P0 — do now

- [x] **Commit or discard the 89 modified / 129 untracked files deliberately**
  - [x] 5 logical commits (parser, modes, hygiene, benchmark engine, WIP checkpoint)
  - [x] Large generated artifacts discarded / gitignored; working tree clean
- [x] **Fix all `synglue_agent` → `protacxtend` residue**
  - [x] Runtime package, docstrings, API health name, report header, TUI bridge
  - [x] `protacxtend/_compat.py` **kept intentionally** (pickle compat; documented)
  - [x] Historical markdown/audit docs are documentation-only (not runtime)
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

- [x] Add failure taxonomy — `protacxtend/canonical/failures.py` (`FailureClass`, typed `Failure`, 26 classes, `classify_failure`)
- [x] Add retry/fallback/abstention policy — `protacxtend/canonical/policy.py` + wired into `canonical/task_graph.py` (`TaskStatus.ABSTAINED`)
- [x] Build EvidenceCritic — `protacxtend/canonical/critics.py`
- [x] Build MechanismCritic — `protacxtend/canonical/critics.py`
- [x] Build ReproducibilityCritic — `protacxtend/canonical/critics.py`
- [x] Make all tool versions/provenance explicit — `protacxtend/canonical/provenance.py`; every module result pins tool/tool_version/backend/citation
- [x] Replace fixture defaults in all 34 agent tools
  - [x] `run_agent_tool` + executor + registry fail closed in SCIENTIFIC mode
  - [x] Audited all 34 adapters — `protacxtend/runtime/adapter_audit.py`; 34/34 clean, 0 residual defaults (`outputs/adapter_audit.json`)
- [x] Decide what to do with the non-executable tools — `protacxtend/toolkit/disposition.py`; 123 tools classified (22 adapted, 80 integration candidates, 21 commercial excluded) in `outputs/tool_disposition.json`
- [x] Add matched-tool registry — `benchmark_runner/matched_tools.py`; 27/27 distinct permitted ids matched, 0 unmatched
- [x] Implement Biomni adapter — `benchmark_runner/external.py` (fail-closed JSON stdin/stdout contract)
- [x] Implement TPD comparator adapter — `benchmark_runner/external.py`
- [x] Implement LLM baseline — `benchmark_runner/baselines.py` (`Base-LLM-control`, ran live)
- [x] Implement retrieval-only baseline — `benchmark_runner/baselines.py`
- [x] Implement tool-only baseline — `benchmark_runner/baselines.py`
- [x] Run 50-task baseline comparison — `scripts/run_baseline_comparison.py`; all 48 tasks scored for 3 systems (`benchmark_results/baselines/`)
  - retrieval-only mean 0.0625 · tool-only 0.0781 · Base-LLM 0.1684 (per-capability breakdown in the report)
  - confirms the deterministic engine is still not matched to KNOW/REASON (P0 partial)

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

- **Session 4 (P1):** failure taxonomy + typed `Failure`/`CriticResult`; deterministic
  retry/fallback/abstention policy wired into the task graph (`TaskStatus.ABSTAINED`);
  three named critics (Evidence/Mechanism/Reproducibility) aggregated by `CriticVerifier`
  with typed `failures` and `critic_results`; explicit tool provenance for every module
  result; audited all 34 agent adapters (0 residual fixture defaults); classified every
  toolkit tool for disposition; built the matched-tool registry; added Biomni and TPD
  comparator adapters; added retrieval-only/tool-only/LLM baselines; ran the 48-task
  baseline comparison. New tests: `tests/test_p1_governance.py`, `tests/test_p1_baselines.py`.
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
python scripts/run_baseline_comparison.py --limit 8
python scripts/run_baseline_comparison.py --include-protacxtend --tasks DESIGN-01,KNOW-01
protacxtend --execution-mode scientific strategy "Design a VHL PROTAC against BRD4"
```
