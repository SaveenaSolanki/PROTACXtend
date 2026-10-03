# Next-phase blockers — evidence-based audit

Date: 2026-10-03 · Repo `sprint-2` · Commit checked: `6780a40` (plus uncommitted fixes in
this pass). Each item lists the evidence path and the actual state. Claims from the
supplied report were treated as starting information and re-verified.

## B1 — S2 observations (PARTIALLY RESOLVED)

**Claim:** "S2 partial tool matching; some SCIENTIFIC-mode observations empty/failed."

**Verified evidence** (`benchmark_results/gateC_four_system/gateC_4sys_v1/raw/S2_*.json`):
- 4 tool calls total across 4 cases: 3 `ok`, 1 `error` (bad param name `name` instead of
  `target_name` on the first attempt — a legitimate argument-validation outcome).
- `DISCOVER-08` made **0 tool calls** (answered from memory).
- The old `_trim()` dropped `provenance`, `evidence`, `artifacts`, `tool_runs` from the
  observation delivered to the model.

**Cause:** (a) observation serializer discarded provenance/evidence; (b) the flat-tool
prompt listed tool names without their parameter schemas, inviting wrong arguments;
(c) no requirement to actually exercise a tool.

**Fix applied this pass** (`benchmark_runner/live_systems.py`):
- `_trim()` now returns `status`, `summary`, `has_data`, `data`, `provenance`, `evidence`,
  `tools`, `artifacts`, `warnings`, `errors` — source fields preserved.
- Catalog prompt prints parameter names; declared permitted resources are included.
- `MIN_TOOL_CALLS=1`: the flat arm must call one domain tool or is re-prompted.
- Meta tools excluded from the catalog (domain-tool parity).
- Distinct outcomes: `ok+has_data` vs `ok+empty` vs typed failure vs error.

**Result (real calls):** all four cases now execute a domain tool with `has_data=True`
and provenance retained. Parity table: `s2_s3_parity.md` (40 common domain tools, all
with executors). **Remaining limitation:** relevance — the model currently selects
`resolve_target` first on every case. Declared, not hidden.

## B2 — S3 abstentions (DIAGNOSED)

| task | provided inputs (actual) | required by policy | routing | gate / code | classification |
|---|---|---|---|---|---|
| REASON-02 | `pair: BRD4 BD2 + VHL`, `linker: PEG3 (MZ1-like)` | `warhead_smiles, linker_smiles, e3_smiles, pose_pdb` for `predict_cooperativity` | REASON → `predict_cooperativity` | `MissingScientificInput` | **Deliberate policy — appropriate** (matches declared `typed_abstention_MISSING_SCIENTIFIC_INPUT`) |
| DESIGN-12 | parent warhead SMILES + principle only | an E3 ligand (a PROTAC needs an E3 half) | DESIGN → clarification before graph | `clarification_required` | **Case under-specified — abstention appropriate**; the pilot's `expected_behavior` (linker hypotheses) does not match the as-authored inputs |
| DISCOVER-08 | placeholder text `"candidates with per-candidate assay cost and predicted value band"` (**no numbers/list**) | concrete candidate list + costs | DISCOVER → clarification | `clarification_required` | **Case under-specified — abstention appropriate** |

**Conclusion.** No evidence of a routing defect that avoids an answerable case: in all
three, the information required by the task's own capability was absent from
`supplied_inputs`. The earlier report's framing ("S3 abstained on 3/4") is true but
ambiguous; two of the three are **input deficits in the pilot cases**, not agent defects.
Fix applied: paired development checks (below). No scientific gate was weakened.

## B3 — MZ1 result (CLAIM CORRECTED)

**Claim:** "30 identity-passing MZ1 assemblies."

**Verified evidence** (`outputs/execution/design_evidence/candidate_evidence.json`):
- 30 raw records. **30 unique isomeric SMILES but only 13 unique constitutional graphs**
  (stereochemistry-stripped) → the set is stereoisomer/duplicate variants, **not 30
  distinct molecules**.
- 28/30 records are sourced from **dBET1** (BRD4–CRBN; DOI `10.1126/science.aab1433`),
  not MZ1. The `candidate_id` `SGA-VERIFIED-MZ1` is **hard-coded** in
  `design_path_agent.py` and mislabels the assembling reference.
- `outputs/execution/design_evidence/source_backed_components.json` recorded MZ1
  (BRD4–VHL) — that was the *probe example*, not the run's reference. **The earlier
  report's "MZ1" attribution was inaccurate.**

**Fix:** corrected candidate id derivation + unique-structure reporting (below).

## B4 — Gold integrity (RESOLVED for the hazard)

- `reviewed_gold/kappa_report.json` had claimed `48×approve`, κ=1.0 with 0 filled
  verdicts → regenerated honestly (`n_filled_both=0`, κ=`null`); `consensus.json`
  re-merged → `approved=false`, `gold={}`.
- No table/metric/report in this repository was found to consume that stale kappa as a
  result; the only consumer is the adjudication status flow (now honest).
- Synthetic fixtures cannot approve gold because `cmd_merge` requires two distinct
  reviewer names + one adjudicator and ≥1 resolved entry; empty sheets yield
  `approved=false`.

## B5 — Telemetry

- S1/S2/S3 report tokens + estimated cost (DeepSeek published rates).
- **S4 (Biomni) cost/tokens are not returned by the installed adapter** → recorded as
  unavailable, never zero-filled. Investigated below.

## Blockers for the 360-run pilot (status)

| prerequisite | status |
|---|---|
| Eligible independently-adjudicated gold | **BLOCKED (human)** — 0/48 |
| S2 tool execution usable | **PASS** (this pass) |
| S3 abstention explained | **PASS** (this pass) |
| Source-backed design correctly labelled | **PASS** (after B3 fix) |
| Telemetry complete | **PASS with declared gap** (S4 cost unavailable) |
| New freeze | **PASS** (new manifest) |
| Resource-matched comparison design | **PARTIAL** — S4 native-only, declared |
