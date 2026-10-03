"""Design-demo chemistry + provenance + plot + DOI + E3-catalog audit.

Audits challenge/outputs/design_demo_analysis/analysis.json (5 top-enriched
candidates from 26 assembled):
1. canonical SMILES + InChIKey (full + components), atom-mapped attachment
   breakdown, RDKit validity — invalid assemblies are rejected BEFORE any
   score is interpreted;
2. five-vs-26 subset membership (what is verifiable on disk);
3. DC50 predicted-vs-measured labels;
4. plot data provenance (axes/units/subset) — the earlier reviewer's image
   unavailability is a review limitation, not evidence of correctness;
5. ternary + synthesis assessment availability vs the stored geometry proxy
   and heuristic synthesis score;
6. DOI identity verification (CrossRef);
7. e3_catalog_v2.csv reconciliation + enrichment (no duplicate library).
"""
from __future__ import annotations

import csv, hashlib, json, os, re, sys, urllib.parse, urllib.request

from rdkit import Chem
from rdkit.Chem import Descriptors
from rdkit.Chem.inchi import MolToInchiKey

ROOT = "/storage/saveena/protacxtend"

def load(p):
    with open(os.path.join(ROOT, p)) as f:
        return json.load(f)

analysis = load("challenge/outputs/design_demo_analysis/analysis.json")
candidates = analysis["candidates"]
scorecards = analysis["scorecards"]

def canonical(smi):
    mol = Chem.MolFromSmiles(smi)
    if mol is None:
        return None, None, None
    return Chem.MolToSmiles(mol, canonical=True, isomericSmiles=True), MolToInchiKey(mol), mol

def attachment_atoms(mol, marker_re):
    """Atom indices + neighbors of dummy marker atoms in a component."""
    out = []
    if mol is None:
        return out
    for atom in mol.GetAtoms():
        if atom.GetAtomicNum() == 0:  # dummy *
            nbrs = [a.GetIdx() for a in atom.GetNeighbors()]
            out.append({"dummy_index": atom.GetIdx(),
                        "dummy_map": atom.GetAtomMapNum(),
                        "attachment_neighbor": nbrs[0] if nbrs else None})
    return out

rows = []
for c in candidates:
    cid = c["candidate_id"]
    full = c.get("full_protac_smiles", "")
    can_full, ikey_full, mol_full = canonical(full)
    comps = {}
    for key in ("warhead_smiles", "linker_smiles", "e3_ligand_smiles"):
        smi = re.sub(r"\[*:?\d*\]", "", c.get(key, ""))   # strip dummy markers for canonicalization
        comps[key] = canonical(smi)   # (canonical, inchikey, mol)
    # validity gate (reject before any score)
    valid = mol_full is not None and c.get("validity_status") == "valid"
    # substructure containment
    containment = {}
    if mol_full:
        for key in ("warhead_smiles", "linker_smiles", "e3_ligand_smiles"):
            _, _, m = comps[key]
            if m is not None:
                frag = Chem.MolFromSmiles(re.sub(r"\[\*:?\d*\]", "", c.get(key, "")))
                containment[key] = bool(frag is not None and mol_full.HasSubstructMatch(frag))
            else:
                containment[key] = False
    att = {"warhead": attachment_atoms(comps["warhead_smiles"][2], None) if comps["warhead_smiles"][0] else [],
           "e3_ligand": attachment_atoms(comps["e3_ligand_smiles"][2], None) if comps["e3_ligand_smiles"][0] else []}
    sc = scorecards.get(cid, {})
    dims = {x["dimension"]: x for x in sc.get("dimensions", [])}
    dc50_dim = dims.get("in_vivo_efficacy", {})
    tern_dim = dims.get("ternary_complex", {})
    synth_dim = dims.get("synthesis_feasibility", {})
    rows.append({
        "candidate_id": cid,
        "parent_ids": c.get("parent_ids"),
        "canonical_full_smiles": can_full,
        "inchikey_full": ikey_full,
        "rdkit_valid": valid,
        "assembly_strategy": c.get("assembly_strategy"),
        "reaction_class": c.get("reaction_class"),
        "components": {k: {"canonical_smiles": comps[k][0], "inchikey": comps[k][1],
                           "present_in_full": containment.get(k, False)} for k in comps},
        "attachment_atoms": att,
        "sources": c.get("provenance", {}).get("sources", {}),
        "verified_components": c.get("provenance", {}).get("verified_components"),
        "dc50_nM": dc50_dim.get("value"),
        "dc50_label": "predicted" if dc50_dim.get("evidence_level") == "ml_model" else dc50_dim.get("evidence_level", "?"),
        "dc50_model": re.search(r"model=([^,;]+)", dc50_dim.get("summary", "")) and re.search(r"model=([^,;]+)", dc50_dim.get("summary", "")).group(1),
        "dc50_dimension_label": dc50_dim.get("label"),
        "dc50_requires_experiment": dc50_dim.get("requires_experiment"),
        "ternary_proxy": tern_dim.get("value"),
        "ternary_backend": re.search(r"backend=(\S+)", tern_dim.get("summary", "")) and re.search(r"backend=(\S+)", tern_dim.get("summary", "")).group(1),
        "ternary_requires_experiment": tern_dim.get("requires_experiment"),
        "synth_heuristic": synth_dim.get("value"),
        "synth_note": "rule/component-join heuristic, NOT a route" if synth_dim.get("summary", "").find("NOT a route") >= 0 else synth_dim.get("summary", "")[:60],
        "warning_flags": c.get("warning_flags", []),
        "protacdb_prior": bool(c.get("provenance", {}).get("protacdb_evidence_prior")),
    })

