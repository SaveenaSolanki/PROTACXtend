#!/usr/bin/env bash
# PROTACXtend modular scientific-environment setup.
#
# Deliberately creates SMALL, separate environments instead of one enormous
# fragile conda env. Every extra environment is registered with the toolkit
# detector, so capabilities resolve across all of them.
#
# Usage:
#   scripts/setup_scientific_envs.sh                 # dry-run: show plan + health
#   scripts/setup_scientific_envs.sh --execute       # create/update envs
#   scripts/setup_scientific_envs.sh --execute --only md,docking
#
# Environments:
#   core      protacxtend CLI + registries (pip)
#   chem      rdkit + openbabel-wheel + meeko
#   docking   AutoDock Vina (conda-forge)
#   ppi       LightDock (pip)
#   md        openmm + pdbfixer + mdtraj (pip)
#   analysis  MDAnalysis + MDTraj + biopython (pip)
#   ml        chemprop + deepchem + fair-esm (pip)
#   gromacs   optional HPC MD (conda-forge)      [never required]
#   mmpbsa    optional gmx_MMPBSA endpoint energy [never required]
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PREFIX_BASE="${PROTACXTEND_ENV_ROOT:-$HOME/.protacxtend/envs}"
EXECUTE=0
ONLY=""
while [ $# -gt 0 ]; do
  case "$1" in
    --execute) EXECUTE=1; shift;;
    --only) ONLY="$2"; shift 2;;
    --root) PREFIX_BASE="$2"; shift 2;;
    *) echo "setup_scientific_envs: unknown option $1" >&2; exit 2;;
  esac
done

log() { printf '  [envs] %s\n' "$*"; }
selected() {
  [ -z "$ONLY" ] && return 0
  case ",$ONLY," in *",$1,"*) return 0;; *) return 1;; esac
}

PIP_ENVS=(
  "core:pip install -e $ROOT"
  "chem:pip install rdkit openbabel-wheel meeko"
  "docking:pip install meeko"
  "ppi:pip install lightdock"
  "md:pip install openmm pdbfixer mdtraj"
  "analysis:pip install MDAnalysis MDTraj biopython"
  "ml:pip install chemprop deepchem fair-esm"
)
CONDA_ENVS=(
  "docking:conda install -y -c conda-forge vina"
  "fpocket:conda install -y -c conda-forge fpocket"
  "gromacs:conda install -y -c conda-forge gromacs"
  "mmpbsa:conda install -y -c conda-forge gmx_MMPBSA"
)
# Non-packaged engines (installed manually, then detected automatically):
#   GNINA   : download the CPU/CUDA static binary from github.com/gnina/gnina
#             into an env bin/ dir (pip CUDA libs may be needed via LD_LIBRARY_PATH).
#   DiffDock: clone github.com/gcorso/DiffDock, add e3nn/prody + PyG extensions,
#             and wrap `inference.py` as an executable named `diffdock`.

create_venv() {
  local name="$1"; local cmd="$2"
  local prefix="$PREFIX_BASE/$name"
  if [ ! -x "$prefix/bin/python" ]; then
    log "create venv $name → $prefix"
    [ "$EXECUTE" = "1" ] && python3 -m venv "$prefix"
  fi
  log "$name: $cmd"
  if [ "$EXECUTE" = "1" ]; then
    # shellcheck disable=SC2086
    "$prefix/bin/python" -m pip install --quiet --upgrade pip >/dev/null 2>&1
    eval "$prefix/bin/python -m ${cmd#pip }" || log "warning: $name install incomplete"
  fi
  echo "$prefix/bin/python"
}

create_conda() {
  local name="$1"; local cmd="$2"
  local prefix="$PREFIX_BASE/$name"
  log "$name: $cmd  (prefix $prefix)"
  if [ "$EXECUTE" = "1" ]; then
    eval "conda create -y -p $prefix python=3.11 >/dev/null 2>&1"
    eval "conda $cmd -p $prefix" || log "warning: $name conda install incomplete"
  fi
}

log "PROTACXtend modular scientific environments"
log "root: $PREFIX_BASE   execute=$EXECUTE   only='${ONLY:-all}'"
echo ""

PYTHONS=()
for entry in "${PIP_ENVS[@]}"; do
  name="${entry%%:*}"; cmd="${entry#*:}"
  selected "$name" || continue
  py="$(create_venv "$name" "$cmd")"
  PYTHONS+=("$name=$py")
done
for entry in "${CONDA_ENVS[@]}"; do
  name="${entry%%:*}"; cmd="${entry#*:}"
  selected "$name" || continue
  create_conda "$name" "$cmd"
  PYTHONS+=("$name=$PREFIX_BASE/$name/bin/python")
done

echo ""
if [ "$EXECUTE" = "1" ] && [ "${#PYTHONS[@]}" -gt 0 ]; then
  REG="$(IFS=,; echo "${PYTHONS[*]}")"
  log "registering environments with the toolkit detector"
  export PROTACXTEND_TOOLKIT_ENVS="$REG"
fi

log "backend health check:"
python3 -c "import protacxtend" 2>/dev/null && \
  python3 -m protacxtend.cli backends || log "run from the repo with protacxtend importable"
echo ""
log "done. Re-run with --execute to provision, then: protacxtend backends"
