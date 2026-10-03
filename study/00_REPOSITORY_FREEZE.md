# 00 — Repository Freeze

**Artifact:** Phase 0 freeze record for the ProtacXtend experimental study
**Freeze timestamp (UTC):** 2026-09-29T08:03:46Z
**Produced by:** Phase 0 audit (read-only). No system file was modified.

> Rule: every subsequent result table must cite the `repo_commit` + `worktree_dirty`
> + `freeze_id` below. A result that cannot be tied to a frozen revision is
> discarded, not reconciled.

---

## 1. Revision control

| Field | Value |
|---|---|
| git HEAD | `82a0e4d1746b8b364b01ad823b16b64b727daefe` |
| branch | `sprint-2` |
| HEAD commit date | 2026-09-23 18:50:35 +0530 |
| HEAD subject | `chore(memory): commit protacpilot-memory -> protacxtend-memory rename (F-14)` |
| worktree dirty | **YES** |
| modified (tracked) files | **69** |
| untracked files/dirs | **241** |
| `git describe` | (n/a, no tags at HEAD) |

**Dirty-state caveat (blocking for a "frozen" claim).** The working tree differs
from HEAD in 69 tracked files, including scientifically load-bearing modules:
`protacxtend/agents/*.py` (binder, construction, design_planner, e3, graph,
linker, runtime, search_control, supervisor, target, warhead), `protacxtend/agentic/*`,
`protacxtend/canonical/*`, `protacxtend/models/degradation_model.py`,
`benchmark_runner/{grader,runner,scoring}.py`, and `protacxtend/data/curated_*.csv`.

Consequences:
1. HEAD is **not** the code that produced the latest runs. Any run executed now
   must be pinned to a new commit or to a content hash of the dirty tree.
2. A `tree_hash` (sorted sha256 of all `protacxtend/**/*.py` + `benchmark_runner/**/*.py`
   + `tpdeval/**/*.py`) MUST be computed and stored in the run manifest before
   Phase 1. See §7.
3. `benchmark/FREEZE_MANIFEST.json` covers the *benchmark assets* (freeze v2A.1,
   100 entries); it does **not** cover the system code. System and benchmark
   are frozen by different mechanisms and both must be recorded.

---

## 2. Host / hardware

| Field | Value |
|---|---|
| hostname | `iiitd` |
| kernel | `5.15.0-91-generic` |
| OS | Ubuntu 22.04.3 LTS |
| CPUs | 32 |
| RAM | 629 GiB total (160 GiB in use at audit time) |
| Disk (`/storage`) | 9.1 TiB, **99 % used, 165 GiB free** ⚠ |
| GPU 0 | NVIDIA RTX 5000 Ada Generation, 32 760 MiB |
| GPU 1 | NVIDIA GeForce RTX 3090, 24 576 MiB |
| GPU driver | 580.126.09 |

⚠ **Disk headroom is a hard risk.** A full primary + ablation + e2e run set with
raw traces, Parquet tables, docking/MD artifacts and figure renders can exceed
165 GiB. Mitigation is in the design doc (log rotation, Parquet compression,
no per-run PDB dumps unless a stage is scored). See `03_EXPERIMENTAL_DESIGN.md` §10.

---

## 3. Python / runtime

| Field | Value |
|---|---|
| interpreter | CPython 3.13.5 |
| path | `/home/saveenas/miniconda3/bin/python3` |
| active conda env | `base` |
| other envs | `docking`, `gromacs`, `md-openff`, `MG` (external backends) |
| test config | `pytest.ini` → `testpaths = tests protacxtend/tests`; 145 test modules |
| markers | `network`, `slow`, `llm` |

---

## 4. Package versions (installed, measured — not from requirements.txt)

| Package | Installed | requirements.txt pin | Drift |
|---|---|---|---|
| rdkit | 2026.3.4 | 2026.3.4 | none |
| numpy | 2.4.6 | 2.4.6 | none |
| pandas | 2.3.3 | 2.3.3 | none |
| scipy | **1.18.0** | 1.17.1 | minor drift |
| scikit-learn | **1.6.1** | 1.9.0 | **drift** |
| torch | **2.10.0** | 2.6.0 | **major-ish drift** |
| chemprop | 2.3.1 | 2.3.0 | patch |
| openai | 0.27.8 | >=1.0 | **below pin** ⚠ |
| anthropic | **not installed** | >=0.40 | missing |
| pydantic | 2.11.7 | >=2.6 | ok |
| fastapi | 0.136.3 | >=0.110 | ok |
| langgraph | 1.2.2 | >=1.2 | ok |
| langchain | **0.0.275** | >=0.2 | **below pin** ⚠ |
| ollama | 0.6.2 | >=0.6 | ok |
| requests | 2.32.3 | >=2.31 | ok |

