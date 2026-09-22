"""Publication-quality figures for the validation benchmarks.

Reads the raw benchmark rows/summaries and writes PNG + PDF + SVG plus a CSV of
the plotted values.  The module is deliberately defensive: a missing benchmark
produces a labelled placeholder rather than a crash, so the one-command runner
always succeeds and reports what was actually measured.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from protacxtend.validation.datasets import ROOT  # noqa: E402

BENCH = ROOT / "results" / "benchmarks"
OUT = ROOT / "results" / "figures_validation"
OUT.mkdir(parents=True, exist_ok=True)

PALETTE = {"vina": "#4C72B0", "gnina": "#DD8452", "diffdock": "#55A868",
           "prospective_consensus": "#8172B3", "oracle": "#937860",
           "lightdock": "#C44E52", "native_control": "#64B5CD",
           "rigid_decoy": "#CCB974", "primary": "#4C72B0", "fallback": "#55A868"}

plt.rcParams.update({
    "figure.dpi": 150, "savefig.dpi": 300, "font.size": 10,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.alpha": 0.25, "grid.linestyle": "--",
})


def _load(rel: str) -> Any:
    try:
        return json.loads((BENCH / rel).read_text())
    except Exception:
        return None


def _rows(rel: str) -> list[dict[str, Any]]:
    path = BENCH / rel
    if not path.exists():
        return []
    try:
        return list(csv.DictReader(path.open()))
    except Exception:
        return []


def _num(v: Any) -> float | None:
    try:
        if v in ("", None, "None", "nan"):
            return None
        return float(v)
    except Exception:
        return None


def _save(fig, name: str, csv_rows: list[dict[str, Any]] | None = None) -> None:
    fig.tight_layout()
    for ext in ("png", "pdf", "svg"):
        fig.savefig(OUT / f"{name}.{ext}", bbox_inches="tight")
    plt.close(fig)
    if csv_rows:
        keys: list[str] = []
        for r in csv_rows:
            for k in r:
                if k not in keys:
                    keys.append(k)
        with (OUT / f"{name}.csv").open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=keys)
            w.writeheader()
            w.writerows(csv_rows)
    print(f"[figures] wrote {name}")


def _placeholder(name: str, title: str, message: str = "benchmark not available") -> None:
    fig, ax = plt.subplots(figsize=(6, 3.5))
    ax.text(0.5, 0.5, message, ha="center", va="center", transform=ax.transAxes)
    ax.set_title(title)
    ax.axis("off")
    _save(fig, name)


# ── docking ─────────────────────────────────────────────────────────────

def docking_figures() -> None:
    summary = _load("docking/docking_summary.json")
    if not summary:
        _placeholder("fig01_docking_rmsd", "Docking RMSD distribution")
        return
    engines = ["vina", "gnina", "diffdock", "prospective_consensus", "oracle"]
    engines = [e for e in engines if summary.get(e)]
    # RMSD strip + box
    fig, ax = plt.subplots(figsize=(7, 4))
    data, labels, colors = [], [], []
    csv_rows = []
    for e in engines:
        vals = [float(v) for v in (summary.get(e, {}).get("rmsd_distribution") or [])]
        if not vals:
            continue
        data.append(vals)
        labels.append(e)
        colors.append(PALETTE.get(e, "#888888"))
        for v in vals:
            csv_rows.append({"engine": e, "rmsd": v})
    if data:
        bp = ax.boxplot(data, labels=labels, patch_artist=True, showfliers=False, widths=0.55)
        for patch, color in zip(bp["boxes"], colors):
            patch.set_facecolor(color)
            patch.set_alpha(0.6)
        rng = np.random.default_rng(3)
        for i, vals in enumerate(data, start=1):
            ax.scatter(np.full(len(vals), i) + rng.normal(0, 0.06, len(vals)), vals,
                       s=14, color=colors[i - 1], edgecolor="black", linewidth=0.2, zorder=3)
        ax.axhline(2.0, color="green", ls="--", lw=1, label="2 A")
        ax.axhline(5.0, color="orange", ls=":", lw=1, label="5 A")
        ax.set_ylabel("Top-1 symmetry-corrected RMSD (A)")
        ax.set_title("Redocking accuracy by engine (frozen docking_v1)")
        ax.legend(frameon=False, fontsize=8)
    else:
        ax.text(0.5, 0.5, "no poses", ha="center", transform=ax.transAxes)
    _save(fig, "fig01_docking_rmsd", csv_rows)

    # success rates with CI
    fig, ax = plt.subplots(figsize=(7, 4))
    x = np.arange(len(engines))
    width = 0.38
    s2 = [(summary.get(e, {}).get("success_lt2A") or {}).get("point", 0) for e in engines]
    s5 = [(summary.get(e, {}).get("success_lt5A") or {}).get("point", 0) for e in engines]
    e2 = [((summary.get(e, {}).get("success_lt2A") or {}).get("point", 0)
           - (summary.get(e, {}).get("success_lt2A") or {}).get("lo", 0)) for e in engines]
    e5 = [((summary.get(e, {}).get("success_lt5A") or {}).get("point", 0)
           - (summary.get(e, {}).get("success_lt5A") or {}).get("lo", 0)) for e in engines]
    ax.bar(x - width / 2, s2, width, yerr=e2, capsize=3, label="<= 2 A", color="#4C72B0")
    ax.bar(x + width / 2, s5, width, yerr=e5, capsize=3, label="<= 5 A", color="#55A868")
    ax.set_xticks(x)
    ax.set_xticklabels(engines, rotation=20, ha="right")
    ax.set_ylabel("Success rate")
    ax.set_ylim(0, 1.05)
    ax.set_title("Redocking success with bootstrap 95% CI (failures in denominator)")
    ax.legend(frameon=False)
    _save(fig, "fig02_docking_success", [
        {"engine": e, "success_lt2A": s2[i], "success_lt5A": s5[i]}
        for i, e in enumerate(engines)])

    # consensus vs oracle
    cons = summary.get("prospective_consensus", {})
    oracle = summary.get("oracle", {})
    if cons or oracle:
        fig, ax = plt.subplots(figsize=(5.5, 4))
        vals = [cons.get("median_rmsd") or 0, oracle.get("median_rmsd") or 0]
        ax.bar(["prospective\nconsensus", "oracle\nupper bound"], vals,
               color=["#8172B3", "#937860"])
        for i, v in enumerate(vals):
            ax.text(i, v + 0.05, f"{v:.2f}", ha="center", fontsize=9)
        ax.set_ylabel("Median top-1 RMSD (A)")
        ax.set_title("Consensus is prospective; oracle is an upper bound only")
        _save(fig, "fig03_consensus_vs_oracle",
              [{"method": "prospective_consensus", "median_rmsd": vals[0]},
               {"method": "oracle", "median_rmsd": vals[1]}])


# ── pocket ──────────────────────────────────────────────────────────────

def pocket_figures() -> None:
    summary = _load("pockets/pocket_rows_summary.json")
    rows = _rows("pockets/pocket_rows.csv")
    if not summary:
        _placeholder("fig04_pocket", "Pocket detection")
        return
    dcc = [v for v in (_num(r.get("dcc")) for r in rows) if v is not None]
    fig, ax = plt.subplots(figsize=(6, 4))
    if dcc:
        ax.hist(dcc, bins=12, color="#4C72B0", alpha=0.8, edgecolor="white")
        ax.axvline(float(np.median(dcc)), color="red", ls="--",
                   label=f"median {np.median(dcc):.1f} A")
        ax.legend(frameon=False)
    ax.set_xlabel("Distance from pocket centre to ligand centroid (DCC, A)")
    ax.set_ylabel("Complexes")
    ax.set_title(f"Pocket centre accuracy (n={summary.get('n_attempted')})")
    _save(fig, "fig04_pocket_dcc", [{"dcc": v} for v in dcc])

    fig, ax = plt.subplots(figsize=(5.5, 4))
    labels = ["top-1", "top-3", "top-5"]
    keys = ["top1_recovery_4A", "top3_recovery_4A", "top5_recovery_4A"]
    vals = [(summary.get(k) or {}).get("point", 0) for k in keys]
    errs = [((summary.get(k) or {}).get("point", 0) - (summary.get(k) or {}).get("lo", 0))
            for k in keys]
    ax.bar(labels, vals, yerr=errs, capsize=4, color="#55A868")
    ax.set_ylim(0, 1.0)
    ax.set_ylabel("Recovery rate (<= 4 A)")
    ax.set_title("Pocket top-k recovery")
    for i, v in enumerate(vals):
        ax.text(i, v + 0.02, f"{v:.2f}", ha="center")
    _save(fig, "fig05_pocket_recovery", [{"k": labels[i], "recovery": vals[i]} for i in range(3)])


# ── PPI ─────────────────────────────────────────────────────────────────

def ppi_figures() -> None:
    summary = _load("ppi/ppi_rows_summary.json")
    rows = _rows("ppi/ppi_rows.csv")
    if not summary:
        _placeholder("fig06_ppi", "PPI docking")
        return
    top1 = [_num(r.get("dockq_top1")) for r in rows if r.get("engine") == "lightdock_summary"]
    top1 = [v for v in top1 if v is not None]
    fig, ax = plt.subplots(figsize=(7, 4))
    if top1:
        ax.hist(top1, bins=np.linspace(0, 1, 21), color="#C44E52", alpha=0.8, edgecolor="white")
        ax.axvline(0.23, color="green", ls="--", label="DockQ 0.23 (acceptable)")
        ax.legend(frameon=False)
    ax.set_xlabel("DockQ (LightDock top-1)")
    ax.set_ylabel("Complexes")
    ax.set_title(f"Binary PPI redocking on experimental complexes (n={summary.get('n_attempted')})")
    _save(fig, "fig06_ppi_dockq", [{"dockq_top1": v} for v in top1])

    fig, ax = plt.subplots(figsize=(6, 4))
    caps = ["High", "Medium", "Acceptable", "Incorrect"]
    vals = [summary.get(f"capri_{c.lower()}", 0) for c in caps]
    ax.bar(caps, vals, color=["#55A868", "#4C72B0", "#DD8452", "#C44E52"])
    ax.set_ylabel("Complexes")
    ax.set_title("CAPRI classification of LightDock top-1")
    _save(fig, "fig07_ppi_capri", [{"capri": caps[i], "n": vals[i]} for i in range(4)])


# ── ternary ─────────────────────────────────────────────────────────────

def ternary_figures() -> None:
    summary = _load("ternary/ternary_rows_summary.json")
    rows = _rows("ternary/ternary_rows.csv")
    if not summary:
        _placeholder("fig08_ternary", "Ternary complexes")
        return
    fig, ax = plt.subplots(figsize=(7, 4))
    x = np.arange(len(rows))
    contacts = [_num(r.get("interface_contacts")) or 0 for r in rows]
    bridging = [(_num(r.get("ligand_bridging_fraction")) or 0) * max(contacts + [1]) for r in rows]
    ax.bar(x, contacts, color="#4C72B0", label="target–E3 interface contacts")
    ax.bar(x, bridging, color="#DD8452", label="ligand-bridging atoms (scaled)")
    ax.set_xticks(x)
    ax.set_xticklabels([r.get("structure_id") for r in rows], rotation=45, ha="right")
    ax.set_ylabel("Contacts")
    ax.set_title("Native ternary geometry (experimental complexes)")
    ax.legend(frameon=False)
    _save(fig, "fig08_ternary", [
        {"structure_id": r.get("structure_id"), "contacts": contacts[i],
         "bridging_fraction": _num(r.get("ligand_bridging_fraction"))}
        for i, r in enumerate(rows)])


# ── energetics ──────────────────────────────────────────────────────────

def energetics_figures() -> None:
    summary = _load("energetics/energetics_rows_summary.json")
    rows = _rows("energetics/energetics_rows.csv")
    if not summary:
        _placeholder("fig09_energetics", "MM/GBSA", "not run")
        return
    fig, ax = plt.subplots(figsize=(6, 4))
    deltas = [(_num(r.get("delta_total_kcal_mol")), r.get("structure_id")) for r in rows]
    deltas = [(v, s) for v, s in deltas if v is not None]
    if deltas:
        ax.bar([s for _v, s in deltas], [v for v, _s in deltas], color="#8172B3")
    ax.set_ylabel("MM/GBSA ΔTOTAL (kcal/mol)")
    ax.set_title(f"MM/GBSA — capability {summary.get('capability_status')}")
    _save(fig, "fig09_energetics", [{"structure_id": s, "delta": v} for v, s in deltas])


# ── fallback / reproducibility / services / dimensions ──────────────────

def fallback_figures() -> None:
    summary = _load("fallback/fallback_summary.json")
    if not summary:
        _placeholder("fig10_fallback", "Fallback testing", "not run")
        return
    fig, ax = plt.subplots(figsize=(6, 4))
    labels = ["normal success", "fallback used", "fallback success"]
    vals = [summary.get("normal_success_rate") or 0,
            summary.get("fallback_used_rate") or 0,
            summary.get("fallback_success_rate") or 0]
    ax.bar(labels, vals, color=["#4C72B0", "#DD8452", "#55A868"])
    for i, v in enumerate(vals):
        ax.text(i, v + 0.02, f"{v:.2f}", ha="center")
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Rate")
    ax.set_title("Fallback success reported separately from normal success")
    _save(fig, "fig10_fallback", [{"metric": labels[i], "value": vals[i]} for i in range(3)])


def reproducibility_figures() -> None:
    summary = _load("reproducibility/reproducibility_summary.json")
    if not summary:
        _placeholder("fig11_reproducibility", "Reproducibility", "not run")
        return
    by = summary.get("by_engine", {})
    fig, ax = plt.subplots(figsize=(6, 4))
    engines = list(by)
    vals = [by[e].get("pose_consistency_median_A") or 0 for e in engines]
    ax.bar(engines, vals, color=[PALETTE.get(e, "#888") for e in engines])
    for i, v in enumerate(vals):
        ax.text(i, v + 0.02, f"{v:.2f}", ha="center")
    ax.set_ylabel("Median pairwise top-pose RMSD (A)")
    ax.set_title("Across-seed pose consistency (lower = more reproducible)")
    _save(fig, "fig11_reproducibility", [{"engine": e, "pose_consistency": vals[i]}
                                         for i, e in enumerate(engines)])


def services_figures() -> None:
    summary = _load("services/services_summary.json")
    if not summary:
        _placeholder("fig12_services", "Live services", "not run")
        return
    counts = summary.get("outcomes", {})
    fig, ax = plt.subplots(figsize=(6.5, 4))
    labels = list(counts)
    vals = [counts[k] for k in labels]
    colors = {"LIVE_VERIFIED": "#55A868", "DECLARED_ONLY": "#CCB974",
              "AUTH_REQUIRED": "#4C72B0", "UNAVAILABLE": "#C44E52",
              "RATE_LIMITED": "#DD8452"}
    ax.bar(labels, vals, color=[colors.get(l, "#999") for l in labels])
    ax.set_ylabel("Services")
    ax.set_title(f"Live service verification (n={summary.get('n_services')})")
    plt.setp(ax.get_xticklabels(), rotation=20, ha="right")
    _save(fig, "fig12_services", [{"outcome": labels[i], "n": vals[i]} for i in range(len(labels))])


def dimensions_figures() -> None:
    summary = _load("capabilities/capability_dimensions.json")
    if not summary:
        _placeholder("fig13_dimensions", "Capability dimensions", "not run")
        return
    totals = summary.get("dimension_totals", {})
    fig, ax = plt.subplots(figsize=(7, 4))
    labels = list(totals)
    vals = [totals[k] for k in labels]
    ax.bar(labels, vals, color="#4C72B0")
    for i, v in enumerate(vals):
        ax.text(i, v + 0.3, str(v), ha="center", fontsize=8)
    plt.setp(ax.get_xticklabels(), rotation=30, ha="right")
    ax.set_ylabel("Capabilities")
    ax.set_title("Capability dimensions are tracked separately (no single READY flag)")
    _save(fig, "fig13_dimensions", [{"dimension": labels[i], "n": vals[i]} for i in range(len(labels))])


def crosswalk_figures() -> None:
    summary = _load("crosswalk/component_crosswalk.json")
    if not summary:
        _placeholder("fig14_crosswalk", "Component crosswalk", "not run")
        return
    fig, ax = plt.subplots(figsize=(6, 4))
    labels = ["inventory 408", "shared", "runtime 367"]
    vals = [summary.get("inventory_total", 0), summary.get("shared_entities", 0),
            summary.get("runtime_total", 0)]
    ax.bar(labels, vals, color=["#4C72B0", "#55A868", "#DD8452"])
    for i, v in enumerate(vals):
        ax.text(i, v + 3, str(v), ha="center")
    ax.set_ylabel("Entities")
    ax.set_title("408 inventory vs 367 runtime registry")
    _save(fig, "fig14_crosswalk", [{"bucket": labels[i], "n": vals[i]} for i in range(3)])


def run() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    for fn in (docking_figures, pocket_figures, ppi_figures, ternary_figures,
               energetics_figures, fallback_figures, reproducibility_figures,
               services_figures, dimensions_figures, crosswalk_figures):
        try:
            fn()
        except Exception as exc:  # noqa: BLE001
            print(f"[figures] {fn.__name__} failed: {exc}")
    index = sorted(p.name for p in OUT.glob("*.png"))
    (OUT / "FIGURE_INDEX.md").write_text(
        "# Validation figures\n\n" + "\n".join(f"- `{n}`" for n in index) + "\n",
        encoding="utf-8")
    return {"n_figures": len(index), "figures": index}


__all__ = ["run", "OUT"]
