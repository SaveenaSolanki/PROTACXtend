# Chemical Synthesis Prediction Setup

This directory isolates synthesis-prediction repositories from the main PROTACXtend environment.

## Repositories

- `repos/linchemin`: installed in `envs/linchemin`.
- `repos/step-wise-chemical-synthesis-prediction`: cloned for legacy Chainer/CuPy review.
- `repos/Deep-Synthesis`: cloned for legacy OpenNMT/PyTorch review.

## Use linchemin

```bash
conda activate /storage/saveena/protacpilot/data/synthesis_prediction/envs/linchemin
python -c "import linchemin, importlib.metadata; print(importlib.metadata.version('linchemin'))"
```

## Legacy Repos

Use the environment specs in `env_specs/` as starting points only. Do not run training or model-download scripts without explicit review.
