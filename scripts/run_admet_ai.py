#!/usr/bin/env python3
"""Subprocess entry for ADMET-AI (isolated venv) — JSON in/out.

Used by synglue_agent/tools/admet_integration.py via subprocess so the
main environment never needs torch>=2.8.

Usage:
    python run_admet_ai.py --out result.json "SMILES1" "SMILES2" ...
Writes one JSON object to --out (model logs may pollute stdout).
"""
from __future__ import annotations

import json
import sys


def main() -> int:
    argv = sys.argv[1:]
    out_path = None
    if argv and argv[0] == "--out":
        out_path = argv[1]
        argv = argv[2:]
    if not argv:
        _emit(out_path, {"ok": False, "error": "no SMILES given"})
        return 2
    try:
        from admet_ai import ADMETModel
        model = ADMETModel()
        smiles_list = sys.argv[1:]
        df = model.predict(smiles_list)
        results = []
        for smiles in smiles_list:
            if smiles not in df.index:
                continue
            row = df.loc[smiles]
            endpoints = {}
            for name in row.index:
                endpoints[str(name)] = _to_jsonable(row[name])
            results.append({"smiles": smiles, "endpoints": endpoints})
        _emit(out_path, {"ok": True, "results": results})
        return 0
    except Exception as exc:  # noqa: BLE001
        _emit(out_path, {"ok": False, "error": str(exc)[:500]})
        return 1


def _emit(out_path, payload):
    if out_path:
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh)
    else:
        print(json.dumps(payload))


def _to_jsonable(value):
    try:
        import numpy as np
        if isinstance(value, np.generic):
            return value.item()
        if isinstance(value, np.ndarray):
            return value.tolist()
    except Exception:  # noqa: BLE001
        pass
    try:
        import pandas as pd
        if isinstance(value, pd.Timestamp):
            return value.isoformat()
    except Exception:  # noqa: BLE001
        pass
    return value


if __name__ == "__main__":
    sys.exit(main())
