# PROTACXtend External Integration Gate Audit

Audit date: 2026-09-01

Scope:

1. PROTAC-Degradation-Predictor
2. RP-PROTAC
3. Deep-QSP Hook model
4. PROTACFold
5. PROTAC ternary benchmark
6. SynPROTAC
7. DeepPROTACs and PROTAC-INVENT as secondary baselines

## Gate Definitions

| Gate | Meaning |
| --- | --- |
| G1 local checkout | Source code exists under `data/protac_repos/repos/` |
| G2 license/readme | Repo has inspectable license/readme or equivalent provenance |
| G3 env spec | Requirements, environment, Dockerfile, or explicit install plan exists |
| G4 isolated executable | A validated Python/conda/docker executable is present |
| G5 safe smoke/import | A bounded non-training, non-docking smoke check passes |
| G6 reproduction gate | Published example, split, benchmark, or route validity is reproduced |
| G7 production trust | Calibration/license/benchmark gates pass and PROTACXtend can use output for ranking |

## Summary

| Component | G1 | G2 | G3 | G4 | G5 | G6 | G7 | Decision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| PROTAC-Degradation-Predictor | PASS | PASS | PASS | FAIL | FAIL | FAIL | FAIL | Needs env repair/install |
| RP-PROTAC | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | Needs clone/provenance audit |
| Deep-QSP Hook model | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | Needs clone/provenance audit |
| PROTACFold | PASS | PASS | PASS | FAIL | FAIL | FAIL | FAIL | Needs env rebuild and AF3/Boltz gate |
| PROTAC ternary benchmark | PASS | PASS | PARTIAL | FAIL | FAIL | FAIL | FAIL | Needs Rosetta/OpenEye/RDKit gate |
| SynPROTAC | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | FAIL | Needs clone/provenance audit |
| DeepPROTACs | PASS | PASS | PASS | FAIL | FAIL | FAIL | FAIL | Needs legacy env/OpenBabel/torch-geometric gate |
| PROTAC-INVENT | PASS | PASS | PASS | FAIL | FAIL | FAIL | FAIL | Needs Docker/conda review |

## Findings

### PROTAC-Degradation-Predictor

Status: not passed.

What passed:

- Source checkout exists:
  `data/protac_repos/repos/PROTAC-Degradation-Predictor`
- License exists.
- README exists.
- `requirements.txt`, `environment.yml`, and `setup.py` exist.
- Recorded conda env exists at:
  `/home/saveenas/miniconda3/envs/pp/envs/protac-degradation-predictor`
- Python executable exists:
  `/home/saveenas/miniconda3/envs/pp/envs/protac-degradation-predictor/bin/python`

What failed:

- Import smoke failed:
  `ModuleNotFoundError: No module named 'protac_degradation_predictor'`
- Source-path import then failed on dependency:
  `ModuleNotFoundError: No module named 'gdown'`
- Registry marks safe wrapper integration as false.

Required to pass:

```bash
/home/saveenas/miniconda3/envs/pp/envs/protac-degradation-predictor/bin/python -m pip install gdown
cd /storage/saveena/protacpilot/data/protac_repos/repos/PROTAC-Degradation-Predictor
/home/saveenas/miniconda3/envs/pp/envs/protac-degradation-predictor/bin/python -m pip install -e .
```

Then run:

```bash
/home/saveenas/miniconda3/envs/pp/envs/protac-degradation-predictor/bin/python -c "import protac_degradation_predictor; print('ok')"
```

Only after this should PROTACXtend wrap inference or reproduce the published
examples.

### RP-PROTAC

Status: not passed.

What failed:

- No exact local checkout exists at:
  `data/protac_repos/repos/RP-PROTAC`
- No registry row matched exact name.
- No license/readme/env/executable can be audited locally.

Required to pass:

- Identify official repo or artifact source.
- Clone into `data/protac_repos/repos/RP-PROTAC`.
- Record license, weights, data provenance, splits, and calibration method.
- Add env spec and safe smoke/import test.

### Deep-QSP Hook Model

Status: not passed.

What failed:

- No exact local checkout exists at:
  `data/protac_repos/repos/protac_deep_qsp`
- No registry row matched exact name.
- No license/readme/env/executable can be audited locally.

Current mitigation:

