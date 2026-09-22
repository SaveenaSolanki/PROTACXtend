"""Live benchmark adapters — Sprint 2C (benchmark execution).

Three real systems run against the frozen 48-task benchmark:

* ``PROTACXtend``            — the full PROTACXtend conversational agent
  (strict tool registry -> optional deterministic SynGlue graph handoff).
* ``Base-LLM-control``       — same underlying model (deepseek-v4-flash),
  plain chat, NO tools/agents/retrieval/orchestration.
* ``AI-Co-Scientist-compatible`` — the local co-scientist *workflow shape*
  defined in benchmark/BASELINES.md (hypothesis generation -> evaluation ->
  synthesis over the same model). This is NOT the Google AI Co-Scientist
  service (formally UNAVAILABLE in this environment; see configs/).

Every adapter fails closed unless ``allow_real=True`` (mirrors the Sprint 2B
lock). Ground truth is never loaded here — adapters only see the blinded task
record (``TaskInput``). Raw model responses, tool transcripts, timings and
usage are captured and returned to the runner envelope for storage *before*
any scoring.

The shared chat client talks directly to the same provider endpoint/model as
the PROTACXtend runtime (deepseek / deepseek-v4-flash @ https://api.deepseek.com)
with a ``max_tokens`` cap so worst-case latency stays bounded; sampling is
temperature 0 / deterministic. Real prompt/completion token usage is recorded.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from benchmark_runner.runner import AdapterError, SystemAdapter, TaskInput

# ── shared runtime identity ────────────────────────────────────────────
PROVIDER = "deepseek"
MODEL = "deepseek-v4-flash"
BASE_URL = "https://api.deepseek.com"
# Published per-1M-token rates at run time (USD / 1M tokens).
COST_IN_PER_MT = 0.14
COST_OUT_PER_MT = 0.28
# NOTE (2026-09-07, pre-acceptance): deepseek-v4-flash defaults to hidden
# chain-of-thought; on REASON-stage plain prompts it can spend an unbounded
# completion budget in `reasoning_content` before emitting `content` (observed
# up to the 24k cap with finish_reason=length and an empty answer). Sending
# `thinking: {type: disabled}` keeps the SAME model/provider for every system
# while forcing visible `content` output (probe-validated: content direct,
# no reasoning tokens). MAX_TOKENS raised to 24000 as a safe ceiling.
MAX_TOKENS = 24000       # hard cap on completion tokens per LLM call
REQUEST_TIMEOUT = 600      # seconds per HTTP call
_MAX_ATTEMPTS = 3


def _api_key() -> str:
    """DeepSeek key from the pi harness auth (never printed)."""
    import os
    try:
        import json as _json
        auth = _json.load(open("/home/saveenas/.pi/agent/auth.json"))
        if auth.get("deepseek", {}).get("key"):
            return auth["deepseek"]["key"]
    except Exception:
        pass
    return os.environ.get("DEEPSEEK_API_KEY", "")


def api_chat(system: str, user: str) -> Dict[str, Any]:
    """One deterministic chat completion. Returns content + usage."""
    import requests
    key = _api_key()
    url = BASE_URL.rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    payload = {
        "model": MODEL,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "temperature": 0.0,
        "max_tokens": MAX_TOKENS,
        "thinking": {"type": "disabled"},  # same model, no hidden CoT burn
        "stream": False,
    }
    last_err: Optional[str] = None
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            resp = requests.post(url, headers=headers, json=payload,
                                 timeout=REQUEST_TIMEOUT)
            if resp.status_code == 200:
                body = resp.json()
                msg = (body.get("choices") or [{}])[0].get("message") or {}
                usage = body.get("usage") or {}
                return {
                    "content": msg.get("content") or "",
                    "reasoning_content": msg.get("reasoning_content") or "",
                    "usage": usage,
                    "tokens_in": usage.get("prompt_tokens", 0),
                    "tokens_out": usage.get("completion_tokens", 0),
                    "latency_s": 0.0,
                }
            last_err = f"http {resp.status_code}: {resp.text[:200]}"
        except Exception as exc:  # noqa: BLE001
            last_err = f"transport error: {exc}"
        time.sleep(5 * attempt)
    raise AdapterError(f"deepseek api failed after {_MAX_ATTEMPTS} attempts: {last_err}")


def est_cost(tokens_in: int, tokens_out: int) -> float:
    return round(tokens_in / 1e6 * COST_IN_PER_MT + tokens_out / 1e6 * COST_OUT_PER_MT, 6)


# ── prompt builders (blindness-safe: supplied_inputs only) ─────────────

OUTPUT_REQUIREMENTS = (
    "Output requirements (apply to your final answer):\n"
    "1. Answer the scientific question directly; produce the requested deliverable explicitly "
    "(identifiers, lists, SMILES, rankings, experimental plans).\n"
    "2. Label the evidence status of every substantive claim: MEASURED / RETRIEVED / CALCULATED / "
    "PREDICTED / MISSING / NOT VERIFIABLE. Never present a prediction as measured.\n"
    "3. Never invent identifiers, citations, DOIs, PDB codes or affinity values. If you cannot "
    "verify something with the permitted sources, say so explicitly ('no evidence found') instead "
    "of guessing.\n"
    "4. State residual uncertainty in one sentence.\n"
    "5. If an input you need (e.g., an attached CSV/table) was not actually provided, state that "
    "the input is missing rather than fabricating it."
)

SYS_BASE_LLM = (
    "You are an expert computational chemist / chemical biologist answering a scientific task "
    "directly. You have NO external tools, databases or retrieval: reason from your own knowledge "
    "only. Be scientifically honest, precise and concise.\n" + OUTPUT_REQUIREMENTS
)

SYS_COSCIENTIST = (
    "You are an AI research co-scientist that reasons in three explicit phases before answering: "
    "(1) GENERATE several distinct candidate answers/hypotheses/plans; "
    "(2) CRITIQUE each candidate against the task constraints and select the strongest; "
    "(3) SYNTHESIZE the final answer.\n"
    "You have no external tools: reason from your own knowledge only. "
    "You are evaluated on the same rubric as tool-using systems, so never fabricate citations or "
    "identifiers and always separate PREDICTED/MEASURED/RETRIEVED claims.\n" + OUTPUT_REQUIREMENTS
)


def task_prompt(task: TaskInput, extra_requirements: str = "") -> str:
    """Build the blinded task text shared verbatim across systems."""
    lines = [
        "Scientific question: " + task.question,
        "",
        "Supplied inputs (these are the ONLY inputs you may use):",
    ]
    for s in task.supplied_inputs or []:
        lines.append("  - " + s)
    lines += [
        "",
        "Permitted tools/databases (use only these if any): "
        + (", ".join(task.permitted_tools) if task.permitted_tools else "none"),
        "Forbidden: " + ("; ".join(task.forbidden) if task.forbidden else "none"),
        "Data cutoff date: " + str(task.data_cutoff_date or "unspecified"),
    ]
    if extra_requirements:
        lines += ["", extra_requirements]
    return "\n".join(lines)


def task_deliverable_prompt(task: TaskInput) -> str:
    """Capability-specific deliverable reminder (part of the shared input text)."""
    cap = task.capability
    if cap == "KNOW":
        return "Deliverable: a factual, sourced answer (identifiers + source/citation where asked)."
    if cap == "REASON":
        return "Deliverable: a mechanistic explanation naming the controlling factors and any structural evidence used."
    if cap == "DESIGN":
        return "Deliverable: the requested candidate molecules/SMILES/designs with validation reasoning."
    if cap == "DISCOVER":
        return "Deliverable: a prioritized/actionable recommendation or experiment plan with rationale."
    return ""


# ── tiny usage bookkeeping ─────────────────────────────────────────────

class LLMCallLog:
    """Records every raw model response + real usage for one task run."""

    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []
        self.tokens_in = 0
        self.tokens_out = 0

    def add(self, *, raw: str, usage: Dict[str, Any], latency_s: float,
            phase: str = "", meta: Optional[Dict[str, Any]] = None) -> None:
        tin = int(usage.get("prompt_tokens", 0) or 0)
        tout = int(usage.get("completion_tokens", 0) or 0)
        self.tokens_in += tin
        self.tokens_out += tout
        call = {
            "phase": phase,
            "latency_s": round(latency_s, 3),
            "raw_model_response": raw,
            "tokens_in": tin,
            "tokens_out": tout,
            "reasoning_tokens": int((usage.get("completion_tokens_details") or {})
                                    .get("reasoning_tokens", 0) or 0),
            "cost_usd_estimated": est_cost(tin, tout),
        }
        if meta:
            call.update(meta)
        self.calls.append(call)

    def estimated_cost_usd(self) -> float:
        return round(sum(c["cost_usd_estimated"] for c in self.calls), 6)

    def to_dict(self) -> Dict[str, Any]:
        return {"calls": self.calls,
                "tokens_in": self.tokens_in, "tokens_out": self.tokens_out,
                "cost_usd": self.estimated_cost_usd()}


class _LiveAdapterBase(SystemAdapter):
    """Common fail-closed + bookkeeping scaffold."""

    system_id: str = "base"

    def __init__(self, system_id: str, allow_real: bool = False) -> None:
        self.system_id = system_id
        self.allow_real = allow_real
        self.log = LLMCallLog()

    def _require_real(self) -> None:
        if not self.allow_real:
            raise AdapterError(
                f"adapter {self.system_id}: real benchmark execution disabled "
                "(Sprint 2B infra only; run with DEV fixtures)")

    def _chat(self, system: str, user: str, phase: str = "") -> str:
        t0 = time.monotonic()
        out = api_chat(system, user)
        out["latency_s"] = time.monotonic() - t0
        self.log.add(raw=out["content"], usage=out["usage"],
                     latency_s=out["latency_s"], phase=phase,
                     meta={"reasoning_preview": (out.get("reasoning_content") or "")[:300]})
        return out["content"]

    def _result(self, task: TaskInput, *, status: str, raw: Any, answer: Any,
                tool_calls: int, error: Optional[str] = None,
                extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "status": status,
            "raw": raw if isinstance(raw, str) else json.dumps(raw, default=str),
            "answer": answer,
            "provider": PROVIDER,
            "model": MODEL,
            "version": MODEL,
            "tool_calls": tool_calls,
            "tokens_in": self.log.tokens_in,
            "tokens_out": self.log.tokens_out,
            "cost_usd": self.log.estimated_cost_usd(),
            "artifacts": [],
            "error": error,
            "llm_log": self.log.to_dict(),
        }
        if extra:
            d.update(extra)
        return d


class PROTACXtendLiveAdapter(_LiveAdapterBase):
    """PROTACXtend conversational agent (tools -> SynGlue graph handoff)."""

    system_id = "PROTACXtend"

    def execute(self, task: TaskInput, ctx: Dict[str, Any]) -> Dict[str, Any]:
        self._require_real()
        from protacxtend.agentic.chat_agent import ConversationalAgent, ClarificationNeeded
        from protacxtend.llm.json_repair import parse_json_robust

        user_text = task_prompt(task, task_deliverable_prompt(task))
        artifact_dir = Path(ctx.get("artifact_dir", "benchmark_results/raw/protacxtend/artifacts"))
        artifact_dir.mkdir(parents=True, exist_ok=True)

        def llm_action(system: str, user: str) -> Dict[str, Any]:
            raw = self._chat(system, user, phase="agent_action")
            return parse_json_robust(raw)

        def workflow_runner(objective):
            """Real graph handoff with artifact persistence (no ground truth)."""
            from protacxtend.backend.main import (run_workflow_from_request,
                                                  summarize_state)
            request = objective.to_request_text()
            t0 = time.monotonic()
            state = run_workflow_from_request(request)
            summary = summarize_state(state)
            self.log.calls.append({
                "phase": "graph_handoff",
                "latency_s": round(time.monotonic() - t0, 3),
                "raw_model_response": json.dumps(summary, default=str)[:20000],
                "tokens_in": 0, "tokens_out": 0, "reasoning_tokens": 0,
                "cost_usd_estimated": 0.0, "kind": "deterministic_graph",
            })
            artifact = artifact_dir / f"{task.task_id}.state.json"
            try:
                artifact.write_text(
                    json.dumps({"objective": objective.__dict__, "request": request,
                                "summary": summary,
                                "state": _safe_state(state)},
                               indent=1, default=str), encoding="utf-8")
            except Exception:
                pass
            return {"objective": objective, "request": request, "state": state,
                    "summary": summary,
                    "run_id": str(getattr(state, "run_id", "") or "")}

        agent = ConversationalAgent(cfg=None, llm_action=llm_action,
                                    workflow_runner=workflow_runner)
        t0 = time.monotonic()
        try:
            run = agent.turn(user_text, ask=None)
        except ClarificationNeeded as need:
            self.log.add(raw=json.dumps({"question": need.question}), usage={},
                         latency_s=0.0, phase="clarification")
            return self._result(task, status="failed", raw=json.dumps({
                "kind": "clarification_required", "question": need.question}, default=str),
                answer=None, tool_calls=0,
                error=f"clarification_required: {need.question}")
        latency = time.monotonic() - t0

        kind = (run.summary or {}).get("kind", "unknown")
        events = [{"kind": e.kind, "action": e.action, "tool": e.tool,
                   "status": e.status, "summary": e.summary} for e in run.events]
        tool_calls = sum(1 for e in events if e["kind"] == "tool"
                         and e["action"] == "calling")
        answer = (run.summary or {}).get("answer")
        raw_blob = {
            "user_text": user_text,
            "kind": kind,
            "summary": run.summary,
            "events": events,
            "transcript": run.transcript,
            "objective": (run.objective.__dict__ if run.objective else None),
            "run_id": run.run_id,
            "steps": run.steps,
        }
        if kind == "answer":
            status, err = "ok", None
        elif kind == "handoff":
            status, err = "ok", None
        elif kind == "clarification":
            status, err = "failed", f"clarification_required: {(run.summary or {}).get('question')}"
            answer = None
        else:  # error / max steps
            status = "failed"
            err = (run.summary or {}).get("error") or f"kind={kind}"
        return self._result(task, status=status, raw=json.dumps(raw_blob, default=str),
                            answer=answer, tool_calls=tool_calls, error=err,
                            extra={"latency_s": round(latency, 3),
                                   "run_events": events,
                                   "artifacts": sorted(str(p) for p in artifact_dir.glob(f"{task.task_id}*"))})


class BaseLLMLiveAdapter(_LiveAdapterBase):
    """Same model, plain chat — no tools, no agents, no retrieval."""

    system_id = "Base-LLM-control"

    def execute(self, task: TaskInput, ctx: Dict[str, Any]) -> Dict[str, Any]:
        self._require_real()
        user_text = task_prompt(task, task_deliverable_prompt(task))
        t0 = time.monotonic()
        raw = self._chat(SYS_BASE_LLM, user_text, phase="direct_answer")
        latency = time.monotonic() - t0
        answer = raw
        status = "ok"
        if not raw or not raw.strip():
            status, answer = "failed", None
        return self._result(task, status=status, raw=raw, answer=answer,
                            tool_calls=0,
                            error=None if status == "ok" else "empty model output",
                            extra={"latency_s": round(latency, 3)})


class AICoScientistLiveAdapter(_LiveAdapterBase):
    """AI-Co-Scientist-compatible local workflow (BASELINES.md shape).

    Phases over the SAME base model (no tools): generate -> critique/select ->
    synthesize. Not the Google AI Co-Scientist service.
    """

    system_id = "AI-Co-Scientist-compatible"

    def execute(self, task: TaskInput, ctx: Dict[str, Any]) -> Dict[str, Any]:
        self._require_real()
        user_text = task_prompt(task, task_deliverable_prompt(task))
        t0 = time.monotonic()

        phase1 = (SYS_COSCIENTIST +
                  "\n\nPHASE 1 — GENERATE. Propose 4-6 DISTINCT candidate answers/plans "
                  "(each 2-5 sentences, numbered). Do not fabricate identifiers.")
        raw1 = self._chat(phase1, user_text, phase="generate")
        if not raw1 or not raw1.strip():
            return self._result(task, status="failed", raw=raw1 or "", answer=None,
                                tool_calls=0, error="phase1 empty output",
                                extra={"latency_s": round(time.monotonic() - t0, 3)})

        phase2 = (SYS_COSCIENTIST +
                  "\n\nPHASE 2 — CRITIQUE & SELECT. Candidate set:\n" + raw1[:9000] +
                  "\n\nCritique each candidate against the question, the supplied inputs and the "
                  "rubric (no fabrication, evidence labels, task completion). State which candidate "
                  "you select and why.")
        raw2 = self._chat(phase2, user_text, phase="critique")
        if not raw2 or not raw2.strip():
            return self._result(task, status="failed",
                                raw=json.dumps({"phase1": raw1, "phase2": raw2 or ""},
                                               default=str),
                                answer=None, tool_calls=0, error="phase2 empty output",
                                extra={"latency_s": round(time.monotonic() - t0, 3)})

        phase3 = (SYS_COSCIENTIST +
                  "\n\nPHASE 3 — SYNTHESIS. Write the FINAL answer only (no meta-commentary). "
                  "Satisfy the Output requirements above.")
        raw3 = self._chat(phase3, raw1[:6000] + "\n\nCritique:\n" + raw2[:9000],
                          phase="synthesize")
        latency = time.monotonic() - t0
        blob = {"phase1_generate": raw1, "phase2_critique": raw2, "phase3_final": raw3}
        if not raw3 or not raw3.strip():
            return self._result(task, status="failed",
                                raw=json.dumps(blob, default=str), answer=None,
                                tool_calls=0, error="phase3 empty output",
                                extra={"latency_s": round(latency, 3)})
        return self._result(task, status="ok", raw=json.dumps(blob, default=str),
                            answer=raw3, tool_calls=0,
                            extra={"latency_s": round(latency, 3)})


# ── helpers ────────────────────────────────────────────────────────────

def _safe_state(state: Any) -> Dict[str, Any]:
    """Best-effort JSON-safe serialization of a workflow state (no GT involved)."""
    try:
        if state is None:
            return {}
        if hasattr(state, "model_dump"):
            return state.model_dump()
        if hasattr(state, "dict"):
            return state.dict()
    except Exception:
        pass
    keys = ("parsed_objective", "retrieved_binders", "selected_warheads",
            "selected_e3_ligands", "generated_linkers", "valid_candidates",
            "final_ranked_candidates", "warnings", "errors", "pipeline_status",
            "run_id")
    out: Dict[str, Any] = {}
    for k in keys:
        try:
            out[k] = getattr(state, k, None)
        except Exception:
            pass
    return out
