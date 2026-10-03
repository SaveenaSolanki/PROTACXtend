# Gate B — scientific integrity repair (implemented)

Date: 2026-09-23 · HEAD before work: `0abbe83` (`sprint-2`)
Scope: `todo/PROTACXtend_05_BENCHMARK_AUDIT_AND_NEXT_STEPS.md` §3 Gate B and §6.

Gate B closes the two severity-1 findings from `todo_audit/FINDINGS.md`:
**F-03** (SCIENTIFIC mode ignored on the canonical path) and **F-04** (BRD4
mis-resolved to `M0QZD9`). It also fixes the installed-console-script finding
**F-15** from Gate A and the pytest-collection finding **F-16**.

---

## 1. Execution-mode propagation (F-03)

**Fix.** Demo seeds in the bundled curated tables are now mode-gated, and the
mode is recorded on every strategy and manifest.

| file | change |
|---|---|
| `protacxtend/runtime/modes.py` | added `is_demo_source()`, `filter_scientific_rows()`, `DEMO_SOURCE_PREFIXES` |
| `protacxtend/tools/protac_toolbox.py` | `load_curated_warheads()` / `load_curated_e3_ligands()` drop `local_demo_*` rows in SCIENTIFIC mode and record `demo_rows_dropped` |
| `protacxtend/canonical/modules.py` | `ChemistryWarheadModule` drops demo warheads leaked via the engine state (defense in depth) and warns |
| `protacxtend/canonical/decision.py` | `_warheads()` drops demo-sourced warheads; `execution_mode` recorded on strategy + manifest |
| `protacxtend/canonical/schemas.py` | `TherapeuticStrategy.execution_mode`, `RunManifest.execution_mode` |
| `protacxtend/results/schema.py` | `ToolRun.execution_mode` (+ to_dict/from_dict) |
| `protacxtend/agents/warhead_agent.py` | abstention message now reports how many demo rows were dropped |
| `protacxtend/agents/e3_agent.py` | SCIENTIFIC abstains with a typed error when no source-backed E3 ligand exists |
| `protacxtend/cli.py` | `strategy` no longer substitutes the hidden default request in SCIENTIFIC mode |
| `protacxtend/backend/api_routes.py` | `ScientificInputError` → HTTP **422** typed JSON (was opaque 500) |

### Before / after (BRD4–VHL, `--execution-mode scientific`)

| field | before (`strategy_1ef85a525b`) | after (`strategy_e94dc7888c`) |
|---|---|---|
| `execution_mode` | *(absent)* | `scientific` |
| `target_validation.uniprot_id` | **`M0QZD9`** (fragment) | **`O60885`** (reviewed) |
| organism | `Homo sapiens` | `human` |
| structures | `[]` | `["2OSS","3MXF","5T35"]` |
| known binder count | `3` (demo) | `120` (curated) |
| tractability | `0.0` | `0.86` |
| warhead sources | `local_demo_brd4_binder`, `local_demo_bromodomain_warhead`, `local_demo_jq1_like_warhead` | **none** (`[]`) |
| E3 ligands | `VHL_demo_hydroxyproline_like`, `VHL_demo_vh032_like` | none emitted (run abstained at warhead step) |
| candidates | `25` (demo-derived) | `0` |
| `stopping_state` | `REVISE` | `INSUFFICIENT EVIDENCE` (explicit abstention) |
| `chemistry_warhead` module | `succeeded` | `degraded` |

Full traces: `trace_before_scientific.strategy.json`,
`trace_after_scientific.strategy.json`, `trace_after_scientific.manifest.json`,
`before_after_scientific.json`.

**Why abstention and not a real BRD4 warhead.** `protacxtend/data/curated_warheads.csv`
contains **only 6 rows and all are demo seeds** (verified: `real=0`). The run
therefore has no *source-backed, derivatizable* warhead. The deterministic engine
does retrieve real ChEMBL/PubChem binders (the after-trace warns
`Retrieved 90 binders from ChEMBL, PubChem`), but those have no validated exit
vector, so constructing a PROTAC from them would be an unaudited surrogate.
Gate B explicitly permits "an explicit abstention if unavailable", which is what
the pipeline now emits with a typed `Insufficient evidence` state.

The E3 side is real: 214 of 221 curated E3 ligands are literature rows with DOIs
(`local_demo` = 7 dropped). In SCIENTIFIC mode the E3 agent now selects
`VH032`, `VH298`, `VHL_ligand_*` etc., never the demo handles.

---

## 2. Protein identity (F-04)

**Fix** in `protacxtend/agents/target_agent.py`: resolution order is now

1. authoritative packaged curated table (`curated_targets.csv` → `O60885`, human,
   structures, tractability);
2. shared reviewed-UniProt client (`protacxtend.backend.uniprot_client`,
   `reviewed=true`, `organism_id:9606`) — the same client the `resolve_target`
   agent tool already used;
3. reviewed-filtered raw UniProt search as last resort.

The resolved `TargetRecord` records `external_ids["uniprot_tier"]`
(`curated` / `reviewed` / `raw_search`). The old bare
`search?query=BRD4&size=1` (which returned the fragment `M0QZD9`) is replaced.

---

## 3. Regression tests

`tests/test_gate_b_scientific_integrity.py` — **11 tests**, all pass:

