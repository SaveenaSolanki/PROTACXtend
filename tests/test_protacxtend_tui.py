"""Tests for the PROTACXtend Feynman-style TUI module."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_tui_module_imports():
    """TUI module loads cleanly with all public symbols."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from synglue_agent.tui.app import (\n"
                "    PROTACXtendTUI, AGENT_PIPELINE, launch_tui,\n"
                "    _detect_llm_config, _detect_chemistry_env, _detect_project_info,\n"
                ")\n"
                "assert len(AGENT_PIPELINE) == 23\n"
                "assert all('id' in a and 'name' in a and 'icon' in a for a in AGENT_PIPELINE)\n"
                "assert callable(launch_tui)\n"
                "print('OK')"
            ),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    assert "OK" in result.stdout


def test_tui_agent_pipeline_matches_architecture():
    """The 23-agent pipeline matches the documented architecture."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from synglue_agent.tui.app import AGENT_PIPELINE\n"
                "ids = [a['id'] for a in AGENT_PIPELINE]\n"
                "# Core pipeline nodes from the 23-node architecture\n"
                "required = [\n"
                "    'supervisor', 'planner', 'safety', 'target_resolver',\n"
                "    'binder_retrieval', 'warhead_selection', 'e3_selection',\n"
                "    'exit_vector_detection', 'linker_generation', 'construction',\n"
                "    'validation', 'ternary_feasibility', 'degradation_prediction',\n"
                "    'admet_prediction', 'novelty_check', 'report',\n"
                "]\n"
                "for node in required:\n"
                "    assert node in ids, f'Missing: {node}'\n"
                "print('OK')"
            ),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    assert "OK" in result.stdout


def test_tui_detect_llm_config_returns_dict():
    """LLM config detection returns a dict with expected keys."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from synglue_agent.tui.app import _detect_llm_config\n"
                "cfg = _detect_llm_config()\n"
                "assert isinstance(cfg, dict)\n"
                "assert 'provider' in cfg\n"
                "assert 'model' in cfg\n"
                "assert 'base_url' in cfg\n"
                "assert 'healthy' in cfg\n"
                "print('OK')"
            ),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    assert "OK" in result.stdout


def test_tui_detect_chemistry_env():
    """Chemistry environment detection returns status for key packages."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from synglue_agent.tui.app import _detect_chemistry_env\n"
                "env = _detect_chemistry_env()\n"
                "assert isinstance(env, dict)\n"
                "for pkg in ['pandas', 'numpy', 'rdkit']:\n"
                "    assert pkg in env, f'Missing: {pkg}'\n"
                "    assert 'installed' in env[pkg]\n"
                "    assert 'version' in env[pkg]\n"
                "print('OK')"
            ),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    assert "OK" in result.stdout


def test_tui_detect_project_info():
    """Project info detection returns expected fields."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from synglue_agent.tui.app import _detect_project_info\n"
                "info = _detect_project_info()\n"
                "assert isinstance(info, dict)\n"
                "assert 'project_root' in info\n"
                "assert 'data_dir' in info\n"
                "assert 'output_dir' in info\n"
                "assert 'data_files' in info\n"
                "assert 'output_runs' in info\n"
                "print('OK')"
            ),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    assert "OK" in result.stdout


def test_cli_tui_subcommand_exists():
    """The tui subcommand is recognized by the CLI parser."""
    result = subprocess.run(
        [sys.executable, "-m", "synglue_agent.cli", "tui", "--help"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    assert "Optional design request" in result.stdout


def test_cli_help_includes_tui():
    """CLI help output mentions the tui subcommand."""
    result = subprocess.run(
        [sys.executable, "-m", "synglue_agent.cli", "--help"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    assert "tui" in result.stdout.lower()


def test_cli_capabilities_includes_tui():
    """CLI capabilities list includes the Feynman-style TUI capability."""
    result = subprocess.run(
        [sys.executable, "-m", "synglue_agent.cli", "capabilities", "--json"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    import json
    payload = json.loads(result.stdout)
    names = [item["name"] for item in payload["capabilities"]]
    assert "Feynman-style TUI" in names


def test_cli_scenarios_includes_tui():
    """CLI scenarios list includes the tui scenario."""
    result = subprocess.run(
        [sys.executable, "-m", "synglue_agent.cli", "scenarios", "--json"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    import json
    payload = json.loads(result.stdout)
    names = [item["name"] for item in payload["scenarios"]]
    assert "tui" in names


def test_tui_app_class_composes():
    """The PROTACXtendTUI app class can be instantiated without error."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from synglue_agent.tui.app import PROTACXtendTUI\n"
                "app = PROTACXtendTUI()\n"
                "assert app is not None\n"
                "assert app.TITLE == 'PROTACXtend'\n"
                "assert len(app.BINDINGS) >= 4\n"
                "print('OK')"
            ),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    assert "OK" in result.stdout


def test_tui_styles_css_exists():
    """The Textual CSS file exists and is valid."""
    css_path = ROOT / "synglue_agent" / "tui" / "styles.tcss"
    assert css_path.exists(), f"CSS file missing: {css_path}"
    content = css_path.read_text()
    assert "#header" in content
    assert "#sidebar" in content
    assert "#workflow-panel" in content
    assert "#model-panel" in content


def test_tui_wrapper_script_works():
    """The shell wrapper script launches the TUI module."""
    wrapper = ROOT / "protacxtend"
    result = subprocess.run(
        [str(wrapper), "tui", "--help"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    assert "Optional design request" in result.stdout
