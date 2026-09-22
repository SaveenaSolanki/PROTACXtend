"""Benchmark provenance and resource accounting.

Every benchmark row written by the validation harness must be reproducible:
who ran it, on what hardware, with which software/model version, using which
command/configuration/seed, for how long, and where the raw output lives.

This module centralises that bookkeeping so no benchmark can silently omit it.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


def file_sha256(path: str | Path, *, limit: int | None = None) -> str:
    p = Path(path)
    if not p.exists() or not p.is_file():
        return ""
    h = hashlib.sha256()
    with p.open("rb") as fh:
        read = 0
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
            read += len(chunk)
            if limit and read >= limit:
                break
    return h.hexdigest()


def git_commit(root: str | Path | None = None) -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(root or os.getcwd()),
                             capture_output=True, text=True, timeout=10)
        return out.stdout.strip() if out.returncode == 0 else ""
    except Exception:
        return ""


def gpu_inventory() -> list[dict[str, Any]]:
    gpus: list[dict[str, Any]] = []
    nvidia = shutil.which("nvidia-smi")
    if not nvidia:
        return gpus
    try:
        out = subprocess.run(
            [nvidia, "--query-gpu=index,name,memory.total,driver_version", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=20)
        for line in out.stdout.strip().splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 4:
                gpus.append({"index": parts[0], "name": parts[1], "memory": parts[2],
                             "driver": parts[3]})
    except Exception:
        pass
    return gpus


def software_versions() -> dict[str, str]:
    versions: dict[str, str] = {"python": sys.version.split()[0]}
    for mod in ("rdkit", "numpy", "pandas", "scipy", "Bio", "openmm", "mdtraj", "torch"):
        try:
            m = __import__(mod)
            versions[mod] = str(getattr(m, "__version__", "unknown"))
        except Exception:
            versions[mod] = ""
    from protacxtend.toolkit.environments import find_executable

    for exe, args in (("vina", ["--version"]), ("gnina", ["--version"]),
                      ("fpocket", ["-h"]), ("gmx_MMPBSA", ["--version"])):
        try:
            found = find_executable(exe)
            if not found:
                versions[exe] = "not_found"
                continue
            proc = subprocess.run([found[0], *args], capture_output=True, text=True, timeout=60)
            text = (proc.stdout or proc.stderr or "").strip().splitlines()
            versions[exe] = text[0][:120] if text else found[0]
        except Exception:
            versions[exe] = "probe_failed"
    try:
        import protacxtend
        versions["protacxtend"] = getattr(protacxtend, "__version__", "")
    except Exception:
        versions["protacxtend"] = ""
    return versions


def host_fingerprint() -> dict[str, Any]:
    cpu = ""
    try:
        with open("/proc/cpuinfo") as fh:
            for line in fh:
                if line.lower().startswith("model name"):
                    cpu = line.split(":", 1)[1].strip()
                    break
    except Exception:
        cpu = platform.processor()
    mem_gb = None
    try:
        with open("/proc/meminfo") as fh:
            for line in fh:
                if line.startswith("MemTotal"):
                    mem_gb = round(int(line.split()[1]) / 1024 / 1024, 1)
                    break
    except Exception:
        pass
    return {
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "cpu": cpu,
        "n_cpu": os.cpu_count(),
        "memory_gb": mem_gb,
        "gpus": gpu_inventory(),
    }


class ResourceMonitor:
    """Context manager sampling CPU/memory for a benchmark call."""

    def __init__(self) -> None:
        self.start_wall = time.time()
        self.start_cpu = time.process_time()
        self.peak_rss_mb = 0.0
        self.cpu_percent_mean = 0.0
        self._psutil = None
        self._proc = None
        self._samples: list[float] = []
        try:
            import psutil

            self._psutil = psutil
            self._proc = psutil.Process(os.getpid())
        except Exception:
            self._psutil = None

    def __enter__(self) -> "ResourceMonitor":
        if self._proc is not None:
            try:
                self._proc.cpu_percent(None)
            except Exception:
                pass
        return self

    def sample(self) -> None:
        if self._proc is None:
            return
        try:
            rss = self._proc.memory_info().rss / 1024 / 1024
            self.peak_rss_mb = max(self.peak_rss_mb, rss)
            self._samples.append(self._proc.cpu_percent(None))
        except Exception:
            pass

    def __exit__(self, *exc: Any) -> None:
        self.sample()
        self.wall_s = round(time.time() - self.start_wall, 3)
        self.cpu_s = round(time.process_time() - self.start_cpu, 3)
        if self._samples:
            self.cpu_percent_mean = round(sum(self._samples) / len(self._samples), 2)

    def to_dict(self) -> dict[str, Any]:
        try:
            import psutil

            disk = psutil.disk_usage(str(Path.home())).free / 1024 ** 3
        except Exception:
            disk = None
        return {
            "wall_s": getattr(self, "wall_s", round(time.time() - self.start_wall, 3)),
            "cpu_s": getattr(self, "cpu_s", round(time.process_time() - self.start_cpu, 3)),
            "peak_rss_mb": round(self.peak_rss_mb, 1),
            "cpu_percent_mean": self.cpu_percent_mean,
            "disk_free_gb": round(disk, 1) if disk is not None else None,
        }


def benchmark_provenance(
    *,
    dataset: str,
    source: str,
    structure_id: str = "",
    ligand_id: str = "",
    software: str = "",
    software_version: str = "",
    model: str = "",
    model_version: str = "",
    command: str = "",
    config: dict[str, Any] | None = None,
    seed: int | None = None,
    output_path: str = "",
) -> dict[str, Any]:
    return {
        "dataset": dataset,
        "source": source,
        "structure_id": structure_id,
        "ligand_id": ligand_id,
        "software": software,
        "software_version": software_version,
        "model": model,
        "model_version": model_version,
        "command": command,
        "config": json.dumps(config or {}, sort_keys=True),
        "seed": seed if seed is not None else "",
        "hardware": json.dumps(host_fingerprint(), sort_keys=True),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "output_path": output_path,
        "code_commit": git_commit(),
    }


__all__ = [
    "file_sha256", "git_commit", "gpu_inventory", "software_versions",
    "host_fingerprint", "ResourceMonitor", "benchmark_provenance",
]
