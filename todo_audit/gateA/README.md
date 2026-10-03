# Gate A — preserve and reproduce (completed)

Date: 2026-09-23 · per `todo/PROTACXtend_05_BENCHMARK_AUDIT_AND_NEXT_STEPS.md` §3 Gate A.

## A1 — Archive and inspect (no destructive cleanup)

| artifact | path |
|---|---|
| HEAD / branch / `git status --porcelain` / log | `archive/git_state.txt` |
| Python version + `pip freeze` | `archive/python_env.txt` |
| raw audit evidence snapshot | `archive/todo_audit_evidence_snapshot/` |

**`protacxtend-memory` rename inspection** (preserve-before-cleanup):

* tracked `protacpilot-memory/`: **104 files** (deleted from disk, `D` in git).
* untracked `protacxtend-memory/`: **338 files**.
* all 104 tracked files exist byte-identically in the new tree; **0** files are
  only in the old tree; **234** are new (`docs/`, `evaluation/`, `paper/`,
  `.pytest_cache/`, `__pycache__/`).
* conclusion: an intended rename + expansion that was never committed.
* action: **nothing deleted or moved**; content preserved in place.

## A2 — Reproduce the audit on this revision

* `bash todo_audit/verify.sh` reproduces parser gate, scorable manifest,
  offline smoke, registry census, agent-tool guardrail probe, and the
  canonical SCIENTIFIC-vs-DEMO divergence (evidence in `../evidence/`).
* project-only test paths: `pytest.ini` now pins
  `testpaths = tests protacxtend/tests` and `norecursedirs`.
  * before: 1357 tests collected, **156 collection errors** (vendored repos)
  * after: **968 collected, 0 errors**
* editable reinstall: `pip install -e . --no-deps` → version `0.3.0`;
  console script now imports `protacxtend.cli` and `protacxtend --help` works
  (was stale `0.1.0` importing `synglue_agent.cli`).

## A3 — Cross-route integration matrix

`cross_route_matrix.py` drives every public route — canonical parser,
canonical orchestrator, agent tools, capability runners, CLI, FastAPI — over
missing input, fixture input, invalid SMILES, invalid PDB, unknown tool and a
valid input, recording typed failure codes, execution, output validity and
provenance.

Outputs: `cross_route_matrix.csv`, `cross_route_matrix.md` (14 rows).

Key outcomes after the Gate B fixes:

* missing / placeholder inputs → typed `MISSING_SCIENTIFIC_INPUT` /
  `SYNTHETIC_INPUT_FORBIDDEN` on the agent, capability, CLI and API routes;
* invalid SMILES → `warning`, `output_valid=false`; invalid PDB →
  `capability_unavailable`; unknown tool → `failed`, not executed;
* valid SMILES → `ok` with `input_origins={smiles: USER}`;
* canonical route drops an injected `local_demo_*` warhead and records
  `execution_mode=scientific`;
* API returns a typed **HTTP 422** body instead of an opaque 500.

## Pass check

* [x] full source files and traces available on the audited revision
* [x] results reproduced / discrepancies documented (`/tmp` logs, CSV/MD artifacts)
* [x] no destructive repository cleanup performed
