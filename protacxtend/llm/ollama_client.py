"""
Ollama structured-chat client (A6).
===================================

- temperature 0 (deterministic decisions)
- Pydantic schema enforced via format=<schema>
- context capped at 16-32K (Ollama defaults to huge contexts on big GPUs,
  which wastes memory — per guidance, start at 16K and measure)
- one model, many roles (roles.py)
- deterministic validators gate every response (tool_registry + schemas)

Model routing (per guidance):
  gpt-oss:20b   — primary (reasoning, agentic, tool-calling)
  qwen2.5:7b    — low-memory fallback (qwen3.5:9b when available)
  api_frontier  — reserved for high-risk decisions; never automatic

Never stores raw chain-of-thought. Stores the validated decision only.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Optional, Type, TypeVar

from pydantic import BaseModel

logger = logging.getLogger("protacpilot.llm")

# ── Configuration ─────────────────────────────────────────────────────
# Server: the newer Ollama (0.32.x) runs on 11435; system one on 11434.
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "127.0.0.1:11435")

PRIMARY_MODEL = os.environ.get("PROTACPILOT_LLM_MODEL", "gpt-oss:20b")
LOW_MEMORY_MODEL = os.environ.get("PROTACPILOT_LLM_FALLBACK", "qwen2.5:7b")

DEFAULT_NUM_CTX = 16384        # 16K effective context (guidance: 16-32K)
MAX_NUM_CTX = 32768

T = TypeVar("T", bound=BaseModel)


def _client():
    import ollama

    return ollama.Client(host=f"http://{OLLAMA_HOST}")


def list_models() -> Dict[str, Any]:
    try:
        return _client().list()
    except Exception as exc:
        logger.warning("Ollama unreachable: %s", exc)
        return {"models": []}


def model_available(model: str) -> bool:
    try:
        models = list_models().get("models", [])
        names = set()
        for m in models:
            name = m.get("name", "")
            names.add(name)
            # ollama client may return model/digest/name variants
            if ":" not in name and m.get("model"):
                names.add(m["model"])
        exact = model in names
        if exact:
            return True
        # prefix match: gpt-oss:20b vs gpt-oss:latest-style listings
        prefix = model.split(":")[0]
        return any(n.split(":")[0] == prefix for n in names)
    except Exception:
        return False


def pick_model(prefer: Optional[str] = None) -> str:
    """Choose a model that is actually pulled; fall back along the chain."""
    candidates = [prefer or PRIMARY_MODEL, PRIMARY_MODEL, LOW_MEMORY_MODEL]
    for m in candidates:
        if model_available(m):
            return m
    return PRIMARY_MODEL  # caller will handle failure


def structured_chat(
    role: str,
    user_content: str,
    schema: Type[T],
    model: Optional[str] = None,
    num_ctx: int = DEFAULT_NUM_CTX,
    extra_context: Optional[str] = None,
) -> T:
    """Call the local model with schema-enforced structured output.

    Deterministic (temperature 0). Raises on invalid schema / unavailable
    server; the caller's deterministic fallback handles the failure.
    """
    from protacxtend.llm.roles import system_prompt

    model = pick_model(model)
    client = _client()

    system = system_prompt(role)
    if extra_context:
        system = f"{system}\n\nContext: {extra_context}"

    response = client.chat(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ],
        format=schema.model_json_schema(),
        options={
            "temperature": 0,
            "num_ctx": min(num_ctx, MAX_NUM_CTX),
        },
    )

    raw = response.message.content
    try:
        decision = schema.model_validate_json(raw)
    except Exception as exc:
        # Try to salvage: strip markdown fences if present
        cleaned = raw.strip().removeprefix("```json").removesuffix("```").strip()
        try:
            decision = schema.model_validate_json(cleaned)
        except Exception as exc2:
            raise ValueError(f"LLM returned invalid schema output: {exc2}") from exc

    logger.info("LLM[%s/%s] → %s", role, model, decision.model_dump() if hasattr(decision, "model_dump") else decision)
    return decision


def structured_chat_with_fallback(
    role: str,
    user_content: str,
    schema: Type[T],
    fallback: T,
    model: Optional[str] = None,
    num_ctx: int = DEFAULT_NUM_CTX,
    extra_context: Optional[str] = None,
) -> T:
    """Try the LLM; on any failure return the deterministic fallback decision."""
    try:
        return structured_chat(role, user_content, schema, model=model, num_ctx=num_ctx,
                               extra_context=extra_context)
    except Exception as exc:
        logger.warning("LLM unavailable (%s) — using deterministic fallback", exc)
        return fallback
