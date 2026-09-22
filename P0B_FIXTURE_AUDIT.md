# P0-B — Fixture/Default Elimination & Execution Modes

**Scope:** eliminate hidden fixture/default scientific inputs from the agent
tools and the canonical workflow; introduce explicit execution modes; make
missing real input a typed failure rather than a silent substitution.

**Baseline HEAD:** `c4af830` (working tree). **Contract:** *no fixture or
synthetic scientific input may be substituted when required real input is
missing; every ToolRun records input origin; SCIENTIFIC mode rejects
FIXTURE/SYNTHETIC.*

> **Status: P0-B implemented and tested.** The wider benchmark-readiness
> sequence (NL parser → canonical orchestrator → typed EvidenceItem/ToolRun/
> RunManifest/TherapeuticStrategy → 50 gold tasks → pilot run) is **not** part
> of this change and is tracked in §8.

---

## 1. Execution modes

`protacxtend/runtime/modes.py` (contextvar-scoped, env default
`PROTACXTEND_EXECUTION_MODE`):

| Mode | Fixtures | Placeholder/synthetic | Use |
|---|---|---|---|
| `DEMO` | allowed, labelled | allowed, labelled | interactive exploration |
| `TEST` | allowed (explicit opt-in), result marked fixture-only | allowed | deterministic tests/CI |
| `SCIENTIFIC` | **forbidden** | **forbidden** | production / benchmark |

```python
from protacxtend.runtime import modes
with modes.execution_mode("scientific"):
    ...
```

## 2. Typed input origins

Every tool call now records where each scientific input came from:

| Origin | Meaning |
|---|---|
| `USER` | supplied by the caller / user request |
| `RETRIEVED` | fetched from a database / API / literature |
| `GENERATED` | produced by a generative model |
| `COMPUTED` | derived deterministically from other inputs |
| `FIXTURE` | bundled probe/demo fixture (value the caller did not supply) |
| `SYNTHETIC` | placeholder (`CCO`…) or synthetic artifact path |

Recorded as `input_origin` (dominant) + `input_origins` (per key) on
`run_agent_tool`, in executor `provenance`, and on `ToolResult`
(`input_origin`, `failure_code`).

## 3. Typed failure codes

`FailureCode`: `MISSING_SCIENTIFIC_INPUT`, `STRUCTURE_UNAVAILABLE`,
`NO_KNOWN_BINDER`, `E3_LIGAND_UNAVAILABLE`, `TOOL_UNAVAILABLE`,
`FIXTURE_FORBIDDEN`, `SYNTHETIC_INPUT_FORBIDDEN`, `INVALID_SCIENTIFIC_INPUT`.
Exceptions carry `.code` and `to_failure()`. A tool abstains with a code
instead of substituting a default.

---

## 4. The 34-agent-tool audit

All **34/34** registered ready tools have an executor and a probe fixture.
Required SCIENTIFIC inputs and the fixture status:

| Tool | Required real input (SCIENTIFIC) | DEMO fixture contains placeholder/synthetic? |
|---|---|---|
| deep_research | query | no |
| search_europe_pmc | query | no |
| search_pubmed | query | no |
| verify_crossref | doi | no |
| retrieve_fulltext | pmcid | no |
| search_web | query | no |
| resolve_target | target_name | no |
| search_uniprot | query | no |
| retrieve_target_binders | target_name | no |
| select_e3_ligase | target | no |
| retrieve_e3_evidence | e3 | no |
| inspect_smiles | smiles | no |
| search_pubchem | term | no |
| search_chembl | term | no |
| search_bindingdb | target | no |
| detect_exit_vectors | smiles | no |
| generate_linkers | *(generative; no required real input — origin GENERATED)* | no |
| construct_protac | warhead_smiles, linker_smiles, e3_smiles | **linker_smiles** |
| check_synthetic_feasibility | smiles | **smiles (CCO)** |
| diagnose_capability | *(metadata; exempt)* | no |
| list_capability_readiness | *(metadata; exempt)* | no |
| list_scientific_capabilities | *(metadata; exempt)* | no |
| run_scientific_capability | capability, params | no |
| retrieve_pdb | target | no |
| model_ternary_complex | target, e3 | **linker_smiles** |
| score_lysine_ubiquitination | target, e3, structure_paths | no |
| predict_cooperativity | warhead_smiles, linker_smiles, e3_smiles, pose_pdb | **linker_smiles, pose_pdb** |
| **simulate_hook_effect** | **target_conc_nM, e3_conc_nM, alpha** *(added)* | no |
| **predict_degradation** | **smiles, e3, cell_line** *(e3/cell_line added)* | **smiles (CCO)** |
| **predict_cell_context** | **smiles, cell_line** *(cell_line added)* | **smiles (CCO)** |
| predict_admet | smiles | **smiles (CCO)** |
| run_protacpilot_structural | target | no |
| rank_candidates | candidates | no |
| build_candidate_dossier | candidate_id, candidate | no |

