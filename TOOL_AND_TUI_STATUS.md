# PROTACXtend — Toolkit, Database & TUI Status (evidence-backed)

Generated: 2026-09-30 · Repo: `/storage/saveena/protacxtend`
Scope: **what the registry actually contains**, **what is installed on this host**, and the
**TUI surface** — every number below is read from code/CSV on disk, not from prose docs.

> This file is the human-readable companion to the machine truth in
> `analysis/inventory/*.csv`. Where a number is a *catalogue* count it is labelled
> **registered**; where it is a *live* count it is labelled **available/installed**.

---

## 1. Registry inventory (`Agent_Toolkit.xlsx`)

Source of truth: `protacxtend/data/toolkit/Agent_Toolkit.xlsx` via
`protacxtend.toolkit.registry.summarize_registry()`.

| Section | Sheet | Registered rows |
|---|---|---:|
| Modalities | `Modalities` | 18 |
| **Tools** | `Tools_Expanded` | **123** |
| **Databases** | `Databases_Expanded` | **49** |
| Packages | `Packages` | 43 |
| Skills | `Skills` | 26 |
| Agent modules | `Agent_Modules` | 37 |
| **Total** | | **296** |

There is a **second, code-level tool registry** used for install detection:

| Registry | File | Count |
|---|---|---:|
| Excel toolkit tools | `Agent_Toolkit.xlsx` (`Tools_Expanded`) | 123 |
| Python operational tools | `protacxtend/tools/toolkit_registry.py` (`_tool(...)`) | 115 |
| LLM-callable agent tools | `protacxtend/agentic/registry.py` (`TOOL_SPECS`) | 44 |
| Self-describing records | `protacxtend/tools/tool_registry.py` (`RegistryTool`) | 11 |
| Strict LLM allowlist | `protacxtend/llm/tool_registry.py` (`ALLOWED_TOOLS`) | 13 |

`123` vs `115`: the Excel sheet contains 11 PROTACXtend-internal/wrapper rows
(`P4ward`, `ProtacPilot ADMET Predictors`, `ProtacPilot Degradation Predictor`,
`ProtacPilot Docking Pipeline`, `ProtacPilot Linker Scanner`,
`ProtacPilot Online Ligand Miner`, `ProtacPilot P4ward Wrapper`,
`ProtacPilot Stereochemistry Engine`, `ProtacPilot Ternary Feasibility Proxy`,
`ProtacPilot TimeStep Prototype`, `Schrödinger LigPrep`) plus a few name variants.
112/123 Excel tool names match a Python-registry name.

---

## 2. Tool availability on this host (live)

Source of truth: `analysis/inventory/toolkit_status_all.csv` (115 tools), produced by
`protacxtend/tools/tool_status.py::detect_all_tool_statuses()` — a cross-environment
probe (current interpreter, `protacpilot` conda env, `PROTACXTEND_TOOLKIT_ENVS`, `PATH`).

| Status | Count |
|---|---:|
| ✅ `installed` | **44** |
| `binary_missing` | 19 |
| `web_only` | 18 |
| `commercial_not_available` | 13 |
| `dependency_present_repo_required` | 12 |
| `python_package_missing` | 8 |
| `registered_but_not_executable` | 1 |
| **Total** | **115** |

By provisioning channel: `pip 23 · conda 24 · repo 21 · binary 18 · web 13 · commercial 13 · api 2 · metadata 1`.

By scientific category (top): `ligand_docking 14 · protein_protein_docking 11 ·
molecular_dynamics 7 · admet_toxicity 7 · molecular_visualization 6 · molecular_ml 6 ·
ligand_preparation 5 · de_novo_generation 5 · retrosynthesis 5 · literature_mining 5 …`

### 2.1 Registry-status summary (after fix — see §5)

`protacxtend.toolkit.summarize_toolkit_status()`:

| | Registered | Available | Executable |
|---|---:|---:|---:|
| Modalities | 18 | 0 | 0 |
| **Tools** | **123** | **42** | **42** |
| Databases | 49 | 7 | 4 |
| Packages | 43 | 20 | 1 |
| Skills | 26 | 0 | 1 |
| Agent modules | 37 | 0 | 0 |
| **Total** | **296** | **72** | **51** |

The tools section is 42 (not 44) because 2 of the 44 installed Python-registry tools
are not represented under a matching `Tools_Expanded` name.

---

## 3. Databases (live)

