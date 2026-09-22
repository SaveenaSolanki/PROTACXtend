"""
PROTACXtend universal setup wizard — API / Local / Configure later.
==================================================================

``protacxtend setup`` drives this wizard. It is provider-NEUTRAL:

  * API mode   → user picks provider (DeepSeek / OpenAI / Anthropic /
                 Google / OpenRouter / any OpenAI-compatible endpoint),
                 model, key and optional base URL → tests auth + ONE small
                 inference → persists the verified config.
  * Local mode → detects Ollama (and lets you point at any OpenAI-compatible
                 local server), lists existing models, lets you select one,
                 only OFFERS a download with explicit confirmation, tests one
                 inference.
  * Configure later → nothing is written.

Secrets: keys are only written to ~/.protacxtend/llm.json (chmod 600), never
echoed to stdout, never stored in result/verification files.

Every function takes ask()/out() so the flow is testable without a TTY.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from protacxtend.llm import manager
from protacxtend.llm.manager import PROVIDER_META
from protacxtend.llm.providers import (
    USER_CONFIG_PATH,
    get_config,
    get_provider,
    load_user_config,
    ProviderConfig,
    set_runtime_config,
)

OLLAMA_DEFAULT_BASE = "http://127.0.0.1:11434"
CUSTOM_KEY_ENVS = ("PROTACPILOT_LLM_API_KEY", "OPENAI_API_KEY", "CUSTOM_LLM_API_KEY")


def needs_setup() -> bool:
    """True when no provider choice exists (env or saved config)."""
    return not manager.is_configured()


def _cloud_providers() -> List[str]:
    return [pid for pid in sorted(PROVIDER_META)
            if not PROVIDER_META[pid].local and pid != "gemini"]


def _sdk_installed(name: str) -> bool:
    """True when an importable SDK is present.

    ``find_spec`` on a dotted name (``google.generativeai``) raises
    ModuleNotFoundError when the top-level package is absent, which must
    not break detection in minimal installs.
    """
    try:
        return importlib.util.find_spec(name) is not None
    except (ModuleNotFoundError, ValueError, AttributeError):
        return False


def detect_provider_frameworks() -> List[Dict[str, Any]]:
    """Existing provider frameworks on this machine (env key or SDK present)."""
    sdk = {"deepseek": None, "openai": "openai", "anthropic": "anthropic",
           "google": "google.generativeai", "openrouter": "openai",
           "openai_compatible": "openai"}
    out = []
    for pid in _cloud_providers():
        m = PROVIDER_META[pid]
        key = m.key_env
        env_key = bool(os.environ.get(key, "")) if key else False
        for k in CUSTOM_KEY_ENVS:
            if os.environ.get(k):
                env_key = True
        sdk_name = sdk.get(pid)
        sdk_ok = bool(sdk_name) and _sdk_installed(sdk_name)
        out.append({"provider": pid, "label": m.label, "key_env": key,
                    "env_key_set": env_key, "sdk_installed": sdk_ok,
                    "default_model": m.default_model or "",
                    "default_base_url": m.default_base_url or ""})
    return out


def _pick_from_list(ask: Callable, out: Callable, rows: List[Any],
                    label: str, default: Optional[str] = None,
                    name_of=lambda r: str(r)) -> Any:
    out("")
    for i, r in enumerate(rows, 1):
        out(f"  [{i}] {name_of(r)}")
    prompt = f"{label}" + (f" [{default}]" if default else "") + ": "
    while True:
        raw = ask(prompt).strip()
        if not raw and default is not None:
            raw = default
        if raw.isdigit() and 1 <= int(raw) <= len(rows):
            return rows[int(raw) - 1]
        if raw:  # allow provider/model name typing
            return raw
        out("  (pick a number or type a name)")


# ── API mode ─────────────────────────────────────────────────────────

def _api_mode(ask: Callable, out: Callable) -> Dict[str, Any]:
    from protacxtend.llm import providers as prov_mod
    saved = load_user_config()
    if saved:
        out(f"\n  currently configured: {saved.provider} · {saved.model} · {saved.base_url}")
        out("  (choose a new provider below to switch; Enter on provider = keep current)\n")

    detected = detect_provider_frameworks()
    framework_rows = _cloud_providers()
    current_hint = ""
    if saved and saved.provider in framework_rows:
        current_hint = f"{saved.provider}/{saved.model or ''}"

    out("API — supported providers (✓ = detected on this machine):")
    rows: List[str] = []
    for pid in framework_rows:
        m = PROVIDER_META[pid]
        det = next((d for d in detected if d["provider"] == pid), {})
        mark = "✓" if (det.get("env_key_set") or det.get("sdk_installed")) else " "
        rows.append(pid)
        hint = m.default_model or "(model required)"
        out(f"  [{rows.index(pid) + 1}] {mark} {pid:<18} {hint}")
    pick = _pick_from_list(ask, out, rows, "Provider", default=saved.provider if saved else None)
    if isinstance(pick, int):
        provider = rows[pick - 1]
    else:
        provider = pick
    if provider not in PROVIDER_META:
        out(f"  unknown provider '{provider}'")
        return {"mode": "api", "ok": False, "error": f"unknown provider {provider}"}
    m = PROVIDER_META[provider]

    env_key = ""
    for k in (m.key_env or "", *CUSTOM_KEY_ENVS):
        env_key = os.environ.get(k, "")
        if env_key:
            break

    if not m.default_base_url:
        base_url = ask("Base URL (OpenAI-compatible endpoint, e.g. http://localhost:8000/v1): ").strip()
        if not base_url:
            out("  base URL is required for custom endpoints")
            return {"mode": "api", "ok": False, "error": "base URL required"}
        model = ask("Model: ").strip()
        if not model:
            out("  model is required")
            return {"mode": "api", "ok": False, "error": "model required"}
    else:
        base_url = ask(f"Base URL [{m.default_base_url}] (Enter for default): ").strip() or m.default_base_url
        model = ask(f"Model [{m.default_model}]: ").strip() or m.default_model

    needs_key = provider not in ("openai_compatible",)
    if env_key:
        out(f"  using API key from environment ({m.key_env or 'PROTACPILOT_LLM_API_KEY'}) — not prompted.")
        api_key = env_key
    elif needs_key:
        try:
            import getpass, sys
            if sys.stdin.isatty():
                api_key = getpass.getpass("API key (hidden): ").strip()
            else:
                api_key = ask("API key: ").strip()
        except Exception:
            api_key = ask("API key: ").strip()
    else:
        api_key = ask("API key (optional for local/self-hosted endpoints): ").strip()

    api_key = api_key.strip()
    if needs_key and not api_key:
        out("  an API key is required for this provider (or export its key env var)")
        return {"mode": "api", "ok": False, "error": "API key required"}

    cfg = ProviderConfig(provider=provider, model=model, base_url=base_url,
                         api_key=api_key)
    out(f"\n  Testing connection + one tiny inference on {provider}/{model} …")
    conn = manager.probe_connection(cfg)
    inf = manager.probe_inference(cfg, allow_cloud=True)
    out(f"  connection  {'PASS' if conn['ok'] else 'FAIL'} — {conn.get('detail', '')}")
    out(f"  inference   {'PASS' if inf['ok'] else 'FAIL'} — {inf.get('detail', '')}")

    verified = bool(conn.get("ok") and inf.get("ok"))
    if not verified:
        out("  note: probe did not fully pass. Save anyway? [y/N]")
        answer = ask("Save anyway? [y/N]: ").strip().lower()
        if answer not in ("y", "yes"):
            out("  setup aborted — nothing was saved.")
            return {"mode": "api", "ok": False,
                    "error": inf.get("detail") or conn.get("detail") or "probe failed"}
    manager.save_config(cfg)
    if verified:
        manager.record_verification({"provider": provider, "model": model,
                                     "base_url": base_url,
                                     "connection_ok": True, "inference_ok": True})
    out(f"\n  ✓ saved to {USER_CONFIG_PATH}  (key stored with mode 600, never printed)")
    out(f"  provider  {provider}")
    out(f"  model     {model}")
    out(f"  status    {'VERIFIED (auth + inference PASS)' if verified else 'SAVED (not verified)'}")
    return {"mode": "api", "ok": True, "provider": provider, "model": model,
            "verified": verified, "config_file": str(USER_CONFIG_PATH)}


# ── Local mode ───────────────────────────────────────────────────────

def _detect_ollama() -> Dict[str, Any]:
    import requests
    base = os.environ.get("OLLAMA_BASE_URL", OLLAMA_DEFAULT_BASE)
    try:
        resp = requests.get(base.rstrip("/") + "/api/tags", timeout=3)
        resp.raise_for_status()
        models = [m.get("name") or m.get("model") for m in resp.json().get("models", [])]
        return {"ok": True, "base_url": base, "models": models,
                "binary": bool(__import__("shutil").which("ollama"))}
    except Exception as exc:
        return {"ok": False, "base_url": base, "models": [],
                "error": str(exc)[:160]}


def _local_mode(ask: Callable, out: Callable) -> Dict[str, Any]:
    ollama = _detect_ollama()
    out("\nLocal mode — detect installed local runtimes…")
    if ollama["ok"]:
        out(f"  ✓ Ollama server   {ollama['base_url']}"
            + (f"  ({ollama['binary'] and 'binary on PATH'})" if ollama.get("binary") else ""))
        out(f"    models: {', '.join(ollama['models']) or '(none pulled yet)'}")
    else:
        out(f"  ✗ Ollama not reachable at {ollama['base_url']} ({ollama.get('error')})")
    binary = __import__("shutil").which("ollama")
    out(f"  {'✓' if binary else '✗'} ollama binary   {binary or 'not on PATH'}")

    if ollama["ok"] and ollama["models"]:
        out("\nAvailable models:")
        out("  [0] use a different local server (OpenAI-compatible)")
        for i, mo in enumerate(ollama["models"], 1):
            out(f"  [{i}] {mo}")
        raw = ask("Model number [1]: ").strip()
        if raw == "0":
            return _custom_local(ask, out)
        try:
            model = ollama["models"][int(raw) - 1]
        except (ValueError, IndexError):
            model = raw or ollama["models"][0]
        base_url = ollama["base_url"]
        provider = "ollama"
    elif binary:
        out("\n  Ollama is installed but has no models pulled yet.")
        model = ask("Model to pull (e.g. llama3.2:1b) [llama3.2:1b]: ").strip() or "llama3.2:1b"
        out(f"  download requires ~1-5 GB and explicit confirmation — never automatic.")
        yes = ask(f"Run `ollama pull {model}` now? [y/N]: ").strip().lower()
        if yes in ("y", "yes"):
            import subprocess
            res = subprocess.run(["ollama", "pull", model], capture_output=True, text=True)
            if res.returncode != 0:
                out(f"  pull failed: {res.stderr[-400:]}")
                return {"mode": "local", "ok": False, "error": "ollama pull failed"}
            out(f"  ✓ pulled {model}")
        else:
            out("  nothing downloaded. Re-run setup after pulling a model.")
            return {"mode": "local", "ok": False, "error": "no model selected"}
        base_url = ollama["base_url"]
        provider = "ollama"
    else:
        out("\n  No local runtime detected.")
        out("  [1] Point at an OpenAI-compatible local server (vLLM/LM Studio/llama.cpp)")
        out("  [2] Configure later")
        raw = ask("Choice [1/2]: ").strip()
        if raw == "2":
            return {"mode": "local", "ok": False, "error": "configure later"}
        return _custom_local(ask, out)

    cfg = ProviderConfig(provider=provider, model=model, base_url=base_url, api_key="")
    out(f"\n  Testing one tiny inference on {provider}/{model} …")
    inf = manager.probe_inference(cfg, allow_cloud=False)
    out(f"  inference   {'PASS' if inf['ok'] else 'FAIL'} — {inf.get('detail', '')}")
    manager.save_config(cfg)
    if inf["ok"]:
        manager.record_verification({"provider": provider, "model": model,
                                     "base_url": base_url,
                                     "connection_ok": True, "inference_ok": True})
    out(f"\n  ✓ saved to {USER_CONFIG_PATH}")
    return {"mode": "local", "ok": True, "provider": provider, "model": model,
            "verified": bool(inf["ok"]), "inference_s": inf.get("elapsed_s")}


def _custom_local(ask: Callable, out: Callable) -> Dict[str, Any]:
    base_url = ask("OpenAI-compatible base URL (e.g. http://localhost:8000/v1): ").strip()
    if not base_url:
        out("  base URL required")
        return {"mode": "local", "ok": False, "error": "base URL required"}
    model = ask("Model: ").strip()
    if not model:
        out("  model required")
        return {"mode": "local", "ok": False, "error": "model required"}
    cfg = ProviderConfig(provider="openai_compatible", model=model,
                         base_url=base_url, api_key="")
    out(f"\n  Testing connection + one tiny inference on {base_url}/{model} …")
    conn = manager.probe_connection(cfg)
    inf = manager.probe_inference(cfg, allow_cloud=False)
    out(f"  connection  {'PASS' if conn['ok'] else 'FAIL'} — {conn.get('detail', '')}")
    out(f"  inference   {'PASS' if inf['ok'] else 'FAIL'} — {inf.get('detail', '')}")
    verified = bool(conn.get("ok") and inf.get("ok"))
    manager.save_config(cfg)
    if verified:
        manager.record_verification({"provider": "openai_compatible", "model": model,
                                     "base_url": base_url,
                                     "connection_ok": True, "inference_ok": True})
    out(f"\n  ✓ saved to {USER_CONFIG_PATH}")
    return {"mode": "local", "ok": True, "provider": "openai_compatible",
            "model": model, "verified": verified}


# ── top-level wizard ─────────────────────────────────────────────────

def run_setup(ask: Callable = input, out: Callable = print) -> Dict[str, Any]:
    """Interactive `protacxtend setup` (API / Local / Configure later)."""
    current = manager.provider_current()
    out("\n  PROTACXtend setup — choose a backend for inference & decision making:")
    if current.get("configured"):
        out(f"    (currently: {current['provider']} · {current['model']} · source={current['source']})")
    out("    [1] API      — DeepSeek / OpenAI / Anthropic / Google / OpenRouter / compatible endpoint")
    out("    [2] Local    — Ollama or any OpenAI-compatible local server (existing models only)")
    out("    [3] Configure later  — nothing is saved")
    raw = ask("Backend [1/2/3]: ").strip().lower()
    if raw in ("2", "local", "l", "ollama"):
        return _local_mode(ask, out)
    if raw in ("3", "later", "skip", "none", "n"):
        out("\n  OK — configure later. Run `protacxtend setup` anytime. "
            "`protacxtend doctor` will stay NOT READY until then.")
        return {"mode": "later", "ok": False, "error": "configure later"}
    if raw in ("", "1", "api", "a"):
        return _api_mode(ask, out)
    out("  unrecognised choice")
    return {"mode": "unknown", "ok": False, "error": "unrecognised choice"}


def first_run_gate(ask: Callable = input, out: Callable = print,
                   skip_env: str = "PROTACXTEND_SKIP_SETUP") -> bool:
    """First-run behaviour: auto-open setup when no provider is configured.

    Returns True when a provider is (now) configured. Set
    PROTACXTEND_SKIP_SETUP=1 (or CI=1) to skip the interactive gate.
    """
    if not needs_setup():
        return True
    if os.environ.get(skip_env, "0") == "1" or os.environ.get("CI", "") == "1":
        out("  no LLM provider configured (skipping setup in non-interactive mode).")
        out("  configure one with: protacxtend setup")
        return False
    out("\n  First run — no LLM provider is configured yet.")
    try:
        run_setup(ask=ask, out=out)
    except (EOFError, KeyboardInterrupt):
        out("\n  setup interrupted — configure later with: protacxtend setup")
        return False
    return needs_setup()