**7 of 34** DEMO fixtures carry placeholder/synthetic values — all are
DEMO/TEST-only and are proven unreachable in SCIENTIFIC mode (§6).

---

## 4b. NL parser (G01) — fixed

The request parser had already been moved from the positional regex heuristic to
`protacxtend/nlp/entity_extraction.py`, but two residual bugs remained and are
now fixed:

| Prompt | Before | After |
|---|---|---|
| `what is the structure of 5T35` | target `T35` | target `''` (PDB ID, not a gene) |
| `use PDB 6HAX for the ternary complex` | target `PDB` | target `''` |
| `degrade BRD4 with 5T35 structure` | target `T35` | target `BRD4` |
| `degrade BRD4` | `BRD4` | `BRD4` |
| `Can BRD4 be degraded by VHL?` | `BRD4` | `BRD4` (e3 `VHL`) |

Fix: a PDB-ID guard (`_PDB_ID_RE`, digit-led 4-char identifiers) added to the
excluded spans, a guard skipping digit-preceded tokens, and database/format
tokens (`PDB`, `CIF`, `EMDB`, `DOI`, `UNIPROT`, `CHEMBL`, …) added to stopwords.
Regression tests added to `protacxtend/tests/test_entity_extraction.py`.

---

## 5. Fixtures found & actions

| # | Finding | File | Action |
|---|---|---|---|
| 1 | Legacy `AGENT_TOOL_RUNNERS` with `smiles="CCO"` probe defaults | `runtime/executor.py` | **already emptied** (kept empty, documented) |
| 2 | Hard-coded `synthetic_feasibility_proxy=0.55` (fabricated score) | `tools/linker_generator.py` | **removed** → computed via `linker_scanner.score_synthesis`, provenance added |
| 3 | Silent E3 default to CRBN when no ligand found | `agents/real_nodes.py::_e3` | **removed in SCIENTIFIC** → `E3_LIGAND_UNAVAILABLE`; DEMO keeps labelled fallback |
| 4 | Silent `e3 or "CRBN"`, `cell_line or "default"` coercion | `agentic/registry.py::exec_predict_degradation` | **removed**; e3/cell_line now required in SCIENTIFIC |
| 5 | `simulate_hook_effect` concentration/alpha defaults hidden | `agentic/registry.py` | **now required** in SCIENTIFIC |
| 6 | Probe fixtures with `CCO`/`CCOCCO`/synthetic pose | `runtime/agent_tools.py` | **retained DEMO-only**, blocked in SCIENTIFIC |
| 7 | Demo warhead fallback | `agents/warhead_agent.py` | gated (SCIENTIFIC forbids; test) |
| 8 | Geometry-proxy ternary fallback | `agents/ternary_agent.py` | labelled `method="geometry_proxy"` (surrogate, not fabricated) |
| 9 | Local curated binder fallback | `agents/binder_agent.py` | labelled `source="local_curated"` (curated data, not fixture) |
| 10 | Local curated wrapper status | `tools/protac_component_wrappers.py` | labelled `local_demo_data_only` |
| 11 | `context=default` in an observation string | `agents/context_agent.py` | cosmetic only — **not** used as a scientific input (flagged) |

**Fixtures removed/unmade-scientific:** #2, #3, #4, #5.
**Fixtures retained but isolated to DEMO/TEST:** #1 (empty), #6, #7.

---

## 6. Typed-failure behaviour (required input removed → abstain)

Verified for a battery of tools that removing required input raises
`MissingScientificInput` (code `MISSING_SCIENTIFIC_INPUT`) instead of
substituting: `inspect_smiles`, `predict_degradation`, `predict_admet`,
`predict_cell_context`, `detect_exit_vectors`, `check_synthetic_feasibility`,
`retrieve_pdb`, `model_ternary_complex`, `resolve_target`,
`retrieve_e3_evidence`, `simulate_hook_effect`.

Also verified: `CCO` → `SYNTHETIC_INPUT_FORBIDDEN`; fixture request in
SCIENTIFIC → `FIXTURE_FORBIDDEN`; unknown tool → `TOOL_UNAVAILABLE`;
`real_nodes._e3` with an unknown E3 → `E3_LIGAND_UNAVAILABLE` (no CRBN rewrite).

## 7. Tests

| Test file | Tests | Covers |
|---|---|---|
| `tests/test_p0b_fixture_elimination.py` **(new)** | **29** | origins (6 values), failure codes, exception mapping, classifier precedence, fixture/placeholder labelling, per-tool missing-input abstention, SCIENTIFIC E3 abstention, no fabricated linker score, DEMO-fixture isolation |
| `tests/test_execution_modes.py` (existing) | 19 | mode machinery, warhead demo gating, benchmark runner fixture refusal |
| **Affected suites re-run** | **114 passed** | agent-tool exposure, escalation, scientific outcomes, architecture unification, protacpilot pipeline |

