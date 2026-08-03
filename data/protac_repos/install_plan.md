# PROTAC Repository Install Plan

## Overview

This plan prepares the collected repositories for future PROTAC agentic-AI integration. The collection step cloned or updated repositories and inspected visible install metadata only. No repository code was executed and no packages were installed into the base environment.

## Why isolated environments are required

These repositories span different research eras, dependency stacks, chemistry toolkits, ML frameworks, docking/conformer workflows, and possible GPU assumptions. Installing them together in the base environment would risk dependency conflicts and accidental execution of unreviewed code. Each repository should be tested in a separate Docker image, conda/mamba environment, or Python virtual environment.

## Repo-by-repo install recommendation

- **PROTAC-RL**: Create separate conda/mamba environment. Detected: environment.yml.
- **DeepPROTACs**: Manual inspection required. Detected: none.
- **PROTAC-Model**: Manual inspection required. Detected: none.
- **PROTACFold**: Create separate Python venv and install requirements there. Detected: requirements.txt.
- **PROTACable**: Manual inspection required. Detected: none.
- **Protac-invent**: Isolated Docker build later after manual review. Detected: Dockerfile.
- **PROTAC-Splitter**: Create separate Python venv and install requirements there. Detected: requirements.txt, setup.py.
- **PROTAC_ternary**: Manual inspection required. Detected: none.
- **ProTACT**: Manual inspection required. Detected: none.
- **PROTAC-STAN**: Manual inspection required. Detected: none.
- **PROTACability**: Manual inspection required. Detected: none.
- **PROTAC-Degradation-Predictor**: Create separate conda/mamba environment. Detected: requirements.txt, environment.yml, setup.py.
- **TERNIFY**: Create separate Python venv and install requirements there. Detected: requirements.txt.
- **AIMLinker**: Manual inspection required. Detected: none.
- **Machine-Learning-for-Predicting-Targeted-Protein-Degradation**: Create separate conda/mamba environment. Detected: environment.yml.
- **MEGA-PROTAC**: Create separate conda/mamba environment. Detected: requirements.txt, environment.yml.
- **SynGlue**: Manual inspection required. Detected: none.
- **PROTAC-Model_benchmark**: Manual inspection required. Detected: none.
- **SE3-protacs**: Create separate conda/mamba environment. Detected: environment.yml.
- **science-paper-protac-conformer-generator-2025**: Manual inspection required. Detected: none.
- **Bellerophon**: Create separate Python venv and install requirements there. Detected: requirements.txt.
- **PROTAC-shotgun**: Manual inspection required. Detected: none.
- **PROTAC_descriptors**: Manual inspection required. Detected: none.
- **computational-PROTAC-development**: Manual inspection required. Detected: none.
- **PROTAC**: Manual inspection required. Detected: none.
- **ProtacDatabase**: Manual inspection required. Detected: none.
- **protacSpace**: Create separate Python venv and install requirements there. Detected: requirements.txt.
- **degradomap**: Editable install in an isolated environment after review. Detected: pyproject.toml.
- **ProtacGPT**: Create separate conda/mamba environment. Detected: environment.yml.

## Which repos look like models

- **PROTAC-RL**: Create separate conda/mamba environment. Status: cloned.
- **PROTAC-Model**: Manual inspection required. Status: cloned.
- **Protac-invent**: Isolated Docker build later after manual review. Status: cloned.
- **PROTAC-STAN**: Manual inspection required. Status: cloned.
- **PROTAC-Degradation-Predictor**: Create separate conda/mamba environment. Status: cloned.
- **Machine-Learning-for-Predicting-Targeted-Protein-Degradation**: Create separate conda/mamba environment. Status: cloned.
- **PROTAC-Model_benchmark**: Manual inspection required. Status: cloned.
- **PROTAC-shotgun**: Manual inspection required. Status: cloned.
- **ProtacGPT**: Create separate conda/mamba environment. Status: cloned.

## Which repos look like datasets

- **PROTAC-Model_benchmark**: Manual inspection required. Status: cloned.
- **PROTAC_descriptors**: Manual inspection required. Status: cloned.
- **ProtacDatabase**: Manual inspection required. Status: cloned.

## Which repos look like molecular processing utilities

- **PROTAC-Splitter**: Create separate Python venv and install requirements there. Status: cloned.
- **AIMLinker**: Manual inspection required. Status: cloned.
- **science-paper-protac-conformer-generator-2025**: Manual inspection required. Status: cloned.
- **PROTAC_descriptors**: Manual inspection required. Status: cloned.
- **protacSpace**: Create separate Python venv and install requirements there. Status: cloned.

## Which repos look like ternary-complex/docking tools

- **PROTACFold**: Create separate Python venv and install requirements there. Status: cloned.
- **Protac-invent**: Isolated Docker build later after manual review. Status: cloned.
- **PROTAC_ternary**: Manual inspection required. Status: cloned.
- **MEGA-PROTAC**: Create separate conda/mamba environment. Status: cloned.
- **SE3-protacs**: Create separate conda/mamba environment. Status: cloned.
- **PROTAC-shotgun**: Manual inspection required. Status: cloned.

## Which repos should not be auto-executed before manual review

All repositories in this collection should avoid automatic execution before manual review. In particular, do not run training scripts, docking workflows, notebooks, shell installers, downloaded checkpoints, or project-specific CLIs until their source, data paths, licenses, and resource requirements have been inspected.

## Next integration step for PROTAC agentic AI

Create one isolated environment per repository, install only that repository's declared dependencies, run minimal import or CLI smoke tests, record executable status separately from clone status, and then wrap successful tools behind small adapter modules in the PROTAC agentic-AI toolkit.
