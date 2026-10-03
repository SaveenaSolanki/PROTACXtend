# Source-backed design — corrected result (supersedes the "30 MZ1" claim)

Date: 2026-10-03 · run `design_sourcebacked_v2` · evidence
`outputs/workflows/design/design_sourcebacked_v2/candidate_evidence.json`

## Correction

The earlier report described "30 identity-passing **MZ1** assemblies". Re-verification
against the run artifacts shows:

| claim | verified actual |
|---|---|
| reference = MZ1 | **dBET1** (BRD4–CRBN, DOI `10.1126/science.aab1433`) — the request was "CRBN-recruiting PROTAC for BRD4" |
| candidate id | was hard-coded `SGA-VERIFIED-MZ1` → **fixed** to derive from the reference (`SGA-VERIFIED-dBET1`) |
| 30 records | 30 raw records in the `design_5ba22e5d9d` run; **13 unique constitutional graphs** |
| "30 validated PROTACs" | **one reconstruction control** with stereoisomer variants — not 30 distinct molecules |

`outputs/execution/design_evidence/source_backed_components.json` recorded MZ1
(BRD4–VHL): that was the probe example, **not** the run's reference. It is relabelled by
the provenance in the design evidence.

## Corrected counts (run `design_sourcebacked_v2`)

```
raw_records: 28
unique_isomeric: 28
unique_constitutional: 13
identity_pass: 28
verified reference: dBET1 (BRD4-CRBN; DOI 10.1126/science.aab1433)
```

Reproduce: `python scripts/audit_unique_structures.py <candidate_evidence.json>`.
Normalization policy: **stereochemistry-aware** — RDKit `MolToSmiles(isomericSmiles=True)`
for the isomeric count and `isomericSmiles=False` for the constitutional count. Both are
reported; neither alone is called "novel molecules".

## What the result establishes / does not

**Establishes:** the pipeline can reconstruct a literature PROTAC from
source-backed warhead + E3-ligand + linker components with atom-mapped attachment
sites; the fail-closed identity gate passes for a genuine source (dBET1) and rejects
placeholder provenance (`tests/test_source_backed_design_and_adapters.py`).

**Does NOT establish:** 30 novel designs; ternary geometry; synthetic feasibility;
degradation activity; experimental DC50 (predictions are computational only);
generalization beyond the 3 documented references (MZ1, dBET1, MT-802). The
`ternary_coordinates` and `synthesis_route` gates remain `unevaluated`.

## Controls

- **Valid control:** dBET1 reconstruction — identity gate PASS (28/28).
- **Invalid control:** placeholder `local_demo_*` provenance — identity gate FAIL
  (`test_placeholder_provenance_fails_identity_gate`). The gate is not bypassed.
- A second independent control is **not added** because no fourth component set with
  documented attachment sites was available; broader generalization remains untested.
