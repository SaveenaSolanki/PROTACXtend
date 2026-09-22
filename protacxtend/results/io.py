"""Persistent result.json I/O + readable CLI rendering (schema 1.0.0).

Users should never need to open result.json by hand: ``human_summary`` is
the canonical readable rendering of a frozen ScientificResult.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from protacxtend.results.schema import SCHEMA_VERSION, from_dict, ScientificResult


def write_result_json(path: Path | str, result: ScientificResult | dict[str, Any],
                      metadata: Optional[dict[str, Any]] = None) -> Path:
    """Write a frozen result.json (pretty, schema-versioned).

    Adds the PROTACXtend version to metadata automatically. Provider/model
    live on the ScientificResult itself (never a key).
    """
    import protacxtend
    out = result.to_dict() if isinstance(result, ScientificResult) else dict(result)
    if metadata:
        merged = dict(out.get("metadata") or {})
        merged.update(metadata)
        out["metadata"] = merged
    out["schema_version"] = SCHEMA_VERSION
    meta = dict(out.get("metadata") or {})
    meta.setdefault("protacxtend_version", getattr(protacxtend, "__version__", "?"))
    meta.setdefault("written_at", datetime.now(timezone.utc).isoformat())
    out["metadata"] = meta
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2, default=str) + "\n")
    return path


def read_result_json(path: Path | str) -> ScientificResult:
    return from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def human_summary(result: ScientificResult | dict[str, Any], width: int = 78) -> str:
    """Readable CLI rendering of a result — no JSON inspection required."""
    r = result.to_dict() if isinstance(result, ScientificResult) else dict(result)
    line = "=" * min(width, 78)
    out: list[str] = [line]
    meta = r.get("metadata") or {}
    head = f"PROTACXtend result · schema {r.get('schema_version', SCHEMA_VERSION)}"
    task = r.get("task_id") or meta.get("request") or ""
    out.append(head + (f" · task {task}" if task else ""))
    out.append(line)
    status = r.get("status", "?")
    icon = "✓" if status in ("ok", "ready") else ("!" if status == "partial" else "✗")
    out.append(f"  {icon} workflow   {r.get('workflow', '?')}  [{status}]")
    prov = r.get("provider") or "deterministic/none"
    out.append(f"    provider   {prov}" + (f"/{r.get('model')}" if r.get("model") else ""))
    out.append(f"    summary    {r.get('summary', '')}")
    result = r.get("result") or {}
    if isinstance(result, dict) and result:
        keys = list(result.keys())[:6]
        out.append("    answer     " + " · ".join(f"{k}={_short(result[k])}" for k in keys))
    ev = r.get("evidence") or []
    if ev:
        out.append(f"    evidence   {len(ev)} item(s):")
        for e in ev[:8]:
            kind = e.get("kind", "retrieved")
            src = f" [{e.get('source')}]" if e.get("source") else ""
            out.append(f"      - ({kind}) {e.get('summary', '')}{src}")
    tools = r.get("tools") or []
    if tools:
        out.append(f"    tools      {', '.join(tools)}")
    arts = r.get("artifacts") or []
    if arts:
        out.append(f"    artifacts  {', '.join(str(a) for a in arts)}")
    for w in r.get("warnings") or []:
        out.append(f"    warning    {w}")
    for e in r.get("errors") or []:
        out.append(f"    error      {e}")
    provs = r.get("provenance") or []
    if provs:
        out.append(f"    provenance {', '.join(p.get('tool', '?') for p in provs)}")
    out.append(line)
    return "\n".join(out)


def _short(v: Any) -> str:
    s = str(v)
    return s if len(s) <= 40 else s[:37] + "…"
