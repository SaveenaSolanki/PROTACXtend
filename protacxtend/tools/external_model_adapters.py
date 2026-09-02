"""Audited adapter layer for external PROTAC model/tool integrations."""

from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from protacxtend.scientific_contract import reviewed_external_methods
from protacxtend.tools.repo_tool_adapter import PROJECT_ROOT, repo_tool_status


RUN_DIR = PROJECT_ROOT / "outputs" / "external_integrations"

REPO_BY_METHOD = {
    "protac_degradation_predictor": "PROTAC-Degradation-Predictor",
    "rp_protac": "RP-PROTAC",
    "deep_qsp_hook": "protac_deep_qsp",
    "protacfold": "PROTACFold",
    "rover_schapira_benchmark": "PROTAC_ternary",
    "synprotac": "SynPROTAC",
    "deep_protacs": "DeepPROTACs",
    "protac_invent": "Protac-invent",
}

REPO_PATH_BY_METHOD = {
    method_id: PROJECT_ROOT / "data" / "protac_repos" / "repos" / repo_name
    for method_id, repo_name in REPO_BY_METHOD.items()
}


@dataclass
class ExternalIntegrationStatus:
    method_id: str
    name: str
    integration_wave: int
    role: str
    gate: str
    repo_name: str = ""
    repo_registered: bool = False
    repo_available: bool = False
    executable: bool = False
    status: str = "not_integrated"
    adapter: str = "status_only"
    warnings: list[str] = field(default_factory=list)

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


def list_external_integration_status() -> list[ExternalIntegrationStatus]:
    """Return executable/readiness state for the external-first roadmap."""

    rows: list[ExternalIntegrationStatus] = []
    for method in reviewed_external_methods():
        if method.method_id not in REPO_BY_METHOD:
            continue
        repo_name = REPO_BY_METHOD[method.method_id]
        status = repo_tool_status(repo_name)
        repo_path = REPO_PATH_BY_METHOD[method.method_id]
        repo_available = repo_path.exists()
        repo_registered = bool(status.get("registered")) and status.get("name") == repo_name
        warnings: list[str] = []
        if not repo_registered:
            warnings.append("Repo/tool is not registered locally; adapter remains status-only.")
        if not repo_available:
            warnings.append("No verified local checkout is available.")
        if repo_available and not status.get("executable"):
            warnings.append("Local checkout exists, but no validated isolated executable is available yet.")
        executable = bool(status.get("executable"))
        rows.append(
            ExternalIntegrationStatus(
                method_id=method.method_id,
                name=method.name,
                integration_wave=method.integration_wave,
                role=method.role,
                gate=method.gate,
                repo_name=repo_name,
                repo_registered=repo_registered,
                repo_available=repo_available,
                executable=executable,
                status="adapter_ready" if executable else "registered_status_only" if repo_registered else "missing",
                adapter="safe_status_and_smoke_job",
                warnings=warnings,
            )
        )
    return rows


def external_status_payload() -> dict[str, Any]:
    rows = [row.model_dump() for row in list_external_integration_status()]
    return {
        "success": True,
        "integration_order": [row["method_id"] for row in rows if row["integration_wave"] == 1],
        "records": rows,
        "limitations": "This adapter reports readiness and launches bounded smoke jobs; it does not claim full scientific validation.",
    }


def launch_external_smoke_jobs(method_ids: list[str] | None = None) -> dict[str, Any]:
    """Launch bounded background smoke/status jobs with nohup-style logs.

    These jobs are intentionally light: they record adapter status and do not run
    folding, training, docking, or long model inference.
    """

    RUN_DIR.mkdir(parents=True, exist_ok=True)
    selected = set(method_ids or [])
    jobs = []
    for row in list_external_integration_status():
        if selected and row.method_id not in selected:
            continue
        log_path = RUN_DIR / f"{row.method_id}.log"
        payload_path = RUN_DIR / f"{row.method_id}.json"
        code = (
            "import json, pathlib, datetime; "
            f"payload={json.dumps(row.model_dump(), sort_keys=True)!r}; "
            f"path=pathlib.Path({str(payload_path)!r}); "
            "data=json.loads(payload); "
            "data['checked_at']=datetime.datetime.now(datetime.timezone.utc).isoformat(); "
            "path.write_text(json.dumps(data, indent=2), encoding='utf-8'); "
            "print(json.dumps({'success': True, 'method_id': data['method_id'], 'status': data['status']}))"
        )
        with log_path.open("ab") as log:
            proc = subprocess.Popen(
                ["nohup", "python", "-c", code],
                cwd=str(PROJECT_ROOT),
                stdout=log,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            )
        jobs.append(
            {
                "method_id": row.method_id,
                "pid": proc.pid,
                "log_path": str(log_path),
                "payload_path": str(payload_path),
                "launched_at": datetime.now(timezone.utc).isoformat(),
            }
        )
    return {"success": True, "jobs": jobs, "run_dir": str(RUN_DIR)}


def read_external_smoke_results() -> dict[str, Any]:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    records = []
    for path in sorted(RUN_DIR.glob("*.json")):
        try:
            records.append(json.loads(path.read_text(encoding="utf-8")))
        except Exception as exc:
            records.append({"path": str(path), "status": "unreadable", "error": str(exc)})
    return {"success": True, "records": records, "run_dir": str(RUN_DIR)}
