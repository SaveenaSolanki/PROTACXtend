#!/usr/bin/env bash
# Phase 3 safe command templates.
# Every install/build/smoke-test command is commented out intentionally.
# Review one repository at a time before uncommenting anything.

# ===== PROTAC-RL =====
# decision: install_now_isolated
# mamba env create -n protac-rl -f data/protac_repos/repos/PROTAC-RL/environment.yml
# conda env create -n protac-rl -f data/protac_repos/repos/PROTAC-RL/environment.yml
# Generic smoke-test plan after manual environment creation:
# python --version
# python -m pip list | head
# ls data/protac_repos/repos/PROTAC-RL

# ===== PROTACFold =====
# decision: docker_only_manual_review
# python -m venv .venvs/protac-protacfold
# source .venvs/protac-protacfold/bin/activate
# python -m pip install --upgrade pip
# pip install -r data/protac_repos/repos/PROTACFold/requirements.txt
# Generic smoke-test plan after manual environment creation:
# python --version
# python -m pip list | head
# ls data/protac_repos/repos/PROTACFold

# ===== MEGA-PROTAC =====
# decision: install_later_manual_review
# mamba env create -n protac-mega-protac -f data/protac_repos/repos/MEGA-PROTAC/environment.yml
# conda env create -n protac-mega-protac -f data/protac_repos/repos/MEGA-PROTAC/environment.yml
# Generic smoke-test plan after manual environment creation:
# python --version
# python -m pip list | head
# ls data/protac_repos/repos/MEGA-PROTAC

# ===== SE3-protacs =====
# decision: install_later_manual_review
# mamba env create -n protac-se3-protacs -f data/protac_repos/repos/SE3-protacs/environment.yml
# conda env create -n protac-se3-protacs -f data/protac_repos/repos/SE3-protacs/environment.yml
# Generic smoke-test plan after manual environment creation:
# python --version
# python -m pip list | head
# ls data/protac_repos/repos/SE3-protacs

# ===== PROTAC-Degradation-Predictor =====
# decision: docker_only_manual_review
# mamba env create -n protac-degradation-predictor -f data/protac_repos/repos/PROTAC-Degradation-Predictor/environment.yml
# conda env create -n protac-degradation-predictor -f data/protac_repos/repos/PROTAC-Degradation-Predictor/environment.yml
# Generic smoke-test plan after manual environment creation:
# python --version
# python -m pip list | head
# ls data/protac_repos/repos/PROTAC-Degradation-Predictor

# ===== TERNIFY =====
# decision: install_now_isolated
# python -m venv .venvs/protac-ternify
# source .venvs/protac-ternify/bin/activate
# python -m pip install --upgrade pip
# pip install -r data/protac_repos/repos/TERNIFY/requirements.txt
# Generic smoke-test plan after manual environment creation:
# python --version
# python -m pip list | head
# ls data/protac_repos/repos/TERNIFY

# ===== PROTAC-Splitter =====
# decision: install_now_isolated
# python -m venv .venvs/protac-splitter
# source .venvs/protac-splitter/bin/activate
# python -m pip install --upgrade pip
# pip install -r data/protac_repos/repos/PROTAC-Splitter/requirements.txt
# Generic smoke-test plan after manual environment creation:
# python --version
# python -m pip list | head
# ls data/protac_repos/repos/PROTAC-Splitter

# ===== Bellerophon =====
# decision: install_later_manual_review
# python -m venv .venvs/protac-bellerophon
# source .venvs/protac-bellerophon/bin/activate
# python -m pip install --upgrade pip
# pip install -r data/protac_repos/repos/Bellerophon/requirements.txt
# Generic smoke-test plan after manual environment creation:
# python --version
# python -m pip list | head
# ls data/protac_repos/repos/Bellerophon

# ===== degradomap =====
# decision: install_later_manual_review
# python -m venv .venvs/protac-degradomap
# source .venvs/protac-degradomap/bin/activate
# python -m pip install --upgrade pip
# pip install -e data/protac_repos/repos/degradomap
# Generic smoke-test plan after manual environment creation:
# python --version
# python -m pip list | head
# ls data/protac_repos/repos/degradomap
