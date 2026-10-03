"""System-wide planning execution contract.

This module wraps the existing deterministic goal planner with a durable run
contract for TUI and API callers: immediate run id, stage progress, persisted
plan/status artifacts, typed failures, and retry deduplication. It deliberately
keeps planning as planning; no design work is executed here.
"""

from __future__ import annotations

import concurrent.futures
import copy
import hashlib
import json
import os
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from protacxtend.planning.goal_planner import build_plan, plan_payload
from protacxtend.planning.planner import plan_request

PLAN_ROOT = Path("outputs/workflows/plan_runs")


class PlanningBackendUnavailable(RuntimeError):
    """Raised when the deterministic planning backend cannot run."""


class PlanningTimeout(RuntimeError):
    """Raised when an optional model-backed planning step times out."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _normalise_request(text: str) -> str:
    cleaned = " ".join((text or "").strip().split())
    if cleaned.lower().startswith("/plan "):
        cleaned = cleaned.split(None, 1)[1]
    return cleaned


def stable_plan_run_id(request: str, conversation_id: str = "default") -> str:
    basis = f"plan.v1|{conversation_id or 'default'}|{_normalise_request(request).lower()}"
    return "plan_" + hashlib.sha256(basis.encode("utf-8")).hexdigest()[:16]


def _request_id(run_id: str) -> str:
    return "req_" + hashlib.sha256(f"request|{run_id}".encode("utf-8")).hexdigest()[:16]


def _json_default(obj: Any) -> Any:
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    return str(obj)


def _write_json(path: Path, payload: dict[str, Any] | list[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=_json_default))


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def _paths(run_id: str) -> dict[str, Path]:
    root = PLAN_ROOT / run_id
    return {
        "run_dir": root,
        "status_json": root / "status.json",
        "plan_json": root / "plan.json",
        "timeline_json": root / "stage_timeline.json",
        "transcript_jsonl": root / "transcript.jsonl",
        "exceptions_jsonl": root / "exceptions.jsonl",
    }


def _artifact_paths(paths: dict[str, Path]) -> dict[str, str]:
    return {k: str(v.resolve()) for k, v in paths.items() if k != "run_dir"}


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(payload, sort_keys=True, default=_json_default) + "\n")


def _backend_health() -> dict[str, Any]:
    try:
        from protacxtend.llm.providers import get_config, provider_health
        cfg = get_config()
        health = provider_health(cfg)
        return {
            "provider": cfg.provider,
            "model": cfg.model,
            "base_url": cfg.base_url,
            "timeout_s": cfg.timeout_s,
            "healthy": bool(health.get("ok")),
            "health": health,
        }
    except Exception as exc:  # noqa: BLE001
        return {"healthy": False, "error": str(exc), "timeout_s": None}


def _resource_reason_summary_for(text: str, *, offline: bool = True) -> dict[str, Any]:
    if not (text or "").strip():
        return {}
    try:
        from protacxtend.workflows.resource_audit import shortlist_resources
        return shortlist_resources(text, offline=offline, top_k=16).get("resource_reason_summary", {})
    except Exception as exc:  # noqa: BLE001
        return {"schema_version": "resource-reason-summary.v1", "error": str(exc)}




def _outcome_flags(payload: dict[str, Any]) -> dict[str, bool]:
    kind = str(payload.get("run_status") or payload.get("kind") or payload.get("status") or "")
    target = payload.get("target") or {}
    tasks = payload.get("tasks") or []
    return {
        "request_completed": True,
        "plan_generated": bool(kind and kind != "clarification_needed" and kind != "failed" and tasks),
        "scientific_answer_supported": bool(kind and kind != "clarification_needed" and kind != "failed" and target and tasks),
    }


def _resource_timeout_summary(text: str, timeout_s: float, *, backend_continues: bool) -> dict[str, Any]:
    return {
        "schema_version": "resource-reason-summary.v1",
        "status": "partial_timeout",
        "request": text,
        "timeout_s": timeout_s,
        "backend_continues_after_timeout": backend_continues,
        "late_results_can_overwrite": False,
        "selected": [],
        "rejected": [],
        "limitation": "resource-reason selection exceeded the planning timeout; target planning continued with explicit evidence gaps",
    }


def _bounded_resource_summary(text: str, *, offline: bool, timeout_s: float) -> tuple[dict[str, Any], dict[str, Any]]:
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="protac-plan-resource")
    fut = executor.submit(_resource_reason_summary_for, text, offline=offline)
    try:
        summary = fut.result(timeout=timeout_s)
        executor.shutdown(wait=False, cancel_futures=True)
        return summary, {"status": "completed", "backend_continues_after_timeout": False}
    except concurrent.futures.TimeoutError:
        cancelled = fut.cancel()
        executor.shutdown(wait=False, cancel_futures=True)
        continues = not cancelled
        return _resource_timeout_summary(text, timeout_s, backend_continues=continues), {
            "status": "timeout", "backend_continues_after_timeout": continues,
            "timeout_s": timeout_s,
        }
    except Exception as exc:  # noqa: BLE001
        executor.shutdown(wait=False, cancel_futures=True)
        return {"schema_version": "resource-reason-summary.v1", "status": "failed", "error": str(exc),
                "late_results_can_overwrite": False, "selected": [], "rejected": []}, {
            "status": "failed", "error": str(exc),
        }

def llm_plan(**_: Any) -> dict[str, Any] | None:
    """Optional model-backed planning hook.

    The current production route is deterministic. Tests and future providers
    may inject this hook; when it is absent or skipped, callers get a clearly
    labeled deterministic plan rather than an LLM-completed plan.
    """
    return None


class _Recorder:
    def __init__(self, *, run_id: str, request_id: str, paths: dict[str, Path],
                 emit_event: Callable[[dict[str, Any]], None] | None):
        self.run_id = run_id
        self.request_id = request_id
        self.paths = paths
        self.emit_event = emit_event
        self.timeline: list[dict[str, Any]] = []

    def emit(self, event: dict[str, Any]) -> None:
        event = {"timestamp": _utc_now(), "run_id": self.run_id,
                 "request_id": self.request_id, **event}
        _append_jsonl(self.paths["transcript_jsonl"], event)
        if self.emit_event:
            self.emit_event(event)

    def stage(self, stage: str, status: str, *, detail: str = "",
              extra: dict[str, Any] | None = None, started: float | None = None) -> dict[str, Any]:
        elapsed = None if started is None else round(time.perf_counter() - started, 6)
        item = {"stage": stage, "status": status, "detail": detail,
                "timestamp": _utc_now()}
        if elapsed is not None:
            item["elapsed_s"] = elapsed
        if extra:
            item.update(extra)
        self.timeline.append(item)
        ev = {"type": "progress", **item}
        self.emit(ev)
        return item

    def status(self, status: str, current_stage: str, **extra: Any) -> None:
        payload = {"run_id": self.run_id, "request_id": self.request_id,
                   "status": status, "current_stage": current_stage,
                   "updated_at": _utc_now(), **extra}
        _write_json(self.paths["status_json"], payload)

    def exception(self, stage: str, exc: BaseException, error_type: str) -> dict[str, Any]:
        payload = {"timestamp": _utc_now(), "run_id": self.run_id,
                   "request_id": self.request_id, "stage": stage,
                   "error_type": error_type, "message": str(exc),
                   "traceback": traceback.format_exc()}
        _append_jsonl(self.paths["exceptions_jsonl"], payload)
        return payload


def _typed_failure(stage: str, exc: BaseException, error_type: str,
                   *, backend_continues_after_timeout: bool | None = None) -> dict[str, Any]:
    out = {"stage": stage, "error_type": error_type, "message": str(exc)}
    if backend_continues_after_timeout is not None:
        out["backend_continues_after_timeout"] = backend_continues_after_timeout
    return out


def _run_llm_step(*, request: str, conversation_id: str, timeout_s: float,
                  recorder: _Recorder) -> tuple[str, dict[str, Any] | None]:
    start = time.perf_counter()
    recorder.stage("llm_planning", "started", detail="optional model-backed planner", started=start)
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="protac-plan-llm")
    fut = executor.submit(llm_plan, request=request, conversation_id=conversation_id)
    try:
        value = fut.result(timeout=timeout_s)
        executor.shutdown(wait=False, cancel_futures=True)
        if value:
            recorder.stage("llm_planning", "completed", detail="model-backed planner returned", started=start)
            return "llm_completed", value
        recorder.stage("llm_planning", "unavailable", detail="no model-backed plan available", started=start)
        return "unavailable", None
    except concurrent.futures.TimeoutError as exc:
        cancelled = fut.cancel()
        executor.shutdown(wait=False, cancel_futures=True)
        continues = not cancelled
        recorder.stage("llm_planning", "timeout", detail=f"timed out after {timeout_s:g}s",
                       extra={"backend_continues_after_timeout": continues}, started=start)
        return "timeout", _typed_failure("llm_planning", PlanningTimeout(f"LLM planning timed out after {timeout_s:g}s"),
                                          "timeout", backend_continues_after_timeout=continues)
    except Exception as exc:  # noqa: BLE001
        executor.shutdown(wait=False, cancel_futures=True)
        recorder.exception("llm_planning", exc, "exception")
        recorder.stage("llm_planning", "failed", detail=str(exc)[:240], started=start)
        return "failed", _typed_failure("llm_planning", exc, "exception")


def _cached_payload(paths: dict[str, Path]) -> dict[str, Any] | None:
    if not paths["plan_json"].exists() or not paths["status_json"].exists():
        return None
    try:
        status = _read_json(paths["status_json"])
        if status.get("status") not in {"ready", "clarification_needed", "failed"}:
            return None
        payload = _read_json(paths["plan_json"])
        payload["cache_hit"] = True
        return payload
    except Exception:  # noqa: BLE001
        return None


def execute_plan_contract(request: str, *, conversation_id: str = "default", offline: bool = False,
                          emit_event: Callable[[dict[str, Any]], None] | None = None,
                          use_llm_planner: bool = False) -> dict[str, Any]:
    text = _normalise_request(request)
    if not text:
        return {"type": "plan_answer", "kind": "error", "status": "failed", "final": True,
                "answer": "plan: empty request", "conversation_id": conversation_id,
                "request_completed": True, "plan_generated": False, "scientific_answer_supported": False}

    run_id = stable_plan_run_id(text, conversation_id)
    request_id = _request_id(run_id)
    paths = _paths(run_id)
    recorder = _Recorder(run_id=run_id, request_id=request_id, paths=paths, emit_event=emit_event)

    recorder.emit({"type": "plan_start", "request": text, "conversation_id": conversation_id,
                   "artifact_dir": str(paths["run_dir"].resolve())})

    cached = _cached_payload(paths)
    if cached is not None:
        # Rehydrate conversation target state for correction flows without
        # rebuilding/persisting duplicate plan work.
        try:
            plan_request(text, conversation_id=conversation_id, offline=offline)
        except Exception:
            pass
        cached = copy.deepcopy(cached)
        cached.update(_outcome_flags(cached))
        recorder.stage("dedupe", "cache_hit", detail="persisted plan reused")
        return cached

    paths["run_dir"].mkdir(parents=True, exist_ok=True)
    recorder.status("running", "received", request=text, conversation_id=conversation_id)

    backend_health = _backend_health()
    typed_failure: dict[str, Any] | None = None
    llm_payload: dict[str, Any] | None = None
    planning_mode = "deterministic"
    llm_completed = False

    start = time.perf_counter()
    try:
        recorder.status("running", "target_resolution")
        s = time.perf_counter()
        resolution = plan_request(text, conversation_id=conversation_id, offline=offline)
        target_payload = resolution.target.__dict__ if getattr(resolution, "target", None) else None
        recorder.stage("target_resolution", "completed", detail=getattr(resolution, "interpretation_line", ""),
                       extra={"target": target_payload, "resolver_status": resolution.status}, started=s)

        recorder.status("running", "resource_retrieval")
        s = time.perf_counter()
        resource_timeout_s = float(os.environ.get("PROTACXTEND_PLAN_RESOURCE_TIMEOUT_S", "2.0"))
        resource_summary, resource_state = _bounded_resource_summary(text, offline=offline, timeout_s=resource_timeout_s)
        recorder.stage("resource_retrieval", resource_state.get("status", "completed"),
                       detail=("resource reasons selected" if resource_state.get("status") == "completed"
                               else "resource retrieval bounded; partial evidence retained"),
                       extra={"resource_reason_summary": resource_summary, **resource_state}, started=s)

        if use_llm_planner:
            timeout_s = float(os.environ.get("PROTACXTEND_PLAN_LLM_TIMEOUT_S", "30"))
            state, llm_result = _run_llm_step(request=text, conversation_id=conversation_id,
                                             timeout_s=timeout_s, recorder=recorder)
            if state == "llm_completed" and llm_result:
                llm_payload = llm_result
                llm_completed = True
                planning_mode = "llm"
            elif state in {"timeout", "failed"}:
                typed_failure = llm_result
                planning_mode = "deterministic_fallback"
        else:
            recorder.stage("llm_planning", "skipped", detail="model-backed planning not requested")

        recorder.status("running", "planner")
        s = time.perf_counter()
        plan = build_plan(text, conversation_id=conversation_id, offline=offline)
        payload = plan_payload(plan)
        recorder.stage("planner", "completed", detail=plan.run_status,
                       extra={"plan_id": plan.plan_id, "run_status": plan.run_status}, started=s)

        if llm_payload:
            payload.update(llm_payload)

        recorder.status("running", "response_serialization")
        s = time.perf_counter()
        payload.update({
            "type": "plan_answer",
            "kind": payload.get("run_status", plan.run_status),
            "status": payload.get("run_status", plan.run_status),
            "run_id": run_id,
            "request_id": request_id,
            "conversation_id": conversation_id,
            "request": text,
            "resource_reason_summary": resource_summary,
            "backend_health": backend_health,
            "planning_mode": planning_mode,
            "llm_completed": llm_completed,
            "typed_failure": typed_failure,
            "cache_hit": False,
            "artifact_paths": _artifact_paths(paths),
            "timing": {"wall_s": round(time.perf_counter() - start, 6)},
        })
        payload.update(_outcome_flags(payload))
        recorder.stage("response_serialization", "completed", detail="plan payload serialized", started=s)

        recorder.status("running", "persistence")
        s = time.perf_counter()
        payload["stage_timeline"] = recorder.timeline
        _write_json(paths["plan_json"], payload)
        _write_json(paths["timeline_json"], recorder.timeline)
        final_status = "clarification_needed" if plan.run_status == "clarification_needed" else "ready"
        recorder.status(final_status, "complete", artifact_paths=_artifact_paths(paths),
                        run_status=plan.run_status)
        recorder.stage("persistence", "completed", detail="plan artifacts persisted", started=s)
        payload["stage_timeline"] = recorder.timeline
        _write_json(paths["plan_json"], payload)
        return payload

    except PlanningBackendUnavailable as exc:
        failure = _typed_failure("planner", exc, "backend_unavailable")
        recorder.exception("planner", exc, "backend_unavailable")
        recorder.stage("planner", "failed", detail=str(exc)[:240])
    except Exception as exc:  # noqa: BLE001
        failure = _typed_failure("planner", exc, "exception")
        recorder.exception("planner", exc, "exception")
        recorder.stage("planner", "failed", detail=str(exc)[:240])

    payload = {
        "type": "plan_answer",
        "kind": "failed",
        "status": "failed",
        "final": True,
        "run_id": run_id,
        "request_id": request_id,
        "conversation_id": conversation_id,
        "request": text,
        "typed_failure": failure,
        "backend_health": backend_health,
        "planning_mode": "failed",
        "llm_completed": False,
        "stage_timeline": recorder.timeline,
        "artifact_paths": _artifact_paths(paths),
        "cache_hit": False,
        "executed_design": False,
        "executed_investigation": False,
        "request_completed": True,
        "plan_generated": False,
        "scientific_answer_supported": False,
    }
    _write_json(paths["plan_json"], payload)
    _write_json(paths["timeline_json"], recorder.timeline)
    recorder.status("failed", failure["stage"], artifact_paths=_artifact_paths(paths), typed_failure=failure)
    return payload
