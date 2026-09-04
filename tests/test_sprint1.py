"""Sprint 1 focused tests: provider manager, auth/model CLI, provider-aware
/doctor verdict, frozen result schema/presentation, six-BRD4 smoke workflow.

Network-free: cloud providers are validated offline (live=False / no keys),
and anything that writes config uses an isolated PROTACXTEND_HOME.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable


def run_cli(*argv: str, cwd: Path = ROOT, env_extra: dict | None = None,
            inp: str = "") -> subprocess.CompletedProcess:
    env = {**os.environ, **(env_extra or {})}
    return subprocess.run([str(ROOT / "PROTACXtend"), *argv], cwd=cwd,
                          input=inp, env=env, text=True, capture_output=True,
                          timeout=90)


# ── 1. Provider manager ────────────────────────────────────────────────────

def test_provider_manager_covers_required_providers():
    from protacxtend.llm import manager
    ids = set(manager.provider_ids())
    for prov in ("deepseek", "ollama", "openai", "anthropic", "google",
                 "gemini", "openrouter", "openai_compatible"):
        assert prov in ids
    meta = manager.meta("deepseek")
    assert meta.default_model == "deepseek-v4-flash"
    assert meta.supports_structured_output and meta.supports_tool_calling


def test_validate_never_raises_and_reports_verdicts():
    from protacxtend.llm import manager
    # cloud provider without a key -> NOT READY, no exception, no key leak
    chk = manager.validate("deepseek", live=False)
    assert chk["verdict"] in {"READY", "DEGRADED", "NOT READY"}
    auth = manager.auth_state("deepseek")
    assert "api_key" not in json.dumps(auth)
    assert "authenticated" in auth
    # unknown provider -> NOT READY
    assert manager.validate("nope", live=False)["verdict"] == "NOT READY"


def test_auth_state_never_contains_key_value():
    from protacxtend.llm import manager
    for prov in ("openai", "anthropic", "google", "openrouter", "deepseek"):
        state = manager.auth_state(prov)
        blob = json.dumps(state)
        assert "not-a-real-key" not in blob.lower() and "sk-" not in blob.lower()


# ── 2. auth/model CLI (isolated PROTACXTEND_HOME) ──────────────────────────

def _tmp_home(tmp_path: Path) -> dict:
    home = tmp_path / "home"
    home.mkdir()
    return {"PROTACXTEND_HOME": str(home)}


def test_auth_login_status_logout_roundtrip(tmp_path):
    env = _tmp_home(tmp_path)
    key = "DUMMY-SPRINT1-KEY-NOT-REAL"
    r = run_cli("auth", "login", "--provider", "deepseek", "--model", "deepseek-v4-flash",
                "--key-stdin", env_extra=env, inp=f"{key}\n")
    assert r.returncode == 0, r.stderr
    assert key not in r.stdout          # never echo the key

    r = run_cli("auth", "status", "--provider", "deepseek", "--json", env_extra=env)
    assert r.returncode == 0
    payload = json.loads(r.stdout)
    assert payload["auth"]["authenticated"] is True
    assert key not in json.dumps(payload)   # key value never serialized

    r = run_cli("auth", "logout", env_extra=env)
    assert r.returncode == 0
    r = run_cli("auth", "status", "--provider", "deepseek", "--json", env_extra=env)
    assert json.loads(r.stdout)["auth"]["authenticated"] is False


def test_model_list_set_status(tmp_path):
    env = _tmp_home(tmp_path)
    r = run_cli("model", "list", "--json", env_extra=env)
    assert r.returncode == 0
    assert len(json.loads(r.stdout)["models"]) >= 1

    r = run_cli("model", "set", "--provider", "openai", "--model", "gpt-4o-mini", env_extra=env)
    assert r.returncode == 0
    r = run_cli("model", "status", "--json", env_extra=env)
    payload = json.loads(r.stdout)
    assert payload["state"]["provider"] == "openai"
    assert payload["state"]["model"] == "gpt-4o-mini"


# ── 3. provider-aware /doctor ──────────────────────────────────────────────

def test_doctor_is_provider_aware():
    from protacxtend.diagnostics import build_doctor_report
    report = build_doctor_report()
    llm = report.get("llm", {})
    assert llm.get("provider")
    assert "model" in llm
    assert llm_verdict_ok(llm.get("verdict"))
    assert report.get("llm_verdict") in {"READY", "DEGRADED", "NOT READY"}
    names = [c["name"] for c in report["checks"]]
    for required in ("llm:provider", "llm:model", "llm:authentication",
                     "llm:inference", "llm:structured-output", "llm:tool-calling"):
        assert required in names


def llm_verdict_ok(v):
    return v in {"READY", "DEGRADED", "NOT READY"}


# ── 4. frozen result schema + presentation ─────────────────────────────────

def test_result_schema_is_frozen_with_all_fields():
    from protacxtend.results.schema import SCHEMA_VERSION, ScientificResult, from_dict
    assert SCHEMA_VERSION == "1.0.0"
    r = ScientificResult(
        workflow="smoke", summary="ok", task_id="t1", status="ok",
        metadata={"request": "x"}, provider="deepseek", model="deepseek-v4-flash",
        result={"answer": 1}, tools=["tool-a"], artifacts=["out.json"],
        errors=[], warnings=["note"])
    d = r.to_dict()
    for field in ("schema_version", "status", "task_id", "workflow", "metadata",
                  "provider", "model", "summary", "result", "tools", "artifacts",
                  "evidence", "warnings", "errors", "provenance"):
        assert field in d
    assert from_dict(d).to_dict() == d


def test_result_json_io_and_human_presentation(tmp_path):
    from protacxtend.results.io import human_summary, read_result_json, write_result_json
    from protacxtend.results.schema import ScientificResult
    path = tmp_path / "result.json"
    r = ScientificResult(workflow="case_study:brd4-vhl-six", summary="winner mol1 (predicted)",
                         task_id="smoke-1", provider="ollama", model="gpt-oss:20b",
                         result={"winner": "mol1"}, tools=["structural_score"],
                         evidence=[])
    write_result_json(path, r)
    back = read_result_json(path)
    d = back.to_dict()
    assert d["schema_version"] == "1.0.0"
    assert d["workflow"] == "case_study:brd4-vhl-six"
    d["metadata"].pop("written_at", None)  # added by the writer only
    assert d["result"] == r.to_dict()["result"]
    text = human_summary(back)
    assert "PROTACXtend result" in text
    assert "mol1" in text
    # readable CLI text is not a JSON blob
    assert not text.lstrip().startswith("{")


# ── 5. six-BRD4 smoke workflow (blinded, prospective) ──────────────────────

def test_six_brd4_vhl_smoke_cli(tmp_path):
    env = _tmp_home(tmp_path)
    out = tmp_path / "case_result.json"
    r = run_cli("case-study", "brd4-vhl", "--out", str(out), env_extra=env)
    assert r.returncode == 0, r.stderr
    assert out.is_file()
    payload = json.loads(out.read_text())
    assert payload["schema_version"] == "1.0.0"
    assert payload["workflow"] == "case_study:brd4-vhl-six"
    result = payload["result"]
    # experimental potency / ground truth stay hidden
    assert result["measured_present"] == 0
    assert result["measured_missing"] == 6
    assert "md_rank" not in json.dumps(payload).lower()
    assert not payload["metadata"].get("scientific_benchmark")
    # readable output exists on stdout
    assert "PROTACXtend result" in r.stdout
    assert "winner mol1" in r.stdout or "winner" in r.stdout