Source of truth: `analysis/inventory/Databases.csv` (49 rows) + `Databases_Expanded`.

| Metric | Count |
|---|---:|
| Registered databases | **49** |
| With a public API | **30** |
| API currently reachable | 21 |
| Local copy available | 4 |
| Requires API key | 7 |
| Requires license | 3 |

Live status: `api_live 21 · registered_but_unavailable 16 · restricted_api 7 ·
download_local 4 · restricted_download 1`.

By domain: `ppi_e3 8 · clinical_genomics 7 · protac_glue 6 · target_biology 6 ·
vendor_libraries 6 · literature_patent 6 · structure 5 · compound_bioactivity 5`.

> **49 databases is a catalogue count, not 49 live connections.** Only 4/49 have a local
> copy; 16 are registered-but-unavailable; 9 are key-gated (DrugBank, MolPort, eMolecules,
> SureChEMBL, Lens, Semantic Scholar, COSMIC, OMIM, DisGeNET).

---

## 4. TUI surface

Two terminal UIs share one JSONL bridge.

| Component | Path | Stack | Size |
|---|---|---|---:|
| Node/TypeScript TUI (default) | `tui/` | Node ≥18, no runtime deps | 3,534 LOC (`tui/src/*.ts`) |
| Python Textual TUI (`py-tui`) | `protacxtend/tui/` | Textual | `app.py` 669 + `engine.py` 168 |
| Shared bridge | `protacxtend/tui_bridge/` | Python | 3,765 LOC (`server.py` 1,465) |

- **46 slash commands** in the Node TUI (`tui/src/commands.ts`), including
  `/design /investigate /reason /evidence /compare /plan /ask /explain /doctor /status /models /databases /skills /workflows /report …`
- Bridge intent types: `KNOW · REASON · DESIGN · DISCOVER · UNKNOWN`.
- Agent graph: **30 unique nodes**; per-capability depth `KNOW 11 · REASON 15 · DESIGN 28 · DISCOVER 16`.
- Tests (run 2026-09-30): Node `cd tui && npm test` → **65 passed / 0 failed**;
  Python `pytest tests/test_tui_slice_routing.py tests/test_protacxtend_tui.py tests/test_tui_response_contract.py tests/test_tui_semantic_repair.py` → **49 passed / 1 failed** (see §6).

---

## 5. Fix 1 — `summarize_toolkit_status()` reported 0/0 (RESOLVED)

**Symptom.** `protacxtend.toolkit.registry` (the legacy scaffold module) returned a
hard-coded `available: 0, executable: 0` for all 296 rows, even though 44 tools are
installed. `protacxtend/tools/tool_registry.py` imported `get_tool_status` from that
module, so the agent-facing tool registry saw everything as unavailable.

**Root cause.** Two functions named `summarize_toolkit_status`/`get_tool_status` existed:
a stale Phase-1 pair in `toolkit/registry.py` (constant 0/0) and the real Phase-2
detectors in `toolkit/status.py`. Callers importing from `.registry` got the constant.

**Fix.**
- `toolkit/registry.py` now **delegates** `get_tool_status` / `summarize_toolkit_status`
  to `toolkit/status.py` (lazy import to avoid the circular import).
- `toolkit/status.py` now consults the authoritative cross-environment detector
  (`tools/tool_status.py::detect_all_tool_statuses`) by tool name, so installed binaries
  and packages in *other* conda envs are counted; it also emits a `status_detail` field.
- `tools/tool_registry.py` and `tools/protac_toolbox.py` now import from
  `protacxtend.toolkit.status` directly.
- Regression test added: `tests` → `protacxtend/tests/test_toolkit_status.py::test_registry_shim_reports_real_availability`.

**Result.** `0/0` → **`72 available / 51 executable`** (tools section `42/42`).
Evidence: `python -c "from protacxtend.toolkit.registry import summarize_toolkit_status as s; print(s())"`.

---

## 6. Fix 2 — `LinkerGenerationAgent` deadline regression (RESOLVED for candidate assembly)

**Symptom.** `/design Design a CRBN-recruiting PROTAC for BRD4` produced
`assembly_counts = {assembled: 0, valid: 0}` and verdict `ABSTAINED`, with reason
`LinkerGenerationAgent: linker generation exceeded the run deadline`.

