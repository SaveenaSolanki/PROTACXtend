#!/usr/bin/env python3
"""MD-docs vs implementation audit.

For every agent spec in md/, verify:
  - the documented source file exists (and approximate line count)
  - the agent class exists in that file
  - each documented tool/module exists
  - documented state fields appear in the WorkflowState schema
For root docs, verify backticked file paths exist and named modules import.
Output: markdown table -> outputs/MD_IMPLEMENTATION_AUDIT.md
"""
from __future__ import annotations

import importlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import ast  # noqa: E402

MD_DIR = ROOT / "md"
AGENTS = ROOT / "synglue_agent" / "agents"
TOOLS = ROOT / "synglue_agent" / "tools"

results = []


def check(name: str, ok: bool, detail: str, doc: str = ""):
    results.append({"doc": doc, "claim": name, "ok": ok, "detail": detail})


def file_line_count(p: Path):
    try:
        return len(p.read_text(encoding="utf-8", errors="ignore").splitlines())
    except Exception:
        return None


def class_exists(p: Path, class_name: str) -> bool:
    try:
        tree = ast.parse(p.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return False
    return any(isinstance(n, ast.ClassDef) and n.name == class_name for n in ast.walk(tree))


def main() -> int:
    # ── 1. md/ agent specs ────────────────────────────────────────────
    specs = sorted(MD_DIR.glob("[0-9][0-9]-*.md"))
    for spec in specs:
        text = spec.read_text(encoding="utf-8", errors="ignore")
        doc_name = spec.name
        m = re.search(r"\*\*Source\*\*\s*\|\s*`([^`]+)`", text)
        m_class = re.search(r"# \d+ · (\w+)", text)
        m_tools = re.search(r"\*\*Tools\*\*\s*\|\s*([^\n]+)", text)
        m_status = re.search(r"\*\*Status\*\*\s*\|\s*([^\n|]+)", text)

        class_name = m_class.group(1) if m_class else None
        src_rel = m.group(1) if m else None
        status = (m_status.group(1).strip() if m_status else "")

        if not src_rel:
            check(f"{doc_name}: source file", False, "no **Source** line", doc_name)
            continue
        src = ROOT / src_rel
        if not src.exists():
            check(f"{doc_name}: file {src_rel}", False, "FILE MISSING", doc_name)
            continue
        lines = file_line_count(src)
        check(f"{doc_name}: file exists", True, f"{src_rel} ({lines} lines)", doc_name)

        if class_name:
            ok = class_exists(src, class_name)
            check(f"{doc_name}: class {class_name}", ok,
                  "found" if ok else f"NOT FOUND in {src_rel}", doc_name)
        else:
            check(f"{doc_name}: class", False, "no class name in title", doc_name)

        # status markers O-1/2/3 -> check if the flag is still justified
        if "O-1" in status or "O-2" in status or "O-3" in status or "⚠" in status:
            check(f"{doc_name}: flagged status", False,
                  f"status flag '{status.strip()}' — verify whether the gap is now closed", doc_name)

        # tools referenced
        if m_tools:
            tools = re.findall(r"`([\w./]+\.py)`", m_tools.group(1))
            for t in tools:
                t_path = ROOT / t if t.startswith("synglue") else TOOLS / t
                check(f"{doc_name}: tool {t}", t_path.exists(),
                      "exists" if t_path.exists() else f"MISSING ({t})", doc_name)

    # ── 2. WorkflowState fields used by docs ──────────────────────────
    schema = (ROOT / "synglue_agent" / "backend" / "schemas.py").read_text(encoding="utf-8")
    fields = set(re.findall(r"^\s{4}([a-z_]+):", schema, re.M))
    for spec in specs:
        for fld in re.findall(r"`state\.([a-z_]+)`", spec.read_text(encoding="utf-8", errors="ignore")):
            if fld not in fields:
                check(f"{spec.name}: state.{fld}", False, f"field NOT in WorkflowState schema", spec.name)

    # ── 3. Root docs: referenced files/modules ────────────────────────
    root_docs = [
        "AGENT_APIS.md", "ARCHITECTURE_SUMMARY.md", "AGENT_DEV_PLAN.md",
        "fey_protac.md", "PROTACPILOT_TECHNICAL_COHERENCE.md", "HERUKA_INTEGRATION.md",
        "ASSET_MANIFEST.md",
    ]
    for doc in root_docs:
        p = ROOT / doc
        if not p.exists():
            check(f"{doc}", False, "doc missing", doc)
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        refs = set(re.findall(r"`([a-zA-Z0-9_./\-]+\.py)`", text))
        all_py = {p.name: p for p in (ROOT / "synglue_agent").rglob("*.py")}
        for ref in refs:
            candidates = [ROOT / ref, ROOT / "synglue_agent" / ref]
            if not any(c.exists() for c in candidates):
                # resolve by basename across synglue_agent
                hits = [p for name, p in all_py.items() if name == Path(ref).name]
                if hits:
                    check(f"{doc}: ref {ref}", True, f"resolved to {hits[0].relative_to(ROOT)}", doc)
                else:
                    check(f"{doc}: ref {ref}", False, "FILE MISSING (no basename match)", doc)
        # importable modules mentioned
        mods = set(re.findall(r"synglue_agent\.([a-z_\.]+)", text))
        for mod in sorted(mods)[:40]:
            try:
                importlib.import_module(f"synglue_agent.{mod}")
                ok = True
            except Exception:
                ok = False
            if not ok:
                check(f"{doc}: module synglue_agent.{mod}", False, "IMPORT FAILS", doc)

    # ── output ────────────────────────────────────────────────────────
    out = ["# MD-Docs vs Implementation Audit", "",
           f"_Generated 2026-08-12 · {len(results)} checks · " +
           f"{sum(1 for r in results if r['ok'])} OK, " +
           f"{sum(1 for r in results if not r['ok'])} FAIL_", "",
           "| Doc | Claim | Status | Evidence |",
           "|---|---|---|---|"]
    for r in results:
        mark = "✅" if r["ok"] else "❌"
        out.append(f"| {r['doc']} | {r['claim']} | {mark} | {r['detail']} |")

    (ROOT / "outputs" / "MD_IMPLEMENTATION_AUDIT.md").write_text("\n".join(out), encoding="utf-8")
    print(f"audit written: {sum(1 for r in results if not r['ok'])} failures / {len(results)} checks")
    for r in results:
        if not r["ok"]:
            print(f"  FAIL {r['doc']}: {r['claim']} — {r['detail'][:90]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
