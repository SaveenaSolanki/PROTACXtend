#!/usr/bin/env bash
# PROTACXtend — universal one-command installer.
#
#   curl -fsSL https://raw.githubusercontent.com/the-ahuja-lab/PROTACXtend/main/scripts/install.sh | bash
#
# Options (pass after `bash -s --`):
#   --profile minimal|scientific|full   minimal = core CLI+setup (default);
#                                        scientific = + rdkit/chemprop/torch stack
#   --prefix DIR                         install root (default ~/.protacxtend/venv)
#   --bin DIR                            wrapper dir (default ~/.local/bin)
#   --source-dir PATH                    install from a local repo copy (dev/test)
#   --source-url URL                     git source (default GitHub repo)
#   --no-wrapper                         skip symlinking wrappers
#   --yes                                non-interactive (auto-confirm prompts)
#
# Env overrides: PROTACXTEND_VENV, PROTACXTEND_BIN, PROTACXTEND_SOURCE_URL,
#                PROTACXTEND_SOURCE_DIR, PROTACXTEND_PROFILE.
#
# The installer NEVER stores LLM API keys. `protacxtend setup` is run by the
# user afterwards (API / Local / Configure later).
set -euo pipefail

INSTALLER_URL="https://raw.githubusercontent.com/the-ahuja-lab/PROTACXtend/main/scripts/install.sh"
DEFAULT_SOURCE_URL="https://github.com/the-ahuja-lab/PROTACXtend.git"
START_EPOCH="$(date +%s)"

# ── option parsing ─────────────────────────────────────────────────────
PROFILE="${PROTACXTEND_PROFILE:-minimal}"
PREFIX="${PROTACXTEND_VENV:-}"
BIN_DIR="${PROTACXTEND_BIN:-}"
SOURCE_URL="${PROTACXTEND_SOURCE_URL:-$DEFAULT_SOURCE_URL}"
SOURCE_DIR="${PROTACXTEND_SOURCE_DIR:-}"
NO_WRAPPER=0
ASSUME_YES=0
while [ $# -gt 0 ]; do
  case "$1" in
    --profile) PROFILE="$2"; shift 2;;
    --prefix) PREFIX="$2"; shift 2;;
    --bin) BIN_DIR="$2"; shift 2;;
    --source-url) SOURCE_URL="$2"; shift 2;;
    --source-dir) SOURCE_DIR="$2"; shift 2;;
    --no-wrapper) NO_WRAPPER=1; shift;;
    --yes) ASSUME_YES=1; shift;;
    *) echo "install: unknown option $1"; exit 2;;
  esac
done

log() { printf '  [install] %s\n' "$*"; }
die() { printf '  [install] ERROR: %s\n' "$*" >&2; exit 1; }

command -v python3 >/dev/null || die "python3 not found (need >= 3.10)"
PYVER="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' \
  || die "python3 >= 3.10 required (found $PYVER)"
command -v pip3 >/dev/null || python3 -m pip --version >/dev/null 2>&1 \
  || die "pip not available"
python3 -c 'import venv' 2>/dev/null || die "python venv module unavailable"

if [ -z "$PREFIX" ]; then
  PREFIX="$HOME/.protacxtend/venv"
fi
if [ -z "$BIN_DIR" ]; then
  BIN_DIR="$HOME/.local/bin"
fi

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# ── source ─────────────────────────────────────────────────────────────
echo ""
log "PROTACXtend universal installer"
log "  profile      $PROFILE   (minimal = core CLI+setup+doctor)"
log "  python       $PYVER  ($(command -v python3))"
log "  venv prefix  $PREFIX"
log "  wrappers     $BIN_DIR"

case "$PROFILE" in
  minimal|scientific|full) ;;
  *) die "unknown profile '$PROFILE' (minimal|scientific|full)";;
esac

