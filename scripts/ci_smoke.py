#!/usr/bin/env python3
"""CI smoke test — asset-free sanity of the ProtacPilot runtime.

Runs on a fresh clone WITHOUT excluded assets (no aizynth models, no SE3
weights, no conda envs). Verifies the software-engineering baseline:

  1. Python imports of the package surface
  2. Configuration parsing
  3. Agent registry loads
  4. Tool registry registers correctly
  5. Pydantic / schema validation
  6. SMILES input validation
  7. Orchestrator entry (mocked/heavy-free)
  8. API startup (FastAPI TestClient)

Exit code 0 = baseline OK. Heavy scientific calls are intentionally NOT run.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

FAILURES: list[str] = []


def check(name: str, fn):
    try:
        fn()
        print(f"  OK   {name}")
    except Exception as exc:  # noqa: BLE001
        FAILURES.append(f"{name}: {exc}")
        print(f"  FAIL {name}: {exc}")


def smoke():
    # 1. imports
    def t_imports():
        import protacxtend  # noqa: F401
        from protacxtend.agents import runtime  # noqa: F401
        from protacxtend.integrations import heruka  # noqa: F401
        from protacxtend.tools import retrosynthesis  # noqa: F401
    check("imports", t_imports)

    # 2. config parsing
    def t_config():
        import protacxtend.backend.config as cfg
        assert cfg.PROJECT_ROOT.exists()
        cfg.ensure_directories()
    check("config parse (backend config)", t_config)

    # 3. agent registry
    def t_agents():
        from protacxtend.agents import (
            agentic_core,  # noqa: F401
            graph,  # noqa: F401
            runtime,  # noqa: F401
        )
    check("agent modules import", t_agents)

    # 4. tool registry
    def t_tools():
        from protacxtend.tools.tool_registry import ToolRegistry
        reg = ToolRegistry()
        rows = reg.as_rows()
        assert len(rows) >= 10, f"expected >=10 tools, got {len(rows)}"
        print(f"         ({len(rows)} tools registered)")
    check("tool registry (>=10 tools)", t_tools)

    # 5. pydantic schemas
    def t_schemas():
        from protacxtend.schemas.agentic_schema import DesignGoal
        from protacxtend.schemas.tool_schema import ToolResult
        g = DesignGoal(target="BRD4", e3="CRBN")
        assert g.target == "BRD4"
        r = ToolResult(tool="test", status="ok", payload={})
        assert r.status == "ok"
    check("pydantic schemas", t_schemas)

    # 6. SMILES validation
    def t_smiles():
        from rdkit import Chem
        assert Chem.MolFromSmiles("CC(=O)Oc1ccccc1C(=O)O") is not None
        assert Chem.MolFromSmiles("not_a_smiles!!") is None
    check("SMILES validation (rdkit)", t_smiles)

    # 7. orchestrator entry + graceful degradation (no assets)
    def t_orchestrator():
        from protacxtend.tools.retrosynthesis import aizynth_route_search
        r = aizynth_route_search("CCO")  # asset-free -> tool_failed, not crash
        assert "tool_failed" in r or r.get("ran") is True
    check("orchestrator graceful degradation", t_orchestrator)

    # 8. API startup
    def t_api():
        from fastapi.testclient import TestClient

        from protacxtend.backend.api_routes import get_app
        app = get_app()
        c = TestClient(app)
        r = c.get("/health")
        assert r.status_code == 200, r.text
        assert r.json().get("status") == "ok"
    check("API startup (/health)", t_api)


if __name__ == "__main__":
    print("ProtacPilot CI smoke (asset-free baseline)")
    smoke()
    print("-" * 50)
    if FAILURES:
        print(f"SMOKE FAILED ({len(FAILURES)}):")
        for f in FAILURES:
            print("  -", f)
        sys.exit(1)
    print("SMOKE PASSED")
