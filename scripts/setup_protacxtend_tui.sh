#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════
# PROTACXtend TUI — One-line installer
#
# Usage:
#   bash scripts/setup_protacxtend_tui.sh
#   — or from any directory:
#   bash <(curl -s <repo_url>/scripts/setup_protacxtend_tui.sh)
#
# What it does:
#   1. Detects Python ≥ 3.10
#   2. Installs textual + rich (TUI dependencies)
#   3. Installs protacxtend package in editable mode
#   4. Verifies the TUI loads
#   5. Prints usage instructions
# ═══════════════════════════════════════════════════════════════════════
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "═══════════════════════════════════════════════════════════"
echo "  PROTACXtend TUI — Setup"
echo "═══════════════════════════════════════════════════════════"
echo ""

# ── 1. Check Python ──
PYTHON="${PYTHON:-python3}"
if ! command -v "$PYTHON" &>/dev/null; then
    echo "ERROR: $PYTHON not found. Install Python ≥ 3.10 first."
    exit 1
fi

PY_VERSION=$("$PYTHON" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$("$PYTHON" -c "import sys; print(sys.version_info.major)")
PY_MINOR=$("$PYTHON" -c "import sys; print(sys.version_info.minor)")

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]; }; then
    echo "ERROR: Python ≥ 3.10 required. Found: $PY_VERSION"
    exit 1
fi
echo "✓ Python $PY_VERSION"

# ── 2. Install TUI dependencies ──
echo ""
echo "Installing TUI dependencies (textual + rich)..."
"$PYTHON" -m pip install --quiet textual rich 2>/dev/null || {
    echo "  Trying with --user flag..."
    "$PYTHON" -m pip install --quiet --user textual rich
}
echo "✓ textual + rich installed"

# ── 3. Install protacxtend in editable mode ──
echo ""
echo "Installing PROTACXtend package..."
cd "$PROJECT_ROOT"
"$PYTHON" -m pip install --quiet -e ".[tui]" 2>/dev/null || {
    echo "  Trying editable install without extras..."
    "$PYTHON" -m pip install --quiet -e .
}
echo "✓ PROTACXtend package installed"

# ── 4. Verify ──
echo ""
echo "Verifying TUI loads..."
VERIFY=$("$PYTHON" -c "
from synglue_agent.tui.app import PROTACXtendTUI, AGENT_PIPELINE
print(f'OK: {len(AGENT_PIPELINE)} agents, TUI class ready')
" 2>&1) || true

if echo "$VERIFY" | grep -q "OK:"; then
    echo "✓ $VERIFY"
else
    echo "WARNING: TUI verification had issues: $VERIFY"
    echo "  The TUI may still work — try: PROTACXtend tui"
fi

# ── 5. Done ──
echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  Setup complete! Usage:"
echo ""
echo "  PROTACXtend              # Launch TUI (on a TTY)"
echo "  PROTACXtend tui          # Explicit TUI launch"
echo "  PROTACXtend tui \"Design CRBN PROTACs for BRD4\""
echo "                           # TUI + immediate workflow run"
echo ""
echo "  PROTACXtend --help       # All commands"
echo "  PROTACXtend status       # System status"
echo "  PROTACXtend ui           # Streamlit web UI"
echo "  PROTACXtend api          # FastAPI backend"
echo "═══════════════════════════════════════════════════════════"
