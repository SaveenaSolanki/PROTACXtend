"""
Backend LLM routes — switch/configure providers at runtime from any client.
==========================================================================

GET  /llm/status        — active provider, health, available providers
POST /llm/switch        — switch provider/model/base_url/api_key (validated)
GET  /llm/providers     — list available providers
GET  /llm/models        — list models for a provider
POST /llm/test          — live connectivity + one schema-validated call
POST /llm/reset         — back to env config
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel


class SwitchRequest(BaseModel):
    provider: str
    model: str = ""
    base_url: str = ""
    api_key: str = ""


class TestRequest(BaseModel):
    provider: str = ""
    model: str = ""
    base_url: str = ""
    api_key: str = ""
    prompt: str = "Reply with a tiny valid JSON object: {\"ok\": true}"


def _status() -> Dict[str, Any]:
    from protacxtend.llm.gateway import gateway_status
    return gateway_status()


def _switch(req: SwitchRequest) -> Dict[str, Any]:
    from protacxtend.llm.gateway import switch_provider
    return switch_provider(req.provider, req.model, req.base_url, req.api_key)


def _providers() -> Dict[str, Any]:
    from protacxtend.llm.providers import list_available_providers
    return {"providers": list_available_providers()}


def _models(provider: str = "") -> Dict[str, Any]:
    from protacxtend.llm.providers import get_provider, get_config
    cfg = get_config()
    if provider:
        cfg.provider = provider
    try:
        models = get_provider(cfg.provider).list_models(cfg)
    except Exception as exc:
        return {"provider": cfg.provider, "ok": False, "error": str(exc)[:200]}
    return {"provider": cfg.provider, "models": models, "ok": True}


def _test(req: TestRequest) -> Dict[str, Any]:
    """Live test: switch (if given) then run one structured call."""
    from protacxtend.llm.gateway import structured_chat
    from protacxtend.llm.providers import ProviderConfig, get_config, set_runtime_config
    from protacxtend.llm.schemas import EvidenceDecision

    if req.provider:
        cfg = get_config()
        cfg.provider = req.provider
        if req.model:
            cfg.model = req.model
        if req.base_url:
            cfg.base_url = req.base_url
        if req.api_key:
            cfg.api_key = req.api_key
        set_runtime_config(cfg)

    try:
        decision = structured_chat(
            "evidence_assessment", req.prompt, EvidenceDecision,
        )
        return {"ok": True, "decision": decision.model_dump()}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:300]}


def _reset() -> Dict[str, Any]:
    from protacxtend.llm.providers import reset_runtime_config
    reset_runtime_config()
    return _status()


def attach_llm_routes(app) -> None:
    from fastapi import APIRouter, Query

    router = APIRouter(prefix="/llm", tags=["llm"])

    @router.get("/status")
    def status():
        return _status()

    @router.get("/providers")
    def providers():
        return _providers()

    @router.get("/models")
    def models(provider: str = Query("")):
        return _models(provider)

    @router.post("/switch")
    def switch(req: SwitchRequest):
        try:
            return _switch(req)
        except ValueError as exc:
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail=str(exc))

    @router.post("/test")
    def test(req: TestRequest):
        return _test(req)

    @router.post("/reset")
    def reset():
        return _reset()

    app.include_router(router)
