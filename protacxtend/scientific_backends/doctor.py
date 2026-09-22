"""Backend readiness rendering for ``protacxtend doctor`` / ``protacxtend backends``."""

from __future__ import annotations

from typing import Any

from protacxtend.scientific_backends.dispatch import binary_available, module_available
from protacxtend.scientific_backends.licenses import (
    LicenseClass,
    policy_from_env,
)
from protacxtend.scientific_backends.registry import load_backends, REGISTRY

# display name -> (backend name or probe, kind)
_DISPLAY: list[tuple[str, str, str]] = [
    ("RDKit", "rdkit", "backend"),
    ("Open Babel", "openbabel", "backend"),
    ("PDBFixer/OpenMM", "pdbfixer_openmm", "backend"),
    ("OpenMM", "openmm", "backend"),
    ("MDAnalysis", "mdanalysis", "backend"),
    ("MDTraj", "mdtraj", "module"),
    ("DiffDock", "diffdock", "backend"),
    ("AutoDock Vina", "autodock_vina", "backend"),
    ("GNINA", "gnina", "backend"),
    ("LightDock", "lightdock", "backend"),
    ("Pocket geometry", "pocket_geometry", "backend"),
    ("GROMACS", "gmx", "binary"),
    ("gmx_MMPBSA", "gmx_MMPBSA", "binary"),
]


def _status_label(available: bool, *, optional: bool, gpu: bool, detail: str = "") -> str:
    if not available:
        return "OPTIONAL" if optional else "MISSING"
    if gpu:
        return "READY GPU"
    return "READY"


def backend_readiness() -> dict[str, Any]:
    load_backends()
    policy = policy_from_env()
    rows: list[dict[str, Any]] = []
    for label, key, kind in _DISPLAY:
        if kind == "backend":
            spec = REGISTRY.get(key)
            if spec is None:
                rows.append({"name": label, "status": "MISSING", "detail": key})
                continue
            health = spec.health()
            detail = health.detail
            status = _status_label(health.available, optional=spec.optional, gpu=health.gpu,
                                   detail=detail)
            if spec.optional and not health.available:
                status = "OPTIONAL"
            rows.append({"name": label, "status": status, "version": health.version or spec.version,
                         "gpu": health.gpu, "license": spec.license_class,
                         "detail": detail or spec.description, "backend": spec.name})
        elif kind == "binary":
            available = binary_available(key)
            rows.append({"name": label, "status": "READY" if available else "OPTIONAL",
                         "version": "", "gpu": False,
                         "license": "open_source_permissive" if key == "gmx" else "open_source_permissive",
                         "detail": "external binary" if available else "not installed (optional)"})
        else:  # module
            available = module_available(key)
            rows.append({"name": label, "status": "READY" if available else "OPTIONAL",
                         "version": "", "gpu": False, "license": "open_source_permissive",
                         "detail": key})

    restricted = [s for s in REGISTRY.all()
                  if not policy.allows(s.license)[0]]
    commercial = [s for s in restricted
                  if s.license.license_class in {LicenseClass.COMMERCIAL, LicenseClass.PROPRIETARY}]
    web = [s for s in restricted if s.license.license_class is LicenseClass.WEB_SERVICE]
    academic = [s for s in restricted if s.license.license_class is LicenseClass.ACADEMIC_ONLY]
    rows.append({"name": "Commercial engines", "status": "DISABLED",
                 "detail": f"{len(commercial)} registered, excluded by licence policy",
                 "license": "commercial"})
    rows.append({"name": "Web-only engines", "status": "DISABLED",
                 "detail": f"{len(web)} registered, never scraped/required",
                 "license": "web_service"})
    rows.append({"name": "Academic-only engines", "status": "DISABLED",
                 "detail": f"{len(academic)} registered, excluded by licence policy",
                 "license": "academic_only"})
    return {
        "rows": rows,
        "commercial_disabled": len(commercial),
        "web_disabled": len(web),
        "academic_disabled": len(academic),
        "policy": {
            "allow_commercial": policy.allow_commercial,
            "allow_academic_only": policy.allow_academic_only,
            "allow_web_service": policy.allow_web_service,
            "allow_network": policy.allow_network,
            "allow_copyleft": policy.allow_copyleft,
        },
    }


