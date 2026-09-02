import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_cli_help_runs():
    result = subprocess.run(
        [sys.executable, "-m", "synglue_agent.cli", "--help"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "PROTACXtend command-line workspace" in result.stdout
    assert "validate" in result.stdout
    assert "ui" in result.stdout
    assert "api" in result.stdout


def test_cli_status_reports_frontend_and_api():
    result = subprocess.run(
        [sys.executable, "-m", "synglue_agent.cli", "status", "--json"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    payload = json.loads(result.stdout)
    assert payload["name"] == "PROTACXtend"
    assert payload["frontend"]["command"] == "PROTACXtend ui"
    assert payload["api"]["command"] == "PROTACXtend api"


def test_repo_local_uppercase_wrapper_runs():
    result = subprocess.run(
        [str(ROOT / "PROTACXtend"), "--version"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    assert result.stdout.strip().startswith("PROTACXtend ")


def test_repo_local_lowercase_wrapper_runs():
    result = subprocess.run(
        [str(ROOT / "protacxtend"), "--version"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    assert result.stdout.strip().startswith("PROTACXtend ")


def test_interactive_backslash_workflow_shortcut():
    result = subprocess.run(
        [str(ROOT / "protacxtend")],
        cwd=ROOT,
        input="\\evidence BRD4 CRBN PROTAC evidence\n\\exit\n",
        text=True,
        capture_output=True,
        check=True,
    )

    assert '"command": "/evidence"' in result.stdout
    assert "PROTAC-DB" in result.stdout


def test_cli_print_mode_estimates_design_runtime():
    result = subprocess.run(
        [str(ROOT / "PROTACXtend"), "-p", "Design CRBN PROTACs for BRD4 degradation"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    payload = json.loads(result.stdout)
    assert payload["mode"] == "agentic"
    assert payload["estimated_runtime"]
    assert "workflow" in payload


def test_cli_scenarios_lists_common_commands():
    result = subprocess.run(
        [str(ROOT / "PROTACXtend"), "scenarios", "--json"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    payload = json.loads(result.stdout)
    commands = [item["command"] for item in payload["scenarios"]]
    names = [item["name"] for item in payload["scenarios"]]
    assert "PROTACXtend status" in commands
    assert any(command.startswith("PROTACXtend -p") for command in commands)
    assert "full_design" in names


def test_cli_capabilities_json_lists_terminal_interface():
    result = subprocess.run(
        [str(ROOT / "PROTACXtend"), "capabilities", "--json"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    payload = json.loads(result.stdout)
    names = [item["name"] for item in payload["capabilities"]]
    assert "Interactive terminal interface" in names
    assert "Print/plan mode" in names


def test_cli_contract_static_summary_exposes_scientific_contract():
    result = subprocess.run(
        [str(ROOT / "protacxtend"), "contract", "--section", "actions"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    payload = json.loads(result.stdout)
    assert payload["mode"] == "contract"
    assert payload["section"] == "actions"
    assert any(action["action_id"] == "reason.dynamic_action_selection" for action in payload["actions"])
    assert all("usable_in_paper_run" in gate for gate in payload["quality_gates"])


def test_cli_contract_models_lists_external_method_gates():
    result = subprocess.run(
        [str(ROOT / "protacxtend"), "contract", "--section", "models"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    payload = json.loads(result.stdout)
    names = [item["name"] for item in payload["external_method_registry"]]
    assert "PROTAC-Degradation-Predictor" in names
    assert "PROTACFold" in names
