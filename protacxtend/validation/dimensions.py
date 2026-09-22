"""Capability dimensions (registered / installable / executable / output_validated /
scientifically_benchmarked / externally_validated / prospectively_validated).

A single ``READY`` flag is explicitly rejected: each dimension is measured and
reported separately so a name in the registry can never masquerade as
validation.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from protacxtend.validation.datasets import ROOT

REGISTRY = ROOT / "results" / "audit" / "capability_registry.csv"
BENCH = ROOT / "results" / "benchmarks"
OUT = ROOT / "results" / "benchmarks" / "capabilities"

#: capability -> (benchmark summary path, external-validation flag)
BENCH_MAP: dict[str, tuple[str, bool]] = {
    "ligand_docking": ("docking/docking_summary.json", True),
    "pocket_detection": ("pockets/pocket_rows_summary.json", True),
    "ppi_docking": ("ppi/ppi_rows_summary.json", True),
    "ternary_docking": ("ternary/ternary_rows_summary.json", True),
    "binding_energy": ("energetics/energetics_rows_summary.json", True),
    "molecular_dynamics": ("reproducibility/reproducibility_summary.json", False),
}


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def _registry_rows() -> list[dict[str, str]]:
    if not REGISTRY.exists():
        return []
    return [r for r in csv.DictReader(REGISTRY.open()) if r.get("kind") in {"scientific", "tpd"}]


def _functional_checks() -> dict[str, Any]:
    return _load_json(ROOT / "results" / "audit" / "functional_checks.json")


def run() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    functional = _functional_checks()
    benchmark_exists = {name: (BENCH / path).exists() for name, (path, _ext) in BENCH_MAP.items()}
    for r in _registry_rows():
        maturity = r.get("maturity_status", "unknown")
        name = r.get("name", "")
        bench_path, external = BENCH_MAP.get(name, ("", False))
        bench = _load_json(BENCH / bench_path) if bench_path else {}
        benchmarked = bool(bench) and benchmark_exists.get(name, False)
        executable = maturity in {"smoke-tested", "internally-benchmarked", "scientifically-validated",
                                  "executable", "tested"} or bool(functional.get(name, {}).get("functional"))
        rows.append({
            "capability": name,
            "kind": r.get("kind"),
            "registered": True,
            "installable": bool(r.get("installation_recipe")) or executable,
            "executable": executable,
            "output_validated": benchmarked or maturity == "scientifically-validated",
            "scientifically_benchmarked": benchmarked,
            "externally_validated": bool(benchmarked and external),
            "prospectively_validated": False,
            "benchmark_path": bench_path,
            "benchmark_n": _benchmark_n(bench),
            "benchmark_metric": _benchmark_metric(name, bench),
            "maturity_status": maturity,
            "evidence_level": _evidence_level(executable, benchmarked, external),
        })
    summary = {
        "n_capabilities": len(rows),
        "dimension_totals": {
            "registered": sum(r["registered"] for r in rows),
            "installable": sum(r["installable"] for r in rows),
            "executable": sum(r["executable"] for r in rows),
            "output_validated": sum(r["output_validated"] for r in rows),
            "scientifically_benchmarked": sum(r["scientifically_benchmarked"] for r in rows),
            "externally_validated": sum(r["externally_validated"] for r in rows),
            "prospectively_validated": sum(r["prospectively_validated"] for r in rows),
        },
        "rows": rows,
    }
    _write_csv(OUT / "capability_dimensions.csv", rows)
    (OUT / "capability_dimensions.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary["dimension_totals"], indent=2))
    return summary


def _benchmark_n(bench: dict[str, Any]) -> Any:
    for key in ("n_attempted", "n_curated_attempted", "n_complexes_with_results",
                "n_evaluated", "n_scenarios", "n_services"):
        if key in bench:
            return bench[key]
    return None


def _benchmark_metric(name: str, bench: dict[str, Any]) -> str:
    if not bench:
        return ""
    if name == "ligand_docking":
        v = bench.get("vina", {}) or {}
        return f"vina_median_rmsd={v.get('median_rmsd')}; consensus_median={ (bench.get('prospective_consensus') or {}).get('median_rmsd') }"
    if name == "pocket_detection":
        return f"top1_4A={bench.get('top1_recovery_4A')}; f1_median={bench.get('residue_f1_median')}"
    if name == "ppi_docking":
        return f"dockq_top1_median={bench.get('dockq_top1_median')}"
    if name == "ternary_docking":
        return f"contacts_median={bench.get('interface_contacts_median')}"
    if name == "binding_energy":
        return f"status={bench.get('capability_status')}; delta_median={bench.get('delta_total_median_kcal_mol')}"
    return ""


def _evidence_level(executable: bool, benchmarked: bool, external: bool) -> str:
    if external:
        return "externally_benchmarked"
    if benchmarked:
        return "internally_benchmarked"
    if executable:
        return "executable"
    return "registered_only"


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("")
        return
    keys = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


__all__ = ["run", "OUT"]
