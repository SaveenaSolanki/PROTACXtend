# PROTACXtend — Project Closeout

> **Purpose:** the final checklist to *close* the project. Covers
> **(1) what is left**, **(2) whether the TUI works**, **(3) how to install on
> different servers**, and **(4) how to reach Biomni-level depth/technicality**.
>
> Companion documents: `CODEBASE_STATE.md` (state of the whole codebase) and
> `BENCHMARK_AUDIT.md` (what is done/scorable/scored in the benchmarks).
> Audit rule throughout: *listed ≠ authored ≠ frozen ≠ scorable ≠ executed ≠
> scored ≠ validated.*

---

## 0. Closeout summary

| # | Aspect | Status today | To close |
|---|---|---|---|
| 1 | Core platform (CLI/API/agents/tools) | ✅ working | commit the uncommitted frontier |
| 2 | Python TUI (Textual) | ✅ runs (23 agents) | fix stale README version + installer import |
| 3 | Node TUI ("Laboratory Night") | ✅ builds & renders | add `--help`/arg parsing, commit `tui/` |
| 4 | Installer / profiles | ✅ implemented | fix deploy Dockerfile stale package name |
| 5 | Docker / compose | ⚠️ works but stale names | rename `synglue_agent` → `protacxtend` |
| 6 | Benchmark (48 tasks) | ⚠️ ≈37% (author+freeze only) | bind scoring, wire systems, run |
| 7 | Head-to-head / Biomni depth | ⚠️ ~5% (instrument only) | author GT, wire adapters, dynamic-code layer |
| 8 | Science validation | ⚠️ partial, several `NOT_VALIDATED` | ternary/MM-GBSA/real-PDB benchmarks |
| 9 | Security | ❌ `shell=True` ×3, `pickle.load` ×5 | harden before any release |
| 10 | Tests | ⚠️ ~962 tests, suite >25 min, some failing | fast/slow split, fix failures |
| 11 | Docs / sheets drift | ⚠️ 4 divergent toolkit sheets, no canonical | declare `TOOLKIT_TRUTH.md` canonical |
| 12 | Release artifacts | ⚠️ wheel built | publish a signed, smoke-tested release |

**Bottom line:** the *software* is close to closable; the *scientific claim* is
not. Closing means (a) commit/consolidate the working tree, (b) fix the
security + stale-name bugs, (c) publish the TUI and install paths, and
(d) either **run the benchmark** or **explicitly freeze it as an unmeasured
instrument**.

---

## 1. What is left to close (by area)

Legend: 🟢 done · 🟡 partial · 🔴 missing/blocking.

### 1.1 Code consolidation
- 🟢 **Parallel agent stacks collapsed** — one canonical control plane now
  wraps both engines: `protacxtend/canonical/` (parser → task graph → 9 modules
  → tool executor → evidence → critic → decision → `TherapeuticStrategy`).
  `agents/graph.py` and `agents/agentic_core.py` are engines reached through
  the canonical Tool Executor; `protacxtend/agentic/` is deprecated. See
  [`documentation/CANONICAL_STACK.md`](documentation/CANONICAL_STACK.md).
- 🟡 **Rename residue** — `synglue_agent/` and `SynGlue_Py/` remain; live code
  and Docker still reference `synglue_agent` (see §5).
- 🟡 **Uncommitted frontier** — 89 modified + 129 untracked files not in git.
  **Close:** commit `tpdeval/`, `audit_nextgen/`, new `protacxtend`
  subsystems, memory upgrades, or explicitly discard.

### 1.2 Science (from `config/scientific_status.yaml`)
- 🟢 M1 hook effect (`VALIDATED BASELINE`), M4 degradation ML, M5 cell-context.
- 🟡 M2 lysine (surrogate, real-PDB benchmark pending), M3 cooperativity
  (data-gated), M6 E3 (prospective validation open), M7 active learning
  (`public_claim: false`).