**Implications.**
- `scikit-learn` and `torch` differ from the declared runtime. Any learned model
  (degradation, ADMET, linker) must be re-validated under the *installed* versions;
  predictions are not assumed byte-identical to earlier runs.
- `openai==0.27.8` and `langchain==0.0.275` are far below the declared floors. Code
  paths that import modern `openai`/`langchain` APIs may fail. This is a Phase 1
  pilot must-catch item.
- `anthropic` absent → the cross-LLM arm cannot use Claude without provisioning.

---

## 5. Model / provider

| Field | Value |
|---|---|
| primary provider | `deepseek` (`PI_PROVIDER`) |
| primary model | `deepseek-v4-flash` (`PI_MODEL`) |
| endpoint (per `benchmark_runner/live.py`) | `https://api.deepseek.com` |
| credential source | `/home/saveenas/.pi/agent/auth.json` (`deepseek.key`) — never printed |
| published price (runtime) | $0.14 / 1M input tokens, $0.28 / 1M output tokens |
| decoding (per `live.py`) | deterministic sampling; `thinking:{type:disabled}`; `max_tokens=24000`; timeout 600 s; ≤3 attempts |

**Provider availability at freeze:** only `deepseek` is authenticated. No
OpenAI/Anthropic/Google/Ollama-hosted alternative key is present in the
environment beyond local Ollama. **Phase 6 (cross-model) is therefore gated**
until ≥3 distinct model families are provisioned (see design doc §10/§11).

---

## 6. Scientific backend versions / provisioning

`config/capability_backend_crosswalk.yaml` records 27 TPD capabilities mapped to
19 capability-first scientific backends with readiness:

```
READY 10 | BLOCKED 11 | EXECUTABLE 6
```

Selected backend facts relevant to reproducibility:

| Backend | Status | Note |
|---|---|---|
| chemistry (RDKit) | READY | 2026.3.4, validated |
| conformer_generation | READY | local |
| ligand_docking | READY | docking conda env |
| protein_preparation | READY | |
| ppi_docking / ternary_docking | EXECUTABLE | external engines |
| binding_energy | EXECUTABLE | |
| molecular_dynamics | EXECUTABLE | gromacs / md-openff envs |
| admet | READY | |
| linker_generation | **BLOCKED** | no provisioned generative linker engine (DeLinker/DiffLinker/LinkInvent absent) |
| de_novo_generation | **BLOCKED** | no 3D-aware generative model |
| reaction_prediction | **BLOCKED** | no atom-mapping/reaction model |
| protein_language_models | **BLOCKED** | ESM-2/ProtT5 weights not provisioned |
| patent_mining | **BLOCKED** | web-only, no licence |
| proteomics / image_analysis | **BLOCKED** | tools not installed |

**Implication:** "linker design" and "retrosynthesis" stages must be scored as
reasoning/constraint tasks, not as validated generative execution, until those
backends are provisioned. The system must not silently substitute a surrogate for
a blocked capability (crosswalk fallback classes: EXACT / APPROXIMATE / SURROGATE /
INFORMATIONAL_ONLY / INVALID).

---

## 7. Freeze actions required before Phase 1 (not yet performed — read-only audit)

1. **Commit or stash** the 69 tracked modifications, or compute and record a
   `tree_hash` over `protacxtend/`, `benchmark_runner/`, `tpdeval/`.
2. Write `study/freeze_manifest.json` = `{repo_commit, tree_hash, dirty, date,
   python, packages, model, provider, benchmark_freeze_version}`.
3. Snapshot the benchmark asset hashes:
   - `benchmark/FREEZE_MANIFEST.json` (freeze v2A.1, 100 entries)
   - `benchmark500/manifests/{general_500,temporal_500}.manifest.json`
   - `benchmark500/ARCHIVE_MANIFEST.json`
   - `tpdeval/config/allocation_500.json`
4. Record backend CLI versions (`vina`, `gmx`, `obabel`, `aizynthcli`) where present.
5. Freeze retrieval corpus: compute sha256 over `protacxtend/memory/literature_store`
   and the RAG index; record the frozen date; block network drift during runs.

Recorded here: **not done**. Phase 0 is inspection only, per instruction.

---

## 8. Provenance summary block (paste into every run manifest)

```yaml
freeze_id: TBD
repo_commit: 82a0e4d1746b8b364b01ad823b16b64b727daefe
branch: sprint-2
worktree_dirty: true
tracked_modified: 69
untracked: 241
tree_hash: TBD
host: iiitd
os: Ubuntu 22.04.3 LTS
python: 3.13.5
provider: deepseek
model: deepseek-v4-flash
temperature: 0.0
top_p: 1.0
max_tokens: 24000
seed: TBD
benchmark_freeze: v2A.1 (benchmark/), benchmark500 ARCHIVE
date_utc: 2026-09-29T08:03:46Z
```
