# Current state — PROTAC/TPD agent benchmark

Date: 2026-10-03 · Repo: `/storage/saveena/protacxtend` · Branch: `sprint-2`
Author: benchmark execution pass (research software engineer)

All counts below were measured on disk during this pass. The supplied strategy
contained historical counts and competitor statistics; those were treated as
**unverified starting information** and reconciled against the repository.

## 1. Repository / git

- `git rev-parse HEAD` = the current `sprint-2` tip at run time (recorded in every
  Gate-C `manifest.json`).
- Working tree carried pre-existing modifications from unrelated work; they were
  preserved (no reset, no overwrite). This pass added only the files listed in §7.
- No `AGENTS.md` exists in the repository (searched to depth 3, excluding `.git`
  and `node_modules`).

## 2. Task / gold inventory (measured)

| Asset | Count | Evidence |
|---|---:|---|
| Governed benchmark cases | **48** | `benchmark/cases/*.json` (50 files incl. 2 non-case) |
| `gold_answers_v1.jsonl` records | 48 | `wc -l gold_answers_v1.jsonl` |
| Gate-C case inventory | 48 (`n_expert_review=29`) | `benchmark/gateC/CASE_INVENTORY.json` |
| Independently **reviewed/adjudicated** answers | **0** | `benchmark/gateC/gold_review.tsv` → 48× `PENDING_ADJUDICATION` |
| Reviewer-decision rows (29 flagged) | 29 pending | `benchmark/gateC/REVIEWER_DECISIONS.tsv` |
| Eligible `consensus.json` gold entries | **0** | `reviewed_gold/consensus.json` `approved=false`, `gold={}` |
| Gate-C pilot cases | 4 | `benchmark/gateC/pilot/*.json` |

## 3. Source-backed chemistry (measured)

| Asset | Count | Evidence |
|---|---:|---|
| Verified component records | 9 | `protacxtend/data/verified_components.json` |
| Source PROTAC references (with DOI/PDB) | **3** | MZ1 (BRD4–VHL, 10.1021/acschembio.5b00216, PDB 5T35); dBET1 (BRD4–CRBN, 10.1126/science.aab1433); MT-802 (BTK–CRBN, 10.1016/j.bmcl.2019.126877) |
| Verified (target, E3) paths | 3 | `verified_components.verified_paths()` |
| Curated demo warheads/E3/linkers | 6 / 95 / ~ | `curated_warheads.csv`, `curated_e3_ligands.csv` (mostly `local_demo_*` → correctly rejected by the identity gate) |

## 4. Tool / capability registry (measured)

| Metric | Count |
|---|---:|
| Excel toolkit registry rows | 296 (tools 123 · databases 49 · packages 43 · skills 26 · modules 37 · modalities 18) |
| Code tool registry | 115 |
| Tools `installed` on this host | **44 / 115** |
| LLM-callable agent tools (`TOOL_SPECS`) | 44 (ready) |
| Scientific backends | 46 (21 permissive OSS · 13 commercial · 9 web · 2 academic-only) |
| Capability readiness | 27 capabilities: 23 ready · 2 installable · 2 web-only |

Separated capability states are preserved: **registered ≠ importable ≠ callable ≠
successfully executed**. (See `TOOL_AND_TUI_STATUS.md`; the registry-status
0/0 bug was fixed this pass.)

## 5. Comparison systems (measured before this pass)

`tpdeval/adapters.py::integration_status()` reported:

| Slot | System | State before |
|---|---|---|
| A | PROTACXtend | EXECUTABLE |
| B | Biomni | wired but native-only (blocker) |
| C | TPD-specific-agent | MISSING |
| D | General-LLM | EXECUTABLE |
| E | Retrieval-only | MISSING |
| F | Tool-only-scripted | MISSING |
| G | LLM+PROTACXtend-tools | MISSING |
| H | PROTACXtend-planner+generic-tools | MISSING |

Mapping used for this pass (declared): **S1→E, S2→F/G, S3→A, S4→B**.

## 6. Discrepancies found and reconciled

1. **Synthetic agreement artifact (hazard).** `reviewed_gold/kappa_report.json`
   claimed `verdict_distribution_{a,b} = {approve: 48}`, `cohens_kappa=1.0` while
   both reviewer workbooks were **empty** (0 filled verdicts) and
   `gold_review.tsv` was 48× `PENDING_ADJUDICATION`. This was a stale pipeline-test
   artifact. It was regenerated honestly (`n_filled_both=0`, kappa `null`) and
   `consensus.json` was re-merged from the real (empty) sheets → `approved=false`,
   `gold={}`. **No synthetic ratings were used as gold.**
2. **Source-backed design was not wired into `/design`.** The deterministic
   `CAPABILITY_NODES["DESIGN"]` omitted `design_path`, so the route generated only
   demo components (identity gate 0/144). With `design_path` added, the run
   assembles the source-backed **MZ1** reference (identity 30/30 pass, 30
   degradation predictions). Reproduced discrepancy → fixed; see §7.
3. **Linker/registry bugs** (fixed earlier this session): `summarize_toolkit_status`
   0/0; double ADMET-AI subprocess causing a 20 s linker-budget stall.
4. Counts in the strategy (e.g., "1000-task cohort", "48 reviewed") do **not**
   match disk: 1000 items are uncurated templates; 0/48 are reviewed.

## 7. What this pass changed (implementation)

- `protacxtend/agents/graph.py` — added `design_path` to `CAPABILITY_NODES["DESIGN"]`.
- `benchmark_runner/live_systems.py` — **new** S1 (`LLM+RAG`), S2 (`LLM+flat-tools`),
  S4 (`Biomni`) live adapters on the existing contract.
- `scripts/biomni_run.py` — **new** official-Biomni subprocess runner.
- `scripts/gateC_four_system.py` — **new** four-system Gate-C runner (immutable raw,
  typed outcomes, cost/latency, resume, no-overwrite).
- `outputs/execution/design_evidence/` — source-backed assembly evidence.
- Gold tooling: regenerated honest `kappa_report.json` + `consensus.json`.

## 8. Capability-state separation (this run)

- Registered: 296 rows. Importable: 46 backends. Callable/installed: 44 tool
  records. **Successfully executed this pass**: S1/S2/S3/S4 on 4 Gate-C cases
  (16 runs). Correctness of those executions: **NOT SCORED** (gold pending).

## 9. Unresolved / blocked

- Independent gold review (0/48) — human task; blocks all adjudicated accuracy.
- S2 tool execution: several flat-tool calls returned empty/failed observations in
  SCIENTIFIC mode; recorded, not hidden.
- S4 (Biomni) cost is **not reported** by the installed adapter → recorded as
  unavailable rather than $0 in the report narrative.
- Resources not matched for Biomni (native tools/data lake vs S1–S3); declared.
