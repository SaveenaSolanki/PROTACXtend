"""FastAPI routes for SynGlue-Agent.

FastAPI is optional. Importing this module without FastAPI installed still works;
``get_app`` raises a clear dependency message only when called.
"""

from __future__ import annotations

from typing import Any, Dict

from synglue_agent.agents.runtime import run_protacpilot  # unified entry point (agentic mode)
from synglue_agent.backend.main import run_workflow_from_request, summarize_state
from synglue_agent.backend.mode_router import run_mode
from synglue_agent.backend.schemas import model_to_dict
from synglue_agent.tools.report_generator import generate_candidate_table

try:
    from pydantic import BaseModel
except Exception:  # pragma: no cover - optional dependency.
    BaseModel = object  # type: ignore[misc,assignment]


class DesignRequest(BaseModel):
    request: str


class AgenticDesignRequest(BaseModel):
    request: str
    config: Dict[str, Any] = {}


class ModeRequest(BaseModel):
    mode: str
    payload: Dict[str, Any] = {}


def run_design(payload: Dict[str, Any]) -> Dict[str, Any]:
    request = payload.get("request") or payload.get("user_request") or ""
    if not request:
        raise ValueError("Payload must include 'request' or 'user_request'.")
    state = run_workflow_from_request(request)
    return {
        "summary": summarize_state(state),
        "candidate_table": generate_candidate_table(state),
        "report": state.report,
        "state": model_to_dict(state),
    }


def run_mode_request(payload: Dict[str, Any]) -> Dict[str, Any]:
    return run_mode(payload)


def get_app():
    try:
        from fastapi import FastAPI
    except Exception as exc:  # pragma: no cover - optional dependency.
        raise RuntimeError("Install fastapi and pydantic to run the API server.") from exc

    app = FastAPI(title="PROTACXtend API", version="0.1.0")

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "SynGlue-Agent"}

    @app.post("/design")
    def design(req: DesignRequest):
        return run_design({"request": req.request})

    @app.post("/agentic-design")
    def agentic_design(req: AgenticDesignRequest):
        result = run_protacpilot(req.request, mode="agentic", config=req.config or {})
        # Return the state for backward compatibility (plus runtime envelope)
        return model_to_dict(result)

    @app.post("/mode")
    def mode(req: ModeRequest):
        merged = dict(req.payload or {})
        merged["mode"] = req.mode
        return run_mode_request(merged)

    # Provider-agnostic LLM routes (switch Ollama ↔ any API at runtime)
    try:
        from synglue_agent.backend.llm_routes import attach_llm_routes
        attach_llm_routes(app)
    except Exception as exc:  # pragma: no cover - optional dependency.
        app.state.llm_routes_error = str(exc)

    return app


app = None
try:  # pragma: no cover - optional dependency.
    app = get_app()
except Exception:
    app = None
