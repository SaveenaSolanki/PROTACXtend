"""Build an EvidenceRunRecord from on-disk artifacts (strategy + manifest
+ optional stage trace). The raw strategy JSON is preserved verbatim."""

from __future__ import annotations

import json, os, platform
from typing import Any

from protacxtend.reporting.run_record import EvidenceRunRecord, ToolCallRecord, now_iso


def _load(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def build_from_artifacts(strategy_path: str, manifest_path: str | None = None,
                         trace_path: str | None = None) -> EvidenceRunRecord:
    strategy = _load(strategy_path)
    manifest = _load(manifest_path) if manifest_path and os.path.exists(manifest_path) else {}
    trace = _load(trace_path) if trace_path and os.path.exists(trace_path) else None

    run_id = strategy.get("run_id") or manifest.get("run_id") or os.path.basename(
        os.path.dirname(strategy_path)) or "run"

    tool_calls: list[ToolCallRecord] = []
    rt = manifest.get("module_runtimes") or {}
    ms = manifest.get("module_status") or {}
    for mod in (manifest.get("module_status") or {}):
        tool_calls.append(ToolCallRecord(
            tool=f"module:{mod}",
            version=f"protacxtend-{manifest.get('protacxtend_version') or '0.3.0'}",
            parameters={},
            output=None,
            error=None if ms.get(mod) in ("succeeded", None) else ms.get(mod),
            started_wall=manifest.get("started_at"),
            finished_wall=manifest.get("finished_at"),
            elapsed_s=rt.get(mod),
            source_identifiers=[],
        ))
    if trace and isinstance(trace.get("stages"), list):
        for st in trace["stages"]:
            tool_calls.append(ToolCallRecord(
                tool=f"node:{st.get('node', '')}",
                version="protacxtend-0.3.0 (deterministic engine)",
                parameters={"request": trace.get("request", strategy.get("request", ""))},
                output=None,
                error="; ".join(st.get("errors") or []) or None,
                finished_wall=now_iso(),
                elapsed_s=st.get("elapsed_s"),
                source_identifiers=[],
            ))

    artifact_paths = [strategy_path]
    if manifest_path and os.path.exists(manifest_path):
        artifact_paths.append(manifest_path)
    if trace_path and os.path.exists(trace_path):
        artifact_paths.append(trace_path)

    return EvidenceRunRecord(
        run_id=run_id,
        question=strategy.get("request") or manifest.get("request") or "",
        inputs={"request": strategy.get("request", ""),
                "execution_mode": strategy.get("execution_mode") or manifest.get("execution_mode"),
                "disease_context": strategy.get("disease_context"),
                "e3_ligase": strategy.get("e3_ligase")},
        tool_calls=tool_calls,
        final_output=strategy,
        raw_json_path=strategy_path,
        artifact_paths=artifact_paths,
        provenance={
            "engine": manifest.get("engine") or "deterministic",
            "execution_mode": strategy.get("execution_mode") or manifest.get("execution_mode"),
            "protacxtend_version": manifest.get("protacxtend_version") or "0.3.0",
            "host": platform.node(),
            "runtime_s": manifest.get("runtime_s"),
            "started_at": manifest.get("started_at"),
            "finished_at": manifest.get("finished_at"),
            "warnings": strategy.get("warnings") or [],
            "errors": [],
            "limitations": strategy.get("limitations") or [],
            "evidence_summary": manifest.get("evidence_summary") or {},
            "module_status": manifest.get("module_status") or {},
        },
        validation={"reviewer": "", "date": "", "status": "unassessed", "reason": ""},
    )