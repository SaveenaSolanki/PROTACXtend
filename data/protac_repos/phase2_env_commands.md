# Phase 2 Isolated Environment Commands

These are manual command templates only. They were generated from static dependency-file inspection.

No commands in `phase2_env_commands.sh` are active by default. Do not run bulk installs.

<a id="phase2-rl"></a>
### PROTAC-RL

- Safe environment name: `protac-rl`
- Repository path: `data/protac_repos/repos/PROTAC-RL`

Recommended isolated conda/mamba command:

```bash
mamba env create -n protac-rl -f data/protac_repos/repos/PROTAC-RL/environment.yml
conda env create -n protac-rl -f data/protac_repos/repos/PROTAC-RL/environment.yml
```

Generic smoke-test plan after manual environment creation:

```bash
python --version
python -m pip list | head
ls data/protac_repos/repos/PROTAC-RL
```

Do not import repository modules until a later smoke-import phase explicitly approves it.

<a id="phase2-deepprotacs"></a>
### DeepPROTACs

- Safe environment name: `protac-deepprotacs`
- Repository path: `data/protac_repos/repos/DeepPROTACs`

Manual inspection required before any environment creation.

<a id="phase2-model"></a>
### PROTAC-Model

- Safe environment name: `protac-model`
- Repository path: `data/protac_repos/repos/PROTAC-Model`

Manual inspection required before any environment creation.

<a id="phase2-protacfold"></a>
### PROTACFold

- Safe environment name: `protac-protacfold`
- Repository path: `data/protac_repos/repos/PROTACFold`

Alternative isolated venv/pip command:

```bash
python -m venv .venvs/protac-protacfold
source .venvs/protac-protacfold/bin/activate
python -m pip install --upgrade pip
pip install -r data/protac_repos/repos/PROTACFold/requirements.txt
```

Generic smoke-test plan after manual environment creation:

```bash
python --version
python -m pip list | head
ls data/protac_repos/repos/PROTACFold
```

Do not import repository modules until a later smoke-import phase explicitly approves it.

<a id="phase2-protacable"></a>
### PROTACable

- Safe environment name: `protac-protacable`
- Repository path: `data/protac_repos/repos/PROTACable`

Manual inspection required before any environment creation.

<a id="phase2-invent"></a>
### Protac-invent

- Safe environment name: `protac-invent`
- Repository path: `data/protac_repos/repos/Protac-invent`

Docker build template, manual review required before use:

```bash
docker build -t protac-toolkit/protac-invent:latest data/protac_repos/repos/Protac-invent
```

Generic smoke-test plan after manual environment creation:

```bash
python --version
python -m pip list | head
ls data/protac_repos/repos/Protac-invent
```

Do not import repository modules until a later smoke-import phase explicitly approves it.

<a id="phase2-splitter"></a>
### PROTAC-Splitter

- Safe environment name: `protac-splitter`
- Repository path: `data/protac_repos/repos/PROTAC-Splitter`

Alternative isolated venv/pip command:

```bash
python -m venv .venvs/protac-splitter
source .venvs/protac-splitter/bin/activate
python -m pip install --upgrade pip
pip install -r data/protac_repos/repos/PROTAC-Splitter/requirements.txt
```

Editable install command for isolated manual testing:

```bash
python -m venv .venvs/protac-splitter
source .venvs/protac-splitter/bin/activate
python -m pip install --upgrade pip
pip install -e data/protac_repos/repos/PROTAC-Splitter
```

Generic smoke-test plan after manual environment creation:

```bash
python --version
python -m pip list | head
ls data/protac_repos/repos/PROTAC-Splitter
```

Do not import repository modules until a later smoke-import phase explicitly approves it.

<a id="phase2-ternary"></a>
### PROTAC_ternary

- Safe environment name: `protac-ternary`
- Repository path: `data/protac_repos/repos/PROTAC_ternary`

Manual inspection required before any environment creation.

<a id="phase2-protact"></a>
### ProTACT

- Safe environment name: `protac-protact`
- Repository path: `data/protac_repos/repos/ProTACT`

Manual inspection required before any environment creation.

<a id="phase2-stan"></a>
### PROTAC-STAN

- Safe environment name: `protac-stan`
- Repository path: `data/protac_repos/repos/PROTAC-STAN`

Manual inspection required before any environment creation.

<a id="phase2-protacability"></a>
### PROTACability

- Safe environment name: `protac-protacability`
- Repository path: `data/protac_repos/repos/PROTACability`

Manual inspection required before any environment creation.

<a id="phase2-degradation-predictor"></a>
### PROTAC-Degradation-Predictor

