#!/usr/bin/env python3
"""PROTACXtend universal-setup measurement & resource report.

Measures wall time, peak RSS and disk space for the full flow:
install (minimal + optional scientific), setup (API mock + Local Ollama),
doctor, base commands, and one deterministic run; then writes a CSV + a
Markdown summary.

Rows (one per measured phase):
    id, category, task, description, wall_s, peak_rss_mb, disk_mb_delta,
    status, notes

Usage:
    python3 scripts/universal_setup_report.py [--with-scientific] [--with-run]

Everything is isolated under PROTACXTEND_HOME temp dirs; no API keys are
read or written. Cloud endpoints are never contacted (loopback mocks only).
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
TIME_BIN = "/usr/bin/time"
HAS_TIME = Path(TIME_BIN).exists()

rows: list[dict] = []
_env_base = {k: v for k, v in os.environ.items()}


def record(rid: str, category: str, task: str, description: str,
           wall_s: float, status: str, notes: str = "",
           peak_rss_mb: float | None = None, disk_mb: float | None = None) -> None:
    rows.append({
        "id": rid, "category": category, "task": task, "description": description,
        "wall_s": round(wall_s, 3), "peak_rss_mb": (round(peak_rss_mb, 1) if peak_rss_mb else ""),
        "disk_mb": (round(disk_mb, 1) if disk_mb else ""),
        "status": status, "notes": notes,
    })
    print(f"  [{status:<6}] {rid:<26} {wall_s:>7.2f}s  {task}")


def du_mb(path: Path) -> float:
    out = subprocess.run(["du", "-sk", str(path)], capture_output=True, text=True)
    try:
        return float(out.stdout.split()[0]) / 1024.0
    except Exception:
        return 0.0


def run_measured(rid: str, category: str, task: str, description: str,
                 argv: list[str], cwd: Path = ROOT, env: dict | None = None,
                 disk_path: Path | None = None, timeout: int = 1800,
                 stdin_text: str | None = None,
                 expected_rc: int = 0) -> subprocess.CompletedProcess:
    e = {**_env_base, **(env or {})}
    e.pop("CI", None)
    e.pop("PROTACXTEND_SKIP_SETUP", None)
    t0 = time.time()
    peak = None
    res = None
    try:
        if HAS_TIME:
            time_out = tempfile.NamedTemporaryFile("w", delete=False)
            time_out.close()
            res = subprocess.run([TIME_BIN, "-v", "-o", time_out.name, *argv],
                                 cwd=cwd, env=e, input=stdin_text,
                                 text=True, capture_output=True, timeout=timeout)
            try:
                for line in Path(time_out.name).read_text().splitlines():
                    if "Maximum resident set size" in line:
                        peak = float(line.split(":")[1].strip()) / 1024.0  # KB -> MB
            except Exception:
                pass
            os.unlink(time_out.name)
        else:
            res = subprocess.run(argv, cwd=cwd, env=e, input=stdin_text,
                                 text=True, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        record(rid, category, task, description, timeout, "FAIL",
               f"timeout after {timeout}s", peak_rss_mb=peak)
        raise
    wall = time.time() - t0
    status = "PASS" if res.returncode == expected_rc else "FAIL"
    notes = ""
    if res.stderr:
        notes = res.stderr.strip().splitlines()[-1][:180] if res.stderr.strip() else ""
    disk = du_mb(disk_path) if disk_path and disk_path.exists() else None
    record(rid, category, task, description, wall, status, notes,
           peak_rss_mb=peak, disk_mb=disk)
    return res


def phase_install_minimal(prefix: Path, bin_dir: Path) -> float:
    argv = ["bash", str(ROOT / "scripts" / "install.sh"),
            "--profile", "minimal", "--prefix", str(prefix),
            "--bin", str(bin_dir), "--source-dir", str(ROOT), "--yes"]
    run_measured("install.minimal", "install", "minimal profile",
                 "pip install protacxtend core into fresh venv", argv)
    venv_mb = du_mb(prefix)
    print(f"  → minimal venv disk: {venv_mb:.1f} MB")
    # wrapper smoke
    t0 = time.time()
    r = subprocess.run([str(bin_dir / "protacxtend"), "--version"],
                       capture_output=True, text=True, timeout=120,
                       env={**_env_base, "PATH": str(bin_dir) + ":" + os.environ["PATH"]})
    record("install.minimal.wrapper", "install", "wrapper --version",
           "installed `protacxtend --version`", time.time() - t0,
           "PASS" if r.returncode == 0 else "FAIL", r.stdout.strip()[:60])
    return venv_mb


def phase_install_scientific(prefix: Path, bin_dir: Path) -> float:
    argv = ["bash", str(ROOT / "scripts" / "install.sh"),
            "--profile", "scientific", "--prefix", str(prefix),
            "--bin", str(bin_dir), "--source-dir", str(ROOT), "--yes"]
    try:
        run_measured("install.scientific", "install", "scientific extras",
                     "pip install rdkit/chemprop/torch/… into the same venv",
                     argv, timeout=2400)
    except subprocess.TimeoutExpired:
        return 0.0
    mb = du_mb(prefix)
    print(f"  → scientific venv disk: {mb:.1f} MB")
    return mb


def phase_api_mock() -> None:
    """Start loopback OpenAI-compatible mock; configure; doctor; measure."""
    mock = subprocess.Popen(
        [PY, str(ROOT / "scripts" / "mock_llm_server.py"), "0"],
        stdout=subprocess.PIPE, text=True, env={**_env_base,
                                                 "REQUIRED_KEY": "sk-report-mock",
                                                 "MOCK_MODEL": "report-probe-model"})
    port = None
    try:
        line = mock.stdout.readline().strip()
        port = int(json.loads(line)["port"])
    except Exception:
        port = None
    if port is None:
        record("api.mock.start", "setup", "mock server", "loopback OpenAI-compatible server",
               0.0, "FAIL", "mock did not start")
        return
    time.sleep(0.3)
    home = tempfile.mkdtemp(prefix="pxt_api_")
    cfg = {"provider": "openai_compatible", "model": "report-probe-model",
           "base_url": f"http://127.0.0.1:{port}/v1", "api_key": "sk-report-mock",
           "num_ctx": 1024, "temperature": 0.0, "timeout_s": 60}
    (Path(home) / "llm.json").write_text(json.dumps(cfg))
    os.chmod(Path(home) / "llm.json", 0o600)
    env = {"PROTACXTEND_HOME": home}

    # wizard (non-interactive) — openai_compatible is item 5 in the API list
    answers = "1\n5\n" + f"http://127.0.0.1:{port}/v1\n" + "report-probe-model\nsk-report-mock\n"
    r = run_measured("setup.api.wizard", "setup", "API wizard (mock)",
                     "protacxtend setup: provider+model+key+auth+inference test",
                     [str(ROOT / "PROTACXtend"), "setup"], env=env,
                     stdin_text=answers)
    run_measured("doctor.api", "doctor", "API doctor (mock)",
                 "protacxtend doctor live vs loopback mock",
                 [str(ROOT / "PROTACXtend"), "doctor"], env=env)
    mock.terminate()
    mock.wait(timeout=5)


def phase_local_ollama() -> None:
    """Local setup + doctor against the machine's Ollama (if reachable)."""
    import requests
    home = tempfile.mkdtemp(prefix="pxt_local_")
    env = {"PROTACXTEND_HOME": home}
    try:
        r = requests.get("http://127.0.0.1:11434/api/tags", timeout=3)
        models = [m.get("name") for m in r.json().get("models", [])]
    except Exception as exc:
        record("setup.local.detect", "setup", "ollama detect", "detect local runtime",
               0.0, "SKIP", f"ollama not reachable: {exc}")
        return
    if not models:
        record("setup.local.wizard", "setup", "ollama models", "existing models",
               0.0, "SKIP", "no pulled models")
        return
    small = next((m for m in models if "coder" in m or "llama3" in m or len(models) == 1), models[0])
    idx = models.index(small) + 1
    answers = f"2\n{idx}\n"
    run_measured("setup.local.wizard", "setup", "Local wizard (ollama)",
                 f"protacxtend setup local → model {small} + inference test",
                 [str(ROOT / "PROTACXtend"), "setup"], env=env, stdin_text=answers)
    run_measured("doctor.local", "doctor", "Local doctor (ollama)",
                 "protacxtend doctor live vs ollama",
                 [str(ROOT / "PROTACXtend"), "doctor"], env=env)


