"""Build data/e3_catalog_v2.csv + data/e3_cell_context_stats.csv.

Sources:
- UniProt GO:0061630 (ubiquitin-protein ligase activity), human, reviewed (374)
- module-6 30-gene catalog (adaptors/ligases not GO-annotated)
- curated_e3_ligands.csv E3 families
- Definite Ligase List / Medvar et al. PubMed:27199454 catalytic ligase table
- The Human E3 Ligome e3Ligome_202508 E3-system roles (Dutta et al. 2025)
- context_joined.csv e3_gene values
DepMap 24Q4 transcriptomics (TPM-log1p, 1,673 cell lines) from the packaged
cache provides per-gene cell-context stats (median/p75/p90/breadth/top lines).
"""
import csv, json, os, sys

ROOT = "/storage/saveena/protacxtend"
OUT_CAT = os.path.join(ROOT, "data", "e3_catalog_v2.csv")
OUT_CTX = os.path.join(ROOT, "data", "e3_cell_context_stats.csv")

rows = []
seen: dict[str, dict] = {}

def add(gene, accession="", entry="", protein_name="", source="", family="", mode=""):
    gene = (gene or "").strip().upper()
    if not gene:
        return
    if gene in seen:
        seen[gene]["sources"] = "|".join(sorted(set(seen[gene]["sources"].split("|") + [source])))
        if accession and not seen[gene]["accession"]:
            seen[gene]["accession"] = accession; seen[gene]["entry"] = entry
        return
    seen[gene] = {"gene": gene, "accession": accession, "entry": entry,
                  "protein_name": protein_name, "sources": source, "family": family, "mode": mode}

# 1) UniProt GO set
if os.path.exists("/tmp/e3_uniprot_go.tsv"):
    with open("/tmp/e3_uniprot_go.tsv") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            add(r.get("gene") or "", r.get("accession", ""), r.get("entry", ""),
                r.get("protein_name", ""), "uniprot_go_0061630 (reviewed)")
else:
    print("WARN: /tmp/e3_uniprot_go.tsv missing; skipping UniProt set", file=sys.stderr)

# 2) module-6 catalog
mod6 = os.path.join(ROOT, "protacxtend/modules/e3_opportunity/data/e3_catalog.csv")
if os.path.exists(mod6):
    with open(mod6) as f:
        for r in csv.DictReader(f):
            add(r.get("gene") or r.get("gene_symbol") or r.get("e3_gene") or "",
                r.get("uniprot", "") or r.get("accession", ""), "", "", "module6_catalog",
                r.get("family", "") or r.get("e3_family", ""), r.get("mode", ""))

# 3) curated e3 ligand families
lig = os.path.join(ROOT, "protacxtend/data/curated_e3_ligands.csv")
if os.path.exists(lig):
    with open(lig) as f:
        for r in csv.DictReader(f):
            e3 = (r.get("e3_ligase") or "").strip().upper()
            if e3 and e3 not in ("CRBN", "VHL"):  # covered by module6
                add(e3, r.get("uniprot", ""), "", "", "curated_e3_ligand_rows")

# 3b) Definite Ligase List (Medvar et al.; PMID:27199454).  This source is a
# catalytic E3 ligase list, not a recruiter-ligand evidence table; do not use it
# to imply PROTAC recruitability or ligand availability.
definite = os.path.join(ROOT, "data", "definite_ligase_list_medvar2016.csv")
if os.path.exists(definite):
    with open(definite) as f:
        for r in csv.DictReader(f):
            add(r.get("gene") or "", r.get("swiss_prot", ""), "",
                r.get("protein_name", ""),
                "definite_ligase_list_medvar2016 (Medvar et al. PMID:27199454)",
                r.get("e3_class", ""), "catalytic_ligase")

# 3c) Human E3 Ligome e3Ligome_202508.  Import E3-system roles only
# (catalytic/receptor/adaptor/scaffold); E1/E2-only rows are intentionally kept
# out of this catalog. Non-catalytic roles are catalogued as components, not as
# evidence of recruiter-ligand availability.
ligome = os.path.join(ROOT, "data", "e3_ligome_202508_systems.csv")
if os.path.exists(ligome):
    with open(ligome) as f:
        for r in csv.DictReader(f):
            add(r.get("gene") or "", r.get("upt_acc", ""), r.get("upt_id", ""), "",
                "e3_ligome_202508 (Dutta et al. Nat Commun 2025; doi:10.1038/s41467-025-67433-4)",
                r.get("cl_type", "") or r.get("class", "") or r.get("cl_name", ""),
                r.get("mode", ""))

# 4) context rows e3_gene
ctx = os.path.join(ROOT, "protacxtend/modules/cell_context_selector/data/context_joined.csv")
if os.path.exists(ctx):
    with open(ctx) as f:
        for r in csv.DictReader(f):
            g = (r.get("e3_gene") or "").strip().upper()
            if g:
                add(g, r.get("e3_uniprot", ""), "", "", "context_degradation_rows")

# DepMap stats
expr_path = os.path.join(ROOT, "outputs/omics_cache/expression_tpmlogp1.csv")
import pandas as pd
expr = pd.read_csv(expr_path, index_col=0)
expr.columns = [c.split(" (")[0].strip() for c in expr.columns]
res = []
for g in seen:
    if g in expr.columns:
        s = expr[g].dropna()
        if len(s) == 0:
            continue
        top = s.sort_values(ascending=False).head(10)
        res.append({"gene": g, "accession": seen[g]["accession"], "entry": seen[g]["entry"],
                    "protein_name": seen[g]["protein_name"], "sources": seen[g]["sources"],
                    "family": seen[g]["family"], "mode": seen[g]["mode"],
                    "n_cell_lines": int(len(s)),
                    "median_tpmlog1p": round(float(s.median()), 3),
                    "p75_tpmlog1p": round(float(s.quantile(0.75)), 3),
                    "p90_tpmlog1p": round(float(s.quantile(0.90)), 3),
                    "max_tpmlog1p": round(float(s.max()), 3),
                    "breadth_gt1tpm": round(float((s > 1.0).mean()), 3),
                    "top10_lines": "|".join(f"{i}:{round(v,2)}" for i, v in top.items())})

with open(OUT_CAT, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(seen.values())[0] if seen else ["gene"])
    w.writeheader()
    for rec in seen.values():
        w.writerow(rec)
with open(OUT_CTX, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(res[0].keys()) if res else ["gene"])
    w.writeheader()
    w.writerows(res)
print(f"catalog genes: {len(seen)} -> {os.path.basename(OUT_CAT)}")
print(f"genes with DepMap context: {len(res)} -> {os.path.basename(OUT_CTX)}")
print("top by median:", sorted(res, key=lambda r: -r['median_tpmlog1p'])[:5])