**Root cause.** The linker panel ran the **isolated ADMET-AI venv subprocess twice**:
once inside `generate_generative_linkers` (candidate selection) and again inside
`rank_linkers` (Link-INVENT ranking). Each subprocess pays a ~10–11 s torch import, so the
panel took **~21–22 s** against the agent's hard **20 s** budget in
`protacxtend/agents/linker_agent.py` → typed deadline abstention.

Measured before the fix:
```
generate_generative_linkers   ~11.6 s
rank_linkers (batch ADMET)     ~10.3 s
full panel                     ~21.4 s      (budget = 20 s)
```
Measured after the fix:
```
full panel                     ~11–13 s     (budget = 20 s)
```

**Fix.**
- `tools/admet_integration.py::_run_admet_ai` now memoises identical batches in-process
  (`_ADMET_RESULT_CACHE`).
- `tools/generative_linker.py`: `generate(..., use_admet=True)` and
  `generate_generative_linkers(..., use_admet=True)`; the generative ADMET pass is skipped
  when the downstream Link-INVENT ranking will apply ADMET anyway.
- `tools/protac_toolbox.py::generate_linkers` passes `use_admet=not scoring_on`, so only
  the meaningful Link-INVENT ADMET pass runs.
- `tools/protac_toolbox.py::generate_rule_based_linkers` now tolerates `linker_types=None`.

**Result (real offline design run `outputs/workflows/design/design_5ba22e5d9d/`):**
```
linker_generation : executed  · 15 linkers
construction      : executed  · 153 assembled
validation        : executed  · 144 valid
```

### 6.1 Remaining, distinct issue — degradation gate is honestly `not_assessable`

The same run shows:
```
degradation_prediction : not_available · 0 predictions
identity gate passed   : 0 / 144 candidates
```
The design request uses **demo-provenance** components (`BRD4_demo_*`,
`CRBN_demo_lenalidomide_like`, `source=local_demo_*`). The fail-closed identity gate
(`protacxtend/identity_gate.py`) requires exact source-backed warhead + E3 binding evidence,
so all 144 candidates fail `source_backed_target_binder` / `source_backed_e3_ligand`;
`predict_degradation()` then returns `[]` by construction
(`gated_candidates = [c for c in candidates if candidate_passes_identity_gate(c)]`).
This is the documented P0-B integrity policy (`CAPABILITY_DOSSIER.md`: “0 verified warhead
provenance”), **not** a linker bug.

Consequence: `tests/test_tui_slice_routing.py::test_execute_design_runs_existing_engine_with_honest_gates`
still fails on `assert gates["degradation"]["status"] == "predicted"` (actual
`not_assessable`). The assertion predates the fail-closed identity gate and is
**contradicted by the integrity policy** — a decision is required:

- **(i)** update the assertion to the honest `not_assessable` for the demo-provenance path, or
- **(ii)** make offline design assemble from *source-backed* warheads/E3 ligands so the
  gate can pass and degradation can run.

---

## 7. Evidence file index

| Claim | Evidence |
|---|---|
| Registry counts (296) | `protacxtend/data/toolkit/Agent_Toolkit.xlsx`; `protacxtend.toolkit.registry.summarize_registry()` |
| 44/115 installed | `analysis/inventory/toolkit_status_all.csv`, `toolkit_installed.csv`, `toolkit_remaining.csv` |
| Headline metrics | `analysis/inventory/Summary.csv` |
| Databases (49) | `analysis/inventory/Databases.csv` |
| Repo tools (29) | `analysis/inventory/repo_tool_channel.csv` |
| Status fix | `protacxtend/toolkit/{registry,status}.py`, `protacxtend/tools/tool_registry.py`, `protacxtend/tests/test_toolkit_status.py` |
| Linker fix | `protacxtend/tools/{admet_integration,generative_linker,protac_toolbox}.py`, `protacxtend/agents/linker_agent.py` |
| Real design run | `outputs/workflows/design/design_5ba22e5d9d/{stage_timeline.json,candidate_evidence.json}` |
| TUI | `tui/`, `protacxtend/tui/`, `protacxtend/tui_bridge/`, `tui_dev/PLAN.md`, `tui_dev/outputs/CAPABILITY_DOSSIER.md` |

## 8. Regenerate

```bash
python analysis/generate_inventory.py          # inventory CSVs + plots
protacxtend toolkit --action truth             # TOOLKIT_TRUTH.md + XLSX
python -c "from protacxtend.toolkit import summarize_toolkit_status as s; print(s())"
cd tui && npm test
```