- 🔴 Ternary predicted-structure DockQ `NOT_VALIDATED`; MM/GBSA `NOT_VALIDATED`.

### 1.3 Benchmark (see `BENCHMARK_AUDIT.md`)
- 🟢 Authoring + freeze (48 cases, 48 GT, 100/100 hashes).
- 🔴 Scoring bindings empty in all 48 cases; runner never loads `ground_truth/`.
- 🔴 2 referenced CSVs missing; 19/48 manifest flags wrong.
- 🔴 0/6 real adapters wired; 0 scored results.

### 1.4 Product surface
- 🟢 CLI (`protacxtend …`, 32 subcommands), Streamlit UI, FastAPI.
- ✅ **Two TUIs working** — see §2.
- 🟡 Website (`website/` static) — deployed Pages needs enabling.

### 1.5 Ops / release
- 🟢 Installer `scripts/install.sh` (3 profiles), `scripts/package_release.sh`,
  `scripts/distribution_smoke.sh`, `deploy/docker-compose.yml`.
- 🔴 Security hardening (G12).
- 🟡 Test-suite runtime >25 min + failures (G11).

### 1.6 Deterministic scoring — DONE (this change)
- 🟢 **`tpdeval/dimensions.py`** implements the scoring contract required before
  any comparison runs: **11 independent 0–5 dimensions** (9 general + 2 temporal)
  with a **machine** component and an **expert** component stored separately and
  never averaged together.
- Machine scorers are pure/deterministic: tool selection, tool execution,
  evidence grounding, quantitative correctness, uncertainty calibration (ECE),
  reproducibility, objective GT correctness, causal-graph matching, temporal
  compliance, future-outcome concordance, decision trajectory.
- Temporal dimensions apply only to the temporal partition; an uncomputable
  component is `None` (reported as missing), never imputed.
- Any failure criterion forces `FAIL`; aggregation is per-dimension only and the
  composite is opt-in, weighted, coverage-labelled and must not be the headline.
- Tests: `tests/test_scoring_dimensions.py` (25) + existing 22 → **47 green**.
- **Next:** wire this scorer to the 48-task runner and the tpdeval run driver,
  collect expert panel scores, before any comparison is reported.

---

## 2. TUI — does it work?

There are **two independent TUIs**, both verified working on this host.

### 2.1 Python Textual TUI — `protacxtend/tui/`

| Check | Result |
|---|---|
| Files | `app.py` (27 KB), `styles.tcss`, `README.md` |
| Import | ✅ `import protacxtend.tui.app` → `PROTACXtendTUI`, `TUI_CSS` |
| Agent pipeline | ✅ `AGENT_PIPELINE` = **23 nodes** |
| Launch | `protacxtend tui` or `PROTACXtend tui` (TTY required) |
| Immediate run | `protacxtend tui "Design CRBN PROTACs for BRD4"` |
| Layout | header · agent sidebar (live status) · model/system panel · research-workflow log · footer |
| Issue | README header shows `v0.1.0` (cosmetic); package is 0.3.0 |

Setup: `bash scripts/setup_protacxtend_tui.sh` — **has a bug** (see §5): it
verifies with `from synglue_agent.tui.app import …`, which now raises
`ModuleNotFoundError`. The install itself works; only the verification step fails.

### 2.2 Node/TypeScript TUI — `tui/` ("Laboratory Night")

| Check | Result |
|---|---|
| Package | `@protacxtend/tui` v0.3.0, **zero runtime deps**, Node ≥ 18 |
| Entry | `tui/dist/index.js` → `ProtacXtendApp` (JSONL bridge to Python agent graph) |
| Build | ✅ `npx tsc --noEmit` clean; `dist/` present |
| Run | ✅ `node dist/index.js` starts the backend and renders the full-screen UI |
| Launcher | ✅ `tui/launch.sh` (clone → pip install -e → npm build → run) |
| Tests | `tui/tests/{app,cli}.test.ts` |
| Issue | 🔴 **no arg parsing** — `--help` / `--version` are ignored and the TUI launches instead |

