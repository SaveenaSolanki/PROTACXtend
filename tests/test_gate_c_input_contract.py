"""Gate C regression — scientific-input contract for ``generate_linkers``.

Gate C scope-lock finding: ``run_agent_tool("generate_linkers", {})`` in
SCIENTIFIC mode generated linker hypotheses with no declared warhead/E3
conjugation partners. That is a hidden scientific input. The contract now
requires both partners, exactly like ``construct_protac``.

Fast/offline: the negative path raises before any generation runs.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from protacxtend.runtime import modes  # noqa: E402


def test_generate_linkers_requires_both_partners_in_mapping():
    required = modes.SCIENTIFIC_REQUIRED_INPUTS.get("generate_linkers")
    assert required is not None, "generate_linkers must declare scientific inputs"
    assert set(required) == {"warhead_smiles", "e3_smiles"}


def test_validate_scientific_params_rejects_empty_generate_linkers():
    with pytest.raises(modes.MissingScientificInput) as exc:
        modes.validate_scientific_params(
            "agent tool 'generate_linkers'", {},
            modes.SCIENTIFIC_REQUIRED_INPUTS["generate_linkers"],
        )
    assert exc.value.code is modes.FailureCode.MISSING_SCIENTIFIC_INPUT


def test_validate_scientific_params_accepts_partner_pair():
    # Must not raise once both partners are declared.
    modes.validate_scientific_params(
        "agent tool 'generate_linkers'",
        {"warhead_smiles": "COc1cc2c(cc1c1c(C)onc1C)cc(c(=O)n2Cc1ccccn1)",
         "e3_smiles": "N[C@@H](C(C)(C)C)C(=O)N1C[C@@H](C[C@H]1C(=O)N[C@H](c1ccc(cc1)c1scnc1C)C)O"},
        modes.SCIENTIFIC_REQUIRED_INPUTS["generate_linkers"],
    )


def test_run_agent_tool_generate_linkers_empty_is_typed_failure():
    from protacxtend.runtime.agent_tools import run_agent_tool

    with modes.execution_mode("scientific"):
        with pytest.raises(modes.MissingScientificInput):
            run_agent_tool("generate_linkers", {})
