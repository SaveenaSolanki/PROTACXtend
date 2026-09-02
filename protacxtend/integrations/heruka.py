"""
HERUKA.AI integration — channel ProtacPilot results to a human-centric frontend.
================================================================================

Design aligned with HERUKA principles (explainability, governance, no
hallucination, human agency):

  - the exported bundle contains ONLY auditable artifacts: decisions,
    reason codes, tool calls, uncertainty, human-gate decisions, provenance
    and the final report. NO raw chain-of-thought is ever exported.
  - every numeric claim carries tool/version/uncertainty provenance.
  - human decisions (gate outcomes) are recorded verbatim, never inferred.

Transport: a configurable webhook (HERUKA_WEBHOOK_URL) or a local export
package (JSON bundle) that a HERUKA-hosted frontend can render.

CLI (Feynman-style):
    python -m protacxtend.integrations.heruka export --run <run_id> --out bundle.json
    python -m protacxtend.integrations.heruka push --run <run_id>
    python -m protacxtend.integrations.heruka status
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("protacpilot.heruka")

ROOT = Path(__file__).resolve().parents[2]
WEBHOOK_URL = os.environ.get("HERUKA_WEBHOOK_URL", "")
API_TOKEN = os.environ.get("HERUKA_API_TOKEN", "")
EXPORT_DIR = ROOT / "outputs" / "heruka"

BUNDLE_SCHEMA_VERSION = "protacpilot-bundle-v1"


def _load_run(run_id: str) -> Dict[str, Any]:
    """Load a run's trace + summary from the observability store."""
    trace_file = ROOT / "outputs" / "runs" / run_id / "trace.jsonl"
    summary_file = ROOT / "outputs" / "runs" / run_id / "summary.json"
    trace: List[Dict[str, Any]] = []
    if trace_file.exists():
        with trace_file.open("r", encoding="utf-8") as f:
            for line in f:
                try:
                    trace.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    summary = {}
    if summary_file.exists():
        summary = json.loads(summary_file.read_text(encoding="utf-8"))
    if not trace and not summary:
        raise FileNotFoundError(f"No run artifacts for run_id={run_id}")
    return {"run_id": run_id, "summary": summary, "trace": trace}


def build_bundle(run_id: str, include_report: bool = True) -> Dict[str, Any]:
    """Build the auditable export bundle for one run.

    Contents (all auditable; no chain-of-thought):
      - run envelope (run_id, mode, status, runtime)
      - decisions (node, decision_type, reason_codes, confidence, next_node)
      - tool calls (tool, args summary, result summary, elapsed)
      - human-gate events (from trace)
      - uncertainty + applicability-domain notes (from trace/tool calls)
      - final report (if available on disk)
    """
    run = _load_run(run_id)
    trace = run["trace"]
    summary = run["summary"]

    decisions = [
        {k: t.get(k) for k in ("node", "decision_type", "reason_codes",
                               "confidence", "next_node", "elapsed_s")}
        for t in trace if t.get("event") == "decision"
    ]
    tool_calls = [
        {k: t.get(k) for k in ("tool", "args", "result_summary", "elapsed_s")}
        for t in trace if t.get("event") == "tool_call"
    ]
    human_gates = [
        {k: t.get(k) for k in ("node", "status", "elapsed_s")}
        for t in trace if t.get("event") == "node_end" and "human" in str(t.get("node", "")).lower()
    ]

    bundle: Dict[str, Any] = {
        "schema": BUNDLE_SCHEMA_VERSION,
        "produced_by": "SynGlue v0.3-agentic-core",
        "run_id": run_id,
        "mode": summary.get("meta", {}).get("mode", "agentic"),
        "status": summary.get("status"),
        "runtime_s": summary.get("runtime_s"),
        "n_decisions": len(decisions),
        "n_tool_calls": len(tool_calls),
        "decisions": decisions,
        "tool_calls": tool_calls,
        "human_gate_events": human_gates,
        "uncertainty_notes": [
            t for t in trace
            if t.get("event") in ("decision", "tool_call")
            and any(k in str(t) for k in ("uncertain", "ad_status", "out_of_domain", "nn_tanimoto"))
        ][:10],
        "evidence_refs": _collect_evidence_refs(trace),
    }

    if include_report:
        report_path = ROOT / "outputs" / "runs" / run_id / "report.md"
        if report_path.exists():
            bundle["report"] = report_path.read_text(encoding="utf-8")

    return bundle


