#!/usr/bin/env python3
"""Single reproducible command for the full scientific-validation audit.

    python scripts/run_full_validation.py [--fast] [--shards N]

Runs, in order (each stage isolated in a subprocess; failures are logged and
never silently dropped):

  1. freeze benchmark datasets                         (frozen manifests + SHA256)
  2. capability / licence / fallback audit             (scripts/run_scientific_audit.py)
  3. expanded sharded redocking + prospective consensus (validation stage docking_shards)
  4. expanded pocket benchmark                          (validation stage pocket)
  5. experimental binary PPI + DockQ                    (validation stage ppi)
  6. ternary / PROTAC validation                        (validation stage ternary)
  7. GAFF2 MM/GBSA (validated parameterisation)         (validation stage energetics)
  8. real fallback execution test                       (validation stage fallback)
  9. reproducibility across seeds                       (validation stage reproducibility)
 10. runtime / resource consolidation                   (validation stage runtime)
 11. live remote-service verification                   (validation stage services)
 12. component crosswalk (408 vs 367)                   (validation stage crosswalk)
 13. capability-dimension matrix                        (validation stage dimensions)
 14. machine-readable claim table                       (validation stage claims)
 15. live agent-tool / backend probe                    (sota/closure/live_capability_probe.py)
 16. figures                                            (validation stage figures)
 17. audit documents / tables                           (scripts/build_audit_docs.py)

Every stage appends raw CSV/JSON under results/; failures are written to
results/logs/ and remain in the denominator.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOGS = ROOT / "results" / "logs"
STAGE = ROOT / "scripts" / "validation" / "run_stage.py"


def run(name: str, args: list[str]) -> None:
    log = LOGS / f"{name}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    print(f"\n=== {name} ===", flush=True)
    with log.open("w") as fh:
        proc = subprocess.run([sys.executable, "-u", *args], cwd=str(ROOT), stdout=fh,
                              stderr=subprocess.STDOUT)
    print(f"{name}: exit={proc.returncode} in {round(time.time() - t0, 1)}s (log {log})",
          flush=True)


def stage(name: str, *extra: str) -> None:
    run(name, [str(STAGE), name, *extra])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fast", action="store_true", help="skip heavy docking/PPI/MD/MMGBSA sweeps")
    ap.add_argument("--shards", type=int, default=3, help="parallel docking shards")
    ap.add_argument("--replicas", type=int, default=3)
    args = ap.parse_args()

    stage("freeze")
    run("01_audit", ["scripts/run_scientific_audit.py"])
    run("02_pocket_legacy", ["scripts/audit_benchmarks.py", "pocket"])

    if not args.fast:
        stage("docking_shards", "--shards", str(args.shards))
        stage("docking_merge")
    stage("pocket")
    stage("ppi", "--limit", "8" if args.fast else "0")
    stage("ternary", "--limit", "8" if args.fast else "0")
    if not args.fast:
        stage("energetics", "--limit", "3")
    stage("fallback")
    stage("reproducibility", "--limit", "3" if args.fast else "5")
    stage("runtime")
    stage("services")
    stage("crosswalk")
    stage("dimensions")
    stage("claims")
    stage("report")
    stage("live_probe")
    stage("figures")
    run("17_docs", ["scripts/build_audit_docs.py"])
    run("18_claims_legacy", ["scripts/build_claim_table.py"])
    print("\nFull validation complete. See results/benchmarks/, results/figures_validation/, "
          "results/CAPABILITY_CLAIM_TABLE_V2.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