```bash
# one-line (any directory, needs node + python)
curl -fsSL https://raw.githubusercontent.com/the-ahuja-lab/PROTACXtend/main/tui/launch.sh | bash

# or local
cd tui && npm install && npm run build && node dist/index.js
```

### 2.3 TUI closeout checklist
1. Fix `scripts/setup_protacxtend_tui.sh` import (`synglue_agent` → `protacxtend`).
2. Point it at a venv instead of the system interpreter.
3. Add `--help` / `--version` handling in `tui/src/index.ts`.
4. Bump the README version string to 0.3.0.
5. Commit `tui/` (currently only `tui/src/app.ts` is modified; dist/node_modules untracked).
6. Add a non-interactive smoke test (import + `--version`) to CI.

---

## 3. Installing on different servers

Three sanctioned paths. All avoid storing API keys in the installer.

### 3.1 Path A — one-line installer (any Linux/macOS server)

```bash
# minimal (CLI + setup + doctor)
curl -fsSL https://raw.githubusercontent.com/the-ahuja-lab/PROTACXtend/main/scripts/install.sh | bash

# scientific (rdkit/chemprop/torch stack)
curl -fsSL https://raw.githubusercontent.com/the-ahuja-lab/PROTACXtend/main/scripts/install.sh \
  | bash -s -- --profile scientific

# custom locations, non-interactive
curl -fsSL .../install.sh | bash -s -- \
  --profile full --prefix /opt/protacxtend/venv --bin /usr/local/bin --yes
```

Writes `~/.protacxtend/install.json`; installs wrappers `protacxtend` /
`PROTACXtend`; never touches keys.

### 3.2 Path B — pip / wheel (managed servers, venvs, CI)

```bash
python3 -m venv /opt/protacxtend && . /opt/protacxtend/bin/activate
pip install "protacxtend[full]"          # or [tui] [api] [ui] [toolkit]…
protacxtend setup        # API / Local / Configure later
protacxtend doctor       # Provider/Model/Auth/Connection/Inference/Status
```

Profiles (from `pyproject.toml`): `minimal`, `ui`, `api`, `tui`, `toolkit-chem`,
`toolkit-structure`, `toolkit-retro`, `toolkit-ml`, `toolkit-nlp`, `toolkit`,
`full`.

> **Conflict note:** `guacamol`/`PyTDC` pull `rdkit-pypi` which can shadow
> conda `rdkit`. Install `[toolkit]` into a dedicated venv or reinstall `rdkit`.

### 3.3 Path C — offline / air-gapped bundle

```bash
scripts/package_release.sh --tar     # → dist/protacxtend-<ver>-<stamp>.tar.gz
# scp the tarball to the server, then:
tar xzf protacxtend-*.tar.gz && pip install artifacts/*.whl
scripts/bootstrap_assets.sh          # restores large excluded assets (checksummed)
```

### 3.4 Path D — Docker / server stack

```bash
# single API container
docker build -t protacxtend:0.3.0 .
docker run -p 8000:8000 protacxtend:0.3.0

# full stack: api + worker + postgres + redis + ollama
cd deploy && docker compose up -d postgres redis ollama && docker compose up -d api worker
docker compose ps
```

Model weights (500 MB+) are **mounted as volumes**, not baked in:
`../data`, `../outputs`, `../SynGlue_Py`.

> 🔴 `deploy/Dockerfile.api` still copies `synglue_agent/` and runs
> `synglue_agent.backend.api_routes` — **must be renamed to `protacxtend`**
> before the server image will work as written.

### 3.5 Path E — HPC / multi-env (recommended for the scientific stack)

```bash
scripts/setup_scientific_envs.sh                 # dry-run plan + health
scripts/setup_scientific_envs.sh --execute       # core chem docking ppi md analysis ml
scripts/setup_scientific_envs.sh --execute --only md,docking

# register extra interpreters so the agent can call across envs
protacxtend toolkit --action envs
export PROTACXTEND_TOOLKIT_ENVS="myconda=/path/to/env/bin/python"
protacxtend backends          # capability × backend readiness
```

