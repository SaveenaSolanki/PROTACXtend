"""MCP tool surface, JSON-RPC server, and CLI smoke tests."""

from __future__ import annotations

import json

from protacpilot_memory import CognitiveMemory
from protacpilot_memory.cli.main import main as cli_main
from protacpilot_memory.mcp.server import McpServer
from protacpilot_memory.mcp.tools import CogToolRegistry
from protacpilot_memory.server.api import _coerce

REQUIRED_TOOLS = {
    "cog_current_project", "cog_encode", "cog_save_episode", "cog_search",
    "cog_recall", "cog_get", "cog_timeline", "cog_neighbors", "cog_context",
    "cog_predict", "cog_record_outcome", "cog_consolidate", "cog_replay",
    "cog_compare", "cog_judge_conflict", "cog_reconsolidate", "cog_strengthen",
    "cog_weaken", "cog_archive", "cog_future", "cog_task_add", "cog_task_resolve",
    "cog_stats", "cog_doctor", "cog_audit",
}


def test_registry_exposes_required_tools(mem):
    registry = CogToolRegistry(mem)
    assert REQUIRED_TOOLS <= set(registry.names())
    tools = registry.list_tools()
    assert all("inputSchema" in t for t in tools)


def test_registry_call_round_trip(mem, project):
    registry = CogToolRegistry(mem)
    result = registry.call("cog_encode", {
        "title": "MCP encode", "content": "dmax 0.2", "event_type": "degradation_assay",
        "project_id": project, "context": {"target_gene": "BRD4", "e3_ligase": "VHL"},
        "observed": {"dmax": 0.2},
    })
    assert result["episode_id"]
    search = registry.call("cog_search", {"query": "MCP encode", "project_id": project})
    assert search["results"]


def test_mcp_server_protocol(mem, project):
    server = McpServer(mem)
    init = server.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    assert init["result"]["serverInfo"]["name"] == "protacpilot-memory"
    notification = server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"})
    assert notification is None
    listing = server.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    names = {t["name"] for t in listing["result"]["tools"]}
    assert "cog_search" in names
    call = server.handle({
        "jsonrpc": "2.0", "id": 3, "method": "tools/call",
        "params": {"name": "cog_stats", "arguments": {}},
    })
    assert call["result"]["isError"] is False
    payload = json.loads(call["result"]["content"][0]["text"])
    assert "total_memories" in payload
    missing = server.handle({
        "jsonrpc": "2.0", "id": 4, "method": "tools/call",
        "params": {"name": "cog_missing", "arguments": {}},
    })
    assert missing["error"]["code"] == -32601
    unknown = server.handle({"jsonrpc": "2.0", "id": 5, "method": "nope", "params": {}})
    assert unknown["error"]["code"] == -32601


def test_mcp_stdio_framing(mem, project):
    import io

    messages = (
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}) + "\n"
        + json.dumps({"jsonrpc": "2.0", "id": 2, "method": "ping", "params": {}}) + "\n"
    )
    out = io.StringIO()
    McpServer(mem).serve(instream=io.StringIO(messages), outstream=out)
    lines = [json.loads(line) for line in out.getvalue().strip().splitlines()]
    assert len(lines) == 2
    assert lines[1]["result"] == {}


def test_cli_smoke(tmp_path):
    db = tmp_path / "cli.db"
    assert cli_main(["--db", str(db), "init"]) == 0
    assert cli_main(["--db", str(db), "stats"]) == 0
    assert cli_main(["--db", str(db), "project", "--name", "cli-project"]) == 0
    assert cli_main([
        "--db", str(db), "--project", "cli-project", "encode",
        "--title", "CLI episode", "--content", "dmax 0.2",
        "--event-type", "degradation_assay",
        "--context", '{"target_gene": "BRD4", "e3_ligase": "VHL"}',
        "--observed", '{"dmax": 0.2}',
    ]) == 0
    assert cli_main(["--db", str(db), "--project", "cli-project", "search", "CLI episode"]) == 0
    assert cli_main(["--db", str(db), "--project", "cli-project", "audit"]) == 0


def test_http_coerce_search_response(mem, project):
    mem.save_episode(
        title="http episode", content="dmax 0.2", event_type="degradation_assay",
        project_id=project, context={"target_gene": "BRD4"}, observed={"dmax": 0.2},
        decision_impact=0.9,
    )
    response = mem.search("http episode", project_id=project)
    payload = _coerce(response)
    assert payload["results"]
    assert payload["results"][0]["id"]
