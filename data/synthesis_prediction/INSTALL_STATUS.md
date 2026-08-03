# Chemical Synthesis Prediction Setup Status

## Installed / Cloned

- `syngenta/linchemin`
  - Local repo: `data/synthesis_prediction/repos/linchemin`
  - Commit: `69f5f39`
  - Environment: `data/synthesis_prediction/envs/linchemin`
  - Install status: installed editable
  - Verification: `import linchemin` succeeded; `pip check` reported no broken requirements.

- `pfnet-research/step-wise-chemical-synthesis-prediction`
  - Local repo: `data/synthesis_prediction/repos/step-wise-chemical-synthesis-prediction`
  - Commit: `a24a88f`
  - Install status: cloned only, legacy manual environment required
  - Reason: upstream README requires `cupy==6.2.0`, `chainer==6.2.0`, editable `chainer-chemistry`, and `rdkit==2017.09.3.0`. This is a Python 3.6/CUDA-era stack and was not force-installed into the project or modern environment.

- `pfnet-research/chainer-chemistry`
  - Local repo: `data/synthesis_prediction/repos/chainer-chemistry`
  - Commit: `efe323a`
  - Install status: cloned only as PFNet step-wise dependency

- `kheyer/Deep-Synthesis`
  - Local repo: `data/synthesis_prediction/repos/Deep-Synthesis`
  - Commit: `2b41a22`
  - Install status: cloned only, legacy Docker/Conda setup required
  - Reason: upstream local setup creates a `deep_synthesis` conda env, installs RDKit, installs old Streamlit/PyTorch/OpenNMT dependencies, clones OpenNMT-py, and downloads a trained model from S3. Training was not run and the model download was not executed.

## Environment Specs

- `data/synthesis_prediction/env_specs/linchemin_environment.yml`
- `data/synthesis_prediction/env_specs/linchemin_freeze.txt`
- `data/synthesis_prediction/env_specs/pfnet_stepwise_legacy_environment.yml`
- `data/synthesis_prediction/env_specs/deep_synthesis_legacy_environment.yml`

## Safety Notes

- No training commands were run.
- No inference commands were run.
- No notebooks were executed.
- No external APIs were called by application code.
- The only network operations performed were repository clones and package downloads for the isolated `linchemin` environment.
- The two legacy ML repositories should be treated as manual/heavy integrations until their CUDA/Python/model compatibility is reviewed.