SRC="$WORK/src"
if [ -n "$SOURCE_DIR" ]; then
  [ -d "$SOURCE_DIR" ] || die "source dir not found: $SOURCE_DIR"
  cp -a "$SOURCE_DIR/." "$SRC/"
  log "  source       local copy of $SOURCE_DIR"
else
  command -v git >/dev/null || die "git required to fetch $SOURCE_URL"
  log "  source       $SOURCE_URL"
  git clone --depth 1 --quiet "$SOURCE_URL" "$SRC" 2>/dev/null \
    || die "git clone failed — check network / PROTACXTEND_SOURCE_URL"
fi
[ -f "$SRC/pyproject.toml" ] || die "source has no pyproject.toml (not the PROTACXtend repo?)"

# ── venv + install ─────────────────────────────────────────────────────
mkdir -p "$PREFIX" "$BIN_DIR"
if [ ! -x "$PREFIX/bin/python" ]; then
  log "creating virtualenv at $PREFIX …"
  python3 -m venv "$PREFIX"
fi
VPY="$PREFIX/bin/python"
"$VPY" -m pip install --quiet --upgrade pip >/dev/null 2>&1 || true

log "installing PROTACXtend (profile=$PROFILE) …"
T0="$(date +%s)"
if [ "$PROFILE" = "full" ] || [ "$PROFILE" = "scientific" ]; then
  "$VPY" -m pip install --quiet "$SRC" || die "pip install failed"
  if [ -f "$SRC/requirements.txt" ]; then
    log "installing scientific stack (rdkit/chemprop/torch …) — this is large"
    "$VPY" -m pip install --quiet -r "$SRC/requirements.txt" || \
      log "warning: scientific extras incomplete — core install is ready; re-run with --profile full"
  fi
else
  "$VPY" -m pip install --quiet "$SRC" || die "pip install failed"
fi
T1="$(date +%s)"
log "package installed in $((T1 - T0))s"

VER="$("$VPY" -c 'import protacxtend; print(protacxtend.__version__)' 2>/dev/null || echo '?')"
log "PROTACXtend $VER ready"

# ── wrappers ───────────────────────────────────────────────────────────
if [ "$NO_WRAPPER" = "0" ]; then
  for name in protacxtend PROTACXtend; do
    WRAP="$BIN_DIR/$name"
    {
      printf '#!/usr/bin/env bash\n'
      printf 'export PROTACXTEND_VENV="%s"\n' "$PREFIX"
      printf 'exec "%s/bin/%s" "$@"\n' "$PREFIX" "$name"
    } > "$WRAP"
    chmod +x "$WRAP"
  done
  log "wrappers installed in $BIN_DIR (add to PATH if needed: export PATH=\"$BIN_DIR:\$PATH\")"
fi

# ── first-run hint ─────────────────────────────────────────────────────
END_EPOCH="$(date +%s)"
mkdir -p "$HOME/.protacxtend"
cat > "$HOME/.protacxtend/install.json" <<EOF
{
  "tool": "PROTACXtend",
  "version": "$VER",
  "profile": "$PROFILE",
  "python": "$PYVER",
  "venv": "$PREFIX",
  "source": "${SOURCE_DIR:-$SOURCE_URL}",
  "installed_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "install_seconds": "$((END_EPOCH - START_EPOCH))"
}
EOF

echo ""
log "INSTALL OK ($((END_EPOCH - START_EPOCH))s, profile=$PROFILE)"
echo ""
echo "  Next steps:"
echo "    1. export PATH=\"$BIN_DIR:\$PATH\"   (add to ~/.bashrc)"
echo "    2. $BIN_DIR/protacxtend setup        # API / Local / Configure later"
echo "    3. $BIN_DIR/protacxtend doctor       # Provider/Model/Auth/Connection/Inference/Status"
echo ""
echo "  curl | bash flow:"
echo "    curl -fsSL $INSTALLER_URL | bash"
echo "    protacxtend setup"
echo ""