- Safe environment name: `protac-degradation-predictor`
- Repository path: `data/protac_repos/repos/PROTAC-Degradation-Predictor`

Recommended isolated conda/mamba command:

```bash
mamba env create -n protac-degradation-predictor -f data/protac_repos/repos/PROTAC-Degradation-Predictor/environment.yml
conda env create -n protac-degradation-predictor -f data/protac_repos/repos/PROTAC-Degradation-Predictor/environment.yml
```

Alternative isolated venv/pip command:

```bash
python -m venv .venvs/protac-degradation-predictor
source .venvs/protac-degradation-predictor/bin/activate
python -m pip install --upgrade pip
pip install -r data/protac_repos/repos/PROTAC-Degradation-Predictor/requirements.txt
```

Editable install command for isolated manual testing:

```bash
python -m venv .venvs/protac-degradation-predictor
source .venvs/protac-degradation-predictor/bin/activate
python -m pip install --upgrade pip
pip install -e data/protac_repos/repos/PROTAC-Degradation-Predictor
```

Generic smoke-test plan after manual environment creation:

```bash
python --version
python -m pip list | head
ls data/protac_repos/repos/PROTAC-Degradation-Predictor
```

Do not import repository modules until a later smoke-import phase explicitly approves it.

<a id="phase2-ternify"></a>
### TERNIFY

- Safe environment name: `protac-ternify`
- Repository path: `data/protac_repos/repos/TERNIFY`

Alternative isolated venv/pip command:

```bash
python -m venv .venvs/protac-ternify
source .venvs/protac-ternify/bin/activate
python -m pip install --upgrade pip
pip install -r data/protac_repos/repos/TERNIFY/requirements.txt
```

Generic smoke-test plan after manual environment creation:

```bash
python --version
python -m pip list | head
ls data/protac_repos/repos/TERNIFY
```

Do not import repository modules until a later smoke-import phase explicitly approves it.

<a id="phase2-aimlinker"></a>
### AIMLinker

- Safe environment name: `protac-aimlinker`
- Repository path: `data/protac_repos/repos/AIMLinker`

Manual inspection required before any environment creation.

<a id="phase2-machine-learning-for-predicting-targeted-protein-degradation"></a>
### Machine-Learning-for-Predicting-Targeted-Protein-Degradation

- Safe environment name: `protac-machine-learning-for-predicting-targeted-protein-degradation`
- Repository path: `data/protac_repos/repos/Machine-Learning-for-Predicting-Targeted-Protein-Degradation`

Recommended isolated conda/mamba command:

```bash
mamba env create -n protac-machine-learning-for-predicting-targeted-protein-degradation -f data/protac_repos/repos/Machine-Learning-for-Predicting-Targeted-Protein-Degradation/environment.yml
conda env create -n protac-machine-learning-for-predicting-targeted-protein-degradation -f data/protac_repos/repos/Machine-Learning-for-Predicting-Targeted-Protein-Degradation/environment.yml
```

Generic smoke-test plan after manual environment creation:

```bash
python --version
python -m pip list | head
ls data/protac_repos/repos/Machine-Learning-for-Predicting-Targeted-Protein-Degradation
```

Do not import repository modules until a later smoke-import phase explicitly approves it.

<a id="phase2-mega-protac"></a>
### MEGA-PROTAC

- Safe environment name: `protac-mega-protac`
- Repository path: `data/protac_repos/repos/MEGA-PROTAC`

Recommended isolated conda/mamba command:

```bash
mamba env create -n protac-mega-protac -f data/protac_repos/repos/MEGA-PROTAC/environment.yml
conda env create -n protac-mega-protac -f data/protac_repos/repos/MEGA-PROTAC/environment.yml
```

Alternative isolated venv/pip command:

```bash
python -m venv .venvs/protac-mega-protac
source .venvs/protac-mega-protac/bin/activate
python -m pip install --upgrade pip
pip install -r data/protac_repos/repos/MEGA-PROTAC/requirements.txt
```

Generic smoke-test plan after manual environment creation:

```bash
python --version
python -m pip list | head
ls data/protac_repos/repos/MEGA-PROTAC
```

Do not import repository modules until a later smoke-import phase explicitly approves it.

<a id="phase2-synglue"></a>
### SynGlue

- Safe environment name: `protac-synglue`
- Repository path: `data/protac_repos/repos/SynGlue`

Manual inspection required before any environment creation.

<a id="phase2-model-benchmark"></a>
### PROTAC-Model_benchmark

- Safe environment name: `protac-model-benchmark`
- Repository path: `data/protac_repos/repos/PROTAC-Model_benchmark`

Manual inspection required before any environment creation.

<a id="phase2-se3-protacs"></a>
### SE3-protacs