Envs created under `$PROTACXTEND_ENV_ROOT` (default `~/.protacxtend/envs`):
`core, chem, docking, ppi, md, analysis, ml` (+ optional `gromacs, mmpbsa`).
Module-load HPC hosts: `module load cuda/12.x` first; the MD/docking layer
falls back **CUDA → OpenCL → CPU** automatically.

### 3.6 Server checklist (per host)

| Item | Command / note |
|---|---|
| Python ≥ 3.10 | installer checks |
| Node ≥ 18 | only for the Node TUI |
| LLM backend | `protacxtend setup` (API key or local Ollama) |
| GPU (optional) | CUDA/OpenCL detected; Vina CPU fallback |
| Ports | API 8000 (compose maps 8001), Streamlit 8501, Postgres 5433, Redis 6378 |
| Services | `systemd` unit wrapping `protacxtend api`; or compose |
| Verification | `protacxtend doctor && protacxtend backends && protacxtend status` |
| Smoke | `scripts/distribution_smoke.sh` (installs wheel into a throwaway venv) |

---

## 4. Working at Biomni-level depth & technicality

### 4.1 The honest gap (from `sota/SOTA_COMPARISON.md`, `Biomni_Gaps`)

| Dimension | Biomni | PROTACXtend | What "closing" requires |
|---|---|---|---|
| Breadth | ~150 general tools (genomics, single-cell, pathology, proteomics) | 115 tools, TPD-weighted | optional: adopt an MCP tool layer, don't chase full breadth |
| Databases | 59 general connectors | 49 registry entries | add general connectors only where TPD needs them |
| Packages | 106 general packages | curated subset | fine as-is |
| **Dynamic code generation & execution** | **agent writes + runs arbitrary Python per task** | governed deterministic tool registry | 🔴 **the key technicality gap — add a sandboxed code-execution layer** |
| Execution environment | managed cloud sandbox | local/self-hosted | add containerised sandbox + resource caps |
| General benchmark | Biomni-Eval1 (433 q) | 48 TPD tasks (unmeasured) | run the 48-task benchmark on both |
| Multi-omics | scRNA-seq, spatial, WGS/WES, pathology | TPD omics only | add only if a TPD task needs it |
| Agent scaffold | general | TPD-specific | keep specialised; wrap with a general planner |

### 4.2 Where PROTACXtend already leads (the moat to protect)

Hook effect · lysine ubiquitination · cooperativity α · ternary feasibility ·
pDC50/Dmax + cell-context + TACK/SynGlue models · 4-stage KNOW→REASON→DESIGN→
DISCOVER workflow · evidence typing (MEASURED/RETRIEVED/CALCULATED/LEARNED/
SURROGATE/HEURISTIC) · self-healing escalation (27 caps × 115 tools) · per-
candidate provenance. Biomni has **no TPD mechanism layer**.

### 4.3 The plan already written — `sota/TPD_WINNING_PLAN.md`

Six pillars; the last four are exactly "Biomni-level technicality, TPD-focused":

1. **Mechanistic layer (owned)** — prove Modules 1–7 with locked benchmarks.
2. **Evidence layers (add)** — cell-type specificity (Tau index, bimodality),
   perturbation signatures, FDA safety signals, clinical precedence,
   single-cell/spatial.
3. **Organisation (adopt)** — CSO + four divisions + scientific reviewer with a
   re-delegation loop, over the existing 31-node graph.
4. **Tool layer (adopt)** — MCP servers per domain with typed tools.
5. **Evaluation (own)** — 504 core + 120 adversarial TPD tasks + prospective
   case study + public leaderboard.
6. **Closed loop (build)** — assay feedback → active learning → next batch →
   PyLabRobot-style execution.

