# Pass 3 — /design cleanliness, pinned trace, probe fixtures, degradation

Date: 2026-10-06 · Repo `sprint-2`

Executed in order, all measured.

## 1. `/design` is now SCIENTIFIC-clean ✅

**Problem:** in `PROTACXTEND_EXECUTION_MODE=scientific`, `run_design` failed closed with
`SyntheticInputNotAllowed: … 14 fixture/synthetic finding(s); first at
candidate_evidence_table[2].provenance.linker_source='curated_demo_linker'`.

**Root cause:** the deterministic DESIGN route mixed the source-backed dBET1 reference with
exploratory candidates built from `curated_demo_*` linkers, and the public payload carried
them. (Note also: the identity gate passed demo-linker candidates, so identity-pass was not
a usable separator.)

**Fix (`protacxtend/workflows/designer.py`):** the SCIENTIFIC-mode payload scanner is now
the policy of record — each candidate row is scanned; scanner-flagged rows are written to
`exploratory_candidates.json` and removed from the scientific `candidate_evidence_table`.
`downstream_scoring_candidate_ids` is restricted to ids present in the scientific table so
the payload is internally consistent.

**Measured (real run):**
```
scientific candidate_evidence_table : 16 rows (2 source-backed dBET1 + 14 generated-linker)
exploratory_candidates.json         : 14 rows (curated_demo_linker)
payload scan                        : CLEAN
```
`PROTACXTEND_EXECUTION_MODE=scientific pytest tests/test_tui_slice_routing.py::test_execute_design_runs_existing_engine_with_honest_gates` → **1 passed**.

## 2. First pinned, evidence-driven, inspectable agent trace ✅

`scripts/pin_agent_trace.py` produces `outputs/execution/agent_trace/<name>/{agent_trace.jsonl,AGENT_TRACE.md,PIN.json}`
with the spec-§12 fields: run identity (commit/mode/model/budgets) · role · action ·
plan_version · status · observation · evidence_kind · inputs_hash · gate · terminal reason.

- **Design trace** — 21 records; terminal `valid_candidate`; one **evidence-driven routing
  decision** (`separate_exploratory_candidates`, 14 candidates routed out, gate
  `identity_assembly`); `payload_scan: clean`.
- **Abstention trace** — terminal `justified_abstention` with
  `MissingScientificInput: warhead_smiles, linker_smiles, e3_smiles, pose_pdb`.

**Honest labelling:** the DESIGN route is a **fixed workflow**, not yet a free adaptive
action-selection agent. The trace states this explicitly in `AGENT_TRACE.md`.

## 3. Probe fixtures for the 10 repo tools ✅

Probed each with real inputs:
- **6 execute** → added real `PROBE_FIXTURES`: `predict_protac_activity`,
  `predict_deepprotacs`, `split_protac_bellerophon`, `assign_e3_mechanism`,
  `inspect_repo_assets`, `list_repo_tools` (uses the source-backed MZ1 canonical SMILES,
  never a `CCO` placeholder).
- **4 cannot run a smoke check** → declared `PROBE_EXEMPT` with reasons:
  `run_degradomap_experiment` (needs merged DEG dataset), `predict_protac_stan` (needs
  checkpoints), `sample_ternary_ternify` (needs ternary data dir), `predict_se3_protacs`
  (model + sequence inputs; envelope invalid).

`list_agent_tools()` now exposes `probe_exempt`; the exposure test asserts
`fixtured | exempt == all-tools`. `protacxtend/tests/test_agent_tool_exposure.py` → **19 passed**
(includes FastAPI/TUI/web transport + `44==44` count).

## 4. Degradation model loader test path ✅

`test_degradation_model::test_tiny_pickle_models_load_and_predict` failed because the test
wrote the tiny model to `/tmp`, which the G12 allowlist (`security/safe_io.py`) correctly
refuses. Fixed the **test** to use a repo-local temp dir (`outputs/_test_tmp`); the security
policy is unchanged. `MODEL_PREDICTED` behavior tests in `test_degradation_endpoint.py`
pass. Both files: **20 passed**.

## Verification

```
pytest tests/test_source_backed_design_and_adapters.py tests/test_gold_integrity.py \
       tests/test_tpdeval.py protacxtend/tests/test_agent_tool_exposure.py \
       protacxtend/tests/test_degradation_model.py protacxtend/tests/test_degradation_endpoint.py
→ 72 passed
pytest tests/test_design_tui_workflow_bridge.py → 8 passed, 1 pre-existing failure
PROTACXTEND_EXECUTION_MODE=scientific pytest tests/test_tui_slice_routing.py::test_…honest_gates → 1 passed
```

## Known remaining (not fixed here)

- `test_design_tui_workflow_bridge::test_design_command_executes_existing_deterministic_engine_and_carries_candidate_evidence`
  is **pre-existing**: its `_fake_state` candidate carries no `identity_assembly_gate`
  provenance, so the identity-gated `downstream_scoring_candidate_ids` is empty. The test
  fixture predates the gate; fixing it means adding realistic gate provenance to the fake.
- The identity gate still passes demo-linker candidates internally (separation happens at
  the payload layer). Tightening the gate to reject non-source-backed linkers is a
  follow-up that changes gate semantics and should be done deliberately.
