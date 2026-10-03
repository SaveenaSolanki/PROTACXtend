#!/usr/bin/env python3
"""Component-identity audit for the frozen BRD4 x CRBN TUI run."""
from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd
from rdkit import Chem
from rdkit.Chem import Draw, rdFMCS

from protacxtend.contracts.assembly import assemble_product
from protacxtend.contracts import run_controlled
from protacxtend.tools import verified_components as vc

ROOT = Path('/storage/saveena/protacxtend')
RUN_ID = 'design_ee2eb431dc'
RUN_DIR = ROOT / 'outputs/runs' / RUN_ID
TUI_DIR = ROOT / 'outputs/priority_agent_audit/tui_brd4_crbn_real'
OUT = ROOT / 'outputs/priority_agent_audit/brd4_crbn_component_identity_audit'
IMG = OUT / 'top_structures'
RERUN_DIR = ROOT / 'outputs/controlled_runs/brd4_crbn_verified_dbet1_rerun'

GLUTARIMIDE = Chem.MolFromSmarts('O=C1CCC(NC1=O)')
PHTHALIMIDE = Chem.MolFromSmarts('O=C1NC(=O)c2ccccc21')


def mol(s: str | None):
    return Chem.MolFromSmiles(s or '')


def strip_dummy(smiles: str) -> str:
    m = mol(smiles)
    if m is None:
        return ''
    rw = Chem.RWMol(m)
    for a in rw.GetAtoms():
        if a.GetAtomicNum() == 0:
            a.SetAtomicNum(1)
            a.SetAtomMapNum(0)
            a.SetIsotope(0)
    try:
        mm = rw.GetMol()
        Chem.SanitizeMol(mm)
        return Chem.MolToSmiles(mm, canonical=True, isomericSmiles=True)
    except Exception:
        return ''


def canon(smiles: str | None, *, dummy_to_h: bool = False) -> str:
    if dummy_to_h:
        return strip_dummy(smiles or '')
    m = mol(smiles)
    return Chem.MolToSmiles(m, canonical=True, isomericSmiles=True) if m is not None else ''


def atom_table(smiles: str) -> list[dict[str, Any]]:
    m = mol(smiles)
    if m is None:
        return []
    rows = []
    for a in m.GetAtoms():
        rows.append({
            'idx': a.GetIdx(), 'symbol': a.GetSymbol(), 'atomic_num': a.GetAtomicNum(),
            'map_num': a.GetAtomMapNum(), 'degree': a.GetDegree(),
            'neighbors': [n.GetIdx() for n in a.GetNeighbors()],
        })
    return rows


def dummy_atoms(smiles: str) -> list[dict[str, Any]]:
    return [r for r in atom_table(smiles) if r['atomic_num'] == 0]


def component_match(product_smiles: str, component_smiles: str) -> list[int]:
    p = mol(product_smiles)
    c = mol(strip_dummy(component_smiles))
    if p is None or c is None:
        return []
    match = p.GetSubstructMatch(c)
    return list(match)


def has_smarts(smiles: str, patt) -> bool:
    m = mol(strip_dummy(smiles)) or mol(smiles)
    return bool(m is not None and patt is not None and m.HasSubstructMatch(patt))