Already implemented in `sota/impl/` (the "depth" scaffolding):

| File | What it gives |
|---|---|
| `impl/tpd_divisions.py` | Virtual TPD Biotech: CSO + 4 divisions + reviewer that hard-fails `not_available` with non-zero confidence |
| `impl/celltype_features.py` | `tau_index`, `bimodality_coefficient`, hallmark signatures, HPA tissue-matrix E3 specificity |
| `impl/tpd_mcp_server.py` | **13 typed MCP tools** over JSON-RPC stdio (zero mandatory deps; FastMCP optional) |
| `impl/clinical_translation.py` | ClinicalTrials.gov v2 + OpenFDA with honest `not_available` fallback |

```bash
python sota/impl/tpd_mcp_server.py --list
python sota/impl/tpd_mcp_server.py --call resolve_target '{"target_name":"BRD4"}'
python -c "from sota.impl.celltype_features import feature_report; print(feature_report('CRBN'))"
python sota/impl/tpd_divisions.py
```

### 4.4 The single biggest technicality upgrade to build

**A sandboxed code-execution tool** (Biomni's defining capability):

- tool contract: `run_python(code, timeout, mem_mb, network=False) → {stdout, stderr, artifacts}`;
- sandbox: subprocess/container with CPU+memory caps, no network by default,
  read-only data mounts, artifact capture;
- guardrails: forbid `shell=True`, `pickle.load` on untrusted data, and key access (links to G12);
- register it in the agent registry and in the MCP server;
- add it to the benchmark's tool-selection metric so "dynamic code" is measured,
  not claimed.

### 4.5 How to *measure* depth (so the claim is defensible)

Use the axes in `SOTA_COMPARISON.md` §7–8 on the same tasks: tool competence,
TPD knowledge, design competence, structural competence, discovery competence;
plus planning/tool/execution/recovery autonomy, evidence grounding, structural
grounding, validity, reproducibility, human-intervention rate, cost, latency.
Replace the current opinion scores (breadth 8.5 / depth 9.5) with measured ones
from an executed 48-task run.

---

## 5. Stale / broken items to fix before close

| # | Item | File | Severity |
|---|---|---|---|
| 1 | TUI setup verifies with old package name | `scripts/setup_protacxtend_tui.sh:67` (`from synglue_agent.tui.app`) | 🔴 breaks verification |
| 2 | Server image copies/launches old package | `deploy/Dockerfile.api:16,35` (`synglue_agent`) | 🔴 container won't run as written |
| 3 | Node TUI ignores `--help`/`--version` | `tui/src/index.ts` | 🟡 UX |
| 4 | TUI README shows v0.1.0 | `protacxtend/tui/README.md` | 🟡 cosmetic |
| 5 | 4 divergent toolkit sheets | `Agent_Toolkit*.xlsx`, `analysis/inventory/*` | 🟡 no canonical source |
| 6 | Benchmark manifest flag wrong 19/48 | `benchmark/benchmark_manifest.csv` | 🔴 misleads scoring |
| 7 | Missing referenced CSVs | `benchmark/cases/DISCOVER-01`, `KNOW-08` | 🔴 blocks run |
| 8 | Security: `shell=True`, `pickle.load` | `toolkit/provision.py:310`, `escalation/installer.py:293`, `models/degradation_model.py:93` | 🔴 RCE risk |
| 9 | Big transient caches untracked | `.p.npy`, `.score.npy`, `.so3_*.npy` (~430 MB) | 🟡 repo hygiene |
| 10 | New closeout docs untracked | `CODEBASE_STATE.md`, `BENCHMARK_AUDIT.md`, this file | 🟡 commit them |

---

## 6. Definition of "closed"

The project can be declared closed when **all** of these hold:

1. **Tree committed** — no critical work only exists as untracked files.
2. **Tests** — `pytest` green in a documented time budget (fast tier < 10 min).
3. **Security** — no `shell=True` / unsafe `pickle.load` on untrusted input.
4. **TUI** — both TUIs launch from a clean install; `--help` works; setup script verifies correctly.
5. **Install** — `scripts/distribution_smoke.sh` passes; one command installs on a clean server (pip / curl / docker).
6. **Benchmark** — *either* a scored 48-task run exists *or* the freeze is explicitly labelled "authored, not yet measured" in `README.md` and `BENCHMARK_AUDIT.md`.
7. **Science** — every `config/scientific_status.yaml` entry is either validated or explicitly `NOT_VALIDATED` in the public docs.
8. **Docs** — one canonical toolkit sheet/markdown; no stale package names.

### Verification commands (run before declaring closed)

```bash
# install + smoke
scripts/package_release.sh && scripts/distribution_smoke.sh
# CLI / provider / backends
protacxtend doctor && protacxtend backends && protacxtend status
# TUIs
protacxtend tui --help
cd tui && npx tsc --noEmit && node dist/index.js --version   # after fix
# tests
pytest -q
# benchmark freeze integrity
python -c "from benchmark_runner.freeze import assert_frozen; assert_frozen()"
# science status
python -c "import yaml;print(len(yaml.safe_load(open('config/scientific_status.yaml'))['modules']),'modules')"
```

---

## 7. Pointer index

| Topic | Where |
|---|---|
| Whole-codebase state | `CODEBASE_STATE.md` |
| Benchmark done/scorable/scored | `BENCHMARK_AUDIT.md` |
| Scientific status source of truth | `config/scientific_status.yaml` |
| TUI (Python) | `protacxtend/tui/` (`app.py`, `README.md`) |
| TUI (Node) | `tui/` (`src/`, `dist/`, `launch.sh`, `package.json`) |
| TUI port audit (Feynman reference) | `docs/FEYNMAN_TUI_PORT_AUDIT.md` |
| Installer | `scripts/install.sh`, `scripts/setup_protacxtend_tui.sh` |
| Packaging / distribution | `documentation/DISTRIBUTION_PLAN.md`, `scripts/package_release.sh`, `scripts/distribution_smoke.sh` |
| Server stack | `Dockerfile`, `deploy/docker-compose.yml`, `deploy/Dockerfile.api` |
| Modular envs / GPU | `scripts/setup_scientific_envs.sh`, `documentation/SCIENTIFIC_BACKENDS.md`, `docs/ENVIRONMENT_MANAGER.md` |
| Offline assets | `scripts/bootstrap_assets.sh`, `ASSET_MANIFEST.md` |
| Setup measurement | `scripts/universal_setup_report.py` |
| Biomni / SOTA comparison | `sota/SOTA_COMPARISON.md`, `sota/TPD_WINNING_PLAN.md`, `sota/PROTACXTEND_AUDIT.md` |
| Biomni install evidence | `benchmark_results/reports/biomni_install_smoke.md`, `benchmark_results/configs/biomni_config.json` |
| Depth scaffolding | `sota/impl/` (`tpd_divisions.py`, `celltype_features.py`, `tpd_mcp_server.py`, `clinical_translation.py`) |
| Gap register | `audit_nextgen/csv/gap_analysis.csv` (G01–G16) |
| Head-to-head plan | `tpdeval/docs/02_BLUEPRINT.md` (P0–P3) |

---

### Closing statement

> PROTACXtend is a large, genuinely functional TPD platform with a working CLI,
> API, Streamlit UI, **two working TUIs**, a real scientific stack, and a
> governance/benchmark apparatus. What remains to *close* is not new science but
> **consolidation and honesty**: commit the tree, fix the stale package names and
> the security items, make the TUI install verifiable, and either run the
> benchmark or label it unmeasured. Depth "like Biomni" is reached not by
> breadth but by adding the one capability Biomni has and we lack — **sandboxed
> dynamic code execution** — on top of the TPD mechanism layer we already own,
> then measuring both on the same frozen tasks.