def _collect_evidence_refs(trace: List[Dict[str, Any]]) -> List[str]:
    refs: List[str] = []
    for t in trace:
        if t.get("event") == "decision" and t.get("evidence_refs"):
            refs.extend(t["evidence_refs"])
    return list(dict.fromkeys(refs))


def export_bundle(run_id: str, out: Optional[str] = None) -> Path:
    """Write the bundle JSON to outputs/heruka/<run_id>.json (or out)."""
    bundle = build_bundle(run_id)
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = Path(out) if out else EXPORT_DIR / f"{run_id}.json"
    path.write_text(json.dumps(bundle, indent=2, default=str), encoding="utf-8")
    logger.info("bundle exported: %s (%d decisions, %d tool calls)",
                path, bundle["n_decisions"], bundle["n_tool_calls"])
    return path


def push_bundle(run_id: str, url: Optional[str] = None,
                token: Optional[str] = None) -> Dict[str, Any]:
    """POST the auditable bundle to the HERUKA webhook endpoint.

    Configuration: HERUKA_WEBHOOK_URL, HERUKA_API_TOKEN (Bearer auth).
    Non-fatal: if the endpoint is unreachable, the bundle stays on disk and
    the error is returned (the run is never lost).
    """
    import requests
    endpoint = url or WEBHOOK_URL
    if not endpoint:
        return {"ok": False, "error": "HERUKA_WEBHOOK_URL not configured",
                "bundle_saved": str(export_bundle(run_id))}

    bundle = build_bundle(run_id)
    headers = {"Content-Type": "application/json"}
    if token or API_TOKEN:
        headers["Authorization"] = f"Bearer {token or API_TOKEN}"

    try:
        resp = requests.post(endpoint, json=bundle, headers=headers, timeout=30)
        if resp.ok:
            logger.info("bundle pushed to %s (HTTP %d)", endpoint, resp.status_code)
            return {"ok": True, "status_code": resp.status_code,
                    "response": resp.text[:200], "bundle_saved": str(export_bundle(run_id))}
        return {"ok": False, "status_code": resp.status_code,
                "response": resp.text[:200], "bundle_saved": str(export_bundle(run_id))}
    except Exception as exc:
        logger.warning("HERUKA push failed: %s", exc)
        return {"ok": False, "error": str(exc)[:200],
                "bundle_saved": str(export_bundle(run_id))}


def status() -> Dict[str, Any]:
    """Integration status for the UI/CLI."""
    return {
        "webhook_configured": bool(WEBHOOK_URL),
        "webhook_url": WEBHOOK_URL or "(not set — set HERUKA_WEBHOOK_URL)",
        "auth": "Bearer" if API_TOKEN else "none",
        "export_dir": str(EXPORT_DIR),
        "bundle_schema": BUNDLE_SCHEMA_VERSION,
        "bundles_on_disk": sorted(p.name for p in EXPORT_DIR.glob("*.json")) if EXPORT_DIR.exists() else [],
    }


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="HERUKA.AI integration (Feynman CLI)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_exp = sub.add_parser("export", help="export a run as an auditable bundle")
    p_exp.add_argument("--run", required=True)
    p_exp.add_argument("--out", default="")

    p_push = sub.add_parser("push", help="push a run bundle to the HERUKA webhook")
    p_push.add_argument("--run", required=True)
    p_push.add_argument("--url", default="")

    p_status = sub.add_parser("status", help="integration status")

    args = ap.parse_args()
    if args.cmd == "export":
        p = export_bundle(args.run, args.out or None)
        print(f"exported: {p}")
    elif args.cmd == "push":
        r = push_bundle(args.run, args.url or None)
        print(json.dumps(r, indent=2))
    elif args.cmd == "status":
        print(json.dumps(status(), indent=2))