def mcs_missing(source_smiles: str, recorded_smiles: str) -> dict[str, Any]:
    source = mol(source_smiles)
    rec = mol(strip_dummy(recorded_smiles))
    if source is None or rec is None:
        return {'mcs_atoms': 0, 'source_atoms': source.GetNumAtoms() if source else 0, 'recorded_atoms': rec.GetNumAtoms() if rec else 0, 'source_atoms_not_in_mcs_count': None}
    res = rdFMCS.FindMCS([source, rec], timeout=3)
    return {
        'mcs_atoms': res.numAtoms,
        'source_atoms': source.GetNumAtoms(),
        'recorded_atoms': rec.GetNumAtoms(),
        'source_atoms_not_in_mcs_count': source.GetNumAtoms() - res.numAtoms,
        'mcs_smarts': res.smartsString,
    }


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def exact_verified_component(role: str, smiles: str, *, target: str = '', e3: str = '') -> dict[str, Any] | None:
    q = canon(smiles, dummy_to_h=True)
    for comp in vc.components():
        if comp.get('role') != role:
            continue
        if target and (comp.get('target') or '').upper() != target.upper():
            continue
        if e3 and (comp.get('e3_ligase') or '').upper() != e3.upper():
            continue
        if canon(comp.get('canonical_smiles') or comp.get('smiles'), dummy_to_h=True) == q:
            return comp
    return None


def source_backed_component(role: str, smiles: str, *, target: str = '', e3: str = '') -> tuple[bool, str, dict[str, Any] | None]:
    comp = exact_verified_component(role, smiles, target=target, e3=e3)
    if comp:
        return True, f"exact verified component {comp.get('component_id')} from {comp.get('source_protac')}", comp
    return False, 'no exact source-backed binding component match; substructure similarity is insufficient', None


