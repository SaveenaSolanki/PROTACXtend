"""Centralized LLM Provider Manager (Sprint 1).

One abstraction over DeepSeek / Ollama / OpenAI / Anthropic / Gemini /
OpenRouter / custom OpenAI-compatible endpoints: provider metadata,
authentication state, model management, capability descriptors and
offline-friendly validation (endpoint, model, inference, structured
output, tool calling). API keys are never printed.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from protacxtend.llm.providers import (
    PROVIDER_REGISTRY,
    USER_CONFIG_PATH,
    get_provider,
    ProviderConfig,
    load_user_config,
    set_runtime_config,
    get_config,
    provider_health,
)

# Verification record (auth + one inference PASSed at setup / doctor --live).
# NEVER contains api keys — only provider/model/base_url + timestamps.
VERIFY_PATH = USER_CONFIG_PATH.parent / "verified.json"

# ── Provider metadata (capabilities are declared; live probes validate) ─

@dataclass
class ProviderMeta:
    provider: str
    label: str
    key_env: str
    default_base_url: str
    default_model: str
    local: bool = False
    supports_structured_output: bool = True
    supports_tool_calling: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "label": self.label,
            "key_env": self.key_env,
            "default_base_url": self.default_base_url,
            "default_model": self.default_model,
            "local": self.local,
            "supports_structured_output": self.supports_structured_output,
            "supports_tool_calling": self.supports_tool_calling,
        }


PROVIDER_META: Dict[str, ProviderMeta] = {
    "deepseek": ProviderMeta(
        "deepseek", "DeepSeek", "DEEPSEEK_API_KEY",
        "https://api.deepseek.com", "deepseek-v4-flash"),
    "ollama": ProviderMeta(
        "ollama", "Ollama (local)", "", "http://127.0.0.1:11434", "gpt-oss:20b",
        local=True),
    "openai": ProviderMeta(
        "openai", "OpenAI", "OPENAI_API_KEY",
        "https://api.openai.com/v1", "gpt-4o-mini"),
    "anthropic": ProviderMeta(
        "anthropic", "Anthropic", "ANTHROPIC_API_KEY",
        "https://api.anthropic.com", "claude-3-5-sonnet-latest"),
    "google": ProviderMeta(
        "google", "Google Gemini", "GEMINI_API_KEY",
        "https://generativelanguage.googleapis.com", "gemini-1.5-flash"),
    "gemini": ProviderMeta(
        "gemini", "Google Gemini", "GEMINI_API_KEY",
        "https://generativelanguage.googleapis.com", "gemini-1.5-flash"),
    "openrouter": ProviderMeta(
        "openrouter", "OpenRouter", "OPENROUTER_API_KEY",
        "https://openrouter.ai/api/v1", "openai/gpt-4o-mini"),
    "openai_compatible": ProviderMeta(
        "openai_compatible", "Custom OpenAI-compatible endpoint", "CUSTOM_LLM_API_KEY",
        "", "", supports_structured_output=True, supports_tool_calling=True),
}

# Common base keys for custom endpoints (OpenAI-compatible local servers)
CUSTOM_KEY_ENVS = ("PROTACPILOT_LLM_API_KEY", "OPENAI_API_KEY", "CUSTOM_LLM_API_KEY")


def provider_ids() -> List[str]:
    return sorted(PROVIDER_META)


def meta(provider: str) -> ProviderMeta:
    if provider not in PROVIDER_META:
        raise ValueError(f"unknown provider {provider!r}; available: {provider_ids()}")
    return PROVIDER_META[provider]


def _env_key(provider: str) -> str:
    m = meta(provider)
    if m.key_env:
        return os.environ.get(m.key_env, "")
    for k in CUSTOM_KEY_ENVS:  # custom/local endpoints may use the shared key
        if os.environ.get(k):
            return os.environ[k]
    return ""


def current_config() -> ProviderConfig:
    """One resolved runtime config for every component (env > saved > none)."""
    return get_config()


def is_configured() -> bool:
    return bool(current_config().provider)


def effective_key(provider: Optional[str] = None) -> str:
    """Key from provider env or saved config — for internal validation only.

    A saved key only ever counts for the provider it was saved under; it is
    never borrowed by a different provider (no cross-provider key leak).
    """
    cfg = current_config()
    prov = provider or cfg.provider
    if cfg.api_key and cfg.provider == prov:
        return cfg.api_key
    return _env_key(prov)


def key_env_name(provider: str) -> str:
    return meta(provider).key_env or "PROTACPILOT_LLM_API_KEY"


def save_config(config: ProviderConfig) -> Path:
    """Persist provider config without echoing the key anywhere."""
    path = USER_CONFIG_PATH
    payload = {
        "provider": config.provider, "model": config.model,
        "base_url": config.base_url, "api_key": config.api_key or "",
        "num_ctx": int(config.num_ctx), "temperature": float(config.temperature),
        "timeout_s": int(config.timeout_s),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    set_runtime_config(config)
    return path


def auth_state(provider: Optional[str] = None) -> Dict[str, Any]:
    """Authentication state — never includes the key value."""
    cfg = current_config()
    prov = (provider or cfg.provider or "").strip()
    if not prov or prov not in PROVIDER_META:
        return {
            "provider": prov or "(none)",
            "model": cfg.model or "",
            "base_url": cfg.base_url or "",
            "local": False,
            "requires_key": True,
            "authenticated": False,
            "key_source": "none",
            "key_env": "PROTACPILOT_LLM_API_KEY",
            "error": "no provider configured — run: protacxtend setup",
        }
    m = meta(prov)
    key = effective_key(prov)
    env_present = bool(_env_key(prov))
    return {
        "provider": prov,
        "model": cfg.model if cfg.provider == prov else m.default_model,
        "base_url": cfg.base_url if cfg.provider == prov else m.default_base_url,
        "local": m.local,
        "requires_key": not m.local,
        "authenticated": bool(key) or m.local,
        "key_source": "env" if env_present else ("config" if cfg.api_key else "none"),
        "key_env": key_env_name(prov),
    }


def validate(provider: Optional[str] = None,
             model: Optional[str] = None,
             base_url: Optional[str] = None,
             live: bool = True) -> Dict[str, Any]:
    """Offline-first validation of endpoint/model/auth/inference/capabilities.

    Never raises on missing credentials or unreachable endpoints; reports
    issues so callers can classify READY / DEGRADED / NOT READY.
    """
    cfg = current_config()
    prov = (provider or cfg.provider or "").strip()
    if not prov:
        return {"provider": "(none)", "model": cfg.model or "", "base_url": cfg.base_url or "",
                "authentication": {"ok": False, "local": False, "source": "none"},
                "endpoint": {"ok": False, "url": cfg.base_url or ""},
                "inference": {"ok": False, "reason": "no provider configured", "probe": {}},
                "structured_output": {"ok": False, "supported": False},
                "tool_calling": {"ok": False, "supported": False},
                "verdict": "NOT READY",
                "issues": ["no provider configured — run: protacxtend setup"]}
    if prov not in PROVIDER_META:
        return {"provider": prov, "model": "", "base_url": "",
                "authentication": {"ok": False, "local": False, "source": "none"},
                "endpoint": {"ok": False, "url": ""},
                "inference": {"ok": False, "reason": f"unknown provider {prov}", "probe": {}},
                "structured_output": {"ok": False, "supported": False},
                "tool_calling": {"ok": False, "supported": False},
                "verdict": "NOT READY",
                "issues": [f"unknown provider {prov}"]}
    m = meta(prov)
    mdl = model or (cfg.model if cfg.provider == prov else m.default_model)
    base = base_url or (cfg.base_url if cfg.provider == prov else m.default_base_url)
    issues: List[str] = []
    auth = auth_state(prov)

    # endpoint
    endpoint_ok = bool(base)
    if base:
        try:
            parsed = urlparse(base)
            endpoint_ok = parsed.scheme in ("http", "https") and bool(parsed.netloc)
        except ValueError:
            endpoint_ok = False
    if not endpoint_ok:
        issues.append("endpoint missing/invalid")

    # model
    model_ok = bool(mdl and mdl.strip())
    if not model_ok:
        issues.append("model missing")

    # authentication
    auth_ok = bool(auth["authenticated"])
    if not auth_ok:
        issues.append("no API key (set with: protacxtend auth login)")

    inference_ok = False
    reason = ""
    probe = {}
    if auth_ok and endpoint_ok and model_ok and not m.local and live:
        # Never hit paid endpoints without an explicit probe opt-in.
        inference_ok = True  # capability present; transport verified at call time
    elif m.local and live:
        try:
            models = get_provider(prov).list_models(ProviderConfig(provider=prov, model=mdl,
                                                                   base_url=base, api_key=effective_key(prov)))
            probe = {"models": models[:20], "reachable": True}
            inference_ok = True
        except Exception as exc:
            reason = f"local endpoint unreachable: {exc}"
            issues.append(reason)
    elif not auth_ok:
        reason = "not configured"

    structured = m.supports_structured_output
    tool = m.supports_tool_calling

    if not model_ok or not endpoint_ok:
        verdict = "NOT READY"
    elif not auth_ok and not m.local:
        verdict = "NOT READY"
    elif not inference_ok and m.local:
        verdict = "DEGRADED"
    elif not (structured and tool):
        verdict = "DEGRADED"
    else:
        verdict = "READY"

    return {
        "provider": prov,
        "model": mdl,
        "base_url": base,
        "authentication": {"ok": auth_ok, "local": m.local,
                           "source": auth["key_source"]},
        "endpoint": {"ok": endpoint_ok, "url": base},
        "inference": {"ok": inference_ok, "reason": reason, "probe": probe},
        "structured_output": {"ok": structured, "supported": structured},
        "tool_calling": {"ok": tool, "supported": tool},
        "verdict": verdict,
        "issues": issues,
    }


def login(provider: str, api_key: str, model: Optional[str] = None,
          base_url: Optional[str] = None) -> Dict[str, Any]:
    """Persist a provider choice + key (key stored only, never printed)."""
    provider = (provider or "").strip()
    if not provider or provider not in PROVIDER_META:
        raise ValueError(
            f"provider required for auth login — choose one of: {', '.join(provider_ids())}")
    m = meta(provider)
    cfg = current_config()
    saved = load_user_config()
    model = model or m.default_model
    base = base_url or m.default_base_url or cfg.base_url
    key = api_key.strip()
    if not m.local and not key and provider != "openai_compatible":
        raise ValueError(f"API key required for provider '{provider}'")
    config = ProviderConfig(provider=provider, model=model, base_url=base,
                            api_key=key, num_ctx=cfg.num_ctx,
                            temperature=cfg.temperature, timeout_s=cfg.timeout_s)
    path = save_config(config)
    return {"saved": str(path), "provider": provider, "model": model,
            "base_url": base, "authenticated": True}


def logout() -> Dict[str, Any]:
    """Remove the stored key while keeping provider/model choice."""
    cfg = current_config()
    saved = load_user_config()
    provider = saved.provider if saved else cfg.provider
    model = saved.model if saved else cfg.model
    base = saved.base_url if saved else cfg.base_url
    config = ProviderConfig(provider=provider, model=model, base_url=base,
                            api_key="", num_ctx=cfg.num_ctx,
                            temperature=cfg.temperature, timeout_s=cfg.timeout_s)
    save_config(config)
    return {"provider": provider, "model": model, "authenticated": False}


def set_model(provider: Optional[str] = None, model: Optional[str] = None,
              base_url: Optional[str] = None) -> Dict[str, Any]:
    if not model:
        raise ValueError("model required (protacxtend model set --model NAME)")
    cfg = current_config()
    saved = load_user_config()
    prov = (provider or (saved.provider if saved else "") or cfg.provider or "").strip()
    if not prov or prov not in PROVIDER_META:
        raise ValueError("no provider selected — run `protacxtend setup` or pass --provider NAME")
    m = meta(prov)
    base = base_url or (saved.base_url if saved and saved.base_url else m.default_base_url or cfg.base_url)
    key = (saved.api_key if saved else "") or (cfg.api_key if cfg.provider == prov else "") or _env_key(prov)
    config = ProviderConfig(provider=prov, model=model, base_url=base, api_key=key,
                            num_ctx=cfg.num_ctx, temperature=cfg.temperature,
                            timeout_s=cfg.timeout_s)
    save_config(config)
    return {"provider": prov, "model": model, "base_url": base}


def list_models(provider: Optional[str] = None) -> Dict[str, Any]:
    """Advertised models per provider; live list only for reachable locals.

    With no provider configured, list every provider's advertised default so
    the user can pick — the manager never fabricates a provider choice.
    """
    cfg = current_config()
    explicit = (provider or "").strip()
    if explicit and explicit not in PROVIDER_META:
        raise ValueError(f"unknown provider '{explicit}' — choose one of: {', '.join(provider_ids())}")
    prov = explicit or cfg.provider or ""
    if not prov or prov not in PROVIDER_META:
        rows = []
        for pid in sorted(PROVIDER_META):
            m = PROVIDER_META[pid]
            rows.append(f"{pid}/{m.default_model}" if m.default_model else pid)
        return {"provider": "(none)", "default_model": "",
                "models": rows, "source": "advertised (pick a provider: protacxtend setup)"}
    m = meta(prov)
    models: List[str] = []
    source = "advertised"
    if m.local:
        try:
            models = get_provider(prov).list_models(
                ProviderConfig(provider=prov, model=m.default_model,
                               base_url=m.default_base_url))
            source = "live (ollama)"
        except Exception:
            models = []
    if not models and cfg.provider == prov and (cfg.base_url or m.default_base_url):
        # configured cloud/custom endpoint → best-effort live model list
        # (GET /models is metadata only; never an inference call).
        try:
            models = get_provider(prov).list_models(
                ProviderConfig(provider=prov, model=cfg.model or m.default_model,
                               base_url=cfg.base_url or m.default_base_url,
                               api_key=effective_key(prov)))
            source = "live"
        except Exception:
            models = []
    if not models:
        models = [m.default_model] if m.default_model else []
        source = "advertised"
    return {"provider": prov, "default_model": m.default_model,
            "models": models, "source": source}


# ── provider list / current (provider-neutral CLI) ──────────────────────

def provider_current() -> Dict[str, Any]:
    """Resolved runtime provider (env > saved > none). Keys never returned."""
    cfg = current_config()
    if not cfg.provider:
        return {"provider": "", "model": "", "base_url": "",
                "configured": False, "source": "none",
                "hint": "run: protacxtend setup"}
    from protacxtend.llm import providers as _prov
    if _prov._runtime_config is not None and _prov._runtime_config.provider == cfg.provider:
        source = "runtime"
    elif os.environ.get("PROTACPILOT_LLM_PROVIDER", "").strip() == cfg.provider:
        source = "env"
    else:
        source = "config"
    state = auth_state(cfg.provider)
    return {
        "provider": cfg.provider,
        "model": cfg.model or state["model"],
        "base_url": cfg.base_url or state["base_url"],
        "configured": True,
        "source": source,
        "authenticated": bool(state["authenticated"]),
        "local": bool(state["local"]),
    }


def provider_list() -> Dict[str, Any]:
    """All supported providers + whether each one is currently usable."""
    cfg = current_config()
    current = cfg.provider or ""
    rows = []
    for pid in sorted(PROVIDER_META):
        m = PROVIDER_META[pid]
        key_set = bool(_env_key(pid))
        saved = load_user_config()
        saved_match = bool(saved and saved.provider == pid)
        configured = (pid == current) or key_set or saved_match
        rows.append({
            "provider": pid,
            "label": m.label,
            "local": m.local,
            "key_env": key_env_name(pid) if m.key_env else "",
            "env_key_set": key_set,
            "default_model": m.default_model or "",
            "current": pid == current,
            "configured": configured,
        })
    return {"current": current or "(none)", "providers": rows}


# ── live probes (connection + tiny inference) ───────────────────────────

def _is_loopback(url: str) -> bool:
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        return False
    return host in ("127.0.0.1", "localhost", "::1") or host.endswith(".local")


def probe_connection(config: Optional[ProviderConfig] = None,
                     timeout_s: int = 6) -> Dict[str, Any]:
    """Reachability probe — no inference, no tokens. Never raises."""
    cfg = config or current_config()
    if not cfg.provider:
        return {"ok": False, "detail": "no provider configured"}
    if cfg.provider not in PROVIDER_META:
        return {"ok": False, "detail": f"unknown provider {cfg.provider!r}"}
    try:
        models = get_provider(cfg.provider).list_models(cfg)
        return {"ok": True, "detail": f"endpoint reachable ({len(models)} models)",
                "models": models[:20], "n_models": len(models)}
    except Exception as exc:
        return {"ok": False, "detail": f"endpoint unreachable: {str(exc)[:160]}"}


INFERENCE_PROBE_SYSTEM = "You are a connectivity probe. Reply with exactly one JSON object: {\"ok\": true}."
INFERENCE_PROBE_USER = "Ping."
INFERENCE_PROBE_SCHEMA = {
    "type": "object",
    "properties": {"ok": {"type": "boolean"}},
    "required": ["ok"],
    "additionalProperties": False,
}


def probe_inference(config: Optional[ProviderConfig] = None,
                    timeout_s: int = 60,
                    allow_cloud: bool = False) -> Dict[str, Any]:
    """One tiny inference against the configured backend. Never raises.

    Providers on localhost are always probed. Cloud APIs are probed when
    ``allow_cloud=True`` (explicit opt-in during `protacxtend setup`) or
    PROTACXTEND_PROBE_CLOUD=1 so `doctor` never spends tokens silently.
    """
    import time
    cfg = config or current_config()
    if not cfg.provider or not cfg.model:
        return {"ok": False, "detail": "provider/model not configured — run: protacxtend setup"}
    if cfg.provider not in PROVIDER_REGISTRY:
        return {"ok": False, "detail": f"unknown provider {cfg.provider!r}"}
    m = PROVIDER_META.get(cfg.provider)
    localish = bool(m and m.local) or _is_loopback(cfg.base_url or (m.default_base_url if m else ""))
    if not localish and not allow_cloud and os.environ.get("PROTACXTEND_PROBE_CLOUD", "0") != "1":
        return {"ok": False, "detail": "cloud inference probe disabled (run inside `protacxtend setup` or set PROTACXTEND_PROBE_CLOUD=1)"}
    probe_cfg = ProviderConfig(provider=cfg.provider, model=cfg.model,
                               base_url=cfg.base_url,
                               api_key=cfg.api_key or "",
                               num_ctx=cfg.num_ctx, temperature=0.0,
                               timeout_s=timeout_s)
    t0 = time.time()
    try:
        raw = get_provider(cfg.provider).chat_raw(
            INFERENCE_PROBE_SYSTEM, INFERENCE_PROBE_USER,
            INFERENCE_PROBE_SCHEMA, probe_cfg)
        elapsed = round(time.time() - t0, 2)
        text = (raw or "").strip()
        ok = bool(text)
        return {"ok": ok, "detail": "inference replied" if ok else "empty reply",
                "elapsed_s": elapsed, "reply": text[:120], "n_chars": len(text)}
    except Exception as exc:
        return {"ok": False, "detail": f"inference failed: {str(exc)[:160]}",
                "elapsed_s": round(time.time() - t0, 2)}


# ── verification record (no secrets) ─────────────────────────────────────

def record_verification(state: Dict[str, Any]) -> Path:
    """Persist that auth+inference PASSED for a provider/model (no keys)."""
    import datetime as _dt
    VERIFY_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "provider": state.get("provider", ""),
        "model": state.get("model", ""),
        "base_url": state.get("base_url", ""),
        "auth": "pass",
        "connection": "pass" if state.get("connection_ok") else "unknown",
        "inference": "pass" if state.get("inference_ok") else "fail",
        "verified_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
    }
    VERIFY_PATH.parent.mkdir(parents=True, exist_ok=True)
    VERIFY_PATH.write_text(json.dumps(payload, indent=2) + "\n")
    try:
        VERIFY_PATH.chmod(0o600)
    except OSError:
        pass
    return VERIFY_PATH


def last_verification() -> Dict[str, Any]:
    try:
        if VERIFY_PATH.exists():
            return json.loads(VERIFY_PATH.read_text())
    except Exception:
        pass
    return {}


def matches_verified(cfg: Optional[ProviderConfig] = None) -> bool:
    """Current provider/model/base_url == last successful live verification."""
    c = cfg or current_config()
    v = last_verification()
    return bool(v and v.get("provider") == c.provider and v.get("model") == c.model
                and (v.get("base_url") or "") == (c.base_url or "")
                and v.get("inference") == "pass")


# ── doctor: one resolved config, six checks ─────────────────────────────

def runtime_checks(live: bool = True,
                   cfg: Optional[ProviderConfig] = None) -> Dict[str, Any]:
    """Provider / Model / Auth / Connection / Inference / Status.

    Never raises, never prints keys, never calls a paid API without the
    PROTACXTEND_PROBE_CLOUD=1 opt-in (localhost backends are probed live).
    ``cfg`` overrides the resolved config (used by `doctor --provider X`).
    """
    cfg = cfg or current_config()
    if not cfg.provider:
        return {
            "provider": "(none)", "model": cfg.model or "",
            "auth": {"ok": False, "detail": "no provider configured"},
            "connection": {"ok": False, "detail": "no provider configured"},
            "inference": {"ok": False, "detail": "no provider configured"},
            "status": "NOT READY", "issues": ["run: protacxtend setup"],
        }
    if cfg.provider not in PROVIDER_META:
        return {
            "provider": cfg.provider, "model": cfg.model or "",
            "auth": {"ok": False, "detail": "unknown provider"},
            "connection": {"ok": False, "detail": "unknown provider"},
            "inference": {"ok": False, "detail": "unknown provider"},
            "status": "NOT READY", "issues": [f"unknown provider {cfg.provider!r}"],
        }
    m = PROVIDER_META[cfg.provider]
    model = cfg.model or m.default_model
    base = cfg.base_url or m.default_base_url

    auth = auth_state(cfg.provider)
    auth_ok = bool(auth["authenticated"])
    auth_detail = ("local backend (no key needed)" if auth["local"]
                   else (f"key present ({auth['key_source']})" if auth_ok else f"no API key (set {auth['key_env']})"))

    conn = {"ok": False, "detail": "not tested"}
    inf = {"ok": False, "detail": "not tested"}
    issues: List[str] = []
    if not model:
        issues.append("model missing — run: protacxtend setup")
    if live:
        if m.local or _is_loopback(base):
            conn = probe_connection(cfg)
            if not conn["ok"]:
                issues.append("endpoint unreachable — is the local server running?")
            if conn["ok"] and model:
                inf = probe_inference(cfg)
                if not inf["ok"]:
                    issues.append("local inference probe failed")
        else:
            conn = probe_connection(cfg)
            if not conn["ok"]:
                issues.append("cloud endpoint unreachable (check base_url / network)")
            if matches_verified(cfg):
                inf = {"ok": True, "detail": "verified at setup",
                       "verified_at": last_verification().get("verified_at")}
            elif os.environ.get("PROTACXTEND_PROBE_CLOUD", "0") == "1":
                inf = probe_inference(cfg)
                if not inf["ok"]:
                    issues.append("cloud inference probe failed")
            else:
                inf = {"ok": False,
                       "detail": "run `protacxtend setup` to verify auth + one inference (no auto-spend)"}
                issues.append("auth+inference not yet verified for this provider/model")
    else:
        issues.append("live probes disabled (--no-live)")

    status = "READY" if (auth_ok and conn["ok"] and inf["ok"] and model) else "NOT READY"
    return {
        "provider": cfg.provider,
        "model": model,
        "auth": {"ok": auth_ok, "detail": auth_detail},
        "connection": conn,
        "inference": inf,
        "status": status,
        "issues": issues,
        "verified": matches_verified(cfg),
    }
