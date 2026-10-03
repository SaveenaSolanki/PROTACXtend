"""Invalid-run quarantine and comparison-only run classification.

A persisted run under ``outputs/runs/<run_id>/`` is classified as:

- ``INVALID`` when it carries an ``INVALID_RUN.md`` (audited/withdrawn) or
  ``INVALID_HISTORICAL`` (preserved only as a regression fixture);
- ``COMPARISON_ONLY`` when its manifest (or provenance) declares
  ``scientific_evidence: false`` or a ``role`` containing
  ``comparison_only`` (e.g. a corrected replay of an invalid run);
- ``OK`` otherwise.

Invalid runs must never be served by the TUI, API, run search, reports or
ENGRAM. Comparison-only runs may be *retrieved* (for regression/audit) but
must be visibly labelled ``comparison_only`` on every surface, and their
citation claim is precise: they are citeable only as a reference
reconstruction, never as scientific evidence. A run that merely emitted JSON
is never treated as evidence.

This module is the single source of truth for that policy.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator

INVALID_MARKERS = ("INVALID_RUN.md", "INVALID_HISTORICAL")
#: Historical alias kept for scripts that predate the marker rename.
INVALID_RUN_MARKER = "INVALID_RUN.md"

#: Precise citation claims (replace the bare ``citeable`` boolean).
CLAIM_INVALID = "not citeable: run is quarantined as invalid/withdrawn"
CLAIM_COMPARISON_ONLY = "citeable as a reference reconstruction (comparison_only); not scientific evidence"
#: The corrected replay (malformed-input regression) has its own narrower claim;
#: it must never be called a reconstruction or candidate evidence.
CLAIM_CORRECTED_REPLAY = "comparison-only malformed-input regression; no candidate or scientific result."
CLAIM_OK = "citeable as a computational run record, subject to module-level claim gating"

#: The only run that may be presented as the MZ1 reference reconstruction.
MZ1_RECONSTRUCTION_RUN = "run_brd4_vhl_scientific_v1"
CLAIM_MZ1_RECONSTRUCTION = "MZ1 reference reconstruction (verified components); computational reconstruction, not a novel candidate"


def _manifest(run_dir: Path) -> dict:
    for name in ("manifest.json", "provenance.json"):
        p = run_dir / name
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8", errors="replace"))
            except Exception:  # noqa: BLE001
                return {}
    return {}


def comparison_only_reason(run_dir: str | Path) -> str | None:
    """Return a reason when *run_dir* is a comparison-only replay, else None."""
    path = Path(run_dir)
    if not path.is_dir():
        return None
    man = _manifest(path)
    role = str(man.get("role") or "")
    sci = man.get("scientific_evidence")
    if "comparison_only" in role or (sci is False):
        return f"comparison_only: {man.get('note') or CLAIM_COMPARISON_ONLY}"
    return None


def quarantine_reason(run_dir: str | Path) -> str | None:
    """Return a human-readable reason when *run_dir* is invalid, else None."""
    path = Path(run_dir)
    if not path.is_dir():
        return f"{path} is not a directory"
    for marker in INVALID_MARKERS:
        if (path / marker).exists():
            try:
                text = (path / marker).read_text(encoding="utf-8", errors="replace").strip()
            except Exception:  # noqa: BLE001
                text = ""
            first = next((ln for ln in text.splitlines() if ln.strip()), "")
            return f"{marker}: {first[:200]}"
    flag = path / "quarantine.json"
    if flag.exists():
        try:
            payload = json.loads(flag.read_text(encoding="utf-8"))
            if payload.get("valid") is False or payload.get("status") in {"INVALID", "INVALID_HISTORICAL"}:
                return f"quarantine.json: {payload.get('reason', 'marked invalid')}"
        except Exception:  # noqa: BLE001
            return "quarantine.json present"
    return None


def run_status(run_dir: str | Path) -> str:
    """One of INVALID | COMPARISON_ONLY | OK."""
    reason = quarantine_reason(run_dir)
    if reason is not None:
        return "INVALID"
    if comparison_only_reason(run_dir) is not None:
        return "COMPARISON_ONLY"
    return "OK"


def _comparison_only_claim(run_dir: Path) -> str:
    """Per-run claim for comparison-only replays.

    ``run_e4e21ccd_corrected_v1`` (and any manifest whose note/determination
    describes a malformed-input regression) is cited only as a
    malformed-input regression — never as a reconstruction, and never as
    candidate evidence. Other comparison-only runs keep the generic claim.
    """
    if run_dir.name == "run_e4e21ccd_corrected_v1":
        return CLAIM_CORRECTED_REPLAY
    man = _manifest(run_dir)
    text = " ".join(str(man.get(k) or "") for k in ("note", "determination", "role", "schema"))
    if any(tok in text.lower() for tok in ("malformed", "corrected replay", "input regression")):
        return CLAIM_CORRECTED_REPLAY
    return CLAIM_COMPARISON_ONLY


def citation_claim(run_dir: str | Path) -> str:
    """Precise citation claim for a run (replaces the broad boolean).

    The MZ1 reconstruction label is reserved for ``run_brd4_vhl_scientific_v1``;
    invalid runs are never citeable; the corrected replay is cited only as a
    malformed-input regression."""
    path = Path(run_dir)
    reason = quarantine_reason(path)
    if reason is not None:
        return f"{CLAIM_INVALID}; {reason}"
    if path.name == MZ1_RECONSTRUCTION_RUN and (path / "run.json").exists():
        return CLAIM_MZ1_RECONSTRUCTION
    if comparison_only_reason(path) is not None:
        return _comparison_only_claim(path)
    return CLAIM_OK


def is_quarantined(run_dir: str | Path) -> bool:
    return quarantine_reason(run_dir) is not None


def is_citeable(run_dir: str | Path) -> bool:
    """True only for OK runs (not invalid and not comparison_only).

    This boolean is kept for backward compatibility; prefer
    :func:`citation_claim` / :func:`run_status` for a precise claim.
    """
    path = Path(run_dir)
    return path.is_dir() and run_status(path) == "OK"


def iter_valid_run_dirs(root: str | Path = "outputs/runs") -> Iterator[Path]:
    """Yield run directories under *root* that are not quarantined."""
    base = Path(root)
    if not base.is_dir():
        return
    for child in sorted(base.iterdir()):
        if child.is_dir() and not is_quarantined(child):
            yield child


def assert_citeable(run_dir: str | Path) -> None:
    reason = quarantine_reason(run_dir)
    if reason is not None:
        raise PermissionError(f"run {Path(run_dir).name!r} is quarantined and cannot be used: {reason}")


def quarantine_manifest(run_dir: str | Path) -> dict:
    """Read-only classification record for a run."""
    path = Path(run_dir)
    reason = quarantine_reason(path)
    comp = comparison_only_reason(path)
    return {
        "run_id": path.name,
        "path": str(path),
        "status": run_status(path),
        "quarantined": reason is not None,
        "comparison_only": comp is not None,
        "reason": reason,
        "citation_claim": citation_claim(path),
        "citeable": reason is None and comp is None,  # legacy bool; use citation_claim
    }


def serve_payload(run_dir: str | Path) -> dict:
    """Payload every surface (TUI/API/search/reports/ENGRAM) should base its
    response on. Guarantees the corrected replay is visibly comparison_only."""
    path = Path(run_dir)
    man = quarantine_manifest(path)
    status = man["status"]
    if status == "INVALID":
        return {"status": "invalid", "run_id": path.name, "dir": str(path),
                "error": f"run {path.name!r} is quarantined and must not be cited: {man['reason']}",
                "citation_claim": man["citation_claim"], "final": True}
    if status == "COMPARISON_ONLY":
        return {"status": "comparison_only", "run_id": path.name, "dir": str(path),
                "banner": "COMPARISON-ONLY REPLAY — citeable as a reference reconstruction only; "
                           "not scientific evidence (see run record: scientific_evidence=false).",
                "citation_claim": man["citation_claim"], "final": True}
    return {"status": "ok", "run_id": path.name, "dir": str(path),
            "citation_claim": man["citation_claim"], "final": False}


__all__ = [
    "INVALID_MARKERS", "INVALID_RUN_MARKER", "CLAIM_INVALID", "CLAIM_COMPARISON_ONLY",
    "CLAIM_CORRECTED_REPLAY", "CLAIM_MZ1_RECONSTRUCTION", "MZ1_RECONSTRUCTION_RUN",
    "comparison_only_reason", "quarantine_reason", "run_status", "citation_claim",
    "is_quarantined", "is_citeable", "iter_valid_run_dirs", "assert_citeable",
    "quarantine_manifest", "serve_payload",
]