def draw_trace(row: dict[str, Any], out: Path) -> None:
    product = mol(row['full_protac_smiles'])
    wh = mol(row['warhead_smiles'])
    e3 = mol(row['e3_ligand_smiles'])
    lk = mol(row['linker_smiles'])
    ms = [x for x in [product, wh, lk, e3] if x is not None]
    for m in ms:
        for a in m.GetAtoms():
            a.SetProp('atomNote', str(a.GetIdx()))
    legends = ['whole molecule', 'BRD4 binder', 'linker', 'CRBN ligand'][:len(ms)]
    Draw.MolsToGridImage(ms, molsPerRow=2, subImgSize=(700, 380), legends=legends, useSVG=False).save(out)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    IMG.mkdir(parents=True, exist_ok=True)
    df = pd.read_parquet(RUN_DIR / 'candidates.parquet').sort_values('candidate_id')
    evidence_rows = json.loads((TUI_DIR / 'candidate_evidence_table.json').read_text())
    ranks = {r['candidate_id']: r['ranking'] for r in evidence_rows}
    evidence_by_id = {r['candidate_id']: r for r in evidence_rows}
    df['rank'] = df['candidate_id'].map(lambda x: ranks[x]['rank'])
    df = df.sort_values('rank')
    warhead_rows = load_csv(ROOT / 'protacxtend/data/curated_warheads.csv')
    e3_rows = load_csv(ROOT / 'protacxtend/data/curated_e3_ligands.csv')
    warhead_by_name = {r['name']: r for r in warhead_rows}
    e3_by_name = {r['name']: r for r in e3_rows}

    audit_rows = []
    for _, r in df.iterrows():
        ok, assembled, inchikey, reason = assemble_product(r.warhead_smiles, r.linker_smiles, r.e3_ligand_smiles)
        parse_valid = mol(r.full_protac_smiles) is not None
        assembled_as_specified = bool(ok and canon(assembled) == canon(r.full_protac_smiles))
        wh_ok, wh_reason, wh_comp = source_backed_component('warhead', r.warhead_smiles, target='BRD4')
        e3_ok, e3_reason, e3_comp = source_backed_component('e3_ligand', r.e3_ligand_smiles, e3='CRBN')
        e3_glut = has_smarts(r.e3_ligand_smiles, GLUTARIMIDE)
        e3_phth = has_smarts(r.e3_ligand_smiles, PHTHALIMIDE)
        old_substructure_e3_evidence = bool(component_match(r.full_protac_smiles, r.e3_ligand_smiles))
        audit_rows.append({
            'candidate_id': r.candidate_id,
            'rank': int(r['rank']),
            'canonical_smiles': canon(r.full_protac_smiles),
            'isomeric_smiles': canon(r.full_protac_smiles),
            'warhead_name': r.warhead_name,
            'warhead_source': r.warhead_source,
            'warhead_smiles': r.warhead_smiles,
            'e3_ligand_name': r.e3_ligand_name,
            'e3_ligase': r.e3_ligase,
            'e3_ligand_smiles': r.e3_ligand_smiles,
            'linker_name': r.linker_name,
            'linker_smiles': r.linker_smiles,
            'parse_valid': parse_valid,
            'assembled_as_specified': assembled_as_specified,
            'assembly_reaction': 'RDKit molzip over warhead [*:1] + linker [*:1]/[*:2] + E3 [*:1]',
            'assembly_product_matches_record': assembled_as_specified,
            'assembly_failure_reason': reason,
            'source_backed_target_binder': wh_ok,
            'target_binder_identity_reason': wh_reason,
            'source_backed_target_component_id': (wh_comp or {}).get('component_id'),
            'source_backed_e3_ligand': e3_ok,
            'e3_ligand_identity_reason': e3_reason,
            'source_backed_e3_component_id': (e3_comp or {}).get('component_id'),
            'binding_unverified': not (wh_ok and e3_ok),
            'identity_gate_passed': bool(parse_valid and assembled_as_specified and wh_ok and e3_ok),
            'shortlist_nomination_allowed': bool(parse_valid and assembled_as_specified and wh_ok and e3_ok),
            'crbn_glutarimide_pharmacophore_present_in_recorded_e3': e3_glut,
            'phthalimide_like_fragment_present_in_recorded_e3': e3_phth,
            'old_substructure_based_e3_match_in_product': old_substructure_e3_evidence,
            'old_rule_failure_mode': 'would accept recorded E3 substructure/phthalimide-like fragment as topology evidence' if old_substructure_e3_evidence and not e3_ok else '',
            'egfr_binder_in_brd4_pool': 'EGFR' in str(r.warhead_name).upper() or 'EGFR' in str(r.warhead_source).upper(),
        })

    top3 = []
    for _, r in df.head(3).iterrows():
        ev = evidence_by_id[r.candidate_id]
        wsrc = warhead_by_name.get(r.warhead_name, {})
        esrc = e3_by_name.get(r.e3_ligand_name, {})
        image = IMG / f'{r.candidate_id}_atom_trace.png'
        draw_trace(r.to_dict(), image)
        ok, assembled, inchikey, reason = assemble_product(r.warhead_smiles, r.linker_smiles, r.e3_ligand_smiles)
        e3_source_candidates = [x for x in e3_rows if x.get('e3_ligase') == 'CRBN' and 'local_demo' not in (x.get('source') or '')][:8]
        source_comparisons = []
        for src in e3_source_candidates:
            source_comparisons.append({
                'name': src.get('name'), 'source': src.get('source'), 'activity_nM': src.get('activity_nM'),
                'source_smiles': src.get('smiles'),
                'source_has_glutarimide': has_smarts(src.get('smiles'), GLUTARIMIDE),
                'recorded_vs_source_mcs': mcs_missing(src.get('smiles',''), r.e3_ligand_smiles),
            })
        top3.append({
            'candidate_id': r.candidate_id,
            'rank': int(r['rank']),
            'whole_molecule_smiles': r.full_protac_smiles,
            'whole_molecule_atoms': atom_table(r.full_protac_smiles),
            'recorded_brd4_binder': {
                'name': r.warhead_name, 'smiles': r.warhead_smiles, 'source': r.warhead_source,
                'source_record': wsrc, 'dummy_atoms_removed_during_assembly': dummy_atoms(r.warhead_smiles),
                'attachment_atom_recorded': ev.get('attachment_atoms', {}).get('warhead'),
                'product_atom_match_after_assembly': component_match(r.full_protac_smiles, r.warhead_smiles),
            },
            'recorded_crbn_ligand': {
                'name': r.e3_ligand_name, 'smiles': r.e3_ligand_smiles, 'source': esrc.get('source'),
                'source_record': esrc, 'dummy_atoms_removed_during_assembly': dummy_atoms(r.e3_ligand_smiles),
                'attachment_atom_recorded': ev.get('attachment_atoms', {}).get('e3_ligand'),
                'product_atom_match_after_assembly': component_match(r.full_protac_smiles, r.e3_ligand_smiles),
                'has_glutarimide_crbn_pharmacophore': has_smarts(r.e3_ligand_smiles, GLUTARIMIDE),
                'has_phthalimide_like_fragment': has_smarts(r.e3_ligand_smiles, PHTHALIMIDE),
                'source_backed_crbn_binding_identity': source_backed_component('e3_ligand', r.e3_ligand_smiles, e3='CRBN')[0],
                'source_comparisons': source_comparisons,
            },
            'recorded_linker': {'name': r.linker_name, 'smiles': r.linker_smiles, 'dummy_atoms': dummy_atoms(r.linker_smiles)},
            'assembly_reaction': {
                'method': 'RDKit molzip', 'matched_recorded_product': bool(ok and canon(assembled) == canon(r.full_protac_smiles)),
                'assembled_smiles': assembled, 'assembled_inchikey': inchikey, 'failure_reason': reason,
            },
            'final_component_mapping': {
                'warhead_product_atom_indices': component_match(r.full_protac_smiles, r.warhead_smiles),
                'e3_product_atom_indices': component_match(r.full_protac_smiles, r.e3_ligand_smiles),
                'attachment_atoms_component_indices': ev.get('attachment_atoms'),
                'component_smiles': ev.get('component_smiles'),
            },
            'annotated_image': str(image),
            'decision': next(a for a in audit_rows if a['candidate_id'] == r.candidate_id),
        })

    egfr_intrusions = [r for r in audit_rows if r['egfr_binder_in_brd4_pool']]
    counts = Counter()
    for key in ['parse_valid','assembled_as_specified','source_backed_target_binder','source_backed_e3_ligand','binding_unverified','identity_gate_passed','shortlist_nomination_allowed']:
        counts[key] = sum(1 for r in audit_rows if r[key])

    # Rerun verified construction because the frozen run used the wrong demo component library for evidence-backed nomination.
    rec = run_controlled('BRD4-CRBN', run_id='brd4_crbn_verified_dbet1_rerun', out_dir=RERUN_DIR)
    rerun_candidate = rec.candidates[0].model_dump() if rec.candidates else None

    summary = {
        'run_id': RUN_ID,
        'denominator': len(audit_rows),
        'counts': dict(counts),
        'changed_denominators': {
            'previous_structural_audit_identity_gate_passed': '150/150 (old structural/proxy definition)',
            'corrected_identity_gate_passed': f"{counts['identity_gate_passed']}/{len(audit_rows)}",
            'corrected_shortlist_nomination_allowed': f"{counts['shortlist_nomination_allowed']}/{len(audit_rows)}",
            'binding_unverified': f"{counts['binding_unverified']}/{len(audit_rows)}",
        },
        'egfr_binder_entered_brd4_pool': {'count': len(egfr_intrusions), 'candidate_ids': [r['candidate_id'] for r in egfr_intrusions]},
        'crbn_pharmacophore_removed_top3': [
            {'candidate_id': t['candidate_id'], 'removed_or_absent': not t['recorded_crbn_ligand']['has_glutarimide_crbn_pharmacophore'], 'has_phthalimide_like_fragment': t['recorded_crbn_ligand']['has_phthalimide_like_fragment']}
            for t in top3
        ],
        'substructure_validation_failure_mode': {
            'old_rule_would_accept_e3_substructure_count': sum(1 for r in audit_rows if r['old_substructure_based_e3_match_in_product']),
            'old_rule_would_accept_without_source_backed_e3_count': sum(1 for r in audit_rows if r['old_substructure_based_e3_match_in_product'] and not r['source_backed_e3_ligand']),
            'corrected_rule': 'exact source-backed target binder and exact source-backed E3 ligand identity are required; CRBN ligands need not be classical IMiDs if an exact binding source exists',
        },
        'rerun_construction': {
            'required': True,
            'reason': 'frozen run selected local_demo component handles; verified BRD4-CRBN dBET1 component set exists and should be used for evidence-backed reconstruction',
            'artifact_dir': str(RERUN_DIR),
            'status': rec.status,
            'status_reason': rec.status_reason,
            'candidate': rerun_candidate,
        },
        'source_artifacts': {
            'frozen_candidate_table': str(TUI_DIR / 'candidate_evidence_table.json'),
            'frozen_candidates_parquet': str(RUN_DIR / 'candidates.parquet'),
            'curated_warheads': str(ROOT / 'protacxtend/data/curated_warheads.csv'),
            'curated_e3_ligands': str(ROOT / 'protacxtend/data/curated_e3_ligands.csv'),
            'verified_components': str(ROOT / 'protacxtend/data/verified_components.json'),
        }
    }

    def write_csv(path: Path, rows: list[dict[str, Any]]):
        keys = sorted({k for row in rows for k in row})
        with path.open('w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            for row in rows:
                w.writerow({k: json.dumps(v, sort_keys=True) if isinstance(v,(dict,list)) else v for k,v in row.items()})

    (OUT / 'audit_summary.json').write_text(json.dumps(summary, indent=2, sort_keys=True))
    (OUT / 'top3_atom_trace.json').write_text(json.dumps(top3, indent=2, sort_keys=True))
    (OUT / 'all150_component_identity.json').write_text(json.dumps(audit_rows, indent=2, sort_keys=True))
    write_csv(OUT / 'all150_component_identity.csv', audit_rows)
    write_csv(OUT / 'top3_decisions.csv', [t['decision'] for t in top3])
    with (OUT / 'report.md').open('w', encoding='utf-8') as f:
        f.write('# BRD4 x CRBN component identity audit\n\n')
        f.write(f"Frozen run: `{RUN_ID}`\n\n")
        f.write('## Corrected denominators\n\n')
        for k,v in summary['changed_denominators'].items():
            f.write(f'- {k}: {v}\n')
        f.write('\n## Gate counts\n\n')
        for k,v in counts.items():
            f.write(f'- {k}: {v}/{len(audit_rows)}\n')
        f.write('\n## Top-three findings\n\n')
        for t in top3:
            d=t['decision']
            f.write(f"- {t['candidate_id']} rank {t['rank']}: assembled_as_specified={d['assembled_as_specified']}; "
                    f"target_source_backed={d['source_backed_target_binder']}; e3_source_backed={d['source_backed_e3_ligand']}; "
                    f"glutarimide_present={t['recorded_crbn_ligand']['has_glutarimide_crbn_pharmacophore']}; "
                    f"phthalimide_like={t['recorded_crbn_ligand']['has_phthalimide_like_fragment']}; image={t['annotated_image']}\n")
        f.write('\n## EGFR contamination\n\n')
        f.write(f"- EGFR binder entries in BRD4 pool: {len(egfr_intrusions)}/{len(audit_rows)}\n")
        f.write('\n## Rerun construction\n\n')
        f.write(f"- Required: true\n- Status: {rec.status}\n- Artifact dir: `{RERUN_DIR}`\n")
        if rerun_candidate:
            f.write(f"- Top verified structure: {rerun_candidate['candidate_id']} `{rerun_candidate['canonical_smiles']}`\n")
    print(json.dumps({'out_dir': str(OUT), 'summary': summary['changed_denominators'], 'rerun_dir': str(RERUN_DIR)}, indent=2))

if __name__ == '__main__':
    main()
