#!/usr/bin/env bash
set -u

ROOT="/storage/saveena/protacpilot"
LOGDIR="$ROOT/data/protac_repos/install_logs"
mkdir -p "$ROOT/.venvs" "$LOGDIR"

cd "$ROOT" || exit 1

echo "Installing all PROTAC repo environments from $ROOT"
echo "Logs: $LOGDIR"

install_venv_requirements () {
  ENV_PATH="$1"
  REQ_PATH="$2"
  LOG_NAME="$3"

  echo "Installing $ENV_PATH from $REQ_PATH"
  python -m venv "$ENV_PATH"
  source "$ENV_PATH/bin/activate"
  python -m pip install --upgrade pip
  pip install -r "$REQ_PATH" 2>&1 | tee "$LOGDIR/$LOG_NAME"
  deactivate
}

install_venv_editable () {
  ENV_PATH="$1"
  REPO_PATH="$2"
  LOG_NAME="$3"

  echo "Installing editable $REPO_PATH into $ENV_PATH"
  python -m venv "$ENV_PATH"
  source "$ENV_PATH/bin/activate"
  python -m pip install --upgrade pip
  pip install -e "$REPO_PATH" 2>&1 | tee "$LOGDIR/$LOG_NAME"
  deactivate
}

install_conda_env () {
  ENV_NAME="$1"
  YAML_PATH="$2"
  LOG_NAME="$3"

  echo "Installing conda/mamba env $ENV_NAME from $YAML_PATH"

  if command -v mamba >/dev/null 2>&1; then
    mamba env create -n "$ENV_NAME" -f "$YAML_PATH" 2>&1 | tee "$LOGDIR/$LOG_NAME"
  elif command -v conda >/dev/null 2>&1; then
    conda env create -n "$ENV_NAME" -f "$YAML_PATH" 2>&1 | tee "$LOGDIR/$LOG_NAME"
  else
    echo "ERROR: neither mamba nor conda found for $ENV_NAME" | tee "$LOGDIR/$LOG_NAME"
  fi
}

# venv/pip repos
install_venv_requirements \
  "$ROOT/.venvs/protac-ternify" \
  "$ROOT/data/protac_repos/repos/TERNIFY/requirements.txt" \
  "ternify_install.log"

install_venv_requirements \
  "$ROOT/.venvs/protac-splitter" \
  "$ROOT/data/protac_repos/repos/PROTAC-Splitter/requirements.txt" \
  "protac_splitter_requirements.log"

source "$ROOT/.venvs/protac-splitter/bin/activate"
pip install -e "$ROOT/data/protac_repos/repos/PROTAC-Splitter" \
  2>&1 | tee "$LOGDIR/protac_splitter_editable.log"
deactivate

install_venv_requirements \
  "$ROOT/.venvs/protac-bellerophon" \
  "$ROOT/data/protac_repos/repos/Bellerophon/requirements.txt" \
  "bellerophon_install.log"

install_venv_editable \
  "$ROOT/.venvs/protac-degradomap" \
  "$ROOT/data/protac_repos/repos/degradomap" \
  "degradomap_editable.log"

install_venv_requirements \
  "$ROOT/.venvs/protac-protacfold" \
  "$ROOT/data/protac_repos/repos/PROTACFold/requirements.txt" \
  "protacfold_install.log"

# conda/mamba repos
install_conda_env \
  "protac-degradation-predictor" \
  "$ROOT/data/protac_repos/repos/PROTAC-Degradation-Predictor/environment.yml" \
  "protac_degradation_predictor_conda.log"

install_conda_env \
  "protac-rl" \
  "$ROOT/data/protac_repos/repos/PROTAC-RL/environment.yml" \
  "protac_rl_conda.log"

install_conda_env \
  "protac-mega-protac" \
  "$ROOT/data/protac_repos/repos/MEGA-PROTAC/environment.yml" \
  "mega_protac_conda.log"

install_conda_env \
  "protac-se3-protacs" \
  "$ROOT/data/protac_repos/repos/SE3-protacs/environment.yml" \
  "se3_protacs_conda.log"

echo "All install commands attempted."
echo "Check logs in $LOGDIR"
