"""
Strict tool registry (A6 / capability 3) — exactly as specified:

  "The model may select a tool, but it may never construct an arbitrary
   function name or execute arbitrary code."
"""

from __future__ import annotations

from typing import Iterable, Set

# The ONLY tools the LLM may reference. Anything else is rejected.
ALLOWED_TOOLS: Set[str] = {
    "search_uniprot",
    "search_chembl",
    "search_bindingdb",
    "retrieve_pdb",
    "retrieve_alphafold",
    "validate_smiles",
    "enumerate_exit_vectors",
    "generate_linkers",
    "assemble_protac",
    "run_p4ward",
    "predict_degradation",
    "evaluate_adme",
    "run_retrosynthesis",
}

# Tools that are expensive or require human approval — the LLM may request
# them, but the gate must pause for human review before execution.
EXPENSIVE_TOOLS: Set[str] = {"run_p4ward", "run_retrosynthesis"}


def validate_selected_tools(selected: Iterable[str]) -> None:
    """Raise ValueError if any selected tool is outside the registry."""
    invalid = set(selected) - ALLOWED_TOOLS
    if invalid:
        raise ValueError(f"Unsupported tools selected: {sorted(invalid)}")


def requires_human_approval(selected: Iterable[str]) -> bool:
    return bool(set(selected) & EXPENSIVE_TOOLS)


def validate_reason_codes(reason_codes: Iterable[str]) -> None:
    """Reason codes must be from the controlled vocabulary (state.ReasonCode)."""
    from synglue_agent.agents.state import ReasonCode

    valid = {r.value for r in ReasonCode}
    # Allow stage-specific codes beyond the core vocabulary (prefixes), but
    # reject free-text tokens.
    bad = [rc for rc in reason_codes
           if not isinstance(rc, str) or len(rc) > 48 or not rc.replace("_", "").isalnum()]
    if bad:
        raise ValueError(f"Malformed reason codes: {bad}")
