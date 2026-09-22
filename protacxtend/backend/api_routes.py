"""FastAPI routes for PROTACXtend.

FastAPI is optional. Importing this module without FastAPI installed still works;
``get_app`` raises a clear dependency message only when called.
"""

from __future__ import annotations

from typing import Any, Dict

from protacxtend import __version__
from protacxtend.agents.runtime import run_protacpilot  # unified entry point (agentic mode)
from protacxtend.backend.main import run_workflow_from_request, summarize_state
from protacxtend.backend.mode_router import run_mode
from protacxtend.backend.schemas import model_to_dict
from protacxtend.tools.report_generator import generate_candidate_table

try:
    from pydantic import BaseModel
except Exception:  # pragma: no cover - optional dependency.
    BaseModel = object  # type: ignore[misc,assignment]


class DesignRequest(BaseModel):
    request: str


class AgenticDesignRequest(BaseModel):
    request: str
    config: Dict[str, Any] = {}


class CapabilityRunRequest(BaseModel):
    params: Dict[str, Any] = {}


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

    app = FastAPI(title="PROTACXtend API", version=__version__)

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "PROTACXtend"}

    @app.get("/resources/health")
    def resources_health():
        from protacxtend.runtime.executor import run_capability
        checks = {}
        for name in ("chemistry", "admet", "protein_structure"):
            try:
                # Real probe molecule (aspirin) instead of a placeholder fixture;
                # this route must stay valid under SCIENTIFIC mode.
                r = run_capability(name, {"smiles": "CC(=O)Oc1ccccc1C(=O)O"}
                                   if name != "protein_structure"
                                   else {"identifier": "1A46"})
                checks[name] = r.get("result", {}).get("status", "unknown")
            except Exception as exc:  # noqa: BLE001
                checks[name] = f"error:{exc}"
        return {"status": "ok", "checks": checks}

    @app.get("/capabilities")
    def capabilities():
        from protacxtend.runtime.registry import build_registry, summary
        recs = build_registry()
        return {"summary": summary(recs), "capabilities": [r.to_row() for r in recs]}

    @app.get("/capabilities/{name}")
    def capability_detail(name: str):
        from protacxtend.runtime.registry import build_registry, trace
        return trace(build_registry(), name)

    @app.post("/capabilities/{name}/run")
    def capability_run(name: str, req: CapabilityRunRequest):
        from protacxtend.runtime.executor import run_capability
        return run_capability(name, req.params or {})

    # ── agent-tool surface (the same executor; no duplicated logic) ──
    @app.get("/tools")
    def tools():
        from protacxtend.runtime.agent_tools import list_agent_tools
        return {"tools": list_agent_tools(), "count": len(list_agent_tools())}

    @app.get("/tools/{name}")
    def tool_detail(name: str):
        from protacxtend.agentic.registry import spec_for
        from protacxtend.runtime.agent_tools import PROBE_FIXTURES
        try:
            spec = spec_for(name)
        except Exception as exc:  # noqa: BLE001
            return {"found": False, "reason": str(exc)}
        return {"found": True, "spec": spec, "fixture": PROBE_FIXTURES.get(name, {})}

    @app.post("/tools/{name}/run")
    def tool_run(name: str, req: CapabilityRunRequest):
        from protacxtend.runtime.executor import run_capability
        return run_capability(f"agent_tool:{name}", req.params or {})

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
        from protacxtend.backend.llm_routes import attach_llm_routes
        attach_llm_routes(app)
    except Exception as exc:  # pragma: no cover - optional dependency.
        app.state.llm_routes_error = str(exc)

    return app


app = None
try:  # pragma: no cover - optional dependency.
    app = get_app()
except Exception:
    app = None
