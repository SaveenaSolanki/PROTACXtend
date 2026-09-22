"""Universal install + LLM setup tests.

Covers: setup wizard (API / Local / Configure later), provider list/current,
neutral auth (no hard-coded default provider), env-over-saved resolution,
`doctor` six checks, first-run auto-setup, and result metadata (provider /
model / version / run id / runtime / tools) without secret leakage.

Network: cloud inference is never probed. Localhost OpenAI-compatible mock
server provides the only real HTTP auth+inference path (see mock_llm_server).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
sys.path.insert(0, str(ROOT / "scripts"))


def run_cli(*argv: str, cwd: Path = ROOT, env_extra: dict | None = None,
            inp: str = "") -> subprocess.CompletedProcess:
    env = {**os.environ, **(env_extra or {})}
    env.pop("CI", None)
    env.pop("PROTACXTEND_SKIP_SETUP", None)
    env["PROTACXTEND_SETUP_HANDLED"] = "0"
    return subprocess.run([str(ROOT / "PROTACXtend"), *argv], cwd=cwd,
                          input=inp, env=env, text=True, capture_output=True,
                          timeout=180)


def tmp_home(tmp_path: Path) -> dict:
    home = tmp_path / "home"
    home.mkdir()
    return {"PROTACXTEND_HOME": str(home)}


class MockLLMServer:
    """Threaded OpenAI-compatible mock with optional bearer-token auth."""

    def __init__(self, required_key: str = "sk-mock-test", model: str = "mock-probe-model"):
        import importlib
        from http.server import ThreadingHTTPServer
        # set env BEFORE the module import: Handler captures REQUIRED_KEY once
        # at class-definition time.
        for k, v in (("REQUIRED_KEY", required_key), ("MOCK_MODEL", model)):
            os.environ[k] = v
        mod = importlib.import_module("mock_llm_server")
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), mod.Handler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def start(self) -> "MockLLMServer":
        self.thread.start()
        for _ in range(50):
            try:
                import requests
                requests.get(f"http://127.0.0.1:{self.port}/health", timeout=1)
                return self
            except Exception:
                time.sleep(0.05)
        raise RuntimeError("mock server failed to start")

    def stop(self) -> None:
        self.server.shutdown()


@pytest.fixture()
def mock_server():
    srv = MockLLMServer().start()
    yield f"http://127.0.0.1:{srv.port}/v1"
    srv.stop()


# ── provider list / current ────────────────────────────────────────────

def test_provider_list_and_current_neutral(tmp_path):
    env = tmp_home(tmp_path)
    r = run_cli("provider", "list", env_extra=env)
    assert r.returncode == 0, r.stderr
    assert "deepseek" in r.stdout and "ollama" in r.stdout and "openai" in r.stdout
    assert "(none)" in r.stdout
    r = run_cli("provider", "current", "--json", env_extra=env)
    assert json.loads(r.stdout)["configured"] is False


def test_provider_list_json_shape(tmp_path):
    env = tmp_home(tmp_path)
    r = run_cli("provider", "list", "--json", env_extra=env)
    payload = json.loads(r.stdout)
    ids = {p["provider"] for p in payload["providers"]}
    assert {"deepseek", "ollama", "openai", "anthropic", "google", "openrouter",
            "openai_compatible"} <= ids
    assert payload["current"] in ("(none)", "")


def test_auth_status_is_neutral_without_config(tmp_path):
    env = tmp_home(tmp_path)
    r = run_cli("auth", "status", "--json", env_extra=env)
    assert r.returncode == 0, r.stderr
    payload = json.loads(r.stdout)
    assert payload["auth"]["authenticated"] is False
    assert "deepseek" not in payload["auth"]["provider"].lower()  # no fake default


def test_auth_login_requires_provider(tmp_path):
    env = tmp_home(tmp_path)
    r = run_cli("auth", "login", "--key-stdin", env_extra=env, inp="sk-x\n")
    assert r.returncode == 1
    assert "provider required" in (r.stdout + r.stderr)


# ── setup wizard: configure later / local (unit, no machine deps) ─────

def _patch_home(monkeypatch, tmp_path) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    from protacxtend.llm import providers as p
    from protacxtend.llm import manager as m
    monkeypatch.setattr(p, "USER_CONFIG_PATH", home / "llm.json")
    monkeypatch.setattr(m, "USER_CONFIG_PATH", home / "llm.json")
    monkeypatch.setattr(m, "VERIFY_PATH", home / "verified.json")
    monkeypatch.setattr(p, "_runtime_config", None)
    return home


def test_wizard_configure_later_writes_nothing(monkeypatch, tmp_path):
    _patch_home(monkeypatch, tmp_path)
    from protacxtend.llm import setup_wizard
    calls = {"ask": [], "out": []}

    def ask(prompt):
        calls["ask"].append(prompt)
        return "3"

    def out(msg):
        calls["out"].append(msg)

    res = setup_wizard.run_setup(ask=ask, out=out)
    assert res["mode"] == "later"
    assert not res["ok"]
    assert not (tmp_path / "home" / "llm.json").exists()


def test_wizard_local_selects_existing_model(monkeypatch, tmp_path):
    home = _patch_home(monkeypatch, tmp_path)
    from protacxtend.llm import setup_wizard, manager
    answers = iter(["2", "2"])  # local → model number 2

    def ask(prompt):
        return next(answers)

    def out(msg):
        pass

    monkeypatch.setattr(setup_wizard, "_detect_ollama",
                        lambda: {"ok": True, "base_url": "http://127.0.0.1:11434",
                                 "models": ["llama3:8b", "deepseek-r1:7b"], "binary": True})
    monkeypatch.setattr(manager, "probe_inference",
                        lambda *a, **k: {"ok": True, "detail": "replied", "elapsed_s": 0.1})
    monkeypatch.setattr(manager, "save_config", lambda cfg: home / "llm.json")
    res = setup_wizard.run_setup(ask=ask, out=out)
    assert res["ok"] and res["provider"] == "ollama"
    assert res["model"] == "deepseek-r1:7b"
    assert res["verified"] is True


def test_wizard_local_never_pulls_without_confirmation(monkeypatch, tmp_path):
    _patch_home(monkeypatch, tmp_path)
    from protacxtend.llm import setup_wizard
    answers = iter(["2", "llama3.2:1b", "n"])  # local, empty models, decline pull

    def ask(prompt):
        return next(answers)

    pulled = []
    monkeypatch.setattr(setup_wizard, "_detect_ollama",
                        lambda: {"ok": False, "base_url": "http://127.0.0.1:11434",
                                 "models": [], "error": "down"})

    # fake `shutil.which` → ollama binary present (installed but nothing pulled)
    real_import = __import__

    def patched_import(name, *args, **kwargs):
        if name == "shutil":
            class _S:
                @staticmethod
                def which(nm):
                    return "/usr/local/bin/ollama" if nm == "ollama" else None
            return _S()
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", patched_import)
    import subprocess as sp

    def fake_run(*a, **k):
        pulled.append(a)
        return type("R", (), {"returncode": 1, "stderr": "x"})()
    monkeypatch.setattr(sp, "run", fake_run)

    res = setup_wizard.run_setup(ask=ask, out=lambda m: None)
    assert pulled == []            # nothing downloaded without confirmation
    assert not res["ok"]


# ── setup wizard API mode against the localhost mock (real HTTP) ───────

def test_wizard_api_mode_live_mock(monkeypatch, tmp_path, mock_server):
    home = _patch_home(monkeypatch, tmp_path)
    from protacxtend.llm import setup_wizard
    answers = iter(["1", "5", f"{mock_server}", "mock-probe-model", "sk-mock-test"])

    def ask(prompt):
        return next(answers)

    out_lines = []
    res = setup_wizard.run_setup(ask=ask, out=out_lines.append)
    assert res["ok"], out_lines
    assert res["provider"] == "openai_compatible"
    assert res["model"] == "mock-probe-model"
    assert res["verified"] is True
    saved = json.loads((home / "llm.json").read_text())
    assert saved["api_key"] == "sk-mock-test"
    assert oct((home / "llm.json").stat().st_mode & 0o777) == "0o600"
    # verification record has no secrets
    verified = json.loads((home / "verified.json").read_text())
    blob = json.dumps(verified)
    assert "sk-mock-test" not in blob and "api_key" not in blob


def test_doctor_ready_against_live_mock(monkeypatch, tmp_path, mock_server):
    home = _patch_home(monkeypatch, tmp_path)
    from protacxtend.llm import manager, setup_wizard
    from protacxtend.llm.providers import ProviderConfig
    cfg = ProviderConfig(provider="openai_compatible", model="mock-probe-model",
                         base_url=mock_server, api_key="sk-mock-test")
    manager.save_config(cfg)
    manager.record_verification({"provider": cfg.provider, "model": cfg.model,
                                 "base_url": cfg.base_url,
                                 "connection_ok": True, "inference_ok": True})
    checks = manager.runtime_checks(live=True)
    assert checks["provider"] == "openai_compatible"
    assert checks["auth"]["ok"] is True
    assert checks["connection"]["ok"] is True
    assert checks["inference"]["ok"] is True
    assert checks["status"] == "READY"
    assert checks["verified"] is True


def test_doctor_connection_fails_with_wrong_key(monkeypatch, tmp_path, mock_server):
    home = _patch_home(monkeypatch, tmp_path)
    from protacxtend.llm import manager
    from protacxtend.llm.providers import ProviderConfig
    cfg = ProviderConfig(provider="openai_compatible", model="mock-probe-model",
                         base_url=mock_server, api_key="sk-WRONG")
    manager.save_config(cfg)
    checks = manager.runtime_checks(live=True)
    assert checks["connection"]["ok"] is False
    assert checks["status"] == "NOT READY"


def test_doctor_cli_output_shape(tmp_path, mock_server):
    env = tmp_home(tmp_path)
    home = Path(env["PROTACXTEND_HOME"])
    cfg = {"provider": "openai_compatible", "model": "mock-probe-model",
           "base_url": mock_server, "api_key": "sk-mock-test",
           "num_ctx": 16384, "temperature": 0.0, "timeout_s": 300}
    (home / "llm.json").write_text(json.dumps(cfg))
    os.chmod(home / "llm.json", 0o600)
    r = run_cli("doctor", env_extra=env)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "Provider     openai_compatible" in r.stdout
    assert r.stdout.count("PASS") >= 3
    assert "Status       READY" in r.stdout


# ── env overrides saved config ─────────────────────────────────────────

def test_environment_overrides_saved_config(tmp_path):
    env = tmp_home(tmp_path)
    r = run_cli("auth", "login", "--provider", "deepseek", "--model", "deepseek-chat",
                "--key-stdin", env_extra=env, inp="sk-envtest\n")
    assert r.returncode == 0
    env2 = {**env, "PROTACPILOT_LLM_PROVIDER": "ollama", "PROTACPILOT_LLM_MODEL": "llama3"}
    r = run_cli("provider", "current", "--json", env_extra=env2)
    payload = json.loads(r.stdout)
    assert payload["provider"] == "ollama"
    assert payload["model"] == "llama3"
    assert payload["source"] == "env"


# ── first run auto-opens setup ─────────────────────────────────────────

def test_first_run_opens_setup_when_no_provider(tmp_path):
    env = tmp_home(tmp_path)
    r = run_cli(inp="3\n", env_extra=env)          # bare PROTACXtend, no provider
    assert "First run" in r.stdout or "setup" in r.stdout.lower()
    assert "configure later" in r.stdout.lower()


# ── result metadata (no secrets) ───────────────────────────────────────

def test_run_record_metadata_records_runtime_envelope(tmp_path):
    from protacxtend.run_records import build_agent_run_record, scrub_secrets, runtime_metadata
    meta = runtime_metadata("run_abc123", 12.5)
    assert meta["provider"] in ("(none)", "") or isinstance(meta["provider"], str)
    assert meta["run_id"] == "run_abc123"
    assert meta["runtime_s"] == 12.5
    assert "protacxtend_version" in meta
    assert isinstance(meta["tools_enabled"], list)
    assert isinstance(meta["tools_disabled"], list)
    blob = json.dumps(meta)
    assert "api_key" not in blob and "secret" not in blob

    state = {
        "decision_log": [], "workflow_log": [],
        "valid_candidates": [], "final_ranked_candidates": [], "ranking_results": [],
        "warnings": [], "errors": [], "parsed_objective": {},
    }
    rec = build_agent_run_record({"state": state}, "run_abc123", "probe", 12.5)
    assert rec.metadata["provider"]
    assert rec.metadata["run_id"] == "run_abc123"
    rec.metadata = scrub_secrets({**rec.metadata, "api_key": "sk-secret", "token": "t"})
    assert "sk-secret" not in json.dumps(rec.metadata)


def test_result_json_writer_adds_version_no_keys(tmp_path):
    from protacxtend.results.io import write_result_json, read_result_json
    from protacxtend.results.schema import ScientificResult
    path = tmp_path / "result.json"
    r = ScientificResult(workflow="smoke", summary="ok", provider="deepseek",
                         model="deepseek-chat")
    write_result_json(path, r, metadata={"request": "x"})
    d = read_result_json(path).to_dict()
    assert d["metadata"]["protacxtend_version"]
    assert "api_key" not in json.dumps(d)


# ── auth/model/status CLI helpers ──────────────────────────────────────

def test_model_list_works_without_provider(tmp_path):
    env = tmp_home(tmp_path)
    r = run_cli("model", "list", "--json", env_extra=env)
    payload = json.loads(r.stdout)
    assert len(payload["models"]) >= 1
    assert any("deepseek" in m for m in payload["models"])