def phase_commands() -> None:
    env = {"PROTACXTEND_HOME": tempfile.mkdtemp(prefix="pxt_cmd_")}
    for rid, task, argv in [
        ("cmd.version", "--version", ["--version"]),
        ("cmd.provider.list", "provider list", ["provider", "list"]),
        ("cmd.model.list", "model list", ["model", "list"]),
        ("cmd.status", "status", ["status"]),
        ("cmd.doctor.offline", "doctor (unconfigured, --no-live)", ["doctor", "--no-live"]),
        ("cmd.validate", "validate --smiles CCO", ["validate", "--smiles", "CCO"]),
        ("cmd.case.study", "case-study brd4-vhl", ["case-study", "brd4-vhl"]),
    ]:
        run_measured(rid, "command", task, "base CLI runtime",
                     [str(ROOT / "PROTACXtend"), *argv], env=env, timeout=900,
                     expected_rc=0 if rid != "cmd.doctor.offline" else 1)


def phase_run() -> None:
    env = {"PROTACXTEND_HOME": tempfile.mkdtemp(prefix="pxt_run_")}
    run_measured("run.deterministic", "run", "deterministic design smoke",
                 "PROTACXtend run (deterministic) — BRD4/CRBN smoke",
                 [str(ROOT / "PROTACXtend"), "run", "--mode", "deterministic",
                  "Design CRBN PROTACs for BRD4 degradation.", "--run-id",
                  "report_smoke"], env=env, timeout=1800)


