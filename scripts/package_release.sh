#!/usr/bin/env bash
# PROTACXtend release packer.
#
# Builds a portable, version-pinned release bundle containing:
#   - wheel + sdist of protacxtend
#   - the toolkit source-of-truth (TOOLKIT_TRUTH.xlsx / .md)
#   - the capability inventory workbook + audit
#   - requirements.txt / pyproject.toml / environment snapshot
#   - SHA256SUMS + RELEASE_MANIFEST.json (tool + dataset + dependency versions)
#
# Usage:
#   scripts/package_release.sh [--out DIR] [--no-build] [--tar]
#
# Options:
#   --out DIR     output root (default: <repo>/dist)
#   --no-build    skip wheel/sdist build (package existing dist/*)
#   --tar         also create a .tar.gz of the release directory
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/dist"
DO_BUILD=1
DO_TAR=0
while [ $# -gt 0 ]; do
  case "$1" in
    --out) OUT="$2"; shift 2;;
    --no-build) DO_BUILD=0; shift;;
    --tar) DO_TAR=1; shift;;
    *) echo "package_release: unknown option $1" >&2; exit 2;;
  esac
done

log() { printf '  [release] %s\n' "$*"; }

VERSION="$(python3 -c "import re,sys; print(re.search(r'__version__\s*=\s*\"([^\"]+)\"', open('$ROOT/protacxtend/__init__.py').read()).group(1))")"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
REL="$OUT/protacxtend-${VERSION}-${STAMP}"
mkdir -p "$REL/artifacts" "$REL/docs" "$REL/inventory" "$REL/repro"

log "PROTACXtend $VERSION → $REL"

# ── build wheel + sdist (run from /tmp; the repo 'build/' dir shadows PyPA build) ──
if [ "$DO_BUILD" = "1" ]; then
  log "building wheel + sdist …"
  if (cd /tmp && python3 -m build --version >/dev/null 2>&1); then
    (cd /tmp && python3 -m build --outdir "$REL/artifacts" "$ROOT")
  else
    log "PyPA 'build' not installed — falling back to pip wheel (wheel only)"
    python3 -m pip wheel --no-deps --wheel-dir "$REL/artifacts" "$ROOT"
  fi
else
  log "skipping build; copying existing dist/*"
  cp -f "$ROOT"/dist/*.whl "$ROOT"/dist/*.tar.gz "$REL/artifacts/" 2>/dev/null || true
fi

# ── source-of-truth + inventory ─────────────────────────────────────────
log "regenerating toolkit truth …"
python3 - "$ROOT" <<'PY' || log "warning: truth generation failed"
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from protacxtend.toolkit.truth import write_truth
xlsx, md = write_truth(compute_hash=False)
Path(sys.argv[1], "TOOLKIT_TRUTH.md").write_text(md.read_text(encoding="utf-8"), encoding="utf-8")
print(f"  truth → {xlsx}")
PY
cp -f "$ROOT/TOOLKIT_TRUTH.md" "$REL/docs/" 2>/dev/null || true
cp -f "$ROOT/analysis/inventory/PROTACXtend_Toolkit_Truth.xlsx" "$REL/docs/" 2>/dev/null || true
cp -f "$ROOT/analysis/inventory/PROTACXtend_Capability_Inventory.xlsx" "$REL/inventory/" 2>/dev/null || true
cp -f "$ROOT/analysis/inventory/"*.csv "$REL/inventory/" 2>/dev/null || true
cp -f "$ROOT/analysis/audit/INVENTORY_AUDIT.md" "$ROOT/analysis/audit/ESCALATION_AUDIT.md" "$REL/docs/" 2>/dev/null || true

# ── repro files ─────────────────────────────────────────────────────────
cp -f "$ROOT/requirements.txt" "$ROOT/pyproject.toml" "$ROOT/MANIFEST.in" "$ROOT/Dockerfile" "$REL/repro/" 2>/dev/null || true
python3 -m pip freeze > "$REL/repro/pip-freeze.txt" 2>/dev/null || true
conda list -p "$(dirname "$(dirname "$(command -v python3)")")" > "$REL/repro/conda-list.txt" 2>/dev/null || true

# ── release manifest (versions) ─────────────────────────────────────────
log "writing RELEASE_MANIFEST.json …"
python3 - "$ROOT" "$REL" "$VERSION" <<'PY'
import json, sys, platform
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, sys.argv[1])
root, rel, version = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
manifest = {
    "package": "protacxtend",
    "version": version,
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "python": platform.python_version(),
    "platform": platform.platform(),
    "toolkit": {},
    "datasets": [],
}
try:
    from protacxtend.toolkit.truth import tool_rows, dataset_rows
    manifest["toolkit"] = {
        "tools_installed": [{"name": r["tool_name"], "version": r["version"],
                             "env": r["provider_env"], "method": r["provision_method"]}
                            for r in tool_rows() if r["installed"]],
    }
    manifest["datasets"] = [{"asset": d["asset"], "hash": d["content_hash"],
                             "kind": d["hash_kind"], "size": d["size"]}
                            for d in dataset_rows(compute_hash=False)]
except Exception as exc:
    manifest["toolkit_error"] = str(exc)
(rel / "RELEASE_MANIFEST.json").write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
PY

# ── checksums ───────────────────────────────────────────────────────────
log "computing SHA256SUMS …"
( cd "$REL" && find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS )

if [ "$DO_TAR" = "1" ]; then
  log "creating tarball …"
  ( cd "$OUT" && tar -czf "$(basename "$REL").tar.gz" "$(basename "$REL")" )
fi

log "release bundle ready: $REL"
find "$REL" -maxdepth 2 -type f | sed "s|$REL/|    |" | sort
