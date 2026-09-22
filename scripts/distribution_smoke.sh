#!/usr/bin/env bash
# PROTACXtend distribution smoke test.
#
# Installs a built wheel into a throwaway virtualenv and verifies that the
# packaged CLI, toolkit subsystem and bundled scientific data all work with no
# repository checkout on PYTHONPATH.
#
# Usage:
#   scripts/distribution_smoke.sh [path/to/protacxtend-*.whl]
#
# With no argument the newest wheel in dist/ is used (build one first with
# scripts/package_release.sh).
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WHEEL="${1:-$(ls -t "$ROOT"/dist/*.whl 2>/dev/null | head -1 || true)}"
if [ -z "$WHEEL" ] || [ ! -f "$WHEEL" ]; then
  echo "No wheel found. Build one first:  scripts/package_release.sh" >&2
  exit 2
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
VENV="$TMP/venv"
PASS=0
FAIL=0

log()  { printf '  [smoke] %s\n' "$*"; }
check() {
  local name="$1"; shift
  if "$@" >"$TMP/$name.log" 2>&1; then
    log "PASS  $name"
    PASS=$((PASS+1))
  else
    log "FAIL  $name   (see $TMP/$name.log)"
    tail -5 "$TMP/$name.log" | sed 's/^/        /'
    FAIL=$((FAIL+1))
  fi
}

log "wheel: $WHEEL"
log "creating venv …"
python3 -m venv "$VENV"
"$VENV/bin/python" -m pip install --quiet --upgrade pip >/dev/null 2>&1 || true

log "installing wheel (with declared core dependencies) …"
if ! "$VENV/bin/python" -m pip install --quiet "$WHEEL" >"$TMP/install.log" 2>&1; then
  log "FATAL install failed"; tail -20 "$TMP/install.log"; exit 1
fi
BIN="$VENV/bin/protacxtend"
[ -x "$BIN" ] || BIN="$VENV/bin/PROTACXtend"

check "import_and_version" "$VENV/bin/python" -c \
  "import protacxtend; assert protacxtend.__version__; print(protacxtend.__version__)"
check "cli_help" "$BIN" --help
check "toolkit_plan" "$BIN" toolkit --action plan --json
check "toolkit_envs" "$BIN" toolkit --action envs --json
check "packaged_dataset" "$VENV/bin/python" -c \
  "from protacxtend.resources import asset_path; p=asset_path('benchmark','chemprop_train.csv'); print(p, p.stat().st_size)"
check "registry_loads" "$VENV/bin/python" -c \
  "from protacxtend.tools.toolkit_registry import get_toolkit_registry as g; assert len(g())>=100; print(len(g()))"
check "excel_toolkit_registry" "$VENV/bin/python" -c \
  "from protacxtend.toolkit import get_tools, load_toolkit_registry; assert callable(get_tools); print(len(get_tools()))"
check "agent_tools_ready" "$VENV/bin/python" -c \
  "from protacxtend.agentic.registry import TOOL_SPECS as T; assert all(s['readiness']=='ready' for s in T); print(len(T))"
check "escalation_readiness" "$VENV/bin/python" -c \
  "from protacxtend.escalation import capability_readiness as c; print(len(c()))"

echo ""
log "result: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