```
pytest tests/test_p0b_fixture_elimination.py tests/test_execution_modes.py -q  → 48 passed
```

---

## 8. BRD4–VHL end-to-end provenance trace

Run: `python scripts/brd4_vhl_provenance_trace.py` (writes
`outputs/reports/brd4_vhl_provenance_trace.{json,md}`).

Dataset: `protacxtend/data/case_study/brd4_vhl_6.csv` (bundled, blinded).

| rank | id | score | recomputed | match | warhead origin | VHL origin | measured |
|---|---|---|---|---|---|---|---|
| 1 | mol1 | 8.0 | 8.0 | ✅ | RETRIEVED | RETRIEVED | MISSING |
| 2 | mol6 | 7.8 | 7.8 | ✅ | RETRIEVED | RETRIEVED | MISSING |
| 3 | mol3 | 6.4 | 6.4 | ✅ | RETRIEVED | RETRIEVED | MISSING |
| 4 | mol5 | 6.2 | 6.2 | ✅ | RETRIEVED | RETRIEVED | MISSING |
| 5 | mol4 | 5.6 | 5.6 | ✅ | RETRIEVED | RETRIEVED | MISSING |
| 6 | mol2 | -3.0 | -3.0 | ✅ | RETRIEVED | RETRIEVED | MISSING |

- **All scores arithmetically traceable:** `base(8.0, COMPUTED) +
  linker_penalty + junction_penalty + vhl_penalty`, each penalty looked up from
  a `RETRIEVED` CSV field (`linker_class`, `warhead_junction`,
  `vhl_ligand_status`).
- **Molecules** come from the CSV (`RETRIEVED`); **RDKit descriptors**
  `COMPUTED`; **score/band** `PREDICTED`.
- **Measured potency:** 0 present / 6 missing (honest — no measured data for
  these molecules in the repository).
- **Fixture/synthetic scientific inputs found: 0.**

> BRD4–VHL is a **prospective case study**, not a benchmark; its ranking is a
> prediction to be locked before any wet-lab outcome. No `NOT_VALIDATED`
> component was relabelled; validated measurements are untouched.

---

## 9. Exact files changed

| File | Change |
|---|---|
| `protacxtend/runtime/modes.py` | `InputOrigin` (6), `FailureCode` (8), exception `.code`/`to_failure`, `classify_input_origin`, `dominant_input_origin`, `is_placeholder_smiles`, `is_synthetic_artifact`; required inputs expanded (predict e3/cell_line, simulate hook) |
| `protacxtend/runtime/agent_tools.py` | per-input + dominant origin, `failure_code`, re-raise typed scientific errors |
| `protacxtend/runtime/executor.py` | origin + failure_code in provenance |
| `protacxtend/agentic/contract.py` | `ToolResult.input_origin`, `ToolResult.failure_code` |
| `protacxtend/agentic/registry.py` | removed `e3 or "CRBN"` / `cell_line or "default"` coercion |
| `protacxtend/schemas/tool_schema.py` | `input_origin`, `failure_code` fields |
| `protacxtend/agents/real_nodes.py` | E3 abstains (`E3_LIGAND_UNAVAILABLE`) in SCIENTIFIC; DEMO fallback labelled |
| `protacxtend/tools/linker_generator.py` | fabricated 0.55 → computed `score_synthesis` + provenance |
| `protacxtend/nlp/entity_extraction.py` | PDB-ID guard + database/format stopwords (G01) |
| `protacxtend/tests/test_entity_extraction.py` | PDB-ID regression test |
| `tests/test_p0b_fixture_elimination.py` | **new** (29 tests) |
| `scripts/brd4_vhl_provenance_trace.py` | **new** provenance tracer |
| `outputs/reports/brd4_vhl_provenance_trace.{json,md}` | generated trace |

## 10. What remains (not done in this change)

This change implements **P0-B (fixtures + modes)** and the first half of the
benchmark-readiness sequence (**NL parser**), and adds no high-level features.
The sequence continues with:

1. **Collapse the duplicate agent stacks** into one canonical orchestrator
   (`agents/graph.py` vs `agentic/`).
2. **Typed schemas:** `EvidenceItem`, `ToolRun`, `RunManifest`,
   `TherapeuticStrategy` (partially present in `results/schema.py`).
3. **Convert 50 benchmark cases** into genuinely scorable gold tasks
   (expected conclusions, accepted alternatives, required evidence/tools,
   provenance, scoring rubrics).
4. **Run PROTACXtend alone** on the 50 tasks; capture every failure into a
   formal failure taxonomy; **do not start the Biomni comparison** until the
   50-task pilot is reproducible and scorable.

_No validated scientific measurement was changed and no `NOT_VALIDATED`
component was relabelled as validated._
