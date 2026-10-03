"""E3 catalog audit: catalytic E3 vs E2 vs substrate receptor/adaptor/complex
component; provenance; recruiter ligand evidence; cell-context coverage.

Heuristic classification is documented ("classifier" column = rule name);
manual curation is required to finalize, and counts are never a correctness
claim without row review.
"""
import csv, json, os, re

ROOT = "/storage/saveena/protacxtend"
OUT = os.path.join(ROOT, "outputs", "audit_b1_e3")
os.makedirs(OUT, exist_ok=True)
CAT = os.path.join(ROOT, "data", "e3_catalog_v2.csv")
CTX = os.path.join(ROOT, "data", "e3_cell_context_stats.csv")
LIG = os.path.join(ROOT, "protacxtend/data/curated_e3_ligands.csv")

cata = list(csv.DictReader(open(CAT)))
ctx = {r["gene"]: r for r in csv.DictReader(open(CTX))}

recruiters = set()
if os.path.exists(LIG):
    for r in csv.DictReader(open(LIG)):
        e3 = (r.get("e3_ligase") or "").strip().upper()
        src = (r.get("source") or "")
        doi = (r.get("article_doi") or "").strip()
        if e3 and "demo" not in src and doi:
            recruiters.add(e3)

NAME = {"CRBN", "VHL", "KEAP1", "KLHL20", "KLHDC2", "DCAF1", "DCAF11", "DCAF15",
        "DCAF16", "FEM1B", "FBXO22", "KLHL2", "KLHL3", "SPOP", "LRRK2", "FBXW7",
        "BTRC", "FBXW11", "SKP1", "CUL1", "CUL2", "CUL3", "CUL4A", "CUL4B", "CUL5",
        "RBX1", "DDB1", "DDB2", "TCEB1", "TCEB2", "WDR26", "WDR23", "DCAF7", "DCAF12"}
_FAM = {"HECT": ("HECTD", "NEDD4", "SMURF", "WWP", "ITCH", "HECW", "HUWE1"),
        "RBR": ("ARIH1", "ARIH2", "PARK2", "RNF216"),
        "U-box": ("STUB1", "UIP5", "PRP19", "CHIP")}

def classify(g, name, family, mode):
    nm = (name or "").lower(); fam = (family or "").lower(); mo = (mode or "").lower()
    if "ubiquitin-conjugating enzyme" in nm or "e2" in nm.split(" ", 1)[0:0] or g.startswith("UBE") or "ubiquitin carrier protein" in nm:
        return "e2_enzyme", "name_e2"
    if "ubiquitin ligase" in nm or "ubiquitin-protein ligase" in nm:
        if "ring" in fam or g.startswith(("RNF", "RING", "TRIM", "PIA", "BRCA", "MDM", "CBLC", "CBL", "MGRN", "RCHY", "LNX", "PDZRN", "DTX", "MIB", "NEURL", "APC11", "RAG1")):
            return "catalytic_e3_ring", "ring_by_name_or_symbol"
        if any(g.startswith(p) for p in _FAM["HECT"]):
            return "catalytic_e3_hect", "hect_symbol"
        if any(g.startswith(p) for p in _FAM["RBR"]):
            return "catalytic_e3_rbr", "rbr_symbol"
        if any(g.startswith(p) for p in _FAM["U-box"]) or "u-box" in nm:
            return "catalytic_e3_ubox", "ubox"
        return "catalytic_e3_unclassified_mode", "name_e3"
    if "substrate receptor" in nm or "adaptor" in nm or "f-box" in nm or "btb" in nm:
        return "substrate_receptor_adaptor", "name_adaptor"
    if mo in ("crl4_adapter", "crl2_adapter", "crl3_adapter", "scf_fbox"):
        return "substrate_receptor_adaptor", "module6_mode"
    if g in NAME:
        return "substrate_receptor_adaptor", "curated_named_adaptor"
    if "component" in nm or "subunit" in nm or "complex" in nm:
        return "complex_component", "name_component"
    if g.startswith(("RNF", "TRIM", "RING", "MARCH", "MEX3", "PJA", "STUB", "RCHY", "RAG1", "RNF216")):
        return "catalytic_e3_ring", "symbol_ring_family"
    return "unclassified", "default"

rows = []
for r in cata:
    g = r["gene"]
    role, rule = classify(g, r.get("protein_name", ""), r.get("family", ""), r.get("mode", ""))
    c = ctx.get(g, {})
    rows.append({
        "gene": g, "accession": r.get("accession", ""), "entry": r.get("entry", ""),
        "protein_name": r.get("protein_name", ""), "role": role, "classifier": rule,
        "family": r.get("family", ""), "mode": r.get("mode", ""),
        "sources": r.get("sources", ""),
        "has_recruiter_ligand": "yes" if g in recruiters else "no",
        "context_lines": c.get("n_cell_lines", "0"),
        "median_tpmlog1p": c.get("median_tpmlog1p", ""),
        "breadth_gt1tpm": c.get("breadth_gt1tpm", ""),
    })

with open(os.path.join(OUT, "e3_audit.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader(); w.writerows(rows)

from collections import Counter
role_c = Counter(r["role"] for r in rows)
rec_c = Counter(r["has_recruiter_ligand"] for r in rows)
prod_src = Counter(s.strip() for r in rows for s in r["sources"].split("|") if s.strip())
n_ctx = sum(1 for r in rows if int(r["context_lines"] or 0) > 0)
summary = {"catalog_total": len(rows), "by_role": dict(role_c),
           "recruiter_evidence": dict(rec_c), "with_cell_context": n_ctx,
           "source_counts": dict(prod_src)}
with open(os.path.join(OUT, "e3_audit_summary.json"), "w") as f:
    json.dump(summary, f, indent=1)
print(json.dumps(summary, indent=1))
print("\nexamples catalytic:", [r["gene"] for r in rows if r["role"].startswith("catalytic_e3_ring")][:8])
print("examples adaptor:", [r["gene"] for r in rows if r["role"] == "substrate_receptor_adaptor"][:8])
print("examples e2:", [r["gene"] for r in rows if r["role"] == "e2_enzyme"][:6])
print("recruiter-ligand genes:", sorted(recruiters & {r['gene'] for r in rows}))