def _default_test_pdb() -> str:
    from pathlib import Path

    candidates = [
        Path("outputs/p4ward_evidence/hmgb2_fixed_minim.pdb"),
        Path("outputs/p4ward_evidence/input_hmgb2_receptor.pdb"),
        Path.home() / ".protacxtend/envs/diffdock/DiffDock/examples/1a46_protein_processed.pdb",
    ]
    for path in candidates:
        if path.exists():
            return str(path)
    return ""


def scientific_doctor() -> dict[str, Any]:
    """Miniature *functional* tests of the scientific stack (not just detection)."""
    import subprocess
    from pathlib import Path as _P

    from protacxtend.scientific_backends.dispatch import binary_path, run_cross_env

    rows: list[dict[str, Any]] = []

    def record(section: str, test: str, ok: bool, detail: str = "", skip: bool = False):
        rows.append({"section": section, "test": test,
                     "status": "SKIP" if skip else ("PASS" if ok else "FAIL"),
                     "detail": detail})

    def run(section, test, fn, skip_if: str = ""):
        if skip_if:
            record(section, test, False, skip_if, skip=True)
            return None
        try:
            detail = fn()
            record(section, test, True, str(detail)[:120])
            return detail
        except Exception as exc:  # noqa: BLE001
            record(section, test, False, f"{type(exc).__name__}: {exc}"[:160])
            return None

    test_pdb = _default_test_pdb()
    import protacxtend.scientific_backends as sb

    run("CHEMISTRY", "RDKit", lambda: sb.chemistry("CCO").data["molecular_weight"])

    def _openff():
        out = run_cross_env("protacxtend.scientific_backends.backends.md",
                            "_parameterize_ligand_openmm", args=["CCO", "LIG"],
                            require_import="openmm", prefer_env="md-openff", timeout=600)
        if not out.get("ok"):
            raise RuntimeError(out.get("error"))
        return out["result"]["engine"]
    run("LIGAND PARAMETERIZATION", "OpenFF/GAFF", _openff)
    run("POCKETS", "fpocket", lambda: sb.detect_pockets(test_pdb, top_n=1).backend,
        skip_if="" if test_pdb else "no test PDB")

    from protacxtend.scientific_backends.backends import docking as dk
    run("DOCKING", "Vina", lambda: len(dk.vina_docking(receptor_pdb=test_pdb,
        ligand_smiles="CCO", exhaustiveness=1, num_modes=1, cpu=2).data.get("poses", [])),
        skip_if="" if test_pdb else "no test PDB")
    for name, exe in (("DiffDock", "diffdock"), ("GNINA", "gnina"), ("LightDock", "lightdock3.py")):
        path = binary_path(exe)
        run("DOCKING" if name != "LightDock" else "PPI", name,
            lambda p=path: subprocess.run([p, "--help"], capture_output=True, timeout=180).returncode,
            skip_if="" if path else f"{exe} not installed")
    run("DOCKING", "Consensus(Borda)", lambda: dk._borda_consensus(
        {"vina": [{"rank": 1}], "gnina": [{"rank": 1}]})["method"])

    md = None
    if test_pdb:
        md_holder: dict[str, Any] = {}

        def _run_md(platform):
            out = run_cross_env("protacxtend.workflows.md_runner", "_openmm_staged",
                                args=[test_pdb, f"/tmp/pxt_doctor_md_{platform}"],
                                kwargs={"minimize_steps": 50, "restrained_steps": 50,
                                        "nvt_steps": 50, "npt_steps": 0, "production_steps": 100,
                                        "platform": platform},
                                require_import="openmm", prefer_env="md-openff", timeout=1800)
            if not out.get("ok"):
                raise RuntimeError(out.get("error"))
            md_holder[platform] = out["result"]
            return out["result"]["platform"]
        out = run("MD", "OpenMM CPU", lambda: _run_md("CPU"))
        md = md_holder.get("CPU")
        run("MD", "OpenMM GPU", lambda: _run_md("auto"))
        if md:
            r = md
            run("MD", "minimization", lambda: len(r["stage_log"]) > 0)
            run("MD", "NVT", lambda: any(s["stage"] == "nvt" for s in r["stage_log"]))
            run("MD", "trajectory", lambda: _P(r["trajectory"]).exists())
            run("MD", "checkpoint/restart", lambda: _P(r["checkpoint"]).exists())
            from protacxtend.workflows.validation_pipeline import sasa_timeseries, trajectory_timeseries
            state: dict[str, Any] = {}

            def _ts():
                state["ts"] = trajectory_timeseries(r["topology_pdb"], r["trajectory"])
                return len(state["ts"].get("rmsd", []))
            run("ANALYSIS", "RMSD/RMSF/Rg/contacts", _ts)

            def _sasa():
                state["sa"] = sasa_timeseries(r["topology_pdb"], r["trajectory"])
                return len(state["sa"].get("sasa", []))
            run("ANALYSIS", "SASA trajectory", _sasa)
            run("ANALYSIS", "three-interface analysis", lambda: bool(state.get("ts") is not None))
    else:
        for test in ("OpenMM CPU", "OpenMM GPU", "minimization", "NVT", "trajectory",
                     "checkpoint/restart"):
            record("MD", test, False, "no test PDB", skip=True)

    gmx = binary_path("gmx_MMPBSA")
    run("ENERGETICS", "gmx_MMPBSA", lambda: subprocess.run([gmx, "--version"],
        capture_output=True, timeout=180).returncode,
        skip_if="" if gmx else "gmx_MMPBSA not installed")
    run("TERNARY", "linker feasibility", lambda: sb.analyze_linker(
        "[*:1]CCOCCO[*:2]").data["contour_length_A"])
    from protacxtend.workflows.validation_pipeline import glue_verdict
    run("APO-vs-BOUND", "matched comparison", lambda: glue_verdict(
        {"summary": {"sasa": {"mean": 100}}}, {"summary": {"sasa": {"mean": 120}}})["verdict"])

    return {"rows": rows,
            "passed": sum(1 for r in rows if r["status"] == "PASS"),
            "failed": sum(1 for r in rows if r["status"] == "FAIL"),
            "skipped": sum(1 for r in rows if r["status"] == "SKIP")}