* demo rows dropped in SCIENTIFIC, kept in DEMO (warheads and E3 ligands);
* `WarheadSelectionAgent` abstains for BRD4 in SCIENTIFIC, still works in DEMO;
* E3 agent selects only DOI-backed ligands in SCIENTIFIC;
* canonical strategy records `execution_mode` and drops leaked demo warheads;
* `TargetResolverAgent` resolves BRD4 → `O60885` (asserts `!= M0QZD9`),
  `uniprot_tier == curated`, `2OSS` in structures;
* unknown gene does not crash and reports a typed error.

### Test results

| command | result |
|---|---|
| `pytest tests/test_gate_b_scientific_integrity.py` | **11 passed** |
| `pytest tests/ -m "not network and not slow"` | **328 passed** |
| focused set (gate-b, modes, p0b, canonical, results schema, cli, uniprot, e3) | **126 passed** |
| cross-route matrix (`todo_audit/gateA/cross_route_matrix.py`) | 14 rows, see below |

---

## 4. Cross-route matrix (Gate A3)

`todo_audit/gateA/cross_route_matrix.csv` / `.md`. Highlights:

| route | case | outcome |
|---|---|---|
| agent-tool | missing input | typed `MISSING_SCIENTIFIC_INPUT` |
| agent-tool | placeholder `CCO` | typed `SYNTHETIC_INPUT_FORBIDDEN` |
| agent-tool | real SMILES | `ok`, `input_origins={smiles: USER}` |
| agent-tool | unknown tool | `failed`, not executed |
| capability-runner | missing SMILES | typed `MISSING_SCIENTIFIC_INPUT` |
| capability-runner | invalid SMILES | `warning`, `output_valid=false` |
| capability-runner | invalid PDB id | `capability_unavailable` |
| canonical | demo warhead injected | `demo_warheads_dropped`, mode `scientific` |
| CLI | empty request | `exit 2`, `MISSING_SCIENTIFIC_INPUT` |
| CLI | target+E3 | `exit 0`, abstention strategy |
| API | missing input | **HTTP 422** typed JSON |
| API | real SMILES | HTTP 200 |

---

## 5. Gate A prep (preserve & reproduce)

| item | artifact |
|---|---|
| HEAD / branch / status / env | `todo_audit/gateA/archive/git_state.txt`, `python_env.txt` |
| raw `todo_audit` snapshot | `todo_audit/gateA/archive/todo_audit_evidence_snapshot/` |
| `protacxtend-memory` rename inspection | `todo_audit/gateA/README.md` |
| reproducible verify | `bash todo_audit/verify.sh` |
| editable reinstall + console script | fixed (see below) |

**Rename inspection result.** `protacxtend-memory/` (338 files, untracked) is a
strict superset of tracked `protacpilot-memory/` (104 files): all 104 tracked
files are byte-identical, 0 files exist only in the old tree, 234 are new
(docs/evaluation/paper + caches). It is clearly an intended rename + expansion
but is **not committed**. Per Gate A, nothing was deleted; the maintainer must
commit the rename or restore the old tree (F-14 was subsequently closed in
`82a0e4d`; see `gateC/F14_memory_provenance.json`).

**F-15 fixed.** `pip install -e . --no-deps` reinstalled version `0.3.0`;
`/home/saveenas/miniconda3/bin/protacxtend` now imports `protacxtend.cli` and
`protacxtend --help` works.

**F-16 fixed.** `pytest.ini` now sets `testpaths = tests protacxtend/tests` and
`norecursedirs`, so bare `pytest` collects project tests only (968 collected,
0 collection errors; previously 1357 collected / 156 errors).

---

## 6. Exact reproduction commands

```bash
cd /storage/saveena/protacxtend
pip install -e . --no-deps                      # F-15
bash todo_audit/verify.sh                       # Gate A reproducible evidence

# F-03 / F-04 end-to-end (scientific now abstains with O60885)
python -m protacxtend.cli --execution-mode scientific strategy "Design a VHL PROTAC against BRD4"

# cross-route matrix
python todo_audit/gateA/cross_route_matrix.py

# regression tests
python -m pytest tests/test_gate_b_scientific_integrity.py -q
python -m pytest tests/ -m "not network and not slow" -q
```

---

## 7. Unresolved failures (honest status)

| id | status |
|---|---|
| F-14 working tree dirty (`protacxtend-memory` rename) | **✅ closed** — committed as a pure rename `82a0e4d`; 104/104 byte-identical, generated outputs re-ignored, no content lost |
| F-01/F-02 full 48-task executed pilot | **open** — not run; Gate C (independent gold) must precede it |
| F-05 circular self-grading (42/48 derived overlays) | **open** — Gate C |
| F-06 29 gold adjudications | **open** — Gate C |
| F-09 scored baselines (`benchmark_results/scored/` empty) | **open** — Gate C/D |
| F-10 artifact tree (splits/pre-registration/gold_review) | **open** — Gate C |
| F-11 temporal/cutoff/leakage (E7) | **open** — Gate E |
| F-12 one `CriticVerifier` vs three critics | **open** — not required by Gate B |
| F-13 provenance: `runtime_s` vs timestamps inconsistency | **partially addressed** (mode now recorded); runtime accounting not changed |
| BRD4 real warhead | **abstains** — no source-backed derivatizable warhead exists in the packaged tables; real ChEMBL binders are retrieved but lack validated exit vectors |

Per §6, the full 48-task benchmark was **not** scored and the `0.885` offline
value is **not** presented as therapeutic performance.
