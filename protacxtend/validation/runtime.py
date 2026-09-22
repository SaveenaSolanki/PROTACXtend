"""Runtime and resource accounting consolidated across benchmarks."""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any

from protacxtend.audit.provenance import ResourceMonitor, host_fingerprint, software_versions
from protacxtend.validation.datasets import ROOT
from protacxtend.validation.io import write_summary_json

OUT = ROOT / "results" / "benchmarks" / "runtime"
BENCH = ROOT / "results" / "benchmarks"


def _load_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text())
        return payload.get("rows", [])
    except Exception:
        return []


def consolidate() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for json_file in sorted(BENCH.glob("*/**/*rows*.json")):
        for r in _load_rows(json_file):
            if "runtime_s" not in r and "wall_s" not in r:
                continue
            rows.append({
                "benchmark": r.get("benchmark") or json_file.parent.name,
                "component": r.get("structure_id") or r.get("capability") or "",
                "engine": r.get("engine") or r.get("software") or "",
                "status": r.get("status"),
                "runtime_s": r.get("runtime_s"),
                "wall_s": r.get("wall_s"),
                "cpu_s": r.get("cpu_s"),
                "peak_rss_mb": r.get("peak_rss_mb"),
                "output_path": r.get("output_path"),
            })
    return rows


def benchmark_overhead() -> list[dict[str, Any]]:
    """T_total (facade+router+envelope) vs T_backend (raw handler)."""
    from protacxtend.scientific_backends import chemistry, detect_pockets

    rows: list[dict[str, Any]] = []

    def _measure(label: str, backend_fn, facade_fn, repeats: int = 5) -> None:
        tb, tt = [], []
        for _ in range(repeats):
            t0 = time.time(); backend_fn(); tb.append(time.time() - t0)
        for _ in range(repeats):
            t0 = time.time(); facade_fn(); tt.append(time.time() - t0)
        b, total = min(tb), min(tt)
        rows.append({"label": label, "t_backend_s": round(b, 5), "t_total_s": round(total, 5),
                     "t_orchestration_s": round(max(0.0, total - b), 5),
                     "overhead_pct": round(100 * max(0.0, total - b) / max(total, 1e-9), 3)})

    from protacxtend.scientific_backends.backends.chemistry import rdkit_descriptors

    _measure("rdkit_descriptor", lambda: rdkit_descriptors("CCO"), lambda: chemistry("CCO"))
    return rows


def gpu_utilization_sample(seconds: int = 5) -> list[dict[str, Any]]:
    import subprocess

    nvidia = shutil.which("nvidia-smi")
    if not nvidia:
        return []
    samples = []
    for _ in range(seconds):
        try:
            out = subprocess.run(
                [nvidia, "--query-gpu=index,utilization.gpu,utilization.memory,memory.used",
                 "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=10)
            for line in out.stdout.strip().splitlines():
                parts = [p.strip() for p in line.split(",")]
                if len(parts) == 4:
                    samples.append({"index": parts[0], "gpu_util_pct": float(parts[1]),
                                    "mem_util_pct": float(parts[2]), "mem_used_mb": float(parts[3])})
        except Exception:
            pass
        time.sleep(1)
    # aggregate
    agg: dict[str, dict[str, Any]] = {}
    for s in samples:
        a = agg.setdefault(s["index"], {"index": s["index"], "n": 0})
        a["n"] += 1
        for k in ("gpu_util_pct", "mem_util_pct", "mem_used_mb"):
            a[k] = a.get(k, 0.0) + s[k]
    for a in agg.values():
        for k in ("gpu_util_pct", "mem_util_pct", "mem_used_mb"):
            a[k] = round(a[k] / a["n"], 2)
        a["peak_mem_used_mb"] = max(s["mem_used_mb"] for s in samples if s["index"] == a["index"])
    return list(agg.values())


def run() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = consolidate()
    overhead = benchmark_overhead()
    gpu = gpu_utilization_sample(3)
    disk = {}
    try:
        total, used, free = shutil.disk_usage(str(ROOT))
        disk = {"total_gb": round(total / 1024 ** 3, 1), "used_gb": round(used / 1024 ** 3, 1),
                "free_gb": round(free / 1024 ** 3, 1)}
    except Exception:
        pass
    results_size = 0
    try:
        results_size = round(sum(p.stat().st_size for p in BENCH.rglob("*") if p.is_file()) / 1024 ** 2, 1)
    except Exception:
        pass
    summary = {
        "host": host_fingerprint(), "software": software_versions(),
        "n_resource_rows": len(rows), "overhead": overhead, "gpu_sample": gpu,
        "disk": disk, "benchmark_output_size_mb": results_size,
    }
    write_summary_json(OUT / "runtime_summary.json", summary)
    _write_csv(OUT / "resource_table.csv", rows)
    _write_csv(OUT / "orchestration_overhead.csv", overhead)
    print(json.dumps(summary, indent=2)[:1500])
    return summary


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    import csv

    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("")
        return
    keys: list[str] = []
    for r in rows:
        for k in r:
            if k not in keys:
                keys.append(k)
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


__all__ = ["run", "OUT", "consolidate"]