def render_scientific_doctor(payload: dict[str, Any]) -> str:
    lines = ["Scientific functional doctor:"]
    section = None
    for row in payload["rows"]:
        if row["section"] != section:
            section = row["section"]
            lines.append(f"\n{section}")
        lines.append(f"  {row['test']:<28}{row['status']}"
                     + (f"  ({row['detail']})" if row.get("detail") and row["status"] != "PASS" else ""))
    lines.append(f"\n{payload['passed']} PASS · {payload['failed']} FAIL · {payload['skipped']} SKIP")
    return "\n".join(lines)


def render_backend_readiness(payload: dict[str, Any] | None = None) -> str:
    payload = payload or backend_readiness()
    lines = ["Scientific backends (capability-first, free/local by default):"]
    for row in payload["rows"]:
        name = row["name"]
        status = row["status"]
        version = f"  {row.get('version','')}" if row.get("version") else ""
        lines.append(f"  {name:<20}{status}{version}")
    lines.append("")
    lines.append("Capability matrix:")
    from protacxtend.scientific_backends.runner import capability_matrix

    for entry in capability_matrix():
        lines.append(f"  {entry['capability']:<26}{entry['status']:<18}{entry['best_backend']}")
    return "\n".join(lines)


__all__ = ["backend_readiness", "render_backend_readiness",
           "scientific_doctor", "render_scientific_doctor"]
