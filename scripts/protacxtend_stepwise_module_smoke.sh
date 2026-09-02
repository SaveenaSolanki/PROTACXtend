#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/outputs/stepwise_module_smoke"
mkdir -p "$OUT"

POSE="$OUT/synthetic_ternary_pose.pdb"
python - "$POSE" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])

def line(serial, name, res, chain, resid, x, y, z, element):
    return (
        f"ATOM  {serial:5d} {name:<4s} {res:>3s} {chain:1s}{resid:4d}    "
        f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00 20.00          {element:>2s}"
    )

path.write_text(
    "\n".join(
        [
            line(1, "CA", "ALA", "A", 1, 0.0, 0.0, 0.0, "C"),
            line(2, "NZ", "LYS", "A", 2, 12.0, 0.0, 0.0, "N"),
            line(3, "CA", "LYS", "A", 2, 11.5, 0.5, 0.0, "C"),
            line(4, "CA", "GLY", "B", 10, 30.0, 0.0, 0.0, "C"),
            line(5, "O", "GLY", "B", 10, 30.5, 0.0, 0.0, "O"),
            line(6, "N", "SER", "B", 11, 31.5, 1.0, 0.0, "N"),
            "END",
        ]
    )
    + "\n",
    encoding="utf-8",
)
PY

cd "$ROOT"

./protacxtend external --action status > "$OUT/01_external_status.json"
./protacxtend dose --alpha 3 --kd-target-nM 40 --kd-e3-nM 80 > "$OUT/02_dose_response.json"
./protacxtend structure --pose "$POSE" --target-chain A --e3-chain B --smiles CCO > "$OUT/03_structure_scores.json"
./protacxtend proteome --target BRD4 --e3 CRBN --cell MM1.S > "$OUT/04_proteome_context.json"
./protacxtend learn --candidates '[{"candidate_id":"A","score":0.7,"uncertainty":0.8},{"candidate_id":"B","score":0.6,"uncertainty":0.4}]' > "$OUT/05_active_learning.json"
./protacxtend context --smiles CCO --poi BRD4 --e3 CRBN --cell MM1.S > "$OUT/06_context_degradation.json"

python - "$OUT" <<'PY'
from pathlib import Path
import json
import sys

out = Path(sys.argv[1])
summary = {"success": True, "artifacts": []}
for path in sorted(out.glob("*.json")):
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        summary["artifacts"].append({"file": str(path), "top_keys": list(payload)[:8]})
    except Exception as exc:
        summary["success"] = False
        summary["artifacts"].append({"file": str(path), "error": str(exc)})
summary_path = out / "summary.json"
summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps(summary, indent=2))
PY