- Safe environment name: `protac-se3-protacs`
- Repository path: `data/protac_repos/repos/SE3-protacs`

Recommended isolated conda/mamba command:

```bash
mamba env create -n protac-se3-protacs -f data/protac_repos/repos/SE3-protacs/environment.yml
conda env create -n protac-se3-protacs -f data/protac_repos/repos/SE3-protacs/environment.yml
```

Generic smoke-test plan after manual environment creation:

```bash
python --version
python -m pip list | head
ls data/protac_repos/repos/SE3-protacs
```

Do not import repository modules until a later smoke-import phase explicitly approves it.

<a id="phase2-science-paper-protac-conformer-generator-2025"></a>
### science-paper-protac-conformer-generator-2025

- Safe environment name: `protac-science-paper-protac-conformer-generator-2025`
- Repository path: `data/protac_repos/repos/science-paper-protac-conformer-generator-2025`

Manual inspection required before any environment creation.

<a id="phase2-bellerophon"></a>
### Bellerophon

- Safe environment name: `protac-bellerophon`
- Repository path: `data/protac_repos/repos/Bellerophon`

Alternative isolated venv/pip command:

```bash
python -m venv .venvs/protac-bellerophon
source .venvs/protac-bellerophon/bin/activate
python -m pip install --upgrade pip
pip install -r data/protac_repos/repos/Bellerophon/requirements.txt
```

Generic smoke-test plan after manual environment creation:

```bash
python --version
python -m pip list | head
ls data/protac_repos/repos/Bellerophon
```

Do not import repository modules until a later smoke-import phase explicitly approves it.

<a id="phase2-shotgun"></a>
### PROTAC-shotgun

- Safe environment name: `protac-shotgun`
- Repository path: `data/protac_repos/repos/PROTAC-shotgun`

Manual inspection required before any environment creation.

<a id="phase2-descriptors"></a>
### PROTAC_descriptors

- Safe environment name: `protac-descriptors`
- Repository path: `data/protac_repos/repos/PROTAC_descriptors`

Manual inspection required before any environment creation.

<a id="phase2-computational-protac-development"></a>
### computational-PROTAC-development

- Safe environment name: `protac-computational-protac-development`
- Repository path: `data/protac_repos/repos/computational-PROTAC-development`

Manual inspection required before any environment creation.

<a id="phase2-protac"></a>
### PROTAC

- Safe environment name: `protac-protac`
- Repository path: `data/protac_repos/repos/PROTAC`

Manual inspection required before any environment creation.

<a id="phase2-protacdatabase"></a>
### ProtacDatabase

- Safe environment name: `protac-protacdatabase`
- Repository path: `data/protac_repos/repos/ProtacDatabase`

Manual inspection required before any environment creation.

<a id="phase2-protacspace"></a>
### protacSpace

- Safe environment name: `protac-protacspace`
- Repository path: `data/protac_repos/repos/protacSpace`

Alternative isolated venv/pip command:

```bash
python -m venv .venvs/protac-protacspace
source .venvs/protac-protacspace/bin/activate
python -m pip install --upgrade pip
pip install -r data/protac_repos/repos/protacSpace/requirements.txt
```

Generic smoke-test plan after manual environment creation:

```bash
python --version
python -m pip list | head
ls data/protac_repos/repos/protacSpace
```

Do not import repository modules until a later smoke-import phase explicitly approves it.

<a id="phase2-degradomap"></a>
### degradomap

- Safe environment name: `protac-degradomap`
- Repository path: `data/protac_repos/repos/degradomap`

Editable install command for isolated manual testing:

```bash
python -m venv .venvs/protac-degradomap
source .venvs/protac-degradomap/bin/activate
python -m pip install --upgrade pip
pip install -e data/protac_repos/repos/degradomap
```

Generic smoke-test plan after manual environment creation:

```bash
python --version
python -m pip list | head
ls data/protac_repos/repos/degradomap
```

Do not import repository modules until a later smoke-import phase explicitly approves it.

<a id="phase2-protacgpt"></a>
### ProtacGPT

- Safe environment name: `protac-protacgpt`
- Repository path: `data/protac_repos/repos/ProtacGPT`

Recommended isolated conda/mamba command:

```bash
mamba env create -n protac-protacgpt -f data/protac_repos/repos/ProtacGPT/environment.yml
conda env create -n protac-protacgpt -f data/protac_repos/repos/ProtacGPT/environment.yml
```

Generic smoke-test plan after manual environment creation:

```bash
python --version
python -m pip list | head
ls data/protac_repos/repos/ProtacGPT
```

Do not import repository modules until a later smoke-import phase explicitly approves it.
