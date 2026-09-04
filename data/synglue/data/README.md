# data/synglue/data — derived caches vs curated inputs

| File | Type | In git? |
|---|---|---|
| `e3_ligand.csv` | curated E3-ligand SMILES list (input) | ✅ committed |
| `grover_warhead.csv` | **derived** — GROVER embeddings of warheads | ❌ gitignored (`.gitignore`: `data/synglue/data/grover_*.csv`) |
| `grover_e3.csv` | **derived** — GROVER embeddings of E3 ligands | ❌ gitignored |

## Why they are not committed
`grover_*.csv` are model-derived embedding caches (hundreds of `Grover_*`
columns; `grover_warhead.csv` alone is ~59 MB > GitHub's 50 MB file cap).
They are reproducible from the input SMILES + the GROVER encoder, so they are
treated as generated data, not primary evidence.

## How to regenerate (from SMILES)
The guarded code path lives in `protacxtend/tools/synglue_degradation.py`:

- `extract_grover_embedding(smiles)` — runs the GROVER checkpoint
  (`data/synglue/models/grover_fixed.pt`, guarded optional) and returns the
  embedding vector.
- The SynGlue integration reads `grover_warhead.csv` / `grover_e3.csv`
  (via `MODEL_PATHS["grover_warhead_csv"]` / `["grover_e3_csv"]`) and falls
  back to the committed multitask transformer when the caches/checkpoint are
  absent (see module docs: optional RF/grover artifacts are guarded extras).

Regeneration command (run only when the GROVER checkpoint is present):

```bash
python - <<'EOF'
import pandas as pd
from protacxtend.tools.synglue_degradation import extract_grover_embedding
# warheads: every SMILES in the curated warhead sources; e3: data/synglue/data/e3_ligand.csv
# write rows: [smiles, Grover_0 .. Grover_{d-1}] -> grover_warhead.csv / grover_e3.csv
EOF
```

Notes:
- Do **not** force-add these files back; the CI artifact job must not depend on them.
- If a future release ships the GROVER checkpoint, regenerate the caches and
  either (a) keep them gitignored and build at install time, or (b) store them
  via Git LFS (`git lfs track "data/synglue/data/grover_*.csv"`) — never plain
  git for a 59 MB derived file.
