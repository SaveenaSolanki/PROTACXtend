"""Shared pytest fixtures for protacpilot-memory tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (str(SRC), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from protacpilot_memory import CognitiveMemory  # noqa: E402


@pytest.fixture
def mem():
    memory = CognitiveMemory.in_memory()
    yield memory
    memory.close()


@pytest.fixture
def project(mem):
    return mem.ensure_project("test-project")


@pytest.fixture
def session(mem, project):
    return mem.start_session(project, goal="Improve permeability while retaining degradation")