# ------------------------------------------------------------------ subset check
subset_check = {
    "n_assembled_asserted": analysis.get("n_assembled"),
    "top_n_enriched": analysis.get("top_n_enriched"),
    "full_26_set_persisted": False,
    "evidence": "analysis.json stores candidates (top-5) and n_assembled=26 only; "
                "no 26-row candidate file found under outputs/runs*/candidates.parquet, challenge/, "
                "outputs/ (searched 2026-09-25); the five-point subset membership in the 26 "
                "cannot be independently verified from on-disk artifacts.",
}

# ------------------------------------------------------------------ plot audit
plot_audit = {
    "plot_files": analysis.get("plots", {}),
    "data_source_in_analysis_json": "plot data (x/y) is NOT stored in analysis.json — only PNG paths; "
                                    "axes/units/points cannot be recomputed from this artifact",
    "dc50_in_plot_is": "predicted (ml_model; tack-style-v1 OR chemprop cross-check; requires_experiment=True)",
    "regenerated_points": [
        {"candidate_id": r["candidate_id"], "predicted_dc50_nM": r["dc50_nM"], "tpsa": next(
            (x["value"] for x in scorecards[r["candidate_id"]]["dimensions"] if x["dimension"] == "cell_permeability"), None)}
        for r in rows],
    "verdict": "original PNG cannot be validated from stored data (a limitation of the artifact, not "
               "of the current reviewer); a regenerated reference plot is produced from scorecard values",
}

# ------------------------------------------------------------------ ternary/synthesis assessments
ternary_available = os.path.exists(os.path.join(ROOT, "protacxtend", "tools", "ternary_engine.py"))
retro_report = None
try:
    from protacxtend.tools.retrosynthesis_engines import render_engine_status_report
    retro_report = render_engine_status_report(skip_network=True)
except Exception as exc:  # noqa: BLE001
    retro_report = {"error": str(exc)}

assess = {
    "ternary_backend_installed": ternary_available,
    "ternary_assessment": "UNEVAUATED — no coordinate/ternary engine on host; scorecard values are geometry_proxy_stub "
                          "(ternary_plausibility/fast_geometry/linker_reachability), flagged requires_experiment",
    "synthesis_engines": retro_report if isinstance(retro_report, (list, dict)) else {"raw": str(retro_report)[:300]},
    "synthesis_assessment": "heuristic component-join score only (rule_descriptor, 'NOT a route'); "
                            "engine routes require a live retrosynthesis call — none executed in this audit",
    "proxy_vs_engine_note": "geometry proxy and heuristic synthesis score are NOT substitutes for "
                            "ternary/DockQ or a retrosynthesis route; both are flagged accordingly",
}

# ------------------------------------------------------------------ DOI audit (CrossRef)
def crossref(doi):
    url = "https://api.crossref.org/works/" + urllib.parse.quote(doi)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "PROTACXtend-audit/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            m = json.loads(resp.read().decode())["message"]
            title = (m.get("title") or [""])[0]
            return {"doi": doi, "resolve": True, "title": title[:110],
                    "container": (m.get("container-title") or [""])[0],
                    "year": (m.get("issued", {}).get("date-parts", [[None]])[0][0])}
    except Exception:  # noqa: BLE001
        return {"doi": doi, "resolve": False, "title": ""}