def phase_sizes() -> None:
    # allocated bytes of git-tracked files (matches `du` semantics)
    tracked_alloc = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, capture_output=True).stdout
    du_res = subprocess.run(["du", "--files0-from=-", "-skc"],
                            input=tracked_alloc, capture_output=True)
    alloc_mb = float(du_res.stdout.decode().strip().splitlines()[-1].split()[0]) / 1024.0
    files = [f for f in tracked_alloc.split(b"\0") if f]
    record("size.repo.tracked", "space", "git-tracked content",
           "allocated bytes of tracked files (du)", 0.0, "OK",
           notes=f"{len(files)} files", disk_mb=alloc_mb)
    pkg_alloc = subprocess.run(
        ["du", "-skc", "protacxtend"], cwd=ROOT, capture_output=True, text=True)
    pkg_mb = float(pkg_alloc.stdout.strip().splitlines()[-1].split()[0]) / 1024.0
    record("size.package.source", "space", "protacxtend/ directory",
           "allocated bytes of the installed python package dir", 0.0, "OK", disk_mb=pkg_mb)
    repo_all = du_mb(ROOT)
    record("size.repo.total", "space", "repository on disk (incl. data/venvs)",
           "du -sk of the working tree", 0.0, "OK", disk_mb=repo_all)
    # wheel size (no-deps build; no network)
    try:
        tmp = Path(tempfile.mkdtemp(prefix="pxt_wheel_"))
        r = subprocess.run([PY, "-m", "pip", "wheel", "--no-deps",
                            "--wheel-dir", str(tmp), str(ROOT)],
                           capture_output=True, text=True, timeout=600, cwd=ROOT)
        wheels = list(tmp.glob("*.whl"))
        if r.returncode == 0 and wheels:
            record("size.package.wheel", "space", "built wheel (no deps)",
                   "pip wheel --no-deps size", 0.0, "OK",
                   notes=wheels[0].name, disk_mb=du_mb(wheels[0]))
        else:
            record("size.package.wheel", "space", "built wheel (no deps)",
                   "pip wheel --no-deps size", 0.0, "SKIP", r.stderr[-160:])
        shutil.rmtree(tmp, ignore_errors=True)
    except Exception as exc:
        record("size.package.wheel", "space", "built wheel (no deps)", "", 0.0, "SKIP", str(exc)[:120])


