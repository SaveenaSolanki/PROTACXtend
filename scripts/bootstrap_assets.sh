#!/usr/bin/env bash
# ============================================================================
# bootstrap_assets.sh — restore excluded/external assets for SynGlue v0.3
# ============================================================================
# Usage:
#   ./scripts/bootstrap_assets.sh            # everything
#   ./scripts/bootstrap_assets.sh --aizynth  # only retrosynthesis models
#   ./scripts/bootstrap_assets.sh --se3      # only SE3-PROTACs clone
#   ./scripts/bootstrap_assets.sh --dry-run  # validate URLs, change nothing
#
# Assets (see ASSET_MANIFEST.md for full provenance):
#   [1] USPTO expansion policy    figshare 23086454 (286.2 MB)
#   [2] USPTO templates           figshare 23086457 ( 42.6 MB)
#   [3] ZINC stock                figshare 23086469 (632.5 MB)
#   [8] SE3-PROTACs               github.com/drugparadigm/SE3-protacs
# ============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AIZYNTN_DIR="$ROOT/data/retrosynthesis/models/aizynth"
SE3_DIR="$ROOT/data/protac_repos/repos/SE3-protacs"
CHECKSUMS="$ROOT/ASSET_MANIFEST.checksums.json"
MODE="${1:-all}"

mkdir -p "$AIZYNTN_DIR"

declare -A URLS=(
  [uspto_policy.hdf5]="https://ndownloader.figshare.com/files/23086454"
  [uspto_templates.hdf5]="https://ndownloader.figshare.com/files/23086457"
  [zinc_stock.hdf5]="https://ndownloader.figshare.com/files/23086469"
  [uspto_model.onnx]="https://zenodo.org/api/records/10548209/files/uspto_stereo_expansion_model.onnx/content"
  [uspto_templates.csv.gz]="https://zenodo.org/api/records/10548209/files/uspto_stereo_unique_templates.csv.gz/content"
)
declare -A SIZES=(
  [uspto_policy.hdf5]=286176870
  [uspto_templates.hdf5]=42580000
  [zinc_stock.hdf5]=632510000
  [uspto_model.onnx]=4670000
  [uspto_templates.csv.gz]=20000
)

sha256_file() { sha256sum "$1" | awk '{print $1}'; }

record_checksum() {
  local name="$1" hash="$2"
  if [ -f "$CHECKSUMS" ]; then
    python3 -c "
import json
p='$CHECKSUMS'
d=json.load(open(p))
d['$name']='$hash'
json.dump(d, open(p,'w'), indent=2)
"
  else
    printf '{\n  "%s": "%s"\n}\n' "$name" "$hash" > "$CHECKSUMS"
  fi
  echo "    recorded sha256($name) -> $CHECKSUMS"
}

verify_checksum() {
  local name="$1" file="$2"
  if [ -f "$CHECKSUMS" ]; then
    local want
    want=$(python3 -c "import json;print(json.load(open('$CHECKSUMS')).get('$name',''))" 2>/dev/null || true)
    if [ -n "$want" ]; then
      local got; got=$(sha256_file "$file")
      if [ "$got" != "$want" ]; then
        echo "    FAIL sha256 mismatch for $name (got $got, want $want)" >&2
        return 1
      fi
      echo "    sha256 OK for $name"
    fi
  fi
}

download_one() {
  local name="$1" url="$2" expected_size="$3" dest="$AIZYNTN_DIR/$name"
  if [ -f "$dest" ] && [ "$(stat -c%s "$dest")" -ge "$expected_size" ]; then
    echo "  [skip] $name already present ($(du -h "$dest" | cut -f1))"
    verify_checksum "$name" "$dest" || true
    return 0
  fi
  echo "  [get]  $name <- $url"
  curl -fL --retry 3 -o "$dest" "$url"
  local actual; actual=$(stat -c%s "$dest")
  if [ "$actual" -lt "$expected_size" ]; then
    echo "    ERROR: $name downloaded size $actual < expected $expected_size" >&2
    rm -f "$dest"; return 1
  fi
  record_checksum "$name" "$(sha256_file "$dest")"
}

echo "== SynGlue v0.3 asset bootstrap =="
echo "   root: $ROOT"
echo "   mode: $MODE"