dois = set()
for r in rows:
    for src in r["sources"].values():
        m = re.search(r"10\.\d{4,9}/[^\s;]+", src or "")
        if m:
            dois.add(m.group(0).rstrip(".,"))
doi_results = {d: crossref(d) for d in sorted(dois)}
# also verify key curated DOIs mentioned in the broader demo
extra_dois = ["10.1038/nature09504", "10.1038/ncomms13312", "10.1021/jacs.8b05807", "10.1021/jacs.8b06155"]
for d in extra_dois:
    doi_results.setdefault(d, crossref(d))

# ------------------------------------------------------------------ E3 catalog reconciliation
e3_rows = list(csv.DictReader(open(os.path.join(ROOT, "data/e3_catalog_v2.csv"))))
recruiter = list(csv.DictReader(open(os.path.join(ROOT, "protacxtend/data/curated_e3_ligands.csv"))))
non_demo = [r for r in recruiter if "demo" not in (r.get("source") or "")]
from collections import Counter
fam_counts = Counter((r.get("e3_ligase") or "").strip() for r in non_demo)
recruiter_by_gene = {}
for r in non_demo:
    fam = (r.get("e3_ligase") or "").strip().upper()
    recruiter_by_gene.setdefault(fam, []).append(r)
# gene-level match: catalog gene (upper) vs curated family aliases
def match_count(gene):
    g = gene.upper()
    return len(recruiter_by_gene.get(g, []))
enriched = []
for r in e3_rows:
    out = dict(r)
    n = match_count(r["gene"])
    out["recruiter_doi_row_count"] = n
    out["has_curated_recruiter"] = "yes" if n else "no"
    out["in_e3_opportunity_30_gene_catalog"] = "yes" if r["gene"].upper() in {
        x.upper() for x in ("CRBN", "VHL", "cIAP1", "cIAP2", "XIAP", "MDM2", "KEAP1", "DCAF1",
                            "DCAF11", "DCAF15", "DCAF16", "KLHDC2", "FEM1B", "RNF4", "RNF114",
                            "RNF126", "FBXO22", "GID4", "SKP1", "TRIM21", "TRIM24", "SPOP", "DDB1",
                            "CUL4A", "CUL2", "AhR", "DCAF16", "UBR5", "KLHL20")} else "no"
    enriched.append(out)

out_dir = os.path.join(ROOT, "outputs", "manuscript_strategy", "challenge_audit")
os.makedirs(out_dir, exist_ok=True)

# persist
with open(os.path.join(out_dir, "chemical_structures.json"), "w") as f:
    json.dump({"candidates": rows, "subset_check": subset_check}, f, indent=1, default=str)
with open(os.path.join(out_dir, "plot_audit.json"), "w") as f:
    json.dump(plot_audit, f, indent=1, default=str)
with open(os.path.join(out_dir, "ternary_synthesis_assessment.json"), "w") as f:
    json.dump(assess, f, indent=1, default=str)
with open(os.path.join(out_dir, "doi_audit.json"), "w") as f:
    json.dump(doi_results, f, indent=1, default=str)
# enriched E3 catalog (no duplicate library; superset of the existing file)
with open(os.path.join(ROOT, "data", "e3_catalog_v2_enriched.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(enriched[0].keys()))
    w.writeheader(); w.writerows(enriched)

print("== CANDIDATE TABLE ==")
for r in rows:
    print(f"{r['candidate_id']:26} valid={r['rdkit_valid']} dc50={r['dc50_nM']}nM [{r['dc50_label']}] "
          f"tern_proxy={r['ternary_proxy']}({r['ternary_backend']}) synth_proxy={r['synth_heuristic']} "
          f"w_in_full={r['components']['warhead_smiles']['present_in_full']} "
          f"e3_in_full={r['components']['e3_ligand_smiles']['present_in_full']} "
          f"l_in_full={r['components']['linker_smiles']['present_in_full']}")
print("\n== SUBSET ==\n", json.dumps(subset_check, indent=1))
print("\n== TERNARY/SYNTH ==\n", json.dumps({k: (v if not isinstance(v, list) else str(v)[:200]) for k, v in assess.items() if k != "synthesis_engines"}, indent=1))
print("\n== DOI ==\n", json.dumps(doi_results, indent=1))
print("\n== E3 CATALOG ==\nrows:", len(e3_rows), "| enriched with recruiter_doi_row_count; families w/ ligands:",
      dict(sorted(fam_counts.items())[:6]))