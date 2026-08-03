"""
Robust JSON extraction from model responses (provider-agnostic).
================================================================

Models occasionally wrap JSON in code fences, prefix with prose, or
truncate. This module extracts and repairs the JSON block before
Pydantic validation — deterministic, no LLM involved.
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional


def extract_json(text: str) -> Optional[str]:
    """Extract the most likely JSON object/array from a model response."""
    if not text:
        return None

    text = text.strip()

    # 1. Strip markdown code fences
    fenced = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE).strip()

    # 2. Find the first balanced { ... } block (best effort)
    candidates = []
    start = fenced.find("{")
    while start != -1:
        depth = 0
        in_str = False
        esc = False
        for i in range(start, len(fenced)):
            ch = fenced[i]
            if esc:
                esc = False
                continue
            if ch == "\\":
                esc = True
                continue
            if ch == '"':
                in_str = not in_str
                continue
            if not in_str:
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        candidates.append(fenced[start:i + 1])
                        break
        start = fenced.find("{", start + 1)

    if candidates:
        # Prefer the longest candidate (usually the real JSON)
        return max(candidates, key=len)

    # 3. Array fallback
    start = fenced.find("[")
    if start != -1:
        depth = 0
        in_str = False
        esc = False
        for i in range(start, len(fenced)):
            ch = fenced[i]
            if esc:
                esc = False
                continue
            if ch == "\\":
                esc = True
                continue
            if ch == '"':
                in_str = not in_str
                continue
            if not in_str:
                if ch == "[":
                    depth += 1
                elif ch == "]":
                    depth -= 1
                    if depth == 0:
                        return fenced[start:i + 1]
    return None


def repair_common(json_text: str) -> str:
    """Fix common truncation issues so json.loads succeeds."""
    # Trailing comma in last object entry (only at the very end of the block)
    json_text = re.sub(r",\s*([}\]])$", r"\1", json_text)
    # Unterminated string at end: only when there is an UNPAIRED quote AND the
    # text does not end with a structural close ( } or ] ).
    stripped = json_text.rstrip()
    if stripped and stripped[-1] not in "}]":
        if stripped.count('"') % 2 == 1:
            json_text = re.sub(r'"[^"]*$', '"', json_text)
    # Trailing garbage after final brace
    end = json_text.rfind("}")
    if end != -1 and end < len(json_text) - 1:
        json_text = json_text[:end + 1]
    # Unclosed braces at end (truncated) — try closing
    open_b = json_text.count("{") - json_text.count("}")
    if open_b > 0:
        json_text += "}" * open_b
    return json_text


def parse_json_robust(text: str) -> Any:
    """Extract + repair + parse. Raises ValueError if impossible."""
    block = extract_json(text)
    if block is None:
        raise ValueError(f"No JSON found in model output: {text[:200]!r}")
    try:
        return json.loads(block)
    except json.JSONDecodeError:
        repaired = repair_common(block)
        try:
            return json.loads(repaired)
        except json.JSONDecodeError as exc:
            raise ValueError(f"JSON repair failed: {exc} at {repaired[:200]!r}") from exc
