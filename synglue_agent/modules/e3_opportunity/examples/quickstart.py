"""Module 6 quickstart — rank E3 ligases for a POI."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from synglue_agent.modules.e3_opportunity import rank_e3_ligases


def main() -> None:
    out = rank_e3_ligases("BRD4", cell_line="K562", top_k=10)
    print(f"POI {out['poi']} (gene {out['poi_gene']}) in {out['cell_line']}")
    for c in out["candidates"]:
        print(f"  {c['rank']:>2} {c['e3_gene']:<8} {c['e3_family']:<6} "
              f"score={c['overall_rank_score']:.3f} conf={c['overall_confidence']:.2f} "
              f"{c['verdict']:<20} ctx={c['cell_context_score']} "
              f"recruiter={c['recruiter_available']}")
        print(f"      next test: {c['recommended_next_test']}")


if __name__ == "__main__":
    main()
