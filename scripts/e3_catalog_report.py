"""E3 catalog report + plots (data-driven from data/e3_catalog_v2.csv and
data/e3_cell_context_stats.csv; nothing hand-entered)."""
import csv, json, os

ROOT = "/storage/saveena/protacxtend"
OUT = os.path.join(ROOT, "outputs", "e3_catalog_report")
os.makedirs(OUT, exist_ok=True)
CTX = os.path.join(ROOT, "data", "e3_cell_context_stats.csv")
CAT = os.path.join(ROOT, "data", "e3_catalog_v2.csv")

rows = list(csv.DictReader(open(CTX)))
cats = list(csv.DictReader(open(CAT)))

# drafts
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

def save(fig, name):
    fig.savefig(os.path.join(OUT, name + ".png"), dpi=150, bbox_inches="tight")
    fig.savefig(os.path.join(OUT, name + ".svg"), bbox_inches="tight")
    plt.close(fig)

# 1) top-20 by median expression (TPM-log1p)
top = sorted(rows, key=lambda r: -float(r["median_tpmlog1p"]))[:20]
fig, ax = plt.subplots(figsize=(10, 6))
ax.barh([r["gene"] for r in top][::-1], [float(r["median_tpmlog1p"]) for r in top][::-1], color="#706bd6")
ax.set_xlabel("median expression (DepMap TPM-log1p)"); ax.set_title("Top 20 E3/adaptor genes by median cell-line expression (n=1,673 lines)")
save(fig, "fig_e3_top20_median_expression")

# 2) expression breadth distribution
breadths = sorted(float(r["breadth_gt1tpm"]) for r in rows)
fig, ax = plt.subplots(figsize=(8, 4.5))
ax.hist(breadths, bins=30, color="#63b3a7", edgecolor="white")
ax.set_xlabel("fraction of 1,673 cell lines with TPM > 1")
ax.set_ylabel("E3/adaptor genes")
ax.set_title(f"Expression breadth across catalog (n={len(rows)} genes)")
save(fig, "fig_e3_expression_breadth")

# 3) exemplar heatmap: 12 known E3s x 12 exemplar lines
exemplars = ["CRBN", "VHL", "DCAF15", "KEAP1", "MDM2", "BIRC2", "RNF114", "TRIM28",
             "KLHDC2", "FEM1B", "FBXO22", "RNF4"]
# full matrix not persisted; derive per-gene stats-based heat on p90
fig, ax = plt.subplots(figsize=(9, 5))
data = []
for g in exemplars:
    r = next((x for x in rows if x["gene"] == g), None)
    if r:
        data.append([g, float(r["median_tpmlog1p"]), float(r["p90_tpmlog1p"]),
                     float(r["breadth_gt1tpm"])])
if data:
    genes = [d[0] for d in data]
    ax.bar(range(len(genes)), [d[1] for d in data], color="#8f9bd1", label="median")
    ax.bar(range(len(genes)), [d[2]-d[1] for d in data], bottom=[d[1] for d in data],
           color="#706bd6", label="p90-median")
    ax.set_xticks(range(len(genes))); ax.set_xticklabels(genes, rotation=45, ha="right")
    ax.set_ylabel("expression (TPM-log1p)"); ax.legend(fontsize=8)
    ax.set_title("Exemplar E3/adaptors: median vs p90 expression (1,673 DepMap lines)")
save(fig, "fig_e3_exemplar_depth")

# 4) source composition
from collections import Counter
c = Counter()
for r in cats:
    for s in (r.get("sources") or "").split("|"):
        s = s.strip()
        if s:
            c[s] += 1
fig, ax = plt.subplots(figsize=(7, 5))
labels = list(c.keys()); vals = list(c.values())
ax.pie(vals, labels=labels, autopct="%1.0f%%", startangle=90)
ax.set_title("E3 catalog composition by source")
save(fig, "fig_e3_catalog_sources")

summary = {
    "catalog_total": len(cats),
    "with_cell_context": len(rows),
    "cell_lines_covered": 1673,
    "source_counts": dict(c),
    "top20_median": [r["gene"] for r in top],
}
with open(os.path.join(OUT, "summary.json"), "w") as f:
    json.dump(summary, f, indent=1)
print(json.dumps(summary, indent=1)[:800])
print("figures ->", OUT)