# Phase 3 Pre-install Audit

This report is based on static file inspection only. No repository code was executed, imported, installed, trained, docked, or run as a notebook.

## PROTAC-RL

- Decision: `install_now_isolated`
- Risk level: `medium`
- Role: model or prediction utility; molecular processing utility; dataset/benchmark/reference; checkpoint/model-assets repository
- Dependency files: environment.yml
- Recommended strategy: conda/mamba
- Recommended command template: `mamba env create -n protac-rl -f data/protac_repos/repos/PROTAC-RL/environment.yml`
- External binaries: none
- Notes: scripts found: 98; README detected; pretrained checkpoint/model weight wording detected

## PROTACFold

- Decision: `docker_only_manual_review`
- Risk level: `high`
- Role: ternary-complex/docking workflow; model or prediction utility; molecular processing utility; dataset/benchmark/reference
- Dependency files: requirements.txt
- Recommended strategy: venv/pip; docker-manual-review
- Recommended command template: `python -m venv .venvs/protac-protacfold && source .venvs/protac-protacfold/bin/activate && python -m pip install --upgrade pip && pip install -r data/protac_repos/repos/PROTACFold/requirements.txt`
- External binaries: alphafold
- Notes: scripts found: 23; README detected; Phase 2 marked manual review required; README or metadata mentions Docker; large dataset wording detected

## MEGA-PROTAC

- Decision: `install_later_manual_review`
- Risk level: `high`
- Role: ternary-complex/docking workflow; model or prediction utility; dataset/benchmark/reference
- Dependency files: requirements.txt, environment.yml
- Recommended strategy: conda/mamba; venv/pip
- Recommended command template: `mamba env create -n protac-mega-protac -f data/protac_repos/repos/MEGA-PROTAC/environment.yml`
- External binaries: megadock, openbabel
- Notes: scripts found: 28; README detected; license file not detected at repository root; Phase 2 marked manual review required

## SE3-protacs

- Decision: `install_later_manual_review`
- Risk level: `high`
- Role: model or prediction utility; molecular processing utility; dataset/benchmark/reference; checkpoint/model-assets repository
- Dependency files: environment.yml
- Recommended strategy: conda/mamba
- Recommended command template: `mamba env create -n protac-se3-protacs -f data/protac_repos/repos/SE3-protacs/environment.yml`
- External binaries: openbabel
- Notes: scripts found: 8; README detected; license file not detected at repository root; Phase 2 marked manual review required

## PROTAC-Degradation-Predictor

- Decision: `docker_only_manual_review`
- Risk level: `medium`
- Role: model or prediction utility; molecular processing utility; dataset/benchmark/reference; notebook-oriented workflow
- Dependency files: requirements.txt, environment.yml, setup.py
- Recommended strategy: conda/mamba; venv/pip; editable-venv; docker-manual-review
- Recommended command template: `mamba env create -n protac-degradation-predictor -f data/protac_repos/repos/PROTAC-Degradation-Predictor/environment.yml`
- External binaries: none
- Notes: notebooks found: 11; scripts found: 23; README detected; README or metadata mentions Docker

## TERNIFY

- Decision: `install_now_isolated`
- Risk level: `low`
- Role: ternary-complex/docking workflow; molecular processing utility; dataset/benchmark/reference
- Dependency files: requirements.txt
- Recommended strategy: venv/pip
- Recommended command template: `python -m venv .venvs/protac-ternify && source .venvs/protac-ternify/bin/activate && python -m pip install --upgrade pip && pip install -r data/protac_repos/repos/TERNIFY/requirements.txt`
- External binaries: none
- Notes: scripts found: 11; README detected

## PROTAC-Splitter

- Decision: `install_now_isolated`
- Risk level: `medium`
- Role: model or prediction utility; molecular processing utility; dataset/benchmark/reference; notebook-oriented workflow
- Dependency files: requirements.txt, setup.py
- Recommended strategy: venv/pip; editable-venv
- Recommended command template: `python -m venv .venvs/protac-splitter && source .venvs/protac-splitter/bin/activate && python -m pip install --upgrade pip && pip install -r data/protac_repos/repos/PROTAC-Splitter/requirements.txt`
- External binaries: none
- Notes: notebooks found: 6; scripts found: 55; README detected; license file not detected at repository root; large dataset wording detected; pretrained checkpoint/model weight wording detected

## Bellerophon

- Decision: `install_later_manual_review`
- Risk level: `low`
- Role: molecular processing utility; dataset/benchmark/reference
- Dependency files: requirements.txt
- Recommended strategy: venv/pip
- Recommended command template: `python -m venv .venvs/protac-bellerophon && source .venvs/protac-bellerophon/bin/activate && python -m pip install --upgrade pip && pip install -r data/protac_repos/repos/Bellerophon/requirements.txt`
- External binaries: none
- Notes: scripts found: 2; README detected; deferred because Phase 3 limits install_now_isolated to 3 safest repositories

## degradomap

- Decision: `install_later_manual_review`
- Risk level: `high`
- Role: ternary-complex/docking workflow; model or prediction utility; dataset/benchmark/reference; notebook-oriented workflow
- Dependency files: pyproject.toml
- Recommended strategy: editable-venv
- Recommended command template: `python -m venv .venvs/protac-degradomap && source .venvs/protac-degradomap/bin/activate && python -m pip install --upgrade pip && pip install -e data/protac_repos/repos/degradomap`
- External binaries: alphafold
- Notes: notebooks found: 1; scripts found: 11; README detected; Phase 2 marked manual review required
