#!/usr/bin/env python
"""Write reviewed BRD4/EGFR/KRAS literature chemical-identity artifacts."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from protacxtend.literature.chemical_identity import write_reviewed_corpus_artifacts


def main() -> int:
    out = write_reviewed_corpus_artifacts(ROOT / "outputs/priority_agent_audit/literature_identity")
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
