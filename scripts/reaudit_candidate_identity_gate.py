#!/usr/bin/env python3
"""Re-audit persisted candidate outputs with CandidateIdentityAndAssemblyGate."""
from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

from protacxtend.backend.schemas import CandidateRecord
from protacxtend.identity_gate import CandidateIdentityAndAssemblyGate, gate_payload

ROOT = Path('/storage/saveena/protacxtend')
DEFAULT_INPUT = ROOT / 'outputs/priority_agent_audit/tui_brd4_crbn_real/candidate_evidence_table.json'
OLD_AUDIT = ROOT / 'outputs/priority_agent_audit/brd4_crbn_structure_audit/audit_all_candidates.json'
OUT = ROOT / 'outputs/priority_agent_audit/candidate_identity_gate_reaudit'


def _candidate_from_row(row: dict[str, Any]) -> CandidateRecord:
    comp = row.get('components') or {}
    smiles = row.get('component_smiles') or {}
    prov = dict(row.get('provenance') or {})
    return CandidateRecord(
        candidate_id=row.get('candidate_id',''),
        target=comp.get('target',''),
        e3_ligase=comp.get('e3_ligase',''),
        warhead_name=comp.get('warhead',''),
        warhead_smiles=smiles.get('warhead',''),
        e3_ligand_name=comp.get('e3_ligand',''),
        e3_ligand_smiles=smiles.get('e3_ligand',''),
        linker_name=comp.get('linker',''),
        linker_smiles=smiles.get('linker',''),
        full_protac_smiles=row.get('canonical_smiles',''),
        validity_status='valid',
        provenance=prov,
        warning_flags=list(row.get('warning_flags') or []),
    )


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    keys = sorted({k for row in rows for k in row})
    with path.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for row in rows:
            w.writerow({k: json.dumps(v, sort_keys=True) if isinstance(v, (dict, list)) else v for k, v in row.items()})


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = json.loads(DEFAULT_INPUT.read_text())
    old_by_id: dict[str, Any] = {}
    if OLD_AUDIT.exists():
        for row in json.loads(OLD_AUDIT.read_text()):
            old_by_id[row.get('candidate_id','')] = row
    gate = CandidateIdentityAndAssemblyGate()
    audited = []
    gate_counts = Counter()
    changed_to_blocked = []
    for row in rows:
        cand = _candidate_from_row(row)
        result = gate.evaluate(cand)
        payload = gate_payload(result)
        old = old_by_id.get(cand.candidate_id, {})
        old_proxy_pass = bool(old.get('chemically_verified_for_shortlist')) if old else None
        new_pass = bool(result.all_required_passed)
        for name, check in result.gates.items():
            if check.passed:
                gate_counts[name] += 1
        if old_proxy_pass and not new_pass:
            changed_to_blocked.append(cand.candidate_id)
        audited.append({
            'candidate_id': cand.candidate_id,
            'old_proxy_chemically_verified_for_shortlist': old_proxy_pass,
            'identity_gate_passed': new_pass,
            'parse_valid': result.gates.get('parse_valid').passed,
            'source_backed_target_binder': result.gates.get('source_backed_target_binder').passed,
            'source_backed_e3_ligand': result.gates.get('source_backed_e3_ligand').passed,
            'supported_exit_vectors': result.gates.get('supported_exit_vectors').passed,
            'component_retention': result.gates.get('component_retention').passed,
            'whole_molecule_connectivity': result.gates.get('whole_molecule_connectivity').passed,
            'evidence_level_gate': result.gates.get('evidence_level').passed,
            'binding_unverified': not new_pass,
            'reasons': result.reasons,
            'gate_payload': payload,
        })
    denom = len(audited)
    old_true = sum(1 for r in audited if r['old_proxy_chemically_verified_for_shortlist'] is True)
    new_true = sum(1 for r in audited if r['identity_gate_passed'])
    summary = {
        'schema': 'candidate_identity_gate_reaudit.v1',
        'input': str(DEFAULT_INPUT),
        'denominator': denom,
        'old_proxy_chemically_verified_for_shortlist_true': old_true,
        'new_identity_gate_passed': new_true,
        'changed_from_old_proxy_pass_to_gate_blocked': len(changed_to_blocked),
        'changed_candidate_ids': changed_to_blocked,
        'gate_pass_counts': dict(gate_counts),
        'status': 'blocked' if new_true == 0 else 'partially_passed',
        'note': 'Missing or contradictory identity evidence fails closed; individual gate results replace any single chemically_verified Boolean.',
    }
    (OUT / 'reaudit_summary.json').write_text(json.dumps(summary, indent=2, sort_keys=True))
    (OUT / 'reaudit_all_candidates.json').write_text(json.dumps(audited, indent=2, sort_keys=True))
    write_csv(OUT / 'reaudit_all_candidates.csv', audited)
    report = [
        '# CandidateIdentityAndAssemblyGate re-audit', '',
        f'- Input: `{DEFAULT_INPUT}`',
        f'- Denominator: {denom}',
        f'- Old proxy chemically_verified_for_shortlist: {old_true}/{denom}',
        f'- New identity gate passed: {new_true}/{denom}',
        f'- Changed from old proxy pass to gate-blocked: {len(changed_to_blocked)}/{denom}',
        '', '## Gate Pass Counts', '',
    ]
    for key in ['parse_valid','source_backed_target_binder','source_backed_e3_ligand','supported_exit_vectors','component_retention','whole_molecule_connectivity','evidence_level']:
        report.append(f'- {key}: {gate_counts.get(key,0)}/{denom}')
    report.extend(['', 'No prediction, ranking, shortlist, or nomination should use rows whose `identity_gate_passed` is false.'])
    (OUT / 'report.md').write_text('\n'.join(report)+'\n')
    print(json.dumps(summary, indent=2))

if __name__ == '__main__':
    main()
