#!/usr/bin/env python
"""Generate the square, fully-labelled E1–E8 experiment-closure figures.

Reads the closure matrix in :mod:`protacxtend.validation.closure_figures` and
writes PNGs plus the plotted values as CSV to ``benchmark_results/figures/``.

Every panel is square with an explicit x label and y label (checked by
``tests/test_figure_quality.py``). Engineering closure and scientific closure
are plotted separately; no pre-gold score is drawn as accuracy.

Usage::

    python scripts/plot_experiment_closure.py
    python scripts/plot_experiment_closure.py --out-dir outputs/closure_figures
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from protacxtend.validation.closure_figures import write_closure_figures  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=ROOT / "benchmark_results" / "figures")
    args = parser.parse_args()
    written = write_closure_figures(args.out_dir)
    for name, path in written.items():
        print(f"{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
