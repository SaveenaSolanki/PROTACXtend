"""Explicit execution modes and scientific-input guardrails.

PROTACXtend historically ran agent tools with hard-coded *probe fixtures*
(``smiles="CCO"``, a synthetic ternary pose, demo warheads).  That made tools
"work" in production and benchmark runs even when no real scientific input was
supplied, which is scientifically meaningless and makes execution success a
false signal.

This module introduces three explicit modes:

``DEMO``
    Interactive exploration.  Fixtures and curated demo fallbacks are allowed
    and are clearly labelled.

``TEST``
    Deterministic test/fixture runs.  Fixtures are allowed (the caller opts in)
    but results are marked as fixture-only.

``SCIENTIFIC``
    Production / benchmark execution.  Fixtures, placeholder SMILES, synthetic
    structures and demo fallbacks are forbidden.  Missing inputs raise rather
    than being silently substituted.

The active mode is held in a :class:`contextvars.ContextVar` so it is
thread- and async-safe, and can be set globally with the
``PROTACXTEND_EXECUTION_MODE`` environment variable.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from contextvars import ContextVar, Token
from enum import Enum
from typing import Any, Iterable, Mapping, Sequence

__all__ = [
    "ExecutionMode",
    "InputOrigin",
    "FailureCode",
    "ScientificInputError",
    "FixtureUsageError",
    "SyntheticInputNotAllowed",
    "MissingScientificInput",
    "SCIENTIFIC_REQUIRED_INPUTS",
    "parse_mode",
    "get_execution_mode",
    "set_execution_mode",
    "reset_execution_mode",
    "execution_mode",
    "is_scientific",
    "resolve_use_fixture",
    "validate_scientific_params",
    "reject_fixture",
    "classify_input_origin",
    "is_placeholder_smiles",
    "is_synthetic_artifact",
    "is_demo_source",
    "filter_scientific_rows",
    "scan_scientific_payload",
    "assert_scientific_payload_clean",
    "DEMO_SOURCE_PREFIXES",
]


# ---------------------------------------------------------------------------
# Modes
# ---------------------------------------------------------------------------
class ExecutionMode(str, Enum):
    DEMO = "demo"
    TEST = "test"
    SCIENTIFIC = "scientific"


class InputOrigin(str, Enum):
    """Provenance of a scientific input to a tool call."""
    USER = "USER"              # supplied by the caller / user request
    RETRIEVED = "RETRIEVED"    # fetched from a database / API / literature
    GENERATED = "GENERATED"    # produced by a generative model
    COMPUTED = "COMPUTED"      # derived deterministically from other inputs
    FIXTURE = "FIXTURE"        # bundled probe/demo fixture
    SYNTHETIC = "SYNTHETIC"    # placeholder / synthetic / mock artifact


class FailureCode(str, Enum):
    """Typed scientific-execution failures. A tool returns/raises one of these
    rather than substituting a fixture when a real input is missing."""
    MISSING_SCIENTIFIC_INPUT = "MISSING_SCIENTIFIC_INPUT"
    STRUCTURE_UNAVAILABLE = "STRUCTURE_UNAVAILABLE"
    NO_KNOWN_BINDER = "NO_KNOWN_BINDER"
    E3_LIGAND_UNAVAILABLE = "E3_LIGAND_UNAVAILABLE"
    TOOL_UNAVAILABLE = "TOOL_UNAVAILABLE"
    FIXTURE_FORBIDDEN = "FIXTURE_FORBIDDEN"
    SYNTHETIC_INPUT_FORBIDDEN = "SYNTHETIC_INPUT_FORBIDDEN"
    INVALID_SCIENTIFIC_INPUT = "INVALID_SCIENTIFIC_INPUT"
    RETRIEVAL_DEADLINE_EXCEEDED = "RETRIEVAL_DEADLINE_EXCEEDED"
    RETRIEVAL_UNAVAILABLE = "RETRIEVAL_UNAVAILABLE"
    AMBIGUOUS_ENTITY = "AMBIGUOUS_ENTITY"


class ScientificInputError(RuntimeError):
    """Base class for explicit scientific-execution policy failures."""

    code: FailureCode = FailureCode.INVALID_SCIENTIFIC_INPUT

    def __init__(self, message: str, code: FailureCode | None = None):
        super().__init__(message)
        if code is not None:
            self.code = code

    def to_failure(self, context: str = "") -> dict:
        """Typed failure payload (never a fabricated result)."""
        return {
            "status": "failed",
            "failure_code": self.code.value,
            "context": context,
            "message": str(self),
            "evidence_kind": "missing",
        }


class FixtureUsageError(ScientificInputError):
    """A fixture/probe default was requested where it is not allowed."""

    code = FailureCode.FIXTURE_FORBIDDEN


class SyntheticInputNotAllowed(ScientificInputError):
    """A placeholder/synthetic/demo input was supplied in SCIENTIFIC mode."""

    code = FailureCode.SYNTHETIC_INPUT_FORBIDDEN


class MissingScientificInput(ScientificInputError):
    """A required scientific input was absent in SCIENTIFIC mode."""

    code = FailureCode.MISSING_SCIENTIFIC_INPUT


class RetrievalDeadlineExceeded(ScientificInputError):
    """A live retrieval did not complete inside the propagated run deadline.

    Raised instead of silently spending the whole run budget on a hanging
    source. Callers convert it into a typed ``retrieval_status`` on the state
    and continue with whatever cited/offline evidence exists.
    """

    code = FailureCode.RETRIEVAL_DEADLINE_EXCEEDED


class AmbiguousEntityError(ScientificInputError):
    """A supplied entity mapped to more than one plausible identifier.

    The workflow must refuse to pick one silently; the caller has to
    disambiguate (or the case is a justified no-go).
    """

    code = FailureCode.AMBIGUOUS_ENTITY
_MODE_ENV = "PROTACXTEND_EXECUTION_MODE"
_UNSET = object()
_ACTIVE_MODE: ContextVar[Any] = ContextVar("protacxtend_execution_mode", default=_UNSET)


def parse_mode(value: Any) -> ExecutionMode:
    """Coerce ``value`` (enum, name or value) into an :class:`ExecutionMode`."""
    if isinstance(value, ExecutionMode):
        return value
    text = str(value or "").strip().lower()
    for mode in ExecutionMode:
        if text in (mode.value, mode.name.lower()):
            return mode
    raise ValueError(
        f"unknown execution mode {value!r}; expected one of "
        f"{', '.join(m.value for m in ExecutionMode)}"
    )


def _default_mode() -> ExecutionMode:
    return parse_mode(os.environ.get(_MODE_ENV, ExecutionMode.DEMO.value))


def get_execution_mode() -> ExecutionMode:
    """Return the active execution mode (env-default DEMO when unset)."""
    current = _ACTIVE_MODE.get()
    if current is _UNSET:
        return _default_mode()
    return current


def set_execution_mode(mode: ExecutionMode | str) -> Token:
    return _ACTIVE_MODE.set(parse_mode(mode))


def reset_execution_mode(token: Token) -> None:
    _ACTIVE_MODE.reset(token)


@contextmanager
def execution_mode(mode: ExecutionMode | str):
    """Context manager that scopes the active execution mode."""
    token = set_execution_mode(mode)
    try:
        yield get_execution_mode()
    finally:
        reset_execution_mode(token)


def is_scientific() -> bool:
    return get_execution_mode() is ExecutionMode.SCIENTIFIC


def resolve_use_fixture(use_fixture: bool | None, mode: ExecutionMode | None = None) -> bool:
    """Resolve the fixture opt-in, defaulting to *not* using fixtures in SCIENTIFIC."""
    active = mode or get_execution_mode()
    if use_fixture is None:
        return active is not ExecutionMode.SCIENTIFIC
    if use_fixture and active is ExecutionMode.SCIENTIFIC:
        raise FixtureUsageError(
            "fixtures are forbidden in SCIENTIFIC mode; pass an explicit "
            "use_fixture=True only under DEMO/TEST"
        )
    return bool(use_fixture)


def reject_fixture(context: str, mode: ExecutionMode | None = None) -> None:
    """Raise :class:`FixtureUsageError` when the active mode is SCIENTIFIC."""
    active = mode or get_execution_mode()
    if active is ExecutionMode.SCIENTIFIC:
        raise FixtureUsageError(f"{context}: fixture execution is forbidden in SCIENTIFIC mode")


# ---------------------------------------------------------------------------
# Scientific-input policy
# ---------------------------------------------------------------------------

#: The canonical probe placeholders.  ``CCO`` is ethanol, ``CCOCCO`` is a
#: diethylene-glycol fragment — neither is a valid PROTAC input.
PLACEHOLDER_SMILES: frozenset[str] = frozenset(
    {"CCO", "CCOCCO", "CCOCCOC", "CC", "C", "O", "CO"}
)

#: Parameter names that carry molecular structure.
_SMILES_KEYS: tuple[str, ...] = (
    "smiles",
    "linker_smiles",
    "warhead_smiles",
    "e3_smiles",
    "protac_smiles",
    "candidate_smiles",
)

#: Parameter names that carry structure/pose paths.
_PATH_KEYS: tuple[str, ...] = (
    "pose_pdb",
    "structure_path",
    "structure_paths",
    "pdb_path",
    "artifact_path",
    "ternary_pose",
    "synthetic_pose",
)

#: Substrings that mark fixture/demo/synthetic artifacts.
SYNTHETIC_MARKERS: tuple[str, ...] = (
    "synthetic",
    "demo",
    "placeholder",
    "stepwise_module_smoke",
    "fixture",
)


#: Required real inputs for scientific execution, per agent tool.  Tools absent
#: from this mapping have no required *scientific* input (or validate internally).
SCIENTIFIC_REQUIRED_INPUTS: Mapping[str, Sequence[str]] = {
    # research / retrieval
    "deep_research": ("query",),
    "search_europe_pmc": ("query",),
    "search_pubmed": ("query",),
    "verify_crossref": ("doi",),
    "retrieve_fulltext": ("pmcid",),
    "search_web": ("query",),
    # target / biology
    "resolve_target": ("target_name",),
    "search_uniprot": ("query",),
    "retrieve_target_binders": ("target_name",),
    "select_e3_ligase": ("target",),
    "retrieve_e3_evidence": ("e3",),
    # chemistry
    "inspect_smiles": ("smiles",),
    "search_pubchem": ("term",),
    "search_chembl": ("term",),
    "search_bindingdb": ("target",),
    "detect_exit_vectors": ("smiles",),
    "generate_linkers": ("warhead_smiles", "e3_smiles"),
    "construct_protac": ("warhead_smiles", "linker_smiles", "e3_smiles"),
    "check_synthetic_feasibility": ("smiles",),
    # capability tooling
    "run_scientific_capability": ("capability", "params"),
    # structure
    "retrieve_pdb": ("target",),
    "model_ternary_complex": ("target", "e3"),
    "score_lysine_ubiquitination": ("target", "e3", "structure_paths"),
    "predict_cooperativity": ("warhead_smiles", "linker_smiles", "e3_smiles", "pose_pdb"),
    # prediction — e3/cell_line materially change the result, so a silent
    # "default"/"CRBN" substitution is a hidden scientific input.
    "predict_degradation": ("smiles", "e3", "cell_line"),
    "predict_cell_context": ("smiles", "cell_line"),
    "predict_admet": ("smiles",),
    # workflow / decision
    "run_protacpilot_structural": ("target",),
    "rank_candidates": ("candidates",),
    "build_candidate_dossier": ("candidate_id", "candidate"),
    # mechanistic simulation — concentration/alpha defaults were hidden inputs
    "simulate_hook_effect": ("target_conc_nM", "e3_conc_nM", "alpha"),
}


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    return False


def _iter_strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            if isinstance(item, str):
                yield item


def _flatten_params(value: Any, prefix: str = "") -> Iterable[tuple[str, Any]]:
    """Yield ``(leaf_key, value)`` pairs, descending through nested dicts."""
    if isinstance(value, Mapping):
        for key, item in value.items():
            name = f"{prefix}.{key}" if prefix else str(key)
            yield from _flatten_params(item, name)
    else:
        yield prefix, value


def validate_scientific_params(
    context: str,
    params: Mapping[str, Any] | None,
    required: Sequence[str] = (),
) -> None:
    """Fail closed when SCIENTIFIC-mode inputs are missing or synthetic.

    Raises :class:`MissingScientificInput` and
    :class:`SyntheticInputNotAllowed`; returns ``None`` when the inputs pass.
    Nested parameter dicts (e.g. ``run_scientific_capability``'s ``params``) are
    scanned recursively so a placeholder cannot hide one level down.
    """
    payload = dict(params or {})

    missing = [key for key in required if _is_empty(payload.get(key))]
    if missing:
        raise MissingScientificInput(
            f"{context}: missing required scientific input(s): {', '.join(missing)}"
        )

    leaves = list(_flatten_params(payload))
    for name, value in leaves:
        leaf_key = name.rsplit(".", 1)[-1]
        if leaf_key in _SMILES_KEYS and isinstance(value, str):
            if value.strip().upper() in PLACEHOLDER_SMILES:
                raise SyntheticInputNotAllowed(
                    f"{context}: placeholder SMILES {value!r} supplied for '{name}' "
                    "in SCIENTIFIC mode"
                )
        if leaf_key in _PATH_KEYS:
            for item in _iter_strings(value):
                if any(marker in item.lower() for marker in SYNTHETIC_MARKERS):
                    raise SyntheticInputNotAllowed(
                        f"{context}: synthetic/demo path {item!r} supplied for "
                        f"'{name}' in SCIENTIFIC mode"
                    )

    # Any field may carry a fixture artifact path (e.g. via a nested list).
    for name, value in leaves:
        for item in _iter_strings(value):
            lowered = item.lower()
            if (
                "synthetic_ternary" in lowered
                or "stepwise_module_smoke" in lowered
                or "demo_warhead" in lowered
                or "placeholder_warhead" in lowered
            ):
                raise SyntheticInputNotAllowed(
                    f"{context}: fixture artifact {item!r} supplied for '{name}' "
                    "in SCIENTIFIC mode"
                )


# ---------------------------------------------------------------------------
# Input-origin classification (P0-B)
# ---------------------------------------------------------------------------

def is_placeholder_smiles(value: Any) -> bool:
    """True for the canonical probe placeholders (``CCO``, ``CC``, …)."""
    return isinstance(value, str) and value.strip().upper() in PLACEHOLDER_SMILES


def is_synthetic_artifact(value: Any) -> bool:
    """True for a path/identifier that marks a fixture or synthetic artifact."""
    if not isinstance(value, str):
        return False
    lowered = value.lower()
    if any(marker in lowered for marker in SYNTHETIC_MARKERS):
        return True
    return any(tag in lowered for tag in
               ("synthetic_ternary", "demo_warhead", "placeholder_warhead"))


# Bundled curated tables mix literature-sourced rows with demo seeds. The demo
# seeds are identified by their ``source`` column (e.g. ``local_demo_warhead``,
# ``local_demo_e3_ligand``). SCIENTIFIC mode must never build a strategy from
# them, even though DEMO/TEST exploration may.
DEMO_SOURCE_PREFIXES = ("local_demo", "demo_", "curated_demo")


def is_demo_source(value: Any) -> bool:
    """True when a record's provenance ``source`` marks it as a demo seed."""
    if not isinstance(value, str):
        return False
    lowered = value.strip().lower()
    if not lowered:
        return False
    if lowered in {"demo", "demo_only"}:
        return True
    if lowered.startswith(DEMO_SOURCE_PREFIXES):
        return True
    return any(tag in lowered for tag in
               ("demo_warhead", "demo_e3_ligand", "placeholder_warhead"))


def filter_scientific_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    source_key: str = "source",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split curated rows into ``(kept, dropped_demo)`` for the active mode.

    In SCIENTIFIC mode every row whose ``source`` is a demo seed is dropped;
    DEMO/TEST modes keep all rows. Callers that drop rows should surface the
    count so the abstention is auditable rather than silent.
    """
    materialised = [dict(row) for row in rows]
    if not is_scientific():
        return materialised, []
    kept: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    for row in materialised:
        (dropped if is_demo_source(row.get(source_key, "")) else kept).append(row)
    return kept, dropped


def classify_input_origin(
    payload: Mapping[str, Any] | None,
    *,
    fixture: Mapping[str, Any] | None = None,
    declared: Mapping[str, Any] | None = None,
    user_keys: Iterable[str] | None = None,
) -> dict[str, str]:
    """Return ``{key: InputOrigin.value}`` for every input of a tool call.

    Precedence: an explicit ``declared`` origin; then a value the caller did
    *not* supply that equals the probe fixture (FIXTURE); then a
    placeholder/synthetic value (SYNTHETIC); then USER.
    """
    payload = dict(payload or {})
    fixture = dict(fixture or {})
    declared = dict(declared or {})
    supplied = set(user_keys) if user_keys is not None else set()
    origins: dict[str, str] = {}
    for key, value in payload.items():
        if key in declared:
            origins[key] = InputOrigin(str(declared[key])).value
            continue
        if key not in supplied and key in fixture and fixture[key] == value:
            origins[key] = InputOrigin.FIXTURE.value
            continue
        if is_placeholder_smiles(value) or is_synthetic_artifact(value):
            origins[key] = InputOrigin.SYNTHETIC.value
            continue
        origins[key] = InputOrigin.USER.value
    return origins



# ---------------------------------------------------------------------------
# Recursive public-payload scan
# ---------------------------------------------------------------------------

def _is_smiles_leaf_key(key: str) -> bool:
    leaf = key.rsplit(".", 1)[-1].lower()
    return leaf in _SMILES_KEYS or leaf.endswith("_smiles") or leaf in {
        "canonical_smiles", "isomeric_smiles", "full_protac_smiles",
    }


def _is_path_leaf_key(key: str) -> bool:
    leaf = key.rsplit(".", 1)[-1].lower()
    return leaf in _PATH_KEYS or leaf.endswith("_path") or leaf.endswith("_file") or leaf.endswith("_dir")


def _is_source_leaf_key(key: str) -> bool:
    leaf = key.rsplit(".", 1)[-1].lower()
    return leaf in {"source", "origin", "fixture", "fixture_name", "fixture_kind"} or leaf.endswith("_source")


def _walk_payload(value: Any, prefix: str = "") -> Iterable[tuple[str, Any]]:
    if isinstance(value, Mapping):
        for key, item in value.items():
            name = f"{prefix}.{key}" if prefix else str(key)
            yield from _walk_payload(item, name)
    elif isinstance(value, (list, tuple)):
        for idx, item in enumerate(value):
            name = f"{prefix}[{idx}]" if prefix else f"[{idx}]"
            yield from _walk_payload(item, name)
    else:
        yield prefix, value


def scan_scientific_payload(payload: Any) -> list[dict[str, str]]:
    """Return fixture/synthetic contamination findings in a public payload.

    This is intentionally narrower than a free-text grep: explanatory strings
    may mention that demo rows were excluded, but structure fields, paths,
    provenance/source fields, and fixture metadata must not carry probe inputs
    in SCIENTIFIC mode.
    """
    findings: list[dict[str, str]] = []
    for path, value in _walk_payload(payload):
        if not isinstance(value, str):
            continue
        text = value.strip()
        lowered = text.lower()
        if _is_smiles_leaf_key(path) and is_placeholder_smiles(text):
            findings.append({"path": path, "value": text, "reason": "placeholder_smiles"})
            continue
        if _is_path_leaf_key(path) and is_synthetic_artifact(text):
            findings.append({"path": path, "value": text, "reason": "synthetic_or_fixture_path"})
            continue
        if _is_source_leaf_key(path) and (is_demo_source(text) or is_synthetic_artifact(text)):
            findings.append({"path": path, "value": text, "reason": "demo_or_fixture_source"})
            continue
        if path.rsplit(".", 1)[-1].lower() in {"input_origin", "input_origins"} and lowered in {"fixture", "synthetic"}:
            findings.append({"path": path, "value": text, "reason": "non_scientific_input_origin"})
    return findings


def assert_scientific_payload_clean(context: str, payload: Any) -> None:
    """Fail closed when a SCIENTIFIC-mode public payload contains fixtures."""
    findings = scan_scientific_payload(payload)
    if not findings:
        return
    first = findings[0]
    raise SyntheticInputNotAllowed(
        f"{context}: scientific payload contains {len(findings)} fixture/synthetic "
        f"finding(s); first at {first['path']}: {first['reason']}={first['value']!r}"
    )

def dominant_input_origin(origins: Mapping[str, str]) -> str:
    """Single label for a tool call.

    SYNTHETIC and FIXTURE dominate (they are the scientifically dangerous
    ones); otherwise the first non-USER origin is reported, else USER.
    """
    values = set(origins.values())
    if InputOrigin.SYNTHETIC.value in values:
        return InputOrigin.SYNTHETIC.value
    if InputOrigin.FIXTURE.value in values:
        return InputOrigin.FIXTURE.value
    for candidate in (InputOrigin.RETRIEVED.value, InputOrigin.GENERATED.value,
                      InputOrigin.COMPUTED.value, InputOrigin.USER.value):
        if candidate in values:
            return candidate
    return InputOrigin.USER.value
