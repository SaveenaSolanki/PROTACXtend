#!/usr/bin/env python
"""Stage-by-stage audit of a persisted controlled run.

Checks identity consistency, binder usability evidence, component attachment
provenance, product validity, funnel reconciliation, prediction provenance,
decision reasons, and report/persisted-record agreement. Emits a PASS/FAIL/
UNVERIFIED table (Markdown + JSON).

Usage::

    python scripts/audit_controlled_run.py --run-dir outputs/runs/run_brd4_vhl_scientific_v1
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _pass(name: str, detail: str, evidence: list[str] | None = None) -> dict[str, Any]:
    return {"check": name, "status": "PASS", "detail": detail, "evidence": evidence or []}


def _fail(name: str, detail: str, evidence: list[str] | None = None) -> dict[str, Any]:
    return {"check": name, "status": "FAIL", "detail": detail, "evidence": evidence or []}


def _unverified(name: str, detail: str) -> dict[str, Any]:
    return {"check": name, "status": "UNVERIFIED", "detail": detail, "evidence": []}


def _rdkit(smiles: str) -> tuple[bool, str]:
    try:
        from rdkit import Chem

        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return False, "rdkit_parse_failed"
        if any(a.GetAtomicNum() == 0 for a in mol.GetAtoms()):
            return False, "residual_attachment_dummy"
        return True, "rdkit_valid"
    except Exception as exc:  # noqa: BLE001
        return False, f"rdkit_error:{exc}"


def audit(run_dir: Path) -> dict[str, Any]:
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    checks: list[dict[str, Any]] = []
    target = run.get("target") or {}
    e3 = run.get("e3_ligase") or {}

    # 1. target/E3 identity consistency
    if target.get("gene_symbol") == "BRD4" and target.get("uniprot_id") == "O60885" \
            and e3.get("gene_symbol") == "VHL" and e3.get("uniprot_id") == "P40337":
        checks.append(_pass("target_e3_identity",
                            f"{target.get('gene_symbol')}/{target.get('uniprot_id')} + "
                            f"{e3.get('gene_symbol')}/{e3.get('uniprot_id')}",
                            [target.get("source_uri", ""), e3.get("source_uri", "")]))
    else:
        checks.append(_fail("target_e3_identity",
                            f"got {target.get('gene_symbol')}/{target.get('uniprot_id')} + "
                            f"{e3.get('gene_symbol')}/{e3.get('uniprot_id')}"))

    # 2. every counted (usable) binder has identity + structure + external evidence
    bad_binders = []
    for b in run.get("binders") or []:
        if b.get("validation_state") != "valid":
            continue
        if not (b.get("name") and b.get("smiles") and b.get("source_uri") and b.get("source_record_id")):
            bad_binders.append(b.get("record_id") or b.get("name") or "?")
    if not bad_binders:
        usable = [b for b in (run.get("binders") or []) if b.get("validation_state") == "valid"]
        checks.append(_pass("binder_evidence",
                            f"{len(usable)} usable binder(s) each have identity+structure+source",
                            [b.get("source_uri", "") for b in usable]))
    else:
        checks.append(_fail("binder_evidence", f"incomplete binder evidence: {bad_binders}"))

    # 3. warhead + E3 ligand structures and source-backed attachment atoms
    warheads, ligands = run.get("warheads") or [], run.get("e3_ligands") or []
    attach_ok = bool(warheads) and bool(ligands)
    detail = []
    if warheads:
        w = warheads[0]
        attach_ok = attach_ok and bool(w.get("canonical_smiles")) and w.get("attachment_atom_map") is not None \
            and bool(w.get("source_uri"))
        detail.append(f"warhead map={w.get('attachment_atom_map')} src={w.get('source_uri')}")
    if ligands:
        lig = ligands[0]
        attach_ok = attach_ok and bool(lig.get("canonical_smiles")) and lig.get("attachment_atom_map") is not None \
            and bool(lig.get("source_uri"))
        detail.append(f"e3 map={lig.get('attachment_atom_map')} src={lig.get('source_uri')}")
    checks.append(_pass("component_attachment_provenance", "; ".join(detail)) if attach_ok
                  else _fail("component_attachment_provenance", "; ".join(detail) or "missing components"))

    # 4. complete, RDKit-valid, isomeric product
    candidates = run.get("candidates") or []
    if candidates:
        c = candidates[0]
        ok, why = _rdkit(c.get("canonical_smiles", ""))
        isomeric = c.get("canonical_smiles", "") != c.get("assembled_smiles", "") or "@" in c.get("canonical_smiles", "")
        if ok and c.get("valid"):
            checks.append(_pass("product_validity",
                                f"{c.get('formula')} {c.get('mw')} Da, InChIKey {c.get('inchikey')}",
                                [f"isomeric={isomeric}", why]))
        else:
            checks.append(_fail("product_validity", f"{why}; valid={c.get('valid')}"))
    else:
        checks.append(_fail("product_validity", "no candidate produced"))

    # 5. funnel reconciliation
    from protacxtend.contracts.records import CandidateFunnel

    try:
        notes = CandidateFunnel(**run.get("funnel", {})).reconcile()
    except Exception as exc:  # noqa: BLE001
        notes = [f"funnel_load_error:{exc}"]
    checks.append(_pass("funnel_reconciliation", "funnel reconciles; notes=" + str(notes)) if not notes
                  else _fail("funnel_reconciliation", "; ".join(notes)))

    # 6. prediction provenance: measured -> source; model -> method/version/input; else unavailable
    pred_problems = []
    for p in run.get("predictions") or []:
        kind = p.get("kind")
        if kind == "measured":
            if not (p.get("source_uri") and p.get("reason")):
                pred_problems.append(f"{p.get('endpoint')}:measured_without_source")
        elif kind == "model":
            if not (p.get("model_name") and p.get("model_version")):
                pred_problems.append(f"{p.get('endpoint')}:model_without_method_version")
        elif kind == "unavailable":
            if p.get("available"):
                pred_problems.append(f"{p.get('endpoint')}:unavailable_but_available_true")
        else:
            pred_problems.append(f"{p.get('endpoint')}:unknown_kind={kind}")
    checks.append(_pass("prediction_provenance",
                        f"{len(run.get('predictions') or [])} prediction record(s) carry source/method or are unavailable")
                  if not pred_problems else _fail("prediction_provenance", "; ".join(pred_problems)))

    # 7. decisions.jsonl reasons
    decisions_path = run_dir / "decisions.jsonl"
    decisions = [json.loads(l) for l in decisions_path.read_text().splitlines() if l.strip()] \
        if decisions_path.exists() else []
    no_reason = [d.get("stage") for d in decisions if not (d.get("reason") or "").strip()]
    checks.append(_pass("decisions_reasons", f"{len(decisions)} decision(s), each with a reason")
                  if decisions and not no_reason else _fail("decisions_reasons",
                                                            f"decisions={len(decisions)} missing_reason={no_reason}"))

    # 8. report agrees with persisted record
    report_path = run_dir / "report.md"
    report = report_path.read_text(encoding="utf-8") if report_path.exists() else ""
    must = [run.get("run_id", ""), run.get("status", ""), target.get("gene_symbol", ""),
            (candidates[0].get("inchikey", "") if candidates else "")]
    missing = [m for m in must if m and m not in report]
    checks.append(_pass("report_consistency", "report.md matches persisted run fields")
                  if not missing else _fail("report_consistency", f"report missing {missing}"))

    # 9. dataset inclusion/exclusion: no synthetic decoy or mismatched target candidate
    mismatched = [c.get("candidate_id") for c in candidates if c.get("target_gene") != target.get("gene_symbol")
                  or c.get("e3_gene") != e3.get("gene_symbol")]
    checks.append(_pass("candidate_identity", "all candidates carry the resolved target/E3")
                  if not mismatched else _fail("candidate_identity", f"mismatched: {mismatched}"))

    passed = sum(1 for c in checks if c["status"] == "PASS")
    return {
        "run_id": run.get("run_id"),
        "run_dir": str(run_dir),
        "status": run.get("status"),
        "classification": run.get("classification"),
        "checks": checks,
        "n_pass": passed,
        "n_fail": sum(1 for c in checks if c["status"] == "FAIL"),
        "n_unverified": sum(1 for c in checks if c["status"] == "UNVERIFIED"),
        "overall": "PASS" if passed == len(checks) else "FAIL",
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines = [
        f"# Controlled-run audit — `{result['run_id']}`",
        "",
        f"- persisted status: **{result['status']}**",
        f"- classification: **{result['classification']}**",
        f"- audit result: **{result['overall']}** "
        f"(PASS={result['n_pass']}, FAIL={result['n_fail']}, UNVERIFIED={result['n_unverified']})",
        "",
        "| check | status | detail |",
        "|---|---|---|",
    ]
    for c in result["checks"]:
        lines.append(f"| {c['check']} | {c['status']} | {c['detail']} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-dir", type=Path, required=True)
    ap.add_argument("--json-out", type=Path, default=None)
    ap.add_argument("--md-out", type=Path, default=None)
    args = ap.parse_args()
    result = audit(args.run_dir)
    json_out = args.json_out or (args.run_dir / "audit.json")
    md_out = args.md_out or (args.run_dir / "AUDIT.md")
    json_out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    md_out.write_text(render_markdown(result), encoding="utf-8")
    print(render_markdown(result))
    print(f"wrote {json_out} and {md_out}")
    return 0 if result["overall"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
