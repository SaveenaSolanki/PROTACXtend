"""Live four-system adapters for the Gate-C / pilot comparison.

Adds the systems that were declared MISSING in ``tpdeval/adapters.py`` while
reusing the existing ``benchmark_runner.live`` contract and fail-closed
behaviour:

* ``LLM+RAG``        (S1 / tpdeval slot E) — frozen-corpus retrieval + LLM
  synthesis. Uses retrieval connectors only; executes no domain/design tools.
* ``LLM+flat-tools`` (S2 / tpdeval slot F/G) — the LLM chooses from the same
  callable tool catalog S3 exposes, through a flat JSON action interface with a
  bounded number of rounds. No specialist orchestration, no evidence gating.
* ``Biomni``         (S4 / tpdeval slot B) — executes the *official* installed
  Biomni (snap-stanford/biomni 0.0.8, isolated venv) with the same model/provider.

Ground truth is never loaded here; adapters only see the blinded ``TaskInput``.
Every adapter fails closed unless ``allow_real=True`` and records raw output,
usage/latency/cost, tool traces and typed status.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from benchmark_runner.live import (BASE_URL, COST_IN_PER_MT, COST_OUT_PER_MT,
                                   MODEL, PROVIDER, SYS_BASE_LLM, _LiveAdapterBase,
                                   api_chat, est_cost)
from benchmark_runner.runner import AdapterError, TaskInput


# ── retrieval-only system (S1) ─────────────────────────────────────────

RETRIEVAL_TOOLS = (
    "search_europe_pmc",
    "search_pubmed",
    "resolve_target",
    "retrieve_target_binders",
)


class RetrievalRAGLiveAdapter(_LiveAdapterBase):
    """S1: retrieve from scientific connectors, then let the LLM synthesize.

    Retrieval only — no design/structure/degradation tools are called. The
    retrieved documents are injected as context and recorded as evidence.
    """

    system_id = "LLM+RAG"

    def __init__(self, system_id: str | None = None, allow_real: bool = False) -> None:
        super().__init__(system_id or self.system_id, allow_real)

    def execute(self, task: TaskInput, ctx: Dict[str, Any]) -> Dict[str, Any]:
        self._require_real()
        from protacxtend.runtime.agent_tools import run_agent_tool

        online = bool(ctx.get("online", False))
        retrieved: List[Dict[str, Any]] = []
        t0 = time.monotonic()
        for tool in RETRIEVAL_TOOLS:
            params: Dict[str, Any] = {"page_size": 5, "top_k": 5}
            if tool in {"search_europe_pmc", "search_pubmed"}:
                params["query"] = task.question[:200]
            elif tool == "resolve_target":
                params["target_name"] = _guess_target(task)
            elif tool == "retrieve_target_binders":
                params["target_name"] = _guess_target(task)
            try:
                res = run_agent_tool(tool, params, use_fixture=False,
                                     allow_network=online)
            except Exception as exc:  # noqa: BLE001
                retrieved.append({"tool": tool, "status": "error",
                                  "error": f"{type(exc).__name__}: {exc}"})
                continue
            retrieved.append({
                "tool": tool,
                "status": res.get("status"),
                "failure_code": res.get("failure_code", ""),
                "data": _trim(res.get("scientific_result")),
            })
        context = _render_retrieval_context(retrieved)
        user_text = (f"{task.question}\n\nSupplied inputs:\n"
                     + "\n".join("  - " + s for s in (task.supplied_inputs or []))
                     + "\n\nRetrieved evidence (the ONLY evidence you may cite; "
                       "label any claim not supported here as unsupported):\n"
                     + context
                     + "\n\nWrite the final answer. Cite retrieved items inline as [tool:index].")
        raw = self._chat(SYS_BASE_LLM + "\nYou answer strictly from the retrieved evidence provided.",
                         user_text, phase="rag_answer")
        latency = time.monotonic() - t0
        status = "ok" if raw and raw.strip() else "failed"
        return self._result(
            task, status=status, raw=json.dumps({"retrieved": retrieved, "answer": raw}, default=str),
            answer=raw or None, tool_calls=len(retrieved),
            error=None if status == "ok" else "empty model output",
            extra={"latency_s": round(latency, 3), "retrieval": retrieved,
                   "n_retrieved": sum(1 for r in retrieved if r.get("status") == "ok")})


# ── flat tool-loop system (S2) ─────────────────────────────────────────

class LLMFlatToolsLiveAdapter(_LiveAdapterBase):
    """S2: LLM + flat tool interface (same tool catalog as S3, no orchestration)."""

    system_id = "LLM+flat-tools"
    MAX_ROUNDS = 3

    def __init__(self, system_id: str | None = None, allow_real: bool = False) -> None:
        super().__init__(system_id or self.system_id, allow_real)

    def _catalog(self) -> List[Dict[str, Any]]:
        from protacxtend.agentic.registry import TOOL_SPECS
        return [{"name": s["name"], "purpose": s["purpose"],
                 "inputs": s.get("inputs", {})}
                for s in TOOL_SPECS if s.get("readiness") == "ready"]

    def execute(self, task: TaskInput, ctx: Dict[str, Any]) -> Dict[str, Any]:
        self._require_real()
        import re
        from protacxtend.runtime.agent_tools import run_agent_tool

        online = bool(ctx.get("online", False))
        catalog = self._catalog()
        tool_names = [c["name"] for c in catalog]
        cat_text = "\n".join(f"- {c['name']}: {c['purpose'][:120]}" for c in catalog)
        base = (f"{task.question}\n\nSupplied inputs:\n"
                + "\n".join("  - " + s for s in (task.supplied_inputs or [])))
        system = (SYS_BASE_LLM + "\nYou may call the tools below. To call one, reply with a "
                  "single JSON object: {\"tool\": name, \"params\": {...}}. To finish, reply "
                  "with {\"final\": \"your answer\"}. Use at most "
                  f"{self.MAX_ROUNDS} tool calls. Do not invent tool names or results.\n\n"
                  "TOOLS:\n" + cat_text)
        history: List[Dict[str, Any]] = []
        tool_trace: List[Dict[str, Any]] = []
        final: Optional[str] = None
        t0 = time.monotonic()
        user = base
        for _round in range(self.MAX_ROUNDS):
            raw = self._chat(system, user, phase=f"flat_tool_round_{_round}")
            obj = _extract_json(raw)
            if obj is None:
                final = raw
                break
            if "final" in obj and obj.get("final"):
                final = str(obj["final"])
                break
            name = str(obj.get("tool") or obj.get("tool_name") or obj.get("name") or "").strip()
            params = obj.get("params") or obj.get("inputs") or obj.get("arguments") or {}
            if name not in tool_names:
                tool_trace.append({"tool": name, "status": "rejected",
                                   "error": "tool not in catalog"})
                user = (f"That tool name is not in the catalog. Reply with a valid tool call "
                        f"or {{\"final\": ...}}.\nQuestion: {task.question}")
                continue
            try:
                res = run_agent_tool(name, params, use_fixture=False, allow_network=online)
                obs = {"status": res.get("status"), "failure_code": res.get("failure_code", ""),
                       "data": _trim(res.get("scientific_result"))}
            except Exception as exc:  # noqa: BLE001
                obs = {"status": "error", "error": f"{type(exc).__name__}: {exc}"}
            tool_trace.append({"tool": name, "params": params, **obs})
            history.append({"tool": name, "observed": obs})
            user = (f"{base}\n\nYour tool call {name} returned:\n"
                    + json.dumps(obs, default=str)[:6000]
                    + "\n\nEither call another tool or finish with {\"final\": answer}.")
        latency = time.monotonic() - t0
        if not (final or "").strip():
            # Bounded tool loop finished without a structured final: make ONE
            # plain-text synthesis call over the recorded observations so the
            # system either answers or fails honestly with a real model output.
            user_final = (f"{base}\n\nTool observations so far:\n"
                          + json.dumps(history, default=str)[:8000]
                          + "\n\nNow write the FINAL answer in plain text (no JSON).")
            try:
                final = self._chat(SYS_BASE_LLM, user_final, phase="flat_tool_finalize")
            except Exception as exc:  # noqa: BLE001
                final = ""
                tool_trace.append({"tool": "finalize", "status": "error",
                                   "error": f"{type(exc).__name__}: {exc}"})
        status = "ok" if (final or "").strip() else "failed"
        return self._result(
            task, status=status,
            raw=json.dumps({"tool_trace": tool_trace, "final": final}, default=str),
            answer=final or None, tool_calls=sum(1 for t in tool_trace if t.get("status") == "ok"),
            error=None if status == "ok" else "no final answer within tool-round budget",
            extra={"latency_s": round(latency, 3), "tool_trace": tool_trace})


# ── Biomni (S4) ────────────────────────────────────────────────────────

BIOMNI_VENV_PY = os.environ.get("BIOMNI_VENV_PY", "/tmp/biomni_venv/bin/python")
BIOMNI_RUNNER = Path(__file__).resolve().parents[1] / "scripts" / "biomni_run.py"


class BiomniLiveAdapter(_LiveAdapterBase):
    """S4: the official installed Biomni implementation (external venv subprocess)."""

    system_id = "Biomni"

    def __init__(self, system_id: str | None = None, allow_real: bool = False) -> None:
        super().__init__(system_id or self.system_id, allow_real)

    def execute(self, task: TaskInput, ctx: Dict[str, Any]) -> Dict[str, Any]:
        self._require_real()
        if not Path(BIOMNI_VENV_PY).exists():
            return self._result(task, status="unavailable", raw="", answer=None,
                                tool_calls=0,
                                error=f"biomni venv not found: {BIOMNI_VENV_PY}",
                                extra={"latency_s": 0.0, "system_available": False})
        prompt = _task_prompt_for_biomni(task)
        timeout_s = int(ctx.get("timeout_s", 1200))
        t0 = time.monotonic()
        out_file = Path(ctx.get("artifact_dir", "benchmark_results/raw/biomni")) / f"{task.task_id}.json"
        out_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            proc = subprocess.run(
                [BIOMNI_VENV_PY, str(BIOMNI_RUNNER), "--prompt", prompt,
                 "--out", str(out_file), "--timeout", str(timeout_s)],
                capture_output=True, text=True, timeout=timeout_s + 60,
            )
        except subprocess.TimeoutExpired as exc:
            return self._result(task, status="timeout", raw=str(exc), answer=None,
                                tool_calls=0, error=f"biomni timeout after {timeout_s}s",
                                extra={"latency_s": round(time.monotonic() - t0, 3)})
        latency = time.monotonic() - t0
        payload: Dict[str, Any] = {}
        if out_file.exists():
            try:
                payload = json.loads(out_file.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                payload = {}
        answer = payload.get("answer")
        if proc.returncode != 0 and not payload:
            return self._result(task, status="failed", raw=json.dumps(
                {"stdout": proc.stdout[-4000:], "stderr": proc.stderr[-4000:]}, default=str),
                answer=None, tool_calls=int(payload.get("tool_calls", 0) or 0),
                error=f"biomni exit {proc.returncode}: {proc.stderr[-300:]}",
                extra={"latency_s": round(latency, 3)})
        status = "ok" if (answer or "").strip() else "failed"
        return self._result(
            task, status=status, raw=json.dumps(payload, default=str),
            answer=answer, tool_calls=int(payload.get("tool_calls", 0) or 0),
            error=None if status == "ok" else (payload.get("error") or "empty biomni output"),
            extra={"latency_s": round(latency, 3), "biomni_version": payload.get("version", ""),
                   "artifacts": [str(out_file)]})


# ── helpers ────────────────────────────────────────────────────────────

def _guess_target(task: TaskInput) -> str:
    import re
    # Supplied inputs are authoritative and already human-structured.
    for s in (task.supplied_inputs or []):
        m = re.search(r"(?:target|gene|protein)[^:]*:\s*([A-Za-z0-9][A-Za-z0-9\-]{1,15})", s, re.I)
        if m:
            return m.group(1).strip()
    text = " ".join([task.question, *(task.supplied_inputs or [])])
    for tok in re.findall(r"\b[A-Z][A-Z0-9]{1,9}\b", text):
        if tok not in {"PROTAC", "SMILES", "TPD", "PDB", "DNA", "RNA", "IC50", "DC50",
                       "ID", "Kd", "EC50", "MW", "ADMET", "E3"}:
            return tok
    return "BRD4"


def _trim(envelope: Any) -> Any:
    """Keep the useful part of a run_agent_tool envelope without GT leakage."""
    if not isinstance(envelope, dict):
        return envelope
    result = envelope.get("result") or {}
    return {"status": envelope.get("status"), "data": (result.get("data") if isinstance(result, dict) else result)}


def _render_retrieval_context(items: List[Dict[str, Any]]) -> str:
    lines = []
    for i, item in enumerate(items):
        lines.append(f"[{item['tool']}:{i}] status={item.get('status')} "
                     f"{json.dumps(item.get('data'), default=str)[:1200]}")
    return "\n".join(lines) if lines else "(no retrieval available)"


def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    import re
    if not text:
        return None
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n|```$", "", text).strip()
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else None
    except Exception:  # noqa: BLE001
        pass
    m = re.search(r"\{.*\}", text, re.S)
    if m:
        try:
            obj = json.loads(m.group(0))
            return obj if isinstance(obj, dict) else None
        except Exception:  # noqa: BLE001
            return None
    return None


def _task_prompt_for_biomni(task: TaskInput) -> str:
    return (f"{task.question}\n\nSupplied inputs:\n"
            + "\n".join("  - " + s for s in (task.supplied_inputs or []))
            + f"\n\nDeliverable: answer the scientific question for capability {task.capability}.")


SYSTEM_ADAPTERS = {
    "S1": ("LLM+RAG", RetrievalRAGLiveAdapter),
    "S2": ("LLM+flat-tools", LLMFlatToolsLiveAdapter),
    "S4": ("Biomni", BiomniLiveAdapter),
}