- PROTACXtend has a native bounded mechanistic hook simulator:
  `synglue_agent/tools/dose_response_simulator.py`

Required to pass:

- Identify official `protac_deep_qsp` source.
- Clone and audit.
- Reproduce at least one published/synthetic hook-effect curve.
- Compare against PROTACXtend's native simulator.

### PROTACFold

Status: not passed.

What passed:

- Source checkout exists:
  `data/protac_repos/repos/PROTACFold`
- MIT license exists.
- README exists.
- `requirements.txt` exists.
- README describes AF3/Boltz workflows and benchmark/evaluation outputs.

What failed:

- Recorded venv is incomplete:
  `.venvs/protac-protacfold` exists but has no `bin/python`.
- Import smoke cannot run.
- README requires heavy AF3/Boltz/PyMOL/Docker-style setup for meaningful use.

Required to pass:

```bash
python -m venv .venvs/protac-protacfold
.venvs/protac-protacfold/bin/python -m pip install --upgrade pip
.venvs/protac-protacfold/bin/python -m pip install -r data/protac_repos/repos/PROTACFold/requirements.txt
```

Then run a non-heavy utility import check:

```bash
PYTHONPATH=data/protac_repos/repos/PROTACFold \
.venvs/protac-protacfold/bin/python -c "import utils.evaluation; print('ok')"
```

Production use still requires AF3/Boltz license/compute/confidence calibration.

### PROTAC Ternary Benchmark

Status: not passed.

What passed:

- Source checkout exists:
  `data/protac_repos/repos/PROTAC_ternary`
- License exists.
- README exists.
- Python scripts exist:
  `ternary_model_prediction.py`, `ppi_ternary_scores.py`,
  `ppi_skeleton_median.py`, `ffc_calculator.py`

What failed:

- No isolated Python executable is recorded.
- README requires Rosetta, OpenEye, and RDKit for the full benchmark path.
- No safe reproduction command has been validated.

Required to pass:

- Create isolated env.
- Confirm license availability for Rosetta/OpenEye or define an open-only subset.
- Add a small example fixture and safe scoring script.
- Reproduce expected FFC/interface-score calculation.

### SynPROTAC

Status: not passed.

What failed:

- No exact local checkout exists at:
  `data/protac_repos/repos/SynPROTAC`
- No registry row matched exact name.
- No license/readme/env/executable can be audited locally.

Required to pass:

- Identify official SynPROTAC repository/artifacts.
- Clone and audit license.
- Add environment spec.
- Reproduce BRD4 example or route-validity example.

### DeepPROTACs

Status: not passed.

What passed:

- Source checkout exists:
  `data/protac_repos/repos/DeepPROTACs`
- License exists.
- README exists.
- `env.yaml` exists.
- Single-prediction script exists.

What failed:

- No isolated executable is recorded.
- README requires legacy environment, OpenBabel, PyTorch, torch-geometric, and
  prepared mol2 pocket/ligand/linker inputs.

Required to pass:

- Build isolated conda env from `env.yaml`.
- Validate OpenBabel.
- Run toy/case-study input if available.
- Only then expose as optional comparator.

### PROTAC-INVENT

Status: not passed.

What passed:

- Source checkout exists:
  `data/protac_repos/repos/Protac-invent`
- License exists.
- README exists.
- Dockerfile exists.

What failed:

- No reviewed Docker/conda runtime is available.
- README indicates custom REINVENT dependencies.

Required to pass:

- Review Dockerfile and dependency provenance.
- Build isolated container.
- Reproduce example generation.
- Compare generated linker validity/novelty/runtime against PROTACXtend.

## Current Gate Decision

No external component currently passes all gates G1-G7.

Current production-safe state:

- External components can be listed, audited, and smoke-job recorded.
- Their outputs are not trusted for ranking.
- PROTACXtend-native bounded modules are safe to run:
  - dose-response simulation
  - structure/ubiquitination geometry scoring from supplied poses
  - cooperativity potential from supplied poses
  - proteome context seed scoring
  - active-learning batch recommendation

## Next Build Step

Repair the first external component:

1. Fix PROTAC-Degradation-Predictor env/package import.
2. Add a non-training inference/example smoke test.
3. Store pass/fail JSON under `outputs/external_integrations/`.
4. Only then promote its adapter from `registered_status_only` to
   `smoke_passed`.

