"""End-to-end audit through the real public interfaces.

Each request travels: surface (CLI / FastAPI HTTP / TUI bridge) -> shared
capability executor -> acquisition resolver -> tool/backend -> output
validation -> provenance record. Results are written to
``results/audit/end_to_end_audit.csv`` and summarised in ``audit.json``.

Metrics reported per request: execution success, acquisition success, fallback
success, output validity, replay success, latency, failure recovery and silent
scientific failure.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# (capability, params, expect_failure)
REQUESTS: list[tuple[str, dict, bool]] = [
    ("chemistry", {"smiles": "CCO", "operation": "descriptors"}, False),
    ("chemistry", {"smiles": "c1ccccc1", "operation": "descriptors"}, False),
    ("chemistry", {"smiles": "not_a_smiles"}, True),
    ("admet", {"smiles": "CCO"}, False),
    ("admet", {"smiles": "CC(=O)Oc1ccccc1C(=O)O"}, False),
    ("conformer_generation", {"smiles": "CCO", "n_conformers": 3}, False),
    ("linker_analysis", {"linker_smiles": "CCOCC"}, False),
    ("candidate_ranking", {}, False),
    ("predict_degradation", {"smiles": "CCO", "e3": "CRBN"}, False),
    ("inspect_smiles", {"smiles": "CCO"}, False),
    ("protein_structure", {"identifier": "P00533"}, False),
]


def _data_hash(exec_result: dict) -> str:
    return hashlib.sha256(json.dumps(exec_result.get("result", {}).get("data", {}),
                                     sort_keys=True, default=str).encode()).hexdigest()[:16]


def _via_api(cap: str, params: dict, client) -> tuple[dict, str]:
    try:
        r = client.post(f"/capabilities/{cap}/run", json={"params": params}, timeout=180)
        if r.status_code >= 500:
            return {}, f"HTTP {r.status_code}"
        return r.json(), f"HTTP {r.status_code}"
    except Exception as exc:  # noqa: BLE001
        return {}, f"{type(exc).__name__}: {exc}"


def _via_cli(cap: str, params: dict) -> tuple[dict, str]:
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "protacxtend.cli", "capabilities", cap, "--json", "--run",
             "--params", json.dumps(params)],
            capture_output=True, text=True, timeout=300, cwd=str(ROOT))
        out = proc.stdout
        start = out.find("{")
        if start >= 0:
            try:
                return json.loads(out[start:]), f"rc={proc.returncode}"
            except Exception:  # noqa: BLE001
                pass
        return {}, f"rc={proc.returncode}; unparsable stdout"
    except Exception as exc:  # noqa: BLE001
        return {}, f"{type(exc).__name__}: {exc}"


def _via_tui(cap: str, params: dict) -> tuple[dict, str]:
    try:
        payload = json.dumps({"type": "capability", "name": cap, "params": params}) + "\n"
        proc = subprocess.run([sys.executable, "-m", "protacxtend.tui_bridge.server"],
                              input=payload, capture_output=True, text=True, timeout=300,
                              cwd=str(ROOT))
        for line in proc.stdout.splitlines():
            line = line.strip()
            if line.startswith("{"):
                obj = json.loads(line)
                if obj.get("type") == "capability_result":
                    return obj.get("result", {}), "bridge ok"
        return {}, f"rc={proc.returncode}; no capability_result"
    except Exception as exc:  # noqa: BLE001
        return {}, f"{type(exc).__name__}: {exc}"


def run_e2e(n: int = 50) -> tuple[list, dict]:
    from protacxtend.runtime.audit import Row  # reuse the audit row shape

    try:
        from fastapi.testclient import TestClient
        from protacxtend.backend.api_routes import get_app
        client = TestClient(get_app())
    except Exception as exc:  # noqa: BLE001
        client = None

    surfaces = ["cli", "api", "tui"]
    rows: list[dict] = []
    counters = {"execution_success": 0, "acquisition_success": 0, "winner_fallback": 0,
                "output_valid": 0, "replay_success": 0, "failure_recovery": 0,
                "silent_scientific_failure": 0, "malformed": 0, "fallback_needed": 0}
    latencies: list[float] = []

    for i in range(n):
        cap, params, expect_failure = REQUESTS[i % len(REQUESTS)]
        surface = surfaces[i % len(surfaces)]
        t0 = time.time()
        if surface == "api" and client is not None:
            res, transport = _via_api(cap, params, client)
        elif surface == "tui":
            res, transport = _via_tui(cap, params)
        else:
            res, transport = _via_cli(cap, params)
        latency = time.time() - t0
        latencies.append(latency)

        executed = bool(res.get("executed"))
        output_valid = bool(res.get("output_valid"))
        state = (res.get("resolution") or {}).get("state", "")
        result = res.get("result") or {}
        status = str(result.get("status", "")).lower()
        data = result.get("data") or {}
        nonfinite = bool(result.get("non_finite_sanitized"))
        provenance = bool((res.get("provenance") or {}).get("timestamp_utc"))
        test = "malformed_recovery" if expect_failure else "interface_traversal"

        recovered = False
        success = False
        if expect_failure:
            counters["malformed"] += 1
            recovered = (not executed) or (not output_valid) or status not in ("success", "warning")
            counters["failure_recovery"] += int(recovered)
            if status in ("success", "warning"):
                counters["silent_scientific_failure"] += 1
        else:
            success = executed and output_valid and status in ("success", "warning") and bool(data)
            counters["execution_success"] += int(success)
            if status in ("success", "warning") and (not output_valid or not data or nonfinite):
                counters["silent_scientific_failure"] += 1

        state_ok = state in ("READY", "INSTALLABLE", "FALLBACK", "REMOTE")
        counters["acquisition_success"] += int(state_ok)
        if state and state != "READY":
            counters["fallback_needed"] += 1
            counters["winner_fallback"] += int(state in ("FALLBACK", "INSTALLABLE", "REMOTE"))
        counters["output_valid"] += int(output_valid)

        replay_ok = ""
        if i % 4 == 0 and not expect_failure:
            if surface == "api" and client is not None:
                res2, _ = _via_api(cap, params, client)
            elif surface == "cli":
                res2, _ = _via_cli(cap, params)
            else:
                res2, _ = _via_tui(cap, params)
            replay_ok = str(_data_hash(res) == _data_hash(res2))
            counters["replay_success"] += int(replay_ok == "True")

        rows.append(Row(
            id=f"e2e:{i:03d}:{surface}:{cap}", kind="end_to_end", name=f"{surface}:{cap}",
            test=test, status="pass" if (success or (expect_failure and recovered)) else "fail",
            detail=(f"state={state} status={status} transport={transport} "
                    f"valid={output_valid} data={bool(data)} replay={replay_ok} "
                    f"prov={provenance} nonfinite={nonfinite}")[:240],
            latency_s=round(latency, 2), evidence="results/audit/end_to_end_audit.csv").to_dict())

    total = max(n, 1)
    non_malformed = sum(1 for i in range(n) if not REQUESTS[i % len(REQUESTS)][2])
    replay_rows = [r for r in rows if "replay=True" in r["detail"] or "replay=False" in r["detail"]]
    fb_needed = counters["fallback_needed"]
    summary = {
        "requests": n,
        "malformed_requests": counters["malformed"],
        "execution_success_rate": round(counters["execution_success"] / max(1, non_malformed), 3),
        "acquisition_success_rate": round(counters["acquisition_success"] / total, 3),
        "fallback_success_rate": (round(counters["winner_fallback"] / fb_needed, 3)
                                  if fb_needed else None),
        "fallback_requests": fb_needed,
        "output_validity_rate": round(counters["output_valid"] / total, 3),
        "replay_success_rate": round(counters["replay_success"] / max(1, len(replay_rows)), 3),
        "failure_recovery_rate": round(counters["failure_recovery"] / max(1, counters["malformed"]), 3),
        "silent_scientific_failures": counters["silent_scientific_failure"],
        "latency_s": {
            "mean": round(sum(latencies) / total, 3),
            "p50": round(sorted(latencies)[total // 2], 3),
            "max": round(max(latencies), 3),
        },
        "by_surface": {s: sum(1 for r in rows if f":{s}:" in r["id"]) for s in surfaces},
    }
    return _rows_from_dicts(rows), summary


def _rows_from_dicts(rows: list[dict]) -> list:
    from protacxtend.runtime.audit import Row
    return [Row(**r) for r in rows]
