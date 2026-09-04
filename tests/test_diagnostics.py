"""Tests for /doctor system diagnostics (machine-readable, real checks)."""

import json

import pytest

from protacxtend.diagnostics import build_doctor_report, doctor_report_json


def test_report_shape_and_consistency():
    report = build_doctor_report()
    assert isinstance(report, dict)
    assert set(report).issuperset({
        "system", "required_ok", "optional_warnings", "summary",
        "required_failures", "optional_warning_names", "checks",
    })
    checks = report["checks"]
    assert len(checks) == report["summary"]["total"]
    n_ok = sum(1 for c in checks if c["status"] == "ok")
    n_warn = sum(1 for c in checks if c["status"] == "warn")
    n_fail = sum(1 for c in checks if c["status"] == "fail")
    assert n_ok == report["summary"]["ok"]
    assert n_warn == report["summary"]["warn"]
    assert n_fail == report["summary"]["fail"]


def test_required_registries_are_present():
    report = build_doctor_report()
    names = [c["name"] for c in report["checks"]]
    for required in ["agents registry", "skills registry", "databases registry",
                     "workflows registry", "protacxtend package", "rdkit"]:
        assert required in names, required


def test_optional_warnings_never_block_system():
    report = build_doctor_report()
    # Overall verdict is a function of REQUIRED checks only:
    # READY (all ok) · WARNING (optional problems) · REQUIRED_FAILURE
    assert report["required_ok"] == (len(report["required_failures"]) == 0)
    assert report["system"] in {"READY", "WARNING", "REQUIRED_FAILURE"}
    if report["required_failures"]:
        assert report["system"] == "REQUIRED_FAILURE"
    else:
        assert report["system"] in {"READY", "WARNING"}
        assert report["system"] == "WARNING" if report["optional_warnings"] else report["system"] == "READY"
    # optional-only failures cannot appear in required_failures
    optional_names = {c["name"] for c in report["checks"] if c["level"] == "optional"}
    assert set(report["required_failures"]).isdisjoint(optional_names)


def test_optional_failure_does_not_fail_required_ok(monkeypatch):
    # Simulate an optional backend being absent -> warn only, required_ok stays True.
    import protacxtend.diagnostics as diag
    from protacxtend.tui_bridge import events as ev

    real_skills = ev.SKILLS
    try:
        # Patch an *optional* path used by the report builder is awkward; instead
        # assert the semantics with a required registry intact and llm marked absent.
        monkeypatch.setattr(diag, "OPTIONAL_MODULES", diag.OPTIONAL_MODULES + ["not_a_real_optional_pkg_xyz"])
        report = build_doctor_report()
        assert report["required_ok"] is True
        assert report["system"] in {"READY", "WARNING"}  # optional absence never blocks
        assert any(c["name"] == "backend:not_a_real_optional_pkg_xyz" and c["status"] == "warn"
                   for c in report["checks"])
    finally:
        ev.SKILLS = real_skills


def test_required_failure_flips_system(monkeypatch):
    import protacxtend.diagnostics as diag
    monkeypatch.setattr(diag, "REQUIRED_MODULES", ["does_not_exist_required_pkg_zz"])
    report = build_doctor_report()
    assert report["required_ok"] is False
    assert report["system"] == "REQUIRED_FAILURE"
    assert "does_not_exist_required_pkg_zz" in report["required_failures"]


def test_machine_readable_json():
    payload = json.loads(doctor_report_json())
    assert isinstance(payload, dict)
    assert "checks" in payload
    # every check is machine-readable
    for c in payload["checks"]:
        assert {"name", "level", "status", "ok", "detail"} <= set(c)
