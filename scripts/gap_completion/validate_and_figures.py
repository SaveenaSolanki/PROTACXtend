#!/usr/bin/env python3
"""Validation, figure-ready tables and publication figures for the three
remaining capability gaps (BRD/BET, cooperativity, E3 expression atlas).

Everything here is derived from the curated, provenance-carrying tables; no
value is fabricated. Plots use a muted publication style, white background,
600-dpi PNG + vector PDF.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import ListedColormap
from matplotlib.lines import Line2D

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from protacxtend.modules import brd_bet_intelligence as bbi  # noqa: E402
from protacxtend.modules.cooperativity_alpha_predictor import (  # noqa: E402
    calibration as coop_cal,
)
from protacxtend.modules.cooperativity_alpha_predictor import (  # noqa: E402
    load_records,
)
from protacxtend.modules.cooperativity_alpha_predictor import (  # noqa: E402
    predict_cooperativity,
)

OUT = ROOT / "outputs" / "gap_completion"
TABLES = OUT / "tables"
FIGS = OUT / "figures"
TABLES.mkdir(parents=True, exist_ok=True)
FIGS.mkdir(parents=True, exist_ok=True)

# ── publication style ───────────────────────────────────────────────────────
MUTED = ["#4E79A7", "#F28E2B", "#59A14F", "#E15759", "#B07AA1",
         "#76B7B2", "#EDC948", "#9C755F", "#BAB0AC", "#8CD17D"]
DOMAIN_COLOR = {"BD1": "#4E79A7", "BD2": "#E15759", "BD1_BD2": "#76B7B2",
                "unspecified": "#BAB0AC"}
plt.rcParams.update({
    "figure.facecolor": "white", "axes.facecolor": "white",
    "savefig.facecolor": "white", "font.family": "DejaVu Sans",
    "font.size": 9, "axes.edgecolor": "black", "axes.linewidth": 0.8,
    "axes.grid": False, "xtick.color": "black", "ytick.color": "black",
    "axes.labelcolor": "black", "text.color": "black",
    "legend.frameon": False, "savefig.dpi": 600, "pdf.fonttype": 42,
    "ps.fonttype": 42, "figure.dpi": 120,
})


def save(fig, name: str):
    fig.savefig(FIGS / f"{name}.png", dpi=600, bbox_inches="tight")
    fig.savefig(FIGS / f"{name}.pdf", bbox_inches="tight")
    plt.close(fig)
    print(f"  figure -> {name}.png/.pdf")


# ═══════════════════════════════════════════════════════════════════════════
# Figure 1 — BRD/BET ligand / domain selectivity landscape
# ═══════════════════════════════════════════════════════════════════════════
def figure1_brd_landscape():
    ev = bbi.load_evidence()
    ev = ev[ev["domain"].isin(["BD1", "BD2", "BD1_BD2"])].copy()
    ev["p"] = 9 - np.log10(ev["value_nM"].clip(lower=1e-6))
    targets = ["BRD2", "BRD3", "BRD4", "BRDT"]
    fig, axes = plt.subplots(1, 2, figsize=(8.0, 3.9),
                             gridspec_kw={"width_ratios": [1.25, 1]})
    # Panel A: per-domain potency distribution per target
    ax = axes[0]
    rng = np.random.default_rng(0)
    for i, tg in enumerate(targets):
        for dom in ["BD1", "BD2", "BD1_BD2"]:
            sub = ev[(ev.target_gene == tg) & (ev.domain == dom)]
            if sub.empty:
                continue
            x = i + rng.uniform(-0.22, 0.22, len(sub))
            ax.scatter(x, sub["p"], s=14, alpha=0.7, linewidths=0,
                       color=DOMAIN_COLOR[dom], zorder=3)
        med = ev[ev.target_gene == tg]["p"].median()
        ax.plot([i - 0.32, i + 0.32], [med, med], color="black", lw=1.2, zorder=4)
    ax.set_xticks(range(len(targets)))
    ax.set_xticklabels(targets)
    ax.set_ylabel(r"$p$($K_d$/$K_i$/$IC_{50}$)  [nM]")
    ax.set_ylim(3, 11)
    ax.set_title("A  Measured BET potency by domain", loc="left",
                 fontsize=10, fontweight="bold")
    handles = [Line2D([], [], marker="o", ls="", color=DOMAIN_COLOR[d],
                      label=("pan-BD1/BD2" if d == "BD1_BD2" else d))
               for d in ["BD1", "BD2", "BD1_BD2"]]
    ax.legend(handles=handles, loc="lower right", fontsize=8)
    # Panel B: BD2-BD1 delta-p histogram
    pairs = bbi.load_pairs()
    pairs["delta_p"] = (9 - np.log10(pairs["BD2"])) - (9 - np.log10(pairs["BD1"]))
    ax = axes[1]
    bins = np.linspace(-2.6, 4.0, 24)
    ax.hist(pairs["delta_p"], bins=bins, color="#76B7B2", edgecolor="white",
            linewidth=0.6, zorder=3)
    ax.axvline(0, color="black", lw=1.0, ls="--")
    ax.axvline(np.median(pairs["delta_p"]), color="#E15759", lw=1.4)
    n_bd1 = int((pairs["delta_p"] < -0.301).sum())
    n_bd2 = int((pairs["delta_p"] > 0.301).sum())
    n_pan = int(len(pairs) - n_bd1 - n_bd2)
    ax.set_xlabel(r"$\Delta p = pBD2 - pBD1$")
    ax.set_ylabel("BD1/BD2 pairs")
    ax.set_title(f"B  Domain bias (n={len(pairs)})", loc="left",
                 fontsize=10, fontweight="bold")
    ax.text(0.98, 0.95, f"BD2-selective: {n_bd2}\nBD1-selective: {n_bd1}\n"
                        f"pan: {n_pan}", transform=ax.transAxes, ha="right",
            va="top", fontsize=8)
    fig.tight_layout()
    save(fig, "fig1_brd_bet_landscape")
    pairs.to_csv(TABLES / "brd_bet_bd1_bd2_pairs.csv", index=False)
    ev[["ligand_name", "target_gene", "domain", "activity_type", "value_nM",
        "doi"]].to_csv(TABLES / "brd_bet_ligand_landscape.csv", index=False)


# ═══════════════════════════════════════════════════════════════════════════
# Figure 2 — experimental cooperativity distribution & coverage
# ═══════════════════════════════════════════════════════════════════════════
def figure2_cooperativity():
    rec = load_records()
    rec["log10_alpha"] = np.log10(rec["alpha"].clip(lower=1e-6))
    fig, axes = plt.subplots(1, 2, figsize=(8.0, 3.9),
                             gridspec_kw={"width_ratios": [1.1, 1]})
    ax = axes[0]
    ax.hist(rec["log10_alpha"], bins=np.linspace(-2, 3, 26),
            color="#4E79A7", edgecolor="white", linewidth=0.6, zorder=3)
    ax.axvline(0, color="black", lw=1.1, ls="--")
    med = float(rec["log10_alpha"].median())
    ax.axvline(med, color="#E15759", lw=1.4)
    ax.set_xlabel(r"$\log_{10}\alpha$")
    ax.set_ylabel("records")
    ax.set_title(f"A  Cooperativity distribution (n={len(rec)})", loc="left",
                 fontsize=10, fontweight="bold")
    ax.text(0.97, 0.95, f"median $\\alpha$ = {10**med:.2f}\n"
                        f"positive {100*(rec['alpha']>1.25).mean():.0f}%  ·  "
                        f"neutral {100*((rec['alpha']>=0.8)&(rec['alpha']<=1.25)).mean():.0f}%  ·  "
                        f"negative {100*(rec['alpha']<0.8).mean():.0f}%",
            transform=ax.transAxes, ha="right", va="top", fontsize=8)
    # Panel B: per-E3 alpha (log scale) with n labels
    ax = axes[1]
    e3s = rec["e3"].value_counts().index.tolist()
    for i, e3 in enumerate(e3s):
        v = rec[rec.e3 == e3]["alpha"].clip(lower=1e-3)
        x = np.full(len(v), i) + np.random.default_rng(1).uniform(-0.09, 0.09, len(v))
        ax.scatter(x, v, s=20, color=MUTED[i % len(MUTED)], alpha=0.8,
                   linewidths=0, zorder=3)
        ax.plot([i - 0.22, i + 0.22], [v.median(), v.median()], color="black",
                lw=1.2, zorder=4)
        ax.text(i, 1.4e-2, f"n={len(v)}", ha="center", va="bottom", fontsize=8)
    ax.set_yscale("log")
    ax.axhline(1.0, color="black", lw=0.9, ls="--")
    ax.set_xticks(range(len(e3s)))
    ax.set_xticklabels(e3s)
    ax.set_ylabel(r"$\alpha$ (log scale)")
    ax.set_ylim(1e-2, 1e3)
    ax.set_title("B  Coverage by E3", loc="left", fontsize=10,
                 fontweight="bold")
    fig.tight_layout()
    save(fig, "fig2_cooperativity_distribution")
    rec[["protac_id", "poi", "e3", "alpha", "log_alpha", "kd_binary_e3_nM",
         "kd_ternary_nM", "assay", "doi"]].to_csv(
        TABLES / "cooperativity_records.csv", index=False)
    dist = pd.DataFrame([
        {"scope": "all", **{k: v for k, v in
                            coop_cal._dist(rec["alpha"]).items()}},
        *[{"scope": f"E3:{e3}", **coop_cal._dist(g["alpha"])}
          for e3, g in rec.groupby("e3")],
    ])
    dist.to_csv(TABLES / "cooperativity_distribution.csv", index=False)


# ═══════════════════════════════════════════════════════════════════════════
# Figure 3 — predicted vs experimental cooperativity (grouped CV)
# ═══════════════════════════════════════════════════════════════════════════
def figure3_calibration():
    from sklearn.linear_model import Ridge
    rec = load_records()
    head = coop_cal._headline(rec).copy().reset_index(drop=True)
    X = coop_cal._featurize(head).to_numpy(dtype=float)
    y = head["log_alpha"].to_numpy(dtype=float)
    groups = head["poi"].astype(str).tolist()
    preds = np.full(len(y), np.nan)
    for g in sorted(set(groups)):
        te = np.array([i for i, x in enumerate(groups) if x == g])
        tr = np.array([i for i, x in enumerate(groups) if x != g])
        if len(tr) < 4:
            continue
        preds[te] = Ridge(alpha=1.0).fit(X[tr], y[tr]).predict(X[te])
    from protacxtend.modules.cooperativity_alpha_predictor.calibration import (
        _metrics,
    )
    met = _metrics(y, preds)
    base = _metrics(y, np.full(len(y), y[np.isfinite(preds)].mean()))
    fig, ax = plt.subplots(figsize=(4.6, 4.4))
    e3col = {"VHL": "#4E79A7", "CRBN": "#E15759", "cIAP1": "#59A14F"}
    for e3, g in head.groupby("e3"):
        idx = g.index.to_numpy()
        ax.scatter(y[idx], preds[idx], s=34,
                   color=e3col.get(e3, "#9C755F"), alpha=0.85,
                   edgecolor="black", linewidth=0.4, label=e3, zorder=3)
    lim = [min(y.min(), np.nanmin(preds)) - 0.5,
           max(y.max(), np.nanmax(preds)) + 0.5]
    ax.plot(lim, lim, color="black", lw=1.0, ls="--", zorder=2)
    ax.set_xlim(lim)
    ax.set_ylim(lim)
    ax.set_xlabel(r"experimental $\ln\alpha$")
    ax.set_ylabel(r"leave-one-POI-out predicted $\ln\alpha$")
    ax.set_title("Experimental vs predicted cooperativity", fontsize=10,
                 fontweight="bold", loc="left")
    ax.text(0.03, 0.97,
            f"n={met['n']}\n$R^2$={met['r2']:.2f} (baseline {base['r2']:.2f})\n"
            f"RMSE={met['rmse']:.2f}\nSpearman={met['spearman']:.2f}",
            transform=ax.transAxes, va="top", fontsize=8)
    ax.text(0.03, 0.03,
            "Model does not beat the mean baseline;\ncooperativity is served "
            "as a measured-pair / E3 prior,\nnot as a trained prediction.",
            transform=ax.transAxes, va="bottom", fontsize=7.5,
            style="italic", color="#444444")
    ax.legend(loc="lower right", fontsize=8)
    fig.tight_layout()
    save(fig, "fig3_cooperativity_calibration")
    pd.DataFrame({"poi": head["poi"], "e3": head["e3"], "observed_log_alpha": y,
                  "loo_predicted_log_alpha": preds}).to_csv(
        TABLES / "cooperativity_calibration_pairs.csv", index=False)


# ═══════════════════════════════════════════════════════════════════════════
# Figure 4 — E3 expression heatmap (HPA tissue RNA)
# ═══════════════════════════════════════════════════════════════════════════
E3_HEAT = ["CRBN", "VHL", "DDB1", "CUL4A", "MDM2", "KEAP1", "DCAF15",
           "DCAF16", "RNF114", "BIRC2", "BIRC3", "FEM1B", "KLHL20",
           "FBXO22", "UBR1", "HUWE1"]
TISSUE_HEAT = ["bone_marrow", "lymph_node", "spleen", "thymus", "liver",
               "kidney", "lung", "breast", "colon", "prostate", "pancreas",
               "cerebral_cortex", "skin", "testis"]


def figure4_e3_heatmap():
    from protacxtend.modules.e3_opportunity import tissue_atlas
    rna = tissue_atlas.atlas()
    rna._ensure()
    genes = [g for g in E3_HEAT if g in rna.rna.index]
    tissues = []
    for t in TISSUE_HEAT:
        r = rna.resolve_tissue(t)
        if r and r in rna.rna.columns and r not in tissues:
            tissues.append(r)
    mat = rna.rna.loc[genes, tissues].apply(pd.to_numeric, errors="coerce")
    logv = np.log10(mat + 1)
    z = logv.sub(logv.mean(axis=1), axis=0).div(logv.std(axis=1).replace(0, np.nan),
                                                 axis=0)
    fig, ax = plt.subplots(figsize=(8.2, 5.2))
    im = ax.imshow(z.to_numpy(), aspect="auto", cmap="RdBu_r", vmin=-2, vmax=2)
    ax.set_xticks(range(len(tissues)))
    ax.set_xticklabels([t.replace("_", " ") for t in tissues], rotation=45,
                       ha="right", fontsize=8)
    ax.set_yticks(range(len(genes)))
    ax.set_yticklabels(genes, fontsize=8)
    for i in range(len(genes)):
        for j in range(len(tissues)):
            v = mat.iloc[i, j]
            if pd.notna(v):
                ax.text(j, i, f"{v:.0f}", ha="center", va="center", fontsize=5.2,
                        color="black")
    ax.set_title("E3 tissue RNA expression (HPA consensus, nTPM; row z-score)",
                 fontsize=10, fontweight="bold", loc="left")
    cb = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
    cb.set_label("row z-score of log10(nTPM+1)", fontsize=8)
    cb.ax.tick_params(labelsize=7)
    fig.tight_layout()
    save(fig, "fig4_e3_tissue_heatmap")
    mat.to_csv(TABLES / "e3_tissue_expression.csv")


# ═══════════════════════════════════════════════════════════════════════════
# Figure 5 — E3 suitability comparison (BRD4, two contexts)
# ═══════════════════════════════════════════════════════════════════════════
AXIS_LABELS = [("cell_context", "cell-line\n(DepMap)"),
               ("tissue_expression", "tissue\n(HPA)"),
               ("recruiter", "recruiter"),
               ("precedent", "precedent"),
               ("selectivity", "selectivity"),
               ("structure", "structure")]


def _axis_matrix(poi, cell_line=None, tissue=None, e3s=None):
    from protacxtend.modules.e3_opportunity import rank as rank_mod
    rows = {}
    for e3 in e3s:
        ev = rank_mod.evaluate_candidate(poi, e3, cell_line, tissue, None, None, None)
        rows[e3] = {k: (ev["axes"].get(k, {}).get("score")) for k, _ in AXIS_LABELS}
    return pd.DataFrame(rows).T


def figure5_e3_suitability():
    from protacxtend.modules.e3_opportunity import rank_e3_ligases
    e3s = ["VHL", "CRBN", "FEM1B", "BIRC2", "MDM2", "KEAP1", "DCAF15", "RNF114"]
    mats = {}
    for label, kw in [("MM1.S (cell line)", {"cell_line": "MM1.S"}),
                      ("bone marrow (tissue)", {"tissue": "bone marrow"})]:
        out = rank_e3_ligases("BRD4", top_k=20, **kw)
        order = [c["e3_gene"] for c in out["candidates"] if c["e3_gene"] in e3s]
        mats[label] = _axis_matrix("BRD4", e3s=order or e3s,
                                   **({"cell_line": "MM1.S"} if "MM1" in label
                                      else {"tissue": "bone marrow"}))
    fig, axes = plt.subplots(1, 2, figsize=(8.4, 4.2), sharey=False)
    for ax, (label, mat) in zip(axes, mats.items()):
        data = mat[[k for k, _ in AXIS_LABELS]].astype(float)
        im = ax.imshow(data.to_numpy(), aspect="auto", cmap="YlGnBu", vmin=0, vmax=1)
        ax.set_xticks(range(len(AXIS_LABELS)))
        ax.set_xticklabels([lab for _, lab in AXIS_LABELS], fontsize=7.5)
        ax.set_yticks(range(len(data.index)))
        ax.set_yticklabels(data.index, fontsize=8)
        for i in range(data.shape[0]):
            for j in range(data.shape[1]):
                v = data.iloc[i, j]
                if pd.notna(v):
                    ax.text(j, i, f"{v:.2f}", ha="center", va="center",
                            fontsize=6, color="black")
                else:
                    ax.text(j, i, "–", ha="center", va="center", fontsize=7,
                            color="#999999")
        ax.set_title(label, fontsize=9.5, fontweight="bold", loc="left")
    fig.suptitle("BRD4 E3 suitability axes (independently inspectable)",
                 fontsize=10.5, fontweight="bold", x=0.02, ha="left")
    cb = fig.colorbar(im, ax=axes, fraction=0.02, pad=0.02)
    cb.set_label("axis score", fontsize=8)
    cb.ax.tick_params(labelsize=7)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    save(fig, "fig5_e3_suitability")
    for label, mat in mats.items():
        mat.to_csv(TABLES / f"e3_suitability_{label.split()[0].replace('.', '')}.csv")


# ═══════════════════════════════════════════════════════════════════════════
# Figure 6 — evidence coverage: measured vs proxy vs absent
# ═══════════════════════════════════════════════════════════════════════════
def figure6_evidence_coverage():
    from protacxtend.modules.e3_opportunity import recruiters
    from protacxtend.modules.e3_opportunity import tissue_atlas
    from protacxtend.modules.e3_opportunity import dataset as e3ds
    from protacxtend.modules.e3_opportunity.e3_catalog import load_catalog
    cat = load_catalog()
    genes = list(cat["e3_gene"])
    rec = load_records()
    coop_e3 = set(rec["e3"].unique())
    columns = ["DepMap\ncell-line", "HPA tissue\nRNA", "HPA tissue\nIHC",
               "HPA tissue\nMS", "DOI-cited\nrecruiter", "measured\nprecedent",
               "measured\ncooperativity"]
    ta = tissue_atlas.atlas()
    ta._ensure()
    from protacxtend.modules.e3_opportunity.tissue_atlas import GENE_ALIASES
    pairs = e3ds.load_benchmark_pairs()
    precedent_genes = set(pairs["e3_gene"].unique())
    rows = []
    for g in genes:
        rec_info = recruiters.recruiter_info(g)
        gx = GENE_ALIASES.get(g, g)
        vals = [
            float(gx in _e3_lookup_matrix().columns),
            float(gx in ta.rna.index) if ta.rna is not None else 0.0,
            float(gx in ta.ihc.index) if ta.ihc is not None else 0.0,
            float(gx in ta.ms.index) if ta.ms is not None else 0.0,
            float(rec_info.get("n_cited_ligands", 0) > 0),
            float(g in precedent_genes),
            float(g in coop_e3),
        ]
        rows.append([g] + vals)
    df = pd.DataFrame(rows, columns=["E3"] + columns)
    data = df[columns].to_numpy(dtype=float)
    order = np.argsort(-data.sum(axis=1))
    df = df.iloc[order].reset_index(drop=True)
    data = data[order]
    fig, ax = plt.subplots(figsize=(6.2, 8.0))
    cmap = ListedColormap(["#F0F0F0", "#4E79A7"])
    ax.imshow(data, aspect="auto", cmap=cmap, vmin=0, vmax=1)
    ax.set_xticks(range(len(columns)))
    ax.set_xticklabels(columns, rotation=45, ha="right", fontsize=7.5)
    ax.set_yticks(range(len(df)))
    ax.set_yticklabels(df["E3"], fontsize=7)
    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            if data[i, j] == 0:
                ax.text(j, i, "–", ha="center", va="center", fontsize=6,
                        color="#999999")
    ax.set_title("Evidence coverage: measured vs absent (catalog E3s)",
                 fontsize=10, fontweight="bold", loc="left")
    handles = [Line2D([], [], marker="s", ls="", color="#4E79A7",
                      label="measured / available"),
               Line2D([], [], marker="s", ls="", color="#F0F0F0",
                      markeredgecolor="#999999", label="absent (not fabricated)")]
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(0, -0.13),
              ncol=2, fontsize=8)
    fig.tight_layout()
    save(fig, "fig6_evidence_coverage")
    df.to_csv(TABLES / "evidence_coverage.csv", index=False)


def context_has_depmap(gene):
    from protacxtend.modules.e3_opportunity import context as e3ctx
    try:
        m = _e3_lookup_matrix()
        return gene in m.columns
    except Exception:
        return False


def _e3_lookup_matrix():
    from protacxtend.modules.e3_opportunity import context as e3ctx
    return e3ctx.lookup()._ensure()


# ═══════════════════════════════════════════════════════════════════════════
# Figure 7 — before vs after ranking for BRD4-VHL / BRD4-CRBN
# ═══════════════════════════════════════════════════════════════════════════
def _coop_score(alpha):
    if alpha is None or alpha <= 0:
        return 0.0
    return float(np.clip(np.log10(alpha) / 1.5, 0.0, 1.0))


def _collect_candidates():
    from protacxtend.modules.e3_opportunity import rank_e3_ligases
    cands = [("BRD4 · JQ1 · VHL", "JQ1", "VHL", "MM1.S"),
             ("BRD4 · JQ1 · CRBN", "JQ1", "CRBN", "MM1.S"),
             ("BRD4 · ABBV-744 · VHL", "ABBV-744", "VHL", "MM1.S"),
             ("BRD4 · ABBV-744 · CRBN", "ABBV-744", "CRBN", "MM1.S")]
    out = []
    rank_cache = {}
    for label, wh, e3, cell in cands:
        if cell not in rank_cache:
            rank_cache[cell] = {c["e3_gene"]: c for c in
                                rank_e3_ligases("BRD4", cell_line=cell,
                                                top_k=30)["candidates"]}
        bet = bbi.score_brd_bet("BRD4", warhead_name=wh)
        coop = predict_cooperativity(protac=wh, poi="BRD4", e3=e3)
        rc = rank_cache[cell].get(e3, {})
        after_bet = bet.get("score")
        after_e3 = (rc.get("tissue_expression_score") or rc.get("cell_context_score"))
        # combined E3 suitability: DePMap cell context + HPA tissue (if any)
        e3_components = [v for v in [rc.get("cell_context_score"),
                                     rc.get("tissue_expression_score")] if v is not None]
        after_e3_ctx = float(np.mean(e3_components)) if e3_components else None
        after_coop = _coop_score(coop.predicted_alpha)
        out.append({
            "candidate": label, "warhead": wh, "e3": e3, "cell_line": cell,
            "before_bet": 0.5, "after_bet": after_bet,
            "before_e3": rc.get("cell_context_score"), "after_e3": after_e3_ctx,
            "before_coop": 0.5, "after_coop": after_coop,
            "coop_alpha": coop.predicted_alpha,
            "coop_confidence": coop.confidence,
            "coop_evidence": coop.uncertainty.get("evidence_level"),
            "bet_evidence": bet.get("evidence_level"),
            "bet_domain_class": (bet.get("domain_selectivity") or {}).get("domain_class"),
            "e3_verdict": rc.get("verdict"),
            "e3_overall": rc.get("overall_rank_score"),
        })
    return pd.DataFrame(out)


def figure7_before_after():
    df = _collect_candidates()
    df.to_csv(TABLES / "before_after_ranking.csv", index=False)
    comps = [("BRD selectivity", "before_bet", "after_bet"),
             ("E3 suitability", "before_e3", "after_e3"),
             ("Cooperativity", "before_coop", "after_coop")]
    fig, axes = plt.subplots(1, 2, figsize=(9.0, 4.2),
                             gridspec_kw={"width_ratios": [1.4, 1]})
    # Panel A: slope per component (mean over candidates)
    ax = axes[0]
    for k, (name, b, a) in enumerate(comps):
        for _, r in df.iterrows():
            bv, av = r[b], r[a]
            if pd.isna(bv) or pd.isna(av):
                continue
            ax.plot([0, 1], [bv, av], color=MUTED[k], alpha=0.45, lw=1.2,
                    marker="o", ms=3.5)
        ax.plot([0, 1], [df[b].mean(), df[a].mean()], color=MUTED[k], lw=2.6,
                marker="o", ms=6, label=name, zorder=5)
    ax.set_xlim(-0.25, 1.25)
    ax.set_ylim(0, 1.02)
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["before\n(generic proxy)", "after\n(curated evidence)"])
    ax.set_ylabel("component score")
    ax.set_title("A  Evidence components before vs after", loc="left",
                 fontsize=10, fontweight="bold")
    ax.legend(loc="center left", fontsize=8)
    # Panel B: overall composite ranking before/after
    ax = axes[1]
    df["overall_before"] = df[["before_bet", "before_e3", "before_coop"]].mean(axis=1)
    df["overall_after"] = df[["after_bet", "after_e3", "after_coop"]].mean(axis=1)
    y = np.arange(len(df))
    ax.hlines(y, df["overall_before"], df["overall_after"], color="#BAB0AC", lw=2)
    ax.scatter(df["overall_before"], y, color="#9C755F", s=42, zorder=3,
               label="before")
    ax.scatter(df["overall_after"], y, color="#4E79A7", s=42, zorder=3,
               label="after")
    for i, r in df.iterrows():
        ax.text(r["overall_after"] + 0.015, i, f"Δ={r['overall_after']-r['overall_before']:+.2f}",
                va="center", fontsize=7)
    ax.set_yticks(y)
    ax.set_yticklabels(df["candidate"], fontsize=7.5)
    ax.set_xlim(0.3, 1.02)
    ax.set_xlabel("illustrative composite priority")
    ax.set_title("B  Overall priority change", loc="left", fontsize=10,
                 fontweight="bold")
    ax.legend(loc="lower right", fontsize=8)
    fig.tight_layout()
    save(fig, "fig7_before_after")
    return df


def main():
    print("Building figure-ready tables and figures ...")
    figure1_brd_landscape()
    figure2_cooperativity()
    figure3_calibration()
    figure4_e3_heatmap()
    figure5_e3_suitability()
    figure6_evidence_coverage()
    df7 = figure7_before_after()
    print("\nBefore/after summary:")
    cols = ["candidate", "before_bet", "after_bet", "bet_evidence",
            "before_e3", "after_e3", "e3_verdict", "before_coop", "after_coop",
            "coop_alpha", "coop_confidence", "coop_evidence"]
    print(df7[cols].to_string(index=False))
    (OUT / "validation_summary.json").write_text(
        json.dumps(df7.to_dict(orient="records"), indent=2, default=str))


if __name__ == "__main__":
    main()
