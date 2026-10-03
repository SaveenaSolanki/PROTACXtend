# Reproduce — exact commands executed

Environment: `conda base` (`saveenas@iiitd`), repo `/storage/saveena/protacxtend`.
Execution mode `scientific`. Live model credentials come from the pi harness auth
(`/home/saveenas/.pi/agent/auth.json`, provider `deepseek`) — never printed or committed.

## 1. Verify prerequisites

```bash
cd /storage/saveena/protacxtend
python -m pytest protacxtend/tests/test_toolkit_status.py -q          # toolkit status fix
python -c "from benchmark_runner.live import api_chat; print(api_chat('t','say PONG')['content'][:8])"
/tmp/biomni_venv/bin/python -c "import biomni; print(biomni.__version__)"   # 0.0.8
```

## 2. Freeze a run (write the manifest)

```bash
python - <<'PY'   # regenerates study/freeze_manifest.json
# see outputs/execution/current_state.md §7 for the generator used
PY
```

## 3. Gate-C four-system pilot (16 intended runs, resumable, no overwrite)

```bash
# dry selection / fresh run (new run_id; refuses to overwrite an existing dir)
python scripts/gateC_four_system.py --systems S1,S2,S3,S4 --online --run-id gateC_4sys_v1

# resume an interrupted run (skips completed case/system/rep)
python scripts/gateC_four_system.py --systems S1,S2,S3,S4 --online \
  --resume benchmark_results/gateC_four_system/gateC_4sys_v1

# subset (e.g. only the TPD agent)
python scripts/gateC_four_system.py --systems S3 --online --resume <run_dir>
```

Outputs: `task_level_results.parquet`, `task_level_results.csv`, `summary.json`,
`REPORT.md`, `raw/*.json`, `traces/*.json`, `manifest.json`.

## 4. Source-backed design control (verifies the identity gate)

```bash
python - <<'PY'
from protacxtend.tools import verified_components as vc
from protacxtend.tools.protac_toolbox import ProtacDesignToolbox
from protacxtend.identity_gate import (source_record_from_verified_component,
                                       CandidateIdentityAndAssemblyGate)
ref = vc.reference_components("BRD4", "VHL")          # -> MZ1 (DOI 10.1021/acschembio.5b00216)
box = ProtacDesignToolbox()
full, msg = box.assemble_components(ref['warhead']['smiles'], ref['linker']['smiles'],
                                    ref['e3_ligand']['smiles'])
print("assembled:", bool(full), msg)
PY
```

## 5. Gold-review pipeline (human review pending; no gold manufactured)

```bash
python scripts/gold_adjudication.py status
python scripts/gold_adjudication.py kappa \
  benchmark/gateC/reviewed_gold/reviewer_1.csv \
  benchmark/gateC/reviewed_gold/reviewer_2.csv      # -> null while unfilled
python scripts/gold_adjudication.py validate benchmark/gateC/reviewed_gold/reviewer_1.csv
python scripts/gold_adjudication.py merge --dir benchmark/gateC/reviewed_gold
```

## 6. Larger 30×4×3 pilot (BLOCKED — do not run yet)

```bash
# Requires: >=1 eligible adjudicated gold gate + S2 completeness + budget cap.
python scripts/gateC_four_system.py --systems S1,S2,S3,S4 --online \
  --replicates 3 --run-id pilot_30x4x3   # populate cases first via the frozen manifest
```

**Missing prerequisites** (must be satisfied first): (a) independent gold review
(0/48 today); (b) S2 tool observations must succeed under SCIENTIFIC mode;
(c) declared budget cap and resource-matched S4 condition. Until then the 30-question
pilot and the 3,600-run primary study must not be launched.