if [ "$MODE" = "--dry-run" ] || [ "$MODE" = "--aizynth" ] || [ "$MODE" = "all" ]; then
  if [ "$MODE" = "--dry-run" ]; then
    echo "== dry-run: validating figshare URLs (1 KB ranged GET) =="
    for name in "${!URLS[@]}"; do
      code=$(curl -sL -r 0-1023 -o /dev/null -w "%{http_code}" "${URLS[$name]}")
      echo "   $code  $name  <- ${URLS[$name]}"
    done
    echo "== dry-run done (no files written) =="
    exit 0
  fi
  echo "== [1-3] AiZynthFinder public data =="
  echo "   figshare 12334577 (full USPTO, keras hdf5 — needs tensorflow-based aizynthfinder)"
  echo "   zenodo 10548209   (official USPTO stereo model, ONNX — works everywhere)"
  for name in uspto_policy.hdf5 uspto_templates.hdf5 zinc_stock.hdf5 uspto_model.onnx uspto_templates.csv.gz; do
    download_one "$name" "${URLS[$name]}" "${SIZES[$name]}"
  done
  echo "   done: $AIZYNTN_DIR"
fi

if [ "$MODE" = "--se3" ] || [ "$MODE" = "all" ]; then
  echo "== [8] SE3-PROTACs clone =="
  if [ -d "$SE3_DIR/.git" ]; then
    echo "  [skip] SE3-protacs already cloned at $SE3_DIR"
  else
    mkdir -p "$(dirname "$SE3_DIR")"
    git clone --depth 1 https://github.com/drugparadigm/SE3-protacs "$SE3_DIR"
  fi
fi

echo ""
echo "== remaining optional assets =="
echo "  #5  grover_fixed.pt (409 MB, locally trained):"
echo "        retrain via SynGlue_Py GROVER pipeline OR copy from the original"
echo "        machine to SynGlue_Py/models/grover_fixed.pt"
echo "  #12 conda environments: conda env create -f data/protac_repos/env_specs/<env>__environment.yml"
echo "        (see data/protac_repos/env_specs/INSTALL_STATUS.md)"
echo "  #13 SynGlue training dumps: regenerate via SynGlue_Py/Architecture_Code (runtime not affected)"
echo ""
echo "== post-bootstrap check =="
python3 - "$AIZYNTN_DIR" << 'PYEOF'
import sys
from pathlib import Path
d = Path(sys.argv[1])
need = ["uspto_model.onnx", "uspto_templates.csv.gz", "zinc_stock.hdf5"]
ok = all((d / n).exists() for n in need)
print("   aizynth models complete:", "YES" if ok else "NO (retrosynthesis will degrade to RAscore-only)")
if not ok:
    for n in need:
        print(f"     - {'OK  ' if (d/n).exists() else 'MISS'} {n}")
PYEOF
echo ""
echo "== bootstrap finished =="

if [ "$MODE" = "--repos" ] || [ "$MODE" = "all" ]; then
  echo "== [9] upstream PROTAC repos (clone from registry) =="
  REGISTRY="$ROOT/data/protac_repos/protac_repo_registry.csv"
  if [ -f "$REGISTRY" ]; then
    WANT="${PROTACPILOT_REPOS:-}"
    n=0
    while IFS=',' read -r name url localpath rest; do
      if [[ "$url" == https* ]]; then
        if [ -n "$WANT" ] && ! [[ ",$WANT," == *",$name,"* ]]; then
          continue
        fi
        target="$ROOT/$localpath"
        if [ -d "$target/.git" ]; then
          echo "  [skip] $name (already cloned)"
        else
          echo "  [get]  $name <- $url"
          mkdir -p "$(dirname "$target")"
          git clone -q --depth 1 "$url" "$target" || echo "    WARN: clone failed for $name"
          n=$((n+1))
        fi
      fi
    done < "$REGISTRY"
    echo "  cloned $n new repos"
  else
    echo "  registry missing: $REGISTRY"
  fi
fi

if [ "$MODE" = "--admet" ] || [ "$MODE" = "all" ]; then
  echo "== ADMET-AI isolated venv =="
  if [ -x "$ROOT/.venvs/admet/bin/python" ]; then
    echo "  [skip] .venvs/admet already present"
  else
    echo "  [get]  creating .venvs/admet + pip install admet_ai==2.0.1 (~2 GB, once)"
    python3 -m venv "$ROOT/.venvs/admet"
    "$ROOT/.venvs/admet/bin/pip" install -q --upgrade pip
    "$ROOT/.venvs/admet/bin/pip" install -q admet_ai==2.0.1
  fi
fi
