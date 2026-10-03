# Gate C — independent gold & preregistration (status)

Date: 2026-09-23 · branch `sprint-2` · F-14 commit `82a0e4d`

This folder records the **audit-side** Gate C work. The benchmark artifacts
themselves live under `benchmark/gateC/` and are hash-frozen in
`benchmark/gateC/provenance_manifest.json`.

## What was done

1. **F-14 closed.** `protacpilot-memory/` → `protacxtend-memory/` committed as a
   rename (`82a0e4d`). All 104 tracked files verified byte-identical at the new
   path before commit; 338 on-disk files hashed in
   `F14_memory_provenance.json`. No memory data deleted. Generated
   `evaluation/`, `paper/`, `benchmarks/results/` re-ignored under the new
   prefix so git hygiene matches the old tree.
2. **48-case inventory** — `benchmark/gateC/CASE_INVENTORY.json`.
3. **Two × 500-task template inventory** —
   `benchmark/gateC/TEMPLATE500_INVENTORY.json`.
4. **Draft evidence packages + rubrics (48 each)** —
   `benchmark/gateC/evidence_packages/`, `benchmark/gateC/rubrics/`. Drafted
   without reading the self-derived `benchmark/scoring/*.json` overlays; every
   item is `pending_independent_review`.
5. **29 reviewer decisions** — `benchmark/gateC/REVIEWER_DECISIONS.tsv`
   (all `PENDING`).
6. **Frozen manifests** — `benchmark/gateC/splits.json`,
   `benchmark/gateC/provenance_manifest.json`,
   `benchmark/gateC/tool_registry_snapshot.json`,
   `benchmark/pre_registration.md`, `benchmark/gold_review.tsv`.
7. **Four question-matched pilot cases** — `benchmark/gateC/pilot/`, runnable
   with `scripts/gateC_pilot.py`.

## What is explicitly *not* done

* No benchmark score is reported.
* Gold is **0/48** adjudicated.
* All 29 reviewer decisions are **PENDING**; no reviewer has been assigned.
* The self-derived `0.885` remains an infrastructure smoke value only.
* The four pilot cases may be *executed* to inspect traces, but their scientific
  conclusions are `PENDING_INDEPENDENT_REVIEW`.

## Reproduce

```bash
python benchmark/gateC/build_gate_c.py            # rebuild + re-freeze
python benchmark/gateC/build_gate_c.py --check    # verify frozen hashes
PROTACXTEND_EXECUTION_MODE=scientific \
  python scripts/gateC_pilot.py --out-dir benchmark_results/gateC_pilot
```
