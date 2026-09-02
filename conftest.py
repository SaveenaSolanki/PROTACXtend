"""pytest configuration for PROTACPilot tests."""

import os
from pathlib import Path


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "p4ward: tests requiring P4ward wrapper")
    config.addinivalue_line("markers", "slow: tests that take >30 seconds")
    config.addinivalue_line("markers", "docker: tests that require Docker")
    config.addinivalue_line("markers", "integration: end-to-end integration tests")


def pytest_addoption(parser):
    """Add custom CLI options."""
    parser.addoption(
        "--run-p4ward",
        action="store_true",
        default=False,
        help="Run P4ward integration tests (requires Docker image)",
    )