def write_outputs(out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    csv_path = out_dir / f"universal_setup_report_{stamp}.csv"
    with csv_path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()) if rows else [])
        w.writeheader()
        w.writerows(rows)
    latest = out_dir / "universal_setup_report_latest.csv"
    shutil.copy(csv_path, latest)
    return csv_path


def summary_md(csv_path: Path, out_dir: Path) -> None:
    def wall(cat: str) -> float:
        return sum(float(r["wall_s"]) for r in rows if r["category"] == cat)
    total = sum(float(r["wall_s"]) for r in rows)
    fails = [r for r in rows if r["status"] == "FAIL"]
    md = [
        "# PROTACXtend universal setup — measured report",
        "",
        f"- generated: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}",
        f"- python: {sys.version.split()[0]}",
        f"- csv: `{csv_path.name}`",
        "",
        "## Totals",
        "",
        "| category | wall s |",
        "|---|---:|",
    ]
    for cat in ("install", "setup", "doctor", "command", "run", "space"):
        w = wall(cat)
        if w > 0:
            md.append(f"| {cat} | {w:.2f} |")
    md += [
        f"| **total measured wall** | **{total:.2f}** |",
        "",
        "## Rows",
        "",
        "| id | category | wall_s | peak_rss_mb | disk_mb | status | notes |",
        "|---|---|---:|---:|---:|---|---|",
    ]
    for r in rows:
        md.append(f"| {r['id']} | {r['category']} | {r['wall_s']} | {r.get('peak_rss_mb')} "
                  f"| {r.get('disk_mb')} | {r['status']} | {r['notes']} |".replace("\n", " "))
    if fails:
        md += ["", f"- FAILED rows: {len(fails)}"]
    (out_dir / "universal_setup_report_latest.md").write_text("\n".join(md))
    (out_dir / "universal_setup_report_latest.json").write_text(
        json.dumps({"rows": rows, "total_wall_s": round(total, 3)}, indent=2))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--with-scientific", action="store_true")
    ap.add_argument("--with-run", action="store_true")
    ap.add_argument("--out", default=str(ROOT / "outputs" / "reports"))
    args = ap.parse_args()
    out_dir = Path(args.out)
    print("PROTACXtend universal-setup report harness")
    print(f"repo: {ROOT}")

    base = Path(tempfile.mkdtemp(prefix="pxt_install_test_"))
    prefix = base / "venv"
    bin_dir = base / "bin"
    try:
        venv_mb = phase_install_minimal(prefix, bin_dir)
        record("install.minimal.disk", "space", "minimal venv disk",
               "du of installed minimal venv", 0.0, "OK",
               disk_mb=venv_mb)
        if args.with_scientific:
            sci_mb = phase_install_scientific(prefix, bin_dir)
            if sci_mb:
                record("install.scientific.disk", "space", "scientific venv disk",
                       "du of venv after scientific extras", 0.0, "OK", disk_mb=sci_mb)
        phase_api_mock()
        phase_local_ollama()
        phase_commands()
        if args.with_run:
            phase_run()
        phase_sizes()
    finally:
        shutil.rmtree(base, ignore_errors=True)   # drop the test venv

    csv_path = write_outputs(out_dir)
    summary_md(csv_path, out_dir)
    print(f"\nreport csv : {csv_path}")
    print(f"report md  : {out_dir / 'universal_setup_report_latest.md'}")
    fails = [r for r in rows if r["status"] == "FAIL"]
    print(f"\nTOTAL measured wall time: {sum(float(r['wall_s']) for r in rows):.2f}s  "
          f"(phases: {len(rows)}, failed: {len(fails)})")


if __name__ == "__main__":
    main()
