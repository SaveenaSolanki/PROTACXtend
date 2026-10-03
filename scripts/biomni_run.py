#!/usr/bin/env python
"""Run one blinded task through the *official installed* Biomni and emit JSON.

Executed by ``/tmp/biomni_venv/bin/python`` (isolated Biomni 0.0.8 environment),
never by the PROTACXtend interpreter. It imports only Biomni + stdlib.

Output JSON:
    {"ok": bool, "answer": str, "version": str, "tool_calls": int,
     "error": str, "raw": str, "usage": {...}, "elapsed_s": float}

Usage:
    /tmp/biomni_venv/bin/python scripts/biomni_run.py --prompt "..." --out out.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path


def _llm_config() -> dict:
    """Same provider/model as PROTACXtend: DeepSeek via Custom OpenAI-compatible."""
    key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not key:
        try:
            auth = json.load(open("/home/saveenas/.pi/agent/auth.json"))
            key = (auth.get("deepseek") or {}).get("key", "")
        except Exception:
            key = ""
    return {
        "llm": os.environ.get("BIOMNI_LLM", "deepseek-v4-flash"),
        "source": "Custom",
        "base_url": os.environ.get("BIOMNI_BASE_URL", "https://api.deepseek.com/v1"),
        "api_key": key,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--timeout", type=int, default=1200)
    args = ap.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    result: dict = {"ok": False, "answer": "", "version": "", "tool_calls": 0,
                    "error": "", "raw": "", "usage": {}, "elapsed_s": 0.0}

    t0 = time.monotonic()
    try:
        import biomni
        result["version"] = getattr(biomni, "__version__", "unknown")
        from biomni.agent import A1

        cfg = _llm_config()
        if not cfg["api_key"]:
            raise RuntimeError("no DeepSeek API key available to Biomni")
        agent = A1(
            path=None,
            llm=cfg["llm"],
            source=cfg["source"],
            base_url=cfg["base_url"],
            api_key=cfg["api_key"],
            timeout_seconds=args.timeout,
            use_tool_retriever=False,
            expected_data_lake_files=[],
        )
        raw = agent.go(args.prompt)
        result["raw"] = str(raw)[:20000]
        import re as _re
        # Biomni returns (answer, history) or a string depending on version.
        if isinstance(raw, tuple):
            full = str(raw[0])
            history = raw[1] if len(raw) > 1 else None
            result["tool_calls"] = len(history) if isinstance(history, list) else 0
        else:
            full = str(raw)
        # Count actual tool executions from the transcript tags (Biomni emits
        # <execute> ... <observation> blocks); history length is not a call count.
        if not result["tool_calls"]:
            result["tool_calls"] = full.count("<observation>") or full.count("<execute>")
        # Prefer the explicit <solution> block when present.
        m = _re.findall(r"<solution>(.*?)</solution>", full, _re.S)
        result["answer"] = (m[-1].strip() if m else full.strip())
        result["ok"] = bool(str(result["answer"]).strip())
    except BaseException as exc:  # noqa: BLE001 - record, never crash
        result["error"] = f"{type(exc).__name__}: {exc}"
    result["elapsed_s"] = round(time.monotonic() - t0, 3)
    out_path.write_text(json.dumps(result, default=str, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"ok": result["ok"], "error": result["error"], "elapsed_s": result["elapsed_s"]}))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
