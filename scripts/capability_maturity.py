#!/usr/bin/env python3
"""Evidence-based capability maturity matrix for PROTACXtend.

Maturity is **never** inferred from package availability alone. Each capability
is classified into one of five levels using explicit, auditable evidence:

    absent                  no installation evidence
    installed               installation/health check only
    smoke-tested            a capability-level smoke test or functional check passed
    internally-benchmarked  a benchmark with dataset + comparator + metric was run
    scientifically-validated benchmark was run AND meets its acceptance threshold
                            AND the capability is not excluded from validation

Hard exclusions (cannot be scientifically validated on this host):
  * partially converged MD (verdict PARTIALLY_CONVERGED; 2 replicas, not 3)
  * untested PPI / ternary workflows (no end-to-end coordinate-level benchmark)
  * surrogate energetics (MM/GBSA & MM/PBSA failed; interaction energy is a
    structural-geometry surrogate with no numeric value)

Outputs
-------
    results/audit/capability_maturity_matrix.csv
    results/audit/run_provenance.json
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "results" / "audit"
TABLES = ROOT / "results" / "tables"
DOCK = ROOT / "results" / "docking"
POCK = ROOT / "results" / "pockets"
PPI = ROOT / "results" / "ppi"
STATS = ROOT / "results" / "statistics" / "statistics.json"
VAL = ROOT / "validation_runs" / "1a46_pl"

MATURITY_LEVELS = [
    "absent",
    "installed",
    "smoke-tested",
    "internally-benchmarked",
    "scientifically-validated",
]
LEVEL_IDX = {name: i for i, name in enumerate(MATURITY_LEVELS)}
LEVEL_COLORS = {
    "absent": "#b9bec6",
    "installed": "#94a3b1",
    "smoke-tested": "#6f92b3",
    "internally-benchmarked": "#c3a15c",
    "scientifically-validated": "#6f9b73",
}
LEVEL_DEFINITION = {
    "absent": "no installation evidence",
    "installed": "installation / backend-health check passed only",
    "smoke-tested": "capability-level smoke or functional check passed",
    "internally-benchmarked": "benchmark run (dataset + comparator + metric), acceptance not met or excluded",
    "scientifically-validated": "benchmark met its pre-registered acceptance threshold",
}

# groups whose capabilities are explicitly NOT eligible for scientific validation
EXCLUDE_VALIDATION = {
    "MOLECULAR_DYNAMICS": "partially converged MD (PARTIALLY_CONVERGED; 2 replicas, not 3)",
    "PPI_DOCKING": "PPI workflow not exercised end-to-end; no positive coordinate-level benchmark",
    "TERNARY_PROTAC": "ternary/PPI workflow not exercised end-to-end",
    "ENERGETICS": "surrogate or failed energetics (MM/GBSA & MM/PBSA failed)",
}

# pytest test-name substrings that exercise each capability group
TEST_GROUP_KEYWORDS = {
    "CHEMISTRY": ["chemistry_and_admet", "conformer_generation", "candidate_ranking", "borda_rank"],
    "PROTEIN_PREPARATION": ["structure_qc", "validate_system_pass"],
    "LIGAND_PARAMETERIZATION": ["real_ligand_parameterization", "ligand_parameterization_provenance"],
    "POCKET_DETECTION": ["pocket_detection"],
    "LIGAND_DOCKING": ["vina_real_pose", "gnina_real_pose", "diffdock_real_pose",
                       "consensus_docking", "docking_adapters", "borda_rank"],
    "PPI_DOCKING": ["lightdock_real_complex", "matched_apo_holo"],
    "TERNARY_PROTAC": ["linker_analysis", "interaction_fingerprint"],
    "MOLECULAR_GLUE": ["molecular_glue", "glue_verdict"],
    "METABOLITE_PPI": ["metabolite_ppi"],
    "MOLECULAR_DYNAMICS": ["openmm_minimize", "openmm_writes", "openmm_run_writes"],
    "TRAJECTORY_ANALYSIS": ["trajectory_sasa", "three_interface", "test_stats", "convergence_detection"],
    "ENERGETICS": ["gmx_mmpbsa", "interaction_fingerprint"],
    "ADMET": ["chemistry_and_admet"],
    "PROVENANCE": ["final_report_provenance", "backend_contract", "result_metadata", "model_registry"],
}

# evidence files hashed into the run provenance
EVIDENCE_FILES = [
    "results/audit/tool_capability_matrix.csv",
    "results/audit/functional_checks.json",
    "results/audit/pytest_results.json",
    "results/audit/summary_metrics.json",
    "results/audit/licence_audit.csv",
    "results/docking/docking_benchmark.csv",
    "results/docking/docking_benchmark.json",
    "results/docking/docking_summary.json",
    "results/pockets/pocket_benchmark.csv",
    "results/pockets/pocket_summary.json",
    "results/ppi/ppi_dockq.csv",
    "results/ppi/ppi_benchmark.json",
    "results/statistics/statistics.json",
    "results/tables/Table_claims.csv",
    "results/tables/Supplementary_S1_software_versions.csv",
    "results/tables/Supplementary_S5_model_weights.csv",
    "results/tables/Table5_usecase_completion.csv",
    "validation_runs/1a46_pl/final_report.json",
    "validation_runs/1a46_pl/analysis/convergence.json",
    "validation_runs/1a46_pl/analysis/analysis_summary.json",
    "validation_runs/1a46_pl/provenance/provenance.json",
    "validation_runs/1a46_pl/energy/mmpbsa.json",
]

# pre-registered acceptance thresholds (frozen before evaluation)
ACCEPTANCE = {
    "docking": "median top-1 pose RMSD ≤ 2.0 Å (comparator: crystal pose)",
    "pocket": "top-1 recovery ≤ 4 Å ≥ 0.50",
    "ppi": "geometric DockQ ≥ 0.49 (CAPRI acceptable)",
    "md": "convergence verdict == CONVERGED with ≥ 3 replicas",
    "mmpbsa": "MM/GBSA status == success and ΔG reported",
}
MATURITY_RULE_VERSION = "2026-09-17.publication-1"


# ── small helpers ───────────────────────────────────────────────────────
def _read_json(path):
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def _read_csv(path):
    p = Path(path)
    if not p.exists():
        return []
    with p.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _sha256(path):
    p = Path(path)
    if not p.exists():
        return ""
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _fnum(x):
    try:
        s = str(x).strip()
        return None if s in ("", "None", "nan", "NaN") else float(s)
    except (TypeError, ValueError):
        return None


def _bool(x):
    return str(x).strip().lower() == "true"


def _git():
    def run(args):
        try:
            return subprocess.check_output(["git", *args], cwd=str(ROOT),
                                           stderr=subprocess.DEVNULL).decode().strip()
        except Exception:
            return ""
    commit = run(["rev-parse", "HEAD"])
    dirty = run(["status", "--porcelain"])
    return {
        "commit": commit,
        "branch": run(["rev-parse", "--abbrev-ref", "HEAD"]),
        "describe": run(["describe", "--tags", "--always", "--dirty"]) or commit[:12],
        "dirty": bool(dirty),
        "n_dirty_paths": len([ln for ln in dirty.splitlines() if ln.strip()]),
    }


def _hardware():
    hw = {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cpu_count": os.cpu_count(),
    }
    try:
        hw["memory_gb"] = round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1e9, 1)
    except Exception:
        hw["memory_gb"] = None
    gpus = []
    try:
        out = subprocess.check_output(["nvidia-smi", "--query-gpu=name,memory.total",
                                       "--format=csv,noheader"],
                                      stderr=subprocess.DEVNULL).decode().strip()
        gpus = [ln.strip() for ln in out.splitlines() if ln.strip()]
    except Exception:
        pass
    hw["gpus"] = gpus
    return hw


def _versions():
    v = {"python": sys.version.split()[0]}
    try:
        import numpy
        v["numpy"] = numpy.__version__
    except Exception:
        pass
    for name, attr in (("rdkit", "rdkit.__version__"), ("matplotlib", "matplotlib.__version__"),
                       ("scipy", "scipy.__version__"), ("pandas", "pandas.__version__")):
        try:
            mod = __import__(name)
            v[name] = getattr(mod, "__version__", "")
        except Exception:
            pass
    try:
        import openmm
        v["openmm"] = openmm.version.version
    except Exception:
        pass
    try:
        import MDAnalysis
        v["mdanalysis"] = MDAnalysis.__version__
    except Exception:
        pass
    try:
        import mdtraj
        v["mdtraj"] = mdtraj.version.version
    except Exception:
        pass
    for row in _read_csv(TABLES / "Supplementary_S1_software_versions.csv"):
        if _bool(row.get("available")) and (row.get("version") or "").strip():
            v.setdefault(f"backend:{row['backend']}", row["version"].strip())
    return v


def build_run_provenance():
    """Automatic run provenance: versions, parameters, hashes, seeds, hardware,
    timestamps and git commit."""
    generated = datetime.now(timezone.utc).isoformat()
    hashes, mtimes = {}, {}
    for rel in EVIDENCE_FILES:
        p = ROOT / rel
        if p.exists():
            hashes[rel] = _sha256(p)
            mtimes[rel] = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc).isoformat()
    prov = {
        "generated_at": generated,
        "maturity_rule_version": MATURITY_RULE_VERSION,
        "git": _git(),
        "hardware": _hardware(),
        "tool_versions": _versions(),
        "parameters": {
            "acceptance_thresholds": ACCEPTANCE,
            "bootstrap_resamples": 20000,
            "bootstrap_seed_base": 1,
            "maturity_levels": MATURITY_LEVELS,
            "excluded_from_validation": EXCLUDE_VALIDATION,
            "evidence_files_hashed": sorted(hashes),
        },
        "seeds": {"md_replicas": _read_json(VAL / "final_report.json")
                  .get("provenance", {}).get("seeds", [])},
        "input_hashes": hashes,
        "input_mtimes": mtimes,
        "script_sha256": _sha256(Path(__file__)),
    }
    payload = json.dumps({k: prov[k] for k in prov if k != "provenance_digest"},
                         sort_keys=True, default=str)
    prov["provenance_digest"] = hashlib.sha256(payload.encode()).hexdigest()
    return prov


# ── benchmark evidence assembly ─────────────────────────────────────────
def _docking_evidence():
    rows = _read_csv(DOCK / "docking_benchmark.csv")
    stats = _read_json(STATS).get("docking", {})
    bench = {}

    def succeed_count(col):
        return sum(1 for r in rows if (_fnum(r.get(col)) is not None and _fnum(r.get(col)) <= 2.0))

    for cap, engine, col in (("vina", "vina", "vina_top1"),
                             ("gnina", "gnina", "gnina_top1"),
                             ("diffdock", "diffdock", "diffdock_top1")):
        median = stats.get(engine, {}).get("median_top1")
        if median is None:
            vals = [v for v in (_fnum(r.get(col)) for r in rows) if v is not None]
            median = round(sorted(vals)[len(vals) // 2], 3) if vals else None
        bench[cap] = {
            "dataset": "6-complex DiffDock example redocking set (results/docking)",
            "comparator": "crystal native ligand pose",
            "metrics": f"median top-1 pose RMSD = {median} Å; success (<2 Å) = "
                       f"{succeed_count(col)}/{len(rows)} complexes",
            "threshold": ACCEPTANCE["docking"],
            "value": median,
            "result": "pass" if (median is not None and median <= 2.0) else "fail",
            "successful": succeed_count(col),
            "attempted": len(rows),
            "evidence": "results/docking/docking_benchmark.json",
        }
    cons_vals = [v for v in (_fnum(r.get("consensus_top1")) for r in rows) if v is not None]
    cons_median = round(sorted(cons_vals)[len(cons_vals) // 2], 3) if cons_vals else None
    bench["consensus_ranking"] = {
        "dataset": "6-complex DiffDock example redocking set (results/docking)",
        "comparator": "crystal native ligand pose (Borda rank winner)",
        "metrics": f"median top-1 pose RMSD = {cons_median} Å; success (<2 Å) = "
                   f"{succeed_count('consensus_top1')}/{len(rows)} complexes",
        "threshold": ACCEPTANCE["docking"],
        "value": cons_median,
        "result": "pass" if (cons_median is not None and cons_median <= 2.0) else "fail",
        "successful": succeed_count("consensus_top1"),
        "attempted": len(rows),
        "evidence": "results/docking/docking_benchmark.csv",
    }
    return bench


def _pocket_evidence():
    stats = _read_json(STATS).get("pocket", {})
    rows = _read_csv(POCK / "pocket_benchmark.csv")
    rec = stats.get("top1_recovery_4A", {}).get("point")
    if rec is None:
        rec = (sum(1 for r in rows if _bool(r.get("top1_recovery_4A"))) / len(rows)) if rows else None
    ok = rec is not None and rec >= 0.5
    ev = {
        "dataset": f"{len(rows)}-complex fpocket benchmark (results/pockets)",
        "comparator": "native ligand centroid",
        "metrics": f"top-1 recovery ≤ 4 Å = {rec:.4f}; top-3 = "
                   f"{stats.get('top3_recovery_4A', {}).get('point')}; "
                   f"median centroid distance = {stats.get('dcc_median')} Å",
        "threshold": ACCEPTANCE["pocket"],
        "value": rec,
        "result": "pass" if ok else "fail",
        "successful": int(round((rec or 0) * len(rows))),
        "attempted": len(rows),
        "evidence": "results/pockets/pocket_benchmark.csv",
    }
    return {"fpocket": ev, "geometry_fallback": dict(ev)}


def _ppi_evidence():
    stats = _read_json(STATS).get("ppi", {})
    bench = _read_json(PPI / "ppi_benchmark.json")
    stats = stats or bench
    rows = _read_csv(PPI / "ppi_dockq.csv")
    dockq = stats.get("geometric_fallback_dockq")
    ok = dockq is not None and dockq >= 0.49
    ev = {
        "dataset": "1 native PPI complex + 20 decoys + geometric fallback (results/ppi)",
        "comparator": "native interface (DockQ)",
        "metrics": f"geometric-fallback DockQ = {dockq} ({stats.get('geometric_fallback_capri')}); "
                   f"native control = {stats.get('native_control_dockq')}; "
                   f"decoy mean = {stats.get('decoy_dockq_mean')}",
        "threshold": ACCEPTANCE["ppi"],
        "value": dockq,
        "result": "pass" if ok else "fail",
        "successful": 0 if not ok else 1,
        "attempted": 1,
        "evidence": "results/ppi/ppi_benchmark.json",
    }
    return {"lightdock": ev, "restrained_docking": dict(ev), "ppi_orientation": dict(ev)}


def _md_evidence():
    conv = _read_json(VAL / "analysis" / "convergence.json")
    ok = conv.get("verdict") == "CONVERGED"
    ev = {
        "dataset": "validation_runs/1a46_pl holo trajectory (2 replicas x 50 frames)",
        "comparator": "predefined convergence acceptance criteria (no external reference)",
        "metrics": f"verdict = {conv.get('verdict')}; {conv.get('n_checks_ok')}/"
                   f"{conv.get('n_checks')} checks pass; replicas = "
                   f"{_read_json(VAL / 'final_report.json').get('md', {}).get('n_replicas')}",
        "threshold": ACCEPTANCE["md"],
        "value": conv.get("verdict"),
        "result": "pass" if ok else "fail",
        "successful": int(conv.get("n_checks_ok") or 0),
        "attempted": int(conv.get("n_checks") or 0),
        "evidence": "validation_runs/1a46_pl/analysis/convergence.json",
    }
    return {c: dict(ev) for c in ("openmm_cpu", "openmm_gpu", "minimization", "nvt", "npt",
                                  "short_md", "replicate_md", "checkpoint_resume")}


def _mmpbsa_evidence():
    m = _read_json(VAL / "energy" / "mmpbsa.json")
    stats_mm = _read_json(STATS).get("mmpbsa", {})
    m_status, s_status = m.get("status"), stats_mm.get("status")
    ok = "success" in (m_status, s_status)
    statuses = " / ".join(x for x in (m_status, s_status) if x)
    ev = {
        "dataset": "OpenFF-parameterised 1a46 system (Amber topology export attempt)",
        "comparator": "AmberTools MMPBSA.py reference implementation",
        "metrics": f"status = {statuses} (report / statistics.json); stage = {stats_mm.get('stage')}",
        "threshold": ACCEPTANCE["mmpbsa"],
        "value": statuses,
        "result": "pass" if ok else "fail",
        "successful": 1 if ok else 0,
        "attempted": 1,
        "evidence": "validation_runs/1a46_pl/energy/mmpbsa.json",
    }
    return {c: dict(ev) for c in ("gmx_mmpbsa", "mmgbsa", "mmpbsa")}


def _provenance_overrides(prov):
    """Provenance capabilities are judged from real artefacts, not from the
    package-availability matrix (which lists them as not installed)."""
    report = _read_json(VAL / "final_report.json")
    models = _read_csv(TABLES / "Supplementary_S5_model_weights.csv")
    models_hashed = all((r.get("sha256") or "").strip() for r in models) and bool(models)
    checks = {
        "software_versions": (bool(prov.get("tool_versions")), "validation_runs/1a46_pl/provenance/provenance.json"),
        "forcefield": (bool(_read_json(VAL / "provenance" / "provenance.json").get("forcefield")),
                       "validation_runs/1a46_pl/provenance/provenance.json"),
        "random_seed": (bool(prov.get("seeds", {}).get("md_replicas")),
                        "validation_runs/1a46_pl/provenance/provenance.json"),
        "input_hashes": (bool(prov.get("input_hashes")), "validation_runs/1a46_pl/provenance/provenance.json"),
        "model_sha256": (models_hashed, "results/tables/Supplementary_S5_model_weights.csv"),
        "gpu_cpu": (bool(_read_json(VAL / "final_report.json").get("md", {}).get("platforms")),
                    "validation_runs/1a46_pl/final_report.json"),
        "evidence_tier": (bool(report.get("evidence_tier")), "validation_runs/1a46_pl/final_report.json"),
    }
    out = {}
    for cap, (present, ev) in checks.items():
        out[cap] = {
            "present": present, "evidence": ev,
            "failure": "" if present else "provenance artefact not populated",
        }
    return out


# ── maturity table ──────────────────────────────────────────────────────
def build_maturity_table(prov=None, with_provenance_completeness=True):
    prov = prov or build_run_provenance()
    matrix = _read_csv(AUDIT / "tool_capability_matrix.csv")
    func = _read_json(AUDIT / "functional_checks.json")
    pytest_rows = _read_json(AUDIT / "pytest_results.json")
    versions = {r["backend"]: (r.get("version") or "").strip()
                for r in _read_csv(TABLES / "Supplementary_S1_software_versions.csv")}

    group_tests = {g: {"total": 0, "passed": 0} for g in TEST_GROUP_KEYWORDS}
    for t in pytest_rows:
        name = t.get("test", "")
        for g, keys in TEST_GROUP_KEYWORDS.items():
            if any(k in name for k in keys):
                group_tests[g]["total"] += 1
                if t.get("status") == "PASS":
                    group_tests[g]["passed"] += 1

    bench = {}
    bench.update(_docking_evidence())
    bench.update(_pocket_evidence())
    bench.update(_ppi_evidence())
    bench.update(_md_evidence())
    bench.update(_mmpbsa_evidence())
    prov_override = _provenance_overrides(prov)

    hashes = prov.get("input_hashes", {})
    hardware_ok = bool(prov.get("hardware", {}).get("platform"))
    timestamp_ok = bool(prov.get("generated_at"))
    git_ok = bool(prov.get("git", {}).get("commit"))
    seed_ok = bool(prov.get("seeds", {}).get("md_replicas"))

    rows_out = []
    for r in matrix:
        group = r["group"]
        cap = r["capability"]
        installed = _bool(r.get("installed"))
        functional_key = next((k for k in (r.get("primary_backend"), r.get("secondary_backend"),
                                           r.get("fallback_backend")) if k in func), None)
        functional = func.get(functional_key, {}).get("functional") if functional_key else None
        matrix_smoke = (r.get("smoke_test_status") or "").upper()
        gt = group_tests.get(group, {"total": 0, "passed": 0})

        smoke_total = gt["total"] + (1 if functional_key else 0)
        smoke_pass = gt["passed"] + (1 if functional else 0)

        # evidence file + installation test
        evidence_file = "results/audit/tool_capability_matrix.csv"
        installation_test = "backend health check: PASS" if installed else "backend health check: FAIL"
        if functional_key:
            installation_test = f"functional check ({functional_key}): " + ("PASS" if functional else "FAIL")
            evidence_file = "results/audit/functional_checks.json"

        b = bench.get(cap)
        prov_art = prov_override.get(cap) if group == "PROVENANCE" else None

        if prov_art is not None:
            installation_test = "provenance artefact check: " + ("PRESENT" if prov_art["present"] else "MISSING")
            evidence_file = prov_art["evidence"]

        # ---- maturity classification ----
        failure_reason = ""
        if prov_art is not None:
            level = "smoke-tested" if prov_art["present"] else "installed"
            if not prov_art["present"]:
                failure_reason = prov_art["failure"]
        elif not installed:
            level = "absent"
            failure_reason = "backend not installed / licence-gated"
        elif b is not None:
            excluded = group in EXCLUDE_VALIDATION
            if b["result"] == "pass" and not excluded:
                level = "scientifically-validated"
            else:
                level = "internally-benchmarked"
                if b["result"] != "pass":
                    failure_reason = f"acceptance not met: {b['metrics']}"
                if excluded:
                    failure_reason = (failure_reason + "; " if failure_reason else "") + \
                        f"excluded: {EXCLUDE_VALIDATION[group]}"
        elif (matrix_smoke == "PASS" or functional) and smoke_pass >= 1:
            level = "smoke-tested"
        else:
            level = "installed"
            if matrix_smoke == "FAIL":
                failure_reason = "capability smoke test failed"

        # benchmark / smoke sample counts
        if b is not None:
            sample_success, sample_attempted = b["successful"], b["attempted"]
            sample_basis = "benchmark cases"
            benchmark_dataset = b["dataset"]
            comparator = b["comparator"]
            metrics = b["metrics"]
            threshold = b["threshold"]
            validation_result = b["result"]
            evidence_file = b["evidence"]
        elif prov_art is not None:
            sample_success, sample_attempted = (1 if prov_art["present"] else 0), 1
            sample_basis = "artefact checks"
            benchmark_dataset = comparator = metrics = threshold = ""
            validation_result = "pass" if prov_art["present"] else "fail"
        else:
            sample_success, sample_attempted = smoke_pass, smoke_total
            sample_basis = "smoke-test cases"
            benchmark_dataset = comparator = metrics = threshold = ""
            validation_result = "pass" if (matrix_smoke == "PASS" or functional) else "not_attempted"

        # provenance completeness
        if with_provenance_completeness:
            applicable = [hardware_ok, timestamp_ok, git_ok]
            if (r.get("primary_backend") or "") not in ("provenance", "models"):
                applicable.append(bool(versions.get(r.get("primary_backend", ""), "").strip()))
            ev_path = evidence_file
            applicable.append(ev_path in hashes)
            stochastic = group in ("LIGAND_DOCKING", "PPI_DOCKING", "MOLECULAR_DYNAMICS",
                                   "MOLECULAR_GLUE", "PROTEIN_PREPARATION")
            if stochastic:
                applicable.append(seed_ok)
            completeness = sum(1 for a in applicable if a) / len(applicable) if applicable else 1.0
            prov_txt = f"{sum(1 for a in applicable if a)}/{len(applicable)} ({completeness:.0%})"
        else:
            completeness = None
            prov_txt = ""

        ver = versions.get(r.get("primary_backend", ""), "")
        rows_out.append({
            "module": group,
            "capability": cap,
            "implementation_tool": r.get("primary_backend", ""),
            "version": ver or "unreported",
            "installation_test": installation_test,
            "smoke_test_cases": smoke_total,
            "successful_cases": smoke_pass,
            "benchmark_dataset": benchmark_dataset,
            "comparator": comparator,
            "evaluation_metrics": metrics,
            "acceptance_threshold": threshold,
            "validation_result": validation_result,
            "provenance_completeness": prov_txt,
            "evidence_file": evidence_file,
            "failure_reason": failure_reason,
            "maturity_level": level,
            "sample_success": sample_success,
            "sample_attempted": sample_attempted,
            "sample_basis": sample_basis,
            "evidence_tier": r.get("evidence_tier", ""),
            "_prov_fraction": completeness,
        })
    return rows_out


def maturity_summary(rows):
    counts = {lv: 0 for lv in MATURITY_LEVELS}
    for r in rows:
        counts[r["maturity_level"]] += 1
    return counts


def save_audit_outputs():
    prov = build_run_provenance()
    rows = build_maturity_table(prov)
    AUDIT.mkdir(parents=True, exist_ok=True)
    cols = [k for k in rows[0] if not k.startswith("_")]
    with (AUDIT / "capability_maturity_matrix.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({k: r[k] for k in cols})
    (AUDIT / "run_provenance.json").write_text(json.dumps(prov, indent=2, default=str),
                                               encoding="utf-8")
    return rows, prov


if __name__ == "__main__":
    rows, prov = save_audit_outputs()
    print(f"wrote results/audit/capability_maturity_matrix.csv ({len(rows)} capabilities)")
    print(f"wrote results/audit/run_provenance.json (digest {prov['provenance_digest'][:12]})")
    for lv, n in maturity_summary(rows).items():
        print(f"  {lv:26s} {n}")
