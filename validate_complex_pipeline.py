#!/usr/bin/env python3
"""Standalone entry point for the end-to-end scientific validation pipeline.

    python validate_complex_pipeline.py \
        --target target.pdb --ligand ligand.sdf [--partner partner.pdb] \
        --mode fast --replicas 2 --output validation_run/

Equivalent to `protacxtend validate-complex ...`.
"""

from __future__ import annotations

import sys

from protacxtend.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["validate-complex", *sys.argv[1:]]))
