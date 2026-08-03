#!/usr/bin/env bash
# Phase 2 isolated environment command templates.
# Safety: every install/build/smoke-test command is commented out intentionally.
# Uncomment and run one repository section at a time only after manual review.

# ===== PROTAC-RL =====
# mamba env create -n protac-rl -f data/protac_repos/repos/PROTAC-RL/environment.yml
# conda env create -n protac-rl -f data/protac_repos/repos/PROTAC-RL/environment.yml
# Generic smoke-test plan after manual environment creation:
# python --version
# python -m pip list | head
# ls data/protac_repos/repos/PROTAC-RL

# ===== DeepPROTACs =====
# manual inspection required

# ===== PROTAC-Model =====
# manual inspection required

# ===== PROTACFold =====
# python -m venv .venvs/protac-protacfold
# source .venvs/protac-protacfold/bin/activate
# python -m pip install --upgrade pip
# pip install -r data/protac_repos/repos/PROTACFold/requirements.txt
# Generic smoke-test plan after manual environment creation:
# python --version
# python -m pip list | head
# ls data/protac_repos/repos/PROTACFold

# ===== PROTACable =====
# manual inspection required

# ===== Protac-invent =====
# docker build -t protac-toolkit/protac-invent:latest data/protac_repos/repos/Protac-invent
# Generic smoke-test plan after manual environment creation:
# python --version
# python -m pip list | head
# ls data/protac_repos/repos/Protac-invent

# ===== PROTAC-Splitter =====
# python -m venv .venvs/protac-splitter
# source .venvs/protac-splitter/bin/activate
# python -m pip install --upgrade pip
# pip install -r data/protac_repos/repos/PROTAC-Splitter/requirements.txt
# python -m venv .venvs/protac-splitter
# source .venvs/protac-splitter/bin/activate
# python -m pip install --upgrade pip
# pip install -e data/protac_repos/repos/PROTAC-Splitter
# Generic smoke-test plan after manual environment creation:
# python --version
# python -m pip list | head
# ls data/protac_repos/repos/PROTAC-Splitter

# ===== PROTAC_ternary =====
# manual inspection required

# ===== ProTACT =====
# manual inspection required

# ===== PROTAC-STAN =====
# manual inspection required

# ===== PROTACability =====
# manual inspection required

# ===== PROTAC-Degradation-Predictor =====
# mamba env create -n protac-degradation-predictor -f data/protac_repos/repos/PROTAC-Degradation-Predictor/environment.yml
# conda env create -n protac-degradation-predictor -f data/protac_repos/repos/PROTAC-Degradation-Predictor/environment.yml
# python -m venv .venvs/protac-degradation-predictor
# source .venvs/protac-degradation-predictor/bin/activate
# python -m pip install --upgrade pip
# pip install -r data/protac_repos/repos/PROTAC-Degradation-Predictor/requirements.txt
# python -m venv .venvs/protac-degradation-predictor
# source .venvs/protac-degradation-predictor/bin/activate
# python -m pip install --upgrade pip
# pip install -e data/protac_repos/repos/PROTAC-Degradation-Predictor
# Generic smoke-test plan after manual environment creation:
# python --version
# python -m pip list | head
# ls data/protac_repos/repos/PROTAC-Degradation-Predictor

# ===== TERNIFY =====
# python -m venv .venvs/protac-ternify
# source .venvs/protac-ternify/bin/activate
# python -m pip install --upgrade pip
# pip install -r data/protac_repos/repos/TERNIFY/requirements.txt
# Generic smoke-test plan after manual environment creation:
# python --version
# python -m pip list | head
# ls data/protac_repos/repos/TERNIFY

# ===== AIMLinker =====
# manual inspection required

# ===== Machine-Learning-for-Predicting-Targeted-Protein-Degradation =====
# mamba env create -n protac-machine-learning-for-predicting-targeted-protein-degradation -f data/protac_repos/repos/Machine-Learning-for-Predicting-Targeted-Protein-Degradation/environment.yml
# conda env create -n protac-machine-learning-for-predicting-targeted-protein-degradation -f data/protac_repos/repos/Machine-Learning-for-Predicting-Targeted-Protein-Degradation/environment.yml
# Generic smoke-test plan after manual environment creation:
# python --version
# python -m pip list | head
# ls data/protac_repos/repos/Machine-Learning-for-Predicting-Targeted-Protein-Degradation

# ===== MEGA-PROTAC =====
# mamba env create -n protac-mega-protac -f data/protac_repos/repos/MEGA-PROTAC/environment.yml
# conda env create -n protac-mega-protac -f data/protac_repos/repos/MEGA-PROTAC/environment.yml
# python -m venv .venvs/protac-mega-protac
# source .venvs/protac-mega-protac/bin/activate
# python -m pip install --upgrade pip
# pip install -r data/protac_repos/repos/MEGA-PROTAC/requirements.txt
# Generic smoke-test plan after manual environment creation:
# python --version
# python -m pip list | head
# ls data/protac_repos/repos/MEGA-PROTAC

# ===== SynGlue =====
# manual inspection required

# ===== PROTAC-Model_benchmark =====
# manual inspection required

# ===== SE3-protacs =====
# mamba env create -n protac-se3-protacs -f data/protac_repos/repos/SE3-protacs/environment.yml
# conda env create -n protac-se3-protacs -f data/protac_repos/repos/SE3-protacs/environment.yml
# Generic smoke-test plan after manual environment creation:
# python --version
# python -m pip list | head
# ls data/protac_repos/repos/SE3-protacs

# ===== science-paper-protac-conformer-generator-2025 =====
# manual inspection required

# ===== Bellerophon =====
# python -m venv .venvs/protac-bellerophon
# source .venvs/protac-bellerophon/bin/activate
# python -m pip install --upgrade pip
# pip install -r data/protac_repos/repos/Bellerophon/requirements.txt
# Generic smoke-test plan after manual environment creation:
# python --version
# python -m pip list | head
# ls data/protac_repos/repos/Bellerophon

# ===== PROTAC-shotgun =====
# manual inspection required

# ===== PROTAC_descriptors =====
# manual inspection required

# ===== computational-PROTAC-development =====
# manual inspection required

# ===== PROTAC =====
# manual inspection required

# ===== ProtacDatabase =====
# manual inspection required

# ===== protacSpace =====
# python -m venv .venvs/protac-protacspace
# source .venvs/protac-protacspace/bin/activate
# python -m pip install --upgrade pip
# pip install -r data/protac_repos/repos/protacSpace/requirements.txt
# Generic smoke-test plan after manual environment creation:
# python --version
# python -m pip list | head
# ls data/protac_repos/repos/protacSpace

# ===== degradomap =====
# python -m venv .venvs/protac-degradomap
# source .venvs/protac-degradomap/bin/activate
# python -m pip install --upgrade pip
# pip install -e data/protac_repos/repos/degradomap
# Generic smoke-test plan after manual environment creation:
# python --version
# python -m pip list | head
# ls data/protac_repos/repos/degradomap

# ===== ProtacGPT =====
# mamba env create -n protac-protacgpt -f data/protac_repos/repos/ProtacGPT/environment.yml
# conda env create -n protac-protacgpt -f data/protac_repos/repos/ProtacGPT/environment.yml
# Generic smoke-test plan after manual environment creation:
# python --version
# python -m pip list | head
# ls data/protac_repos/repos/ProtacGPT
