#!/usr/bin/env python3
"""Publication-ready figure suite for the PROTACXtend validation pipeline.

Principal system under evaluation
---------------------------------
    protacxtend/workflows/validation_pipeline.py
(docking-only ``protacxtend/tools/docking_pipeline.py`` is *not* treated as the
complete workflow).

Every figure is built only from real, already-written structured outputs; no
value is synthesised.  Provenance per figure is recorded in
``results/figures_publication/MANIFEST.csv`` and ``COVERAGE.json``.

Primary sources
---------------
    validation_runs/1a46_pl/            single-system end-to-end run
    results/docking/                    six-complex three-engine benchmark
    results/pockets/                    six-complex fpocket benchmark
    results/audit/                      capability / licence / test audit
    results/runtime/, results/fallback_benchmark/, results/figures/raw/

Outputs
-------
    results/figures_publication/{svg,pdf,png}/<name>.{svg,pdf,png}   (600 dpi PNG)
    results/figures_publication/csv/<name>.csv                        source data
    results/figures_publication/{README.md,captions.md,MANIFEST.csv,COVERAGE.json}
"""

from __future__ import annotations

import csv as csvmod
import json
import warnings
from pathlib import Path

import numpy as np

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, ListedColormap
from matplotlib.lines import Line2D
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

warnings.filterwarnings("ignore")

# ── paths ───────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[1]
VAL = ROOT / "validation_runs" / "1a46_pl"
AUDIT = ROOT / "results" / "audit"
DOCK = ROOT / "results" / "docking"
POCK = ROOT / "results" / "pockets"
RUNTIME = ROOT / "results" / "runtime"
FALLBACK = ROOT / "results" / "fallback_benchmark"
RAW = ROOT / "results" / "figures" / "raw"

OUT = ROOT / "results" / "figures_publication"
OUT_SVG, OUT_PDF, OUT_PNG, OUT_CSV = OUT / "svg", OUT / "pdf", OUT / "png", OUT / "csv"
for _d in (OUT_SVG, OUT_PDF, OUT_PNG, OUT_CSV):
    _d.mkdir(parents=True, exist_ok=True)

# ── styling ─────────────────────────────────────────────────────────────
INK = "#1f2933"
MUTED = "#6b7280"
GRID = "#e5e7eb"
COL = {
    "vina": "#4c72b0",
    "gnina": "#dd8452",
    "diffdock": "#55a868",
    "consensus": "#8172b3",
    "r1": "#2b6cb0",
    "r2": "#c05621",
    "pass": "#5b8c5a",
    "warn": "#d9a441",
    "fail": "#b5544a",
    "neutral": "#7b8794",
    "accent": "#3f6f8f",
}
CMAP_MUTED = LinearSegmentedColormap.from_list(
    "muted", ["#f7fafc", "#cbd5e0", "#8fa8bd", "#3f6f8f", "#1f3a4d"]
)

plt.rcParams.update(
    {
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "savefig.facecolor": "white",
        "font.size": 9,
        "axes.titlesize": 10,
        "axes.labelsize": 9,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "legend.fontsize": 8,
        "axes.edgecolor": INK,
        "axes.linewidth": 0.8,
        "xtick.color": INK,
        "ytick.color": INK,
        "text.color": INK,
        "axes.labelcolor": INK,
        "svg.fonttype": "none",
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
    }
)

CAPTIONS: dict[str, str] = {}
MANIFEST: list[dict] = []
COVERAGE = {
    "produced": [],
    "skipped": [],
    "notes": [],
    "run_labels": {
        "validation_runs/1a46_pl": {
            "evidence_tier": "TIER_3_SHORT_MD",
            "qc_verdict": "WARN",
            "convergence": "PARTIALLY_CONVERGED",
            "replicas": 2,
            "mmpbsa": "MMPBSA_UNAVAILABLE",
        }
    },
}


def clean(ax, grid="y"):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    if grid:
        ax.grid(True, color=GRID, lw=0.6, alpha=0.9, axis=grid, zorder=0)
    else:
        ax.grid(False)
    ax.set_axisbelow(True)


def tag(ax, letter):
    ax.text(-0.14, 1.04, letter, transform=ax.transAxes, fontsize=11,
            fontweight="bold", va="bottom", ha="left")


def run_banner(fig, extra="TIER_3_SHORT_MD · QC WARN · PARTIALLY_CONVERGED · 2 replicas · MM/PBSA unavailable"):
    fig.text(0.5, -0.012, extra, ha="center", va="top", fontsize=7.4, color=MUTED)


def finish(fig, name, caption, header=None, rows=None, sources=(), banner=None, tight=True):
    if banner:
        run_banner(fig, banner)
    for ext, d in (("svg", OUT_SVG), ("pdf", OUT_PDF), ("png", OUT_PNG)):
        fig.savefig(d / f"{name}.{ext}", dpi=600,
                    bbox_inches=("tight" if tight else None), facecolor="white")
    if header is not None and rows is not None:
        with (OUT_CSV / f"{name}.csv").open("w", newline="", encoding="utf-8") as fh:
            w = csvmod.writer(fh)
            w.writerow(header)
            w.writerows(rows)
    plt.close(fig)
    CAPTIONS[name] = caption
    MANIFEST.append({"figure": name, "caption": caption, "sources": ";".join(sources),
                     "csv": f"csv/{name}.csv" if rows is not None else ""})
    COVERAGE["produced"].append(name)


def write_json(path, payload):
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


# ── data loaders ────────────────────────────────────────────────────────
def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_csv(path):
    with Path(path).open(newline="", encoding="utf-8") as fh:
        return list(csvmod.DictReader(fh))


def fnum(x):
    if x is None:
        return None
    s = str(x).strip()
    if s in ("", "None", "nan", "NaN"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def load_docking():
    rows = load_csv(DOCK / "docking_benchmark.csv")
    complexes = [r["complex"] for r in rows]
    per = {}
    for c in complexes:
        j = load_json(DOCK / f"{c}.json")
        per[c] = j
    cons = {r["complex"]: fnum(r["consensus_top1"]) for r in rows}
    return complexes, per, cons


DOCKING_COMPLEXES, DOCKING, DOCKING_CONSENSUS = load_docking()
ENGINES = ["vina", "gnina", "diffdock"]


def engine_rmsd_list(complex_id, engine):
    e = (DOCKING[complex_id].get("engines") or {}).get(engine) or {}
    return [float(x) for x in (e.get("all") or [])]


def engine_top1(complex_id, engine):
    e = (DOCKING[complex_id].get("engines") or {}).get(engine) or {}
    return fnum(e.get("top1"))


def bootstrap_ci(flags, n_boot=20000, seed=0):
    arr = np.asarray([f for f in flags if f is not None], dtype=bool)
    if arr.size == 0:
        return (np.nan, np.nan)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, arr.size, size=(n_boot, arr.size))
    rates = arr[idx].mean(axis=1)
    return (float(np.percentile(rates, 2.5)), float(np.percentile(rates, 97.5)))


# ── MD derivation (from stored trajectories) ────────────────────────────
def _kabsch(P, Q):
    """Rotation R and translation t minimising |R·P + t − Q|."""
    Pc, Qc = P - P.mean(0), Q - Q.mean(0)
    H = Pc.T @ Qc
    U, _, Vt = np.linalg.svd(H)
    d = np.sign(np.linalg.det(Vt.T @ U.T))
    R = Vt.T @ np.diag([1.0, 1.0, d]) @ U.T
    t = Q.mean(0) - R @ P.mean(0)
    return R, t


_MD_CACHE: dict[int, dict] = {}


def derive_md(replica, cutoff=5.0):
    """Recompute ligand RMSD, per-residue RMSF and contact occupancy from the
    real stored trajectory (topology.pdb + trajectory.dcd)."""
    if replica in _MD_CACHE:
        return _MD_CACHE[replica]

    import MDAnalysis as mda
    from MDAnalysis.analysis.distances import distance_array

    base = VAL / "md" / f"replica_{replica}"
    u = mda.Universe(str(base / "topology.pdb"), str(base / "trajectory.dcd"))
    prot = u.select_atoms("protein")
    lig = u.select_atoms("resname LIG")
    ca = prot.select_atoms("name CA")
    bb = prot.select_atoms("backbone")

    g2l = {int(gi): i for i, gi in enumerate(prot.indices)}
    res_atoms = [[g2l[int(gi)] for gi in res.atoms.indices] for res in prot.residues]
    resids = [int(r) for r in prot.residues.resids]
    resnames = [str(r) for r in prot.residues.resnames]
    ca_residx = []
    for atom in ca:
        ca_residx.append(int(atom.resindex))

    bb0 = None
    lig0 = None
    ca_ref = None
    rmsd, lig_rmsd, rg = [], [], []
    contact_map = []
    ca_positions = []

    for _ts in u.trajectory:
        P = bb.positions
        if bb0 is None:
            bb0 = P.copy()
            lig0 = lig.positions.copy()
            ca_ref = ca.positions.copy()
        R, t = _kabsch(P, bb0)
        lig_al = lig.positions @ R.T + t
        lig_rmsd.append(float(np.sqrt(((lig_al - lig0) ** 2).sum(1).mean())))
        rmsd.append(float(np.sqrt(((P @ R.T + t - bb0) ** 2).sum(1).mean())))
        prot_al = prot.positions @ R.T + t
        p = prot_al
        rg.append(float(np.sqrt(((p - p.mean(0)) ** 2).sum(1).mean())))
        ca_positions.append((ca.positions @ R.T + t).copy())
        d = distance_array(prot.positions, lig.positions)
        close = (d < cutoff).any(axis=1)
        contact_map.append([int(close[idx].any()) for idx in res_atoms])

    contact_map = np.asarray(contact_map, dtype=int)  # frames x residues
    occ = contact_map.mean(axis=0)
    ca_positions = np.asarray(ca_positions)  # frames x nCA x 3
    rmsf = ca_positions.std(axis=0).mean(axis=1)

    keep = np.where(occ > 0)[0]
    out = {
        "rmsd": np.asarray(rmsd),
        "lig_rmsd": np.asarray(lig_rmsd),
        "rg": np.asarray(rg),
        "rmsf_resids": [resids[i] for i in keep],
        "rmsf_resnames": [resnames[i] for i in keep],
        "rmsf_occ": occ[keep],
        "contact_matrix": contact_map[:, keep].T,  # residues x frames
        "contact_resids": [resids[i] for i in keep],
        "contact_resnames": [resnames[i] for i in keep],
        "contact_occ": occ[keep],
        "ca_rmsf_resids": [resids[i] for i in ca_residx],
        "ca_rmsf": rmsf,
        "n_frames": int(contact_map.shape[0]),
    }
    _MD_CACHE[replica] = out
    return out


# ════════════════════════════════════════════════════════════════════════
# 1. Workflow schematic
# ════════════════════════════════════════════════════════════════════════
def fig_workflow():
    stages = [
        ("Input", "target PDB ± ligand SDF/SMILES ± partner", "solid"),
        ("Preparation & QC", "PDBFixer protonation · OpenFF ligand params · structure QC", "solid"),
        ("Pocket detection", "fpocket ranking + druggability", "solid"),
        ("Three-engine docking + rank consensus", "Vina · GNINA · DiffDock → Borda aggregation", "solid"),
        ("PPI / ternary modelling", "LightDock → geometric orientation search", "solid"),
        ("OpenMM replica MD", "implicit solvent · minimise/NVT/NPT/production", "solid"),
        ("Convergence assessment", "RMSD/BSA/contact plateau · replica agreement", "solid"),
        ("Contacts / SASA / BSA / energy", "trajectory analysis of each replica", "solid"),
        ("Evidence tier · QC · provenance report", "tier, verdicts, SHA-256 inputs, versions", "solid"),
    ]
    side = [
        (4, "PPI/ternary outputs", "no structures produced\nfor this run", "dashed"),
        (7, "MM/GBSA endpoint", "defined but UNAVAILABLE\n(OpenFF→Amber export failed)", "dashed"),
    ]

    fig, ax = plt.subplots(figsize=(8.2, 9.0))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    n = len(stages)
    top, bottom = 0.965, 0.045
    h = 0.070
    gap = (top - bottom - n * h) / (n - 1)
    x0, w = 0.04, 0.68
    centers = []
    y = top - h
    for title, sub, kind in stages:
        box = FancyBboxPatch((x0, y), w, h, boxstyle="round,pad=0.004,rounding_size=0.012",
                             lw=1.0, ec=COL["accent"], fc="#eef3f7", zorder=3)
        ax.add_patch(box)
        ax.text(x0 + w / 2, y + h * 0.63, title, ha="center", va="center",
                fontsize=9.2, fontweight="bold", zorder=4)
        ax.text(x0 + w / 2, y + h * 0.24, sub, ha="center", va="center",
                fontsize=7.2, color=MUTED, zorder=4)
        centers.append(y + h / 2)
        y -= (h + gap)

    for i in range(n - 1):
        ax.add_patch(FancyArrowPatch(
            (x0 + w / 2, centers[i] - h / 2), (x0 + w / 2, centers[i + 1] + h / 2),
            arrowstyle="-|>", mutation_scale=11, color=MUTED, lw=1.1, zorder=2))

    for idx, title, sub, _k in side:
        ys = centers[idx] - h / 2
        box = FancyBboxPatch((0.79, ys - 0.006), 0.19, 0.072,
                             boxstyle="round,pad=0.004,rounding_size=0.012",
                             lw=1.0, ec=COL["fail"], fc="#fbeeec", ls="--", zorder=3)
        ax.add_patch(box)
        ax.text(0.885, ys + 0.049, title, ha="center", va="center", fontsize=7.8,
                fontweight="bold", color=COL["fail"], zorder=4)
        ax.text(0.885, ys + 0.018, sub, ha="center", va="center", fontsize=6.8,
                color=COL["fail"], zorder=4)
        ax.add_patch(FancyArrowPatch(
            (x0 + w + 0.005, centers[idx]), (0.788, ys + 0.03),
            arrowstyle="-|>", mutation_scale=9, color=COL["fail"], lw=0.9,
            ls="--", zorder=2))

    ax.text(0.04, 0.012, "Solid = executed and evidenced in validation_runs/1a46_pl  ·  "
                         "Dashed = defined in the pipeline but not produced for this run",
            fontsize=7.0, color=MUTED, ha="left", va="bottom")

    header = ["step", "title", "detail", "status"]
    rows = [[i + 1, t, s, k] for i, (t, s, k) in enumerate(stages)]
    finish(fig, "F01_workflow_schematic",
           "End-to-end workflow of protacxtend/workflows/validation_pipeline.py. Stages reflect the "
           "pipeline module docstring and orchestration in run_validation(); dashed side boxes mark "
           "branches that produced no output for validation_runs/1a46_pl.",
           header, rows, sources=["protacxtend/workflows/validation_pipeline.py",
                                  "validation_runs/1a46_pl/final_report.json"])


# ════════════════════════════════════════════════════════════════════════
# 2. Validation-tier retention
# ════════════════════════════════════════════════════════════════════════
def fig_tier_retention():
    universe = len(DOCKING_COMPLEXES)
    n_dock_ok = sum(1 for c in DOCKING_COMPLEXES
                    if any(engine_top1(c, e) is not None for e in ENGINES))
    n_consensus = sum(1 for c in DOCKING_COMPLEXES if DOCKING_CONSENSUS.get(c) is not None)
    stages = [
        ("Structure preparation & QC", universe, universe, universe,
         "all benchmark complexes entered preparation/QC"),
        ("Docking: ≥1 valid pose", universe, n_dock_ok, universe,
         "1cbr produced no valid pose in any engine"),
        ("Rank consensus (Borda)", universe, n_consensus, universe,
         "consensus undefined when no engine yields a pose"),
        ("Short MD (≥1 replica)", 1, 1, universe,
         "only 1a46 was escalated into the MD stage"),
        ("Replicated converged MD", 1, 0, universe,
         "1a46 has 2 replicas but PARTIALLY_CONVERGED"),
        ("Validated energy estimation", 1, 0, universe,
         "MM/PBSA unavailable; interaction energy is a structural surrogate"),
    ]
    labels = [s[0] for s in stages]
    entered = np.array([s[1] for s in stages], float)
    reached = np.array([s[2] for s in stages], float)
    pct = reached / universe * 100.0

    fig, ax = plt.subplots(figsize=(7.6, 6.4))
    ypos = np.arange(len(stages))[::-1]
    ax.barh(ypos + 0.16, entered / universe * 100, height=0.30,
            color="#dbe3ea", edgecolor="none", label="entered / attempted")
    ax.barh(ypos - 0.16, pct, height=0.30,
            color=COL["accent"], edgecolor="none", label="reached")
    for y, p, r in zip(ypos, pct, reached):
        ax.text(p + 1.5, y - 0.16, f"{int(r)}/{universe}  ({p:.1f}%)",
                va="center", ha="left", fontsize=8, color=INK)
    ax.set_yticks(ypos)
    ax.set_yticklabels(labels)
    ax.set_xlim(0, 118)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_xlabel(f"systems reaching stage (% of {universe}-complex benchmark universe)")
    ax.axhspan(-0.5, 2.5, color="#fdf6ec", zorder=0)
    ax.text(117, 1.0, "MD-only stages\n(1 system escalated)", ha="right", va="center",
            fontsize=7.2, color=COL["warn"], style="italic")
    clean(ax, grid="x")
    ax.legend(loc="lower right", frameon=False)
    tag(ax, "A")

    header = ["stage", "universe_n", "n_entered", "n_reached", "pct_reached", "note"]
    rows = [[s[0], s[3], s[1], s[2], round(s[2] / s[3] * 100, 1), s[4]] for s in stages]
    finish(fig, "F02_tier_retention",
           "Retention of systems by pipeline stage. Preparation/docking/consensus are the six-complex "
           "benchmark (results/docking, results/pockets); MD stages cover the single escalated system "
           "(validation_runs/1a46_pl). The docking→MD drop reflects protocol scope (one system "
           "escalated), not five MD failures. Percentages are of the six-system universe.",
           header, rows, sources=["results/docking/docking_benchmark.csv",
                                  "results/docking/*.json",
                                  "validation_runs/1a46_pl/final_report.json"])


# ════════════════════════════════════════════════════════════════════════
# 3. Docking figures
# ════════════════════════════════════════════════════════════════════════
def fig_docking_paired():
    fig, (ax, axs) = plt.subplots(2, 1, figsize=(7.8, 7.4), height_ratios=[3.1, 1.0],
                                  sharex=True)
    xs = np.arange(len(DOCKING_COMPLEXES))
    series = [("vina", COL["vina"], "o"), ("gnina", COL["gnina"], "s"),
              ("diffdock", COL["diffdock"], "^"), ("consensus", COL["consensus"], "D")]
    for name, color, marker in series:
        vals, px = [], []
        for i, c in enumerate(DOCKING_COMPLEXES):
            v = DOCKING_CONSENSUS[c] if name == "consensus" else engine_top1(c, name)
            if v is not None:
                vals.append(v)
                px.append(i)
        ax.plot(px, vals, ls="none", marker=marker, ms=7, mfc=color, mec="white",
                mew=0.8, label=name.capitalize(), zorder=4)
    ax.axhline(2.0, color=COL["pass"], lw=1.0, ls="--", zorder=1)
    ax.axhline(5.0, color=COL["warn"], lw=1.0, ls=":", zorder=1)
    ax.text(len(DOCKING_COMPLEXES) - 0.55, 2.05, "2 Å success", fontsize=7.2,
            color=COL["pass"], va="bottom", ha="right")
    ax.text(len(DOCKING_COMPLEXES) - 0.55, 5.05, "5 Å acceptable", fontsize=7.2,
            color=COL["warn"], va="bottom", ha="right")
    allvals = []
    for c in DOCKING_COMPLEXES:
        for e in ENGINES:
            v = engine_top1(c, e)
            if v is not None:
                allvals.append(v)
        if DOCKING_CONSENSUS[c] is not None:
            allvals.append(DOCKING_CONSENSUS[c])
    ax.set_yscale("log")
    ax.set_ylim(0.3, max(20.0, max(allvals) * 1.3) if allvals else 20.0)
    ax.set_ylabel("top-1 pose RMSD to crystal (Å)")
    ax.set_title("Per-complex top-1 pose RMSD")
    clean(ax)
    ax.legend(frameon=False, ncol=4, loc="upper left")

    # status matrix
    status_val = {"success": 2, "warning": 1, "error": 0}
    mat = np.full((len(ENGINES), len(DOCKING_COMPLEXES)), np.nan)
    for j, c in enumerate(DOCKING_COMPLEXES):
        for i, e in enumerate(ENGINES):
            eobj = (DOCKING[c].get("engines") or {}).get(e) or {}
            st = eobj.get("status")
            mat[i, j] = status_val.get(st, np.nan)
    cmap = LinearSegmentedColormap.from_list("st", [COL["fail"], COL["warn"], COL["pass"]])
    axs.imshow(mat, cmap=cmap, vmin=0, vmax=2, aspect="auto")
    axs.set_yticks(range(len(ENGINES)))
    axs.set_yticklabels([e.capitalize() for e in ENGINES])
    axs.set_xticks(xs)
    axs.set_xticklabels(DOCKING_COMPLEXES)
    axs.set_xlabel("complex")
    axs.set_title("Engine status", fontsize=9)
    for j, c in enumerate(DOCKING_COMPLEXES):
        for i, e in enumerate(ENGINES):
            eobj = (DOCKING[c].get("engines") or {}).get(e) or {}
            st = eobj.get("status", "?")
            npose = eobj.get("n_poses", "?")
            axs.text(j, i, f"{st[:3]}\n{npose}", ha="center", va="center",
                     fontsize=6.6, color="white" if mat[i, j] != 1 else INK)
    for s in ("top", "right", "left", "bottom"):
        axs.spines[s].set_visible(False)
    axs.set_xticks(np.arange(-0.5, len(DOCKING_COMPLEXES), 1), minor=True)
    axs.set_yticks(np.arange(-0.5, len(ENGINES), 1), minor=True)
    axs.grid(which="minor", color="white", lw=1.4)
    axs.tick_params(which="minor", length=0)
    tag(ax, "A")
    tag(axs, "B")

    header = ["complex", "engine", "top1_rmsd_A", "n_poses", "status"]
    rows = []
    for c in DOCKING_COMPLEXES:
        for e in ENGINES:
            eobj = (DOCKING[c].get("engines") or {}).get(e) or {}
            rows.append([c, e,
                         "" if engine_top1(c, e) is None else engine_top1(c, e),
                         eobj.get("n_poses", ""), eobj.get("status", "")])
        rows.append([c, "consensus",
                     "" if DOCKING_CONSENSUS[c] is None else DOCKING_CONSENSUS[c], "", ""])
    finish(fig, "F03_docking_paired_rmsd",
           "Paired top-1 pose RMSD per complex across Vina, GNINA, DiffDock and the Borda rank "
           "consensus (panel A; log scale, 2 Å and 5 Å thresholds) together with the per-engine "
           "execution status and pose count (panel B). Failed engines are retained explicitly "
           "rather than dropped from the denominator.",
           header, rows, sources=["results/docking/*.json", "results/docking/docking_benchmark.csv"])


def fig_docking_ecdf():
    fig, ax = plt.subplots(figsize=(7.0, 6.2))
    for e in ENGINES:
        vals = []
        for c in DOCKING_COMPLEXES:
            vals.extend(engine_rmsd_list(c, e))
        if not vals:
            continue
        vals = np.sort(np.asarray(vals, float))
        ecdf = np.arange(1, len(vals) + 1) / len(vals)
        ax.step(vals, ecdf, where="post", color=COL[e], lw=1.6,
                label=f"{e.capitalize()} (n={len(vals)} poses)")
        ax.plot(vals, ecdf, ls="none", marker="o", ms=3.5, mfc=COL[e], mec="white", mew=0.5)
    cons = np.sort(np.asarray([v for v in DOCKING_CONSENSUS.values() if v is not None], float))
    if cons.size:
        ax.step(cons, np.arange(1, cons.size + 1) / cons.size, where="post",
                color=COL["consensus"], lw=1.6, ls="--",
                label=f"Consensus top-1 (n={cons.size})")
    for thr, color in ((2.0, COL["pass"]), (5.0, COL["warn"])):
        ax.axvline(thr, color=color, ls="--", lw=1.0)
        ax.text(thr, 0.03, f"{thr:g} Å", rotation=90, fontsize=7.2, color=color,
                va="bottom", ha="right")
    _all = []
    for e in ENGINES:
        for c in DOCKING_COMPLEXES:
            _all.extend(engine_rmsd_list(c, e))
    _all.extend(v for v in DOCKING_CONSENSUS.values() if v is not None)
    ax.set_xlim(0, max(10.0, max(_all) * 1.1) if _all else 10.0)
    ax.set_ylim(0, 1.02)
    ax.set_xlabel("pose RMSD to crystal (Å)")
    ax.set_ylabel("empirical cumulative probability")
    ax.set_title("Pose-RMSD ECDF, pooled poses per engine")
    clean(ax)
    ax.legend(frameon=False, loc="lower right")
    tag(ax, "A")

    header = ["engine", "n_poses", "rmsd_A", "ecdf"]
    rows = []
    for e in ENGINES:
        vals = []
        for c in DOCKING_COMPLEXES:
            vals.extend(engine_rmsd_list(c, e))
        for v, f in zip(np.sort(vals), np.arange(1, len(vals) + 1) / max(len(vals), 1)):
            rows.append([e, len(vals), round(float(v), 3), round(float(f), 4)])
    finish(fig, "F04_docking_rmsd_ecdf",
           "Empirical CDF of pose RMSD for all retained poses of each engine, with 2 Å and 5 Å "
           "success thresholds. Consensus is shown for its top-1 pose per complex only, because "
           "the Borda aggregation ranks items and does not emit a pooled pose ensemble.",
           header, rows, sources=["results/docking/*.json"])


def fig_docking_success_ci():
    fig, ax = plt.subplots(figsize=(7.2, 6.2))
    n = len(DOCKING_COMPLEXES)
    methods = ENGINES + ["consensus"]
    cutoffs = [(2.0, "≤ 2 Å"), (5.0, "≤ 5 Å")]
    ypos = np.arange(len(methods))
    for mi, m in enumerate(methods):
        for k, (cut, _lbl) in enumerate(cutoffs):
            flags = []
            for c in DOCKING_COMPLEXES:
                v = DOCKING_CONSENSUS[c] if m == "consensus" else engine_top1(c, m)
                flags.append(v is not None and v <= cut)
            rate = float(np.mean(flags))
            lo, hi = bootstrap_ci(flags, seed=1 + 7 * mi + k)
            y = ypos[mi] + (0.18 if k == 0 else -0.18)
            color = COL.get(m, COL["neutral"])
            ax.plot([lo * 100, hi * 100], [y, y], color=color, lw=2.3,
                    alpha=0.45 if k else 0.95, solid_capstyle="round")
            ax.plot([rate * 100], [y], marker="o", ms=7, mfc=color, mec="white", mew=0.9,
                    alpha=0.45 if k else 1.0, zorder=4)
            ax.text(103, y, f"{int(np.sum(flags))}/{n}", va="center", fontsize=7.6,
                    color=MUTED)
    ax.set_yticks(ypos)
    ax.set_yticklabels([m.capitalize() for m in methods])
    ax.set_xlim(-3, 112)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_xlabel("success rate (%), failures retained in denominator (n = 6)")
    ax.invert_yaxis()
    clean(ax, grid="x")
    handles = [Line2D([0], [0], color=INK, lw=2.3, alpha=0.95, label="≤ 2 Å"),
               Line2D([0], [0], color=INK, lw=2.3, alpha=0.45, label="≤ 5 Å"),
               Line2D([0], [0], marker="o", color="none", mfc=INK, mec="white",
                      label="bootstrap 95% CI")]
    ax.legend(handles=handles, frameon=False, loc="lower right")
    ax.set_title("Docking success rate with bootstrap 95% CI")
    tag(ax, "A")

    header = ["method", "cutoff_A", "n_systems", "n_success", "rate", "ci_low", "ci_high", "failed_systems"]
    rows = []
    for mi, m in enumerate(methods):
        for k, (cut, _lbl) in enumerate(cutoffs):
            flags, fails = [], []
            for c in DOCKING_COMPLEXES:
                v = DOCKING_CONSENSUS[c] if m == "consensus" else engine_top1(c, m)
                ok = v is not None and v <= cut
                flags.append(ok)
                if not ok:
                    fails.append(c)
            lo, hi = bootstrap_ci(flags, seed=1 + 7 * mi + k)
            rows.append([m, cut, n, int(np.sum(flags)), round(float(np.mean(flags)), 4),
                         round(lo, 4), round(hi, 4), ";".join(fails)])
    finish(fig, "F05_docking_success_ci",
           "Top-1 docking success rate at 2 Å and 5 Å with bootstrap 95% confidence intervals "
           "(20000 resamples of complexes). Failures — including complexes where no pose was "
           "produced — stay in the denominator of six, so the point estimates are deliberately "
           "lower than vendor-style 'completion-only' rates.",
           header, rows, sources=["results/docking/*.json"])


# ════════════════════════════════════════════════════════════════════════
# 4. Pocket figures
# ════════════════════════════════════════════════════════════════════════
def fig_pocket_topk():
    rows_raw = load_csv(POCK / "pocket_benchmark.csv")
    n = len(rows_raw)
    ks = [1, 3, 5]
    rec = []
    for k in ks:
        key = f"top{k}_recovery_4A"
        hit = sum(1 for r in rows_raw if str(r[key]).strip().lower() == "true")
        rec.append(hit / n)
    fig, ax = plt.subplots(figsize=(6.6, 6.0))
    ax.plot(ks, np.array(rec) * 100, color=COL["accent"], lw=1.8, marker="o", ms=8,
            mfc=COL["accent"], mec="white", mew=1.0, zorder=4)
    for k, r in zip(ks, rec):
        ax.annotate(f"{int(round(r * n))}/{n}", (k, r * 100), textcoords="offset points",
                    xytext=(0, 11), ha="center", fontsize=8)
    ax.set_xticks(ks)
    ax.set_ylim(-4, 65)
    ax.set_xlabel("top-k fpocket pockets considered")
    ax.set_ylabel("complexes with pocket centroid ≤ 4 Å of native ligand (%)")
    ax.set_title("fpocket top-k recovery (n = 6 complexes)")
    clean(ax)
    tag(ax, "A")

    header = ["top_k", "n_complexes", "n_recovered", "recovery_fraction", "recovery_pct"]
    rows = [[k, n, int(round(r * n)), round(r, 4), round(r * 100, 1)] for k, r in zip(ks, rec)]
    finish(fig, "F06_pocket_topk_recovery",
           "fpocket top-k recovery at the 4 Å centroid criterion across the six benchmark complexes. "
           "Recovery is reported as a fraction of all six complexes, so non-recovered cases are "
           "retained in the denominator.",
           header, rows, sources=["results/pockets/pocket_benchmark.csv"])


def fig_pocket_distance():
    rows_raw = load_csv(POCK / "pocket_benchmark.csv")
    cids = [r["complex"] for r in rows_raw]
    dist = [float(r["centroid_distance_A"]) for r in rows_raw]
    cov = [float(r["ligand_atom_coverage_8A"]) for r in rows_raw]
    drug = [float(r["druggability_top1"]) for r in rows_raw]
    x = np.arange(len(cids))
    fig, ax = plt.subplots(figsize=(7.4, 6.2))
    sc = ax.scatter(x, dist, s=70 + 260 * np.asarray(cov), c=drug, cmap=CMAP_MUTED,
                    vmin=0, vmax=0.8, edgecolor=INK, linewidth=0.7, zorder=4)
    for xi, d in zip(x, dist):
        ax.plot([xi, xi], [0, d], color=GRID, lw=1.0, zorder=1)
    ax.axhline(4.0, color=COL["pass"], ls="--", lw=1.1)
    ax.text(len(cids) - 0.5, 4.4, "4 Å recovery threshold", ha="right", fontsize=7.4,
            color=COL["pass"])
    ax.set_xticks(x)
    ax.set_xticklabels(cids)
    ax.set_xlabel("complex")
    ax.set_ylabel("pocket centroid → native-ligand distance (Å)")
    ax.set_title("fpocket top-1 centroid distance to native ligand")
    cb = fig.colorbar(sc, ax=ax, shrink=0.8, pad=0.02)
    cb.set_label("top-1 druggability", fontsize=8)
    clean(ax)
    tag(ax, "A")

    header = ["complex", "centroid_distance_A", "ligand_atom_coverage_8A",
              "druggability_top1", "n_pockets", "recovered_4A"]
    rows = [[r["complex"], float(r["centroid_distance_A"]), float(r["ligand_atom_coverage_8A"]),
             float(r["druggability_top1"]), int(r["n_pockets"]),
             str(r["top1_recovery_4A"]).lower()] for r in rows_raw]
    finish(fig, "F07_pocket_centroid_distance",
           "Per-complex distance from the top-ranked fpocket centroid to the native ligand, drawn as "
           "a strip plot. Marker area encodes native-ligand atom coverage within 8 Å; fill encodes "
           "top-1 druggability. The dashed line marks the 4 Å recovery criterion.",
           header, rows, sources=["results/pockets/pocket_benchmark.csv"])


# ════════════════════════════════════════════════════════════════════════
# 5. MD figures (validation_runs/1a46_pl)
# ════════════════════════════════════════════════════════════════════════
def _ts(replica):
    rows = load_csv(VAL / "analysis" / f"timeseries_replica_{replica}.csv")
    return {k: np.asarray([float(r[k]) for r in rows if r[k] not in ("", None)], float)
            for k in rows[0].keys()}


def fig_md_backbone_rmsd():
    fig, ax = plt.subplots(figsize=(7.0, 6.0))
    for r, color in ((1, COL["r1"]), (2, COL["r2"])):
        ts = _ts(r)
        ax.plot(ts["frame"], ts["rmsd"], color=color, lw=1.5, label=f"replica {r}")
        n = len(ts["rmsd"])
        for a, b, ls in ((0, n // 2, ":"), (n // 2, n, ":")):
            ax.plot([a, b], [ts["rmsd"][a:b].mean()] * 2, color=color, lw=1.0, ls=ls)
    ax.set_xlabel("frame")
    ax.set_ylabel("protein backbone RMSD (Å)")
    ax.set_title("Backbone RMSD, two independently seeded replicas")
    ax.set_ylim(bottom=0)
    clean(ax)
    ax.legend(frameon=False)
    tag(ax, "A")
    header = ["frame", "replica_1_rmsd_A", "replica_2_rmsd_A"]
    t1, t2 = _ts(1), _ts(2)
    rows = [[int(f), round(float(a), 3), round(float(b), 3)]
            for f, a, b in zip(t1["frame"], t1["rmsd"], t2["rmsd"])]
    finish(fig, "F08_md_backbone_rmsd",
           "Protein backbone RMSD over 50 analysed production frames for the two replicas of "
           "1a46 (TIER_3_SHORT_MD, PARTIALLY_CONVERGED). Dotted segments are first/second-half "
           "means used by the plateau test. No reproducibility claim is made: the run has two "
           "replicas, not three.",
           header, rows, sources=["validation_runs/1a46_pl/analysis/timeseries_replica_*.csv"],
           banner="TIER_3_SHORT_MD · QC WARN · PARTIALLY_CONVERGED · 2 replicas · "
                  "not a reproducibility or binding-affinity claim")


def fig_md_ligand_rmsd():
    fig, ax = plt.subplots(figsize=(7.0, 6.0))
    rows = []
    maxn = 0
    series = {}
    for r, color in ((1, COL["r1"]), (2, COL["r2"])):
        d = derive_md(r)
        series[r] = d["lig_rmsd"]
        maxn = max(maxn, len(d["lig_rmsd"]))
        ax.plot(np.arange(len(d["lig_rmsd"])), d["lig_rmsd"], color=color, lw=1.5,
                label=f"replica {r}")
    ax.set_xlabel("frame")
    ax.set_ylabel("ligand RMSD after protein superposition (Å)")
    ax.set_title("Ligand RMSD after backbone alignment")
    ax.set_ylim(bottom=0)
    clean(ax)
    ax.legend(frameon=False)
    tag(ax, "A")
    for i in range(maxn):
        rows.append([i,
                     round(float(series[1][i]), 3) if i < len(series[1]) else "",
                     round(float(series[2][i]), 3) if i < len(series[2]) else ""])
    finish(fig, "F09_md_ligand_rmsd",
           "Ligand-root-mean-square deviation after superposing each frame on the frame-0 protein "
           "backbone, recomputed directly from the stored trajectories (topology.pdb + "
           "trajectory.dcd) of validation_runs/1a46_pl.",
           ["frame", "replica_1_ligand_rmsd_A", "replica_2_ligand_rmsd_A"], rows,
           sources=["validation_runs/1a46_pl/md/replica_*/trajectory.dcd"],
           banner="TIER_3_SHORT_MD · QC WARN · PARTIALLY_CONVERGED · 2 replicas · "
                  "derived from stored trajectories")


def fig_md_rmsf():
    fig, ax = plt.subplots(figsize=(7.8, 6.0))
    rows_by = {}
    for r, color in ((1, COL["r1"]), (2, COL["r2"])):
        d = derive_md(r)
        ax.plot(d["ca_rmsf_resids"], d["ca_rmsf"], color=color, lw=1.0, alpha=0.9,
                label=f"replica {r}")
        for rid, v in zip(d["ca_rmsf_resids"], d["ca_rmsf"]):
            rows_by.setdefault(int(rid), {})[r] = float(v)
    allres = sorted(rows_by)
    ax.set_xlabel("protein residue number")
    ax.set_ylabel("Cα RMSF (Å)")
    ax.set_title("Per-residue Cα flexibility")
    clean(ax)
    ax.legend(frameon=False)
    tag(ax, "A")
    rows = [[rid, round(rows_by[rid].get(1, float("nan")), 3),
             round(rows_by[rid].get(2, float("nan")), 3)] for rid in allres]
    finish(fig, "F10_md_rmsf",
           "Per-residue Cα root-mean-square fluctuation computed from the stored trajectories after "
           "backbone superposition to frame 0. Two replicas only; fluctuations are not a "
           "reproducibility estimate.",
           ["residue", "replica_1_rmsf_A", "replica_2_rmsf_A"], rows,
           sources=["validation_runs/1a46_pl/md/replica_*/trajectory.dcd"],
           banner="TIER_3_SHORT_MD · QC WARN · PARTIALLY_CONVERGED · 2 replicas")


def fig_md_rg():
    fig, ax = plt.subplots(figsize=(7.0, 6.0))
    t1, t2 = _ts(1), _ts(2)
    for ts, color, r in ((t1, COL["r1"], 1), (t2, COL["r2"], 2)):
        ax.plot(ts["frame"], ts["rg"], color=color, lw=1.5, label=f"replica {r}")
    ax.set_xlabel("frame")
    ax.set_ylabel("radius of gyration (Å)")
    ax.set_title("Radius of gyration")
    clean(ax)
    ax.legend(frameon=False)
    tag(ax, "A")
    rows = [[int(f), round(float(a), 3), round(float(b), 3)]
            for f, a, b in zip(t1["frame"], t1["rg"], t2["rg"])]
    finish(fig, "F11_md_radius_of_gyration",
           "Radius of gyration for the two replicas of 1a46. The observable is a global compaction "
           "check; it is stable within the short trajectory but does not by itself establish "
           "convergence.",
           ["frame", "replica_1_rg_A", "replica_2_rg_A"], rows,
           sources=["validation_runs/1a46_pl/analysis/timeseries_replica_*.csv"],
           banner="TIER_3_SHORT_MD · QC WARN · PARTIALLY_CONVERGED · 2 replicas")


def _energy(replica):
    rows = load_csv(VAL / "md" / f"replica_{replica}" / "energy.csv")
    def col(name):
        return np.asarray([float(r[name]) for r in rows if r.get(name) not in ("", None)], float)
    return {
        "time_ps": np.asarray([float(r["Time (ps)"]) for r in rows], float),
        "potential": col("Potential Energy (kJ/mole)"),
        "kinetic": col("Kinetic Energy (kJ/mole)"),
        "temperature": col("Temperature (K)"),
        "speed": np.asarray([float(r["Speed (ns/day)"]) for r in rows], float),
    }


def fig_md_energy_timeseries():
    fig, (ax, ax2) = plt.subplots(2, 1, figsize=(7.2, 7.4), sharex=True,
                                  height_ratios=[2.0, 1.0])
    e1, e2 = _energy(1), _energy(2)
    for e, color, r in ((e1, COL["r1"], 1), (e2, COL["r2"], 2)):
        ax.plot(e["time_ps"], e["potential"] / 1000.0, color=color, lw=1.3,
                label=f"replica {r}")
        ax2.plot(e["time_ps"], e["temperature"], color=color, lw=1.1, alpha=0.85)
    ax.set_ylabel("potential energy (10³ kJ mol⁻¹)")
    ax.set_title("OpenMM potential energy and temperature")
    clean(ax)
    ax.legend(frameon=False)
    ax2.axhline(300, color=MUTED, ls=":", lw=1.0)
    ax2.text(e1["time_ps"][-1], 300, " 300 K", fontsize=7.2, color=MUTED, va="bottom", ha="right")
    ax2.set_xlabel("time (ps)")
    ax2.set_ylabel("temperature (K)")
    clean(ax2)
    tag(ax, "A")
    tag(ax2, "B")
    rows = []
    for i in range(min(len(e1["time_ps"]), len(e2["time_ps"]))):
        rows.append([round(float(e1["time_ps"][i]), 3),
                     round(float(e1["potential"][i]), 3), round(float(e2["potential"][i]), 3),
                     round(float(e1["temperature"][i]), 3), round(float(e2["temperature"][i]), 3)])
    finish(fig, "F12_md_energy_timeseries",
           "OpenMM MD potential energy and temperature for the two replicas. This is the total "
           "potential energy of the simulated system, not a binding free energy; MM/GBSA and "
           "MM/PBSA are unavailable for this run and are not shown.",
           ["time_ps", "replica_1_potential_kJ_mol", "replica_2_potential_kJ_mol",
            "replica_1_temperature_K", "replica_2_temperature_K"], rows,
           sources=["validation_runs/1a46_pl/md/replica_*/energy.csv"],
           banner="TIER_3_SHORT_MD · QC WARN · PARTIALLY_CONVERGED · 2 replicas · "
                  "potential energy ≠ binding affinity · MM/GBSA & MM/PBSA unavailable")


def fig_md_contact_occupancy():
    fig, (ax, axb) = plt.subplots(1, 2, figsize=(8.6, 7.2), sharey=True,
                                  width_ratios=[3.0, 1.0])
    d = derive_md(1)
    mat = d["contact_matrix"].astype(float)
    labels = [f"{n}{r}" for n, r in zip(d["contact_resnames"], d["contact_resids"])]
    im = ax.imshow(mat, aspect="auto", cmap="Blues", vmin=0, vmax=1,
                   interpolation="nearest")
    ax.set_yticks(np.arange(len(labels)))
    ax.set_yticklabels(labels, fontsize=6.4)
    ax.set_xlabel("frame")
    ax.set_title("Replica 1: residue–ligand contact map", fontsize=9.5)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    axb.barh(np.arange(len(labels)), d["contact_occ"] * 100, color=COL["accent"], height=0.75)
    axb.set_xlim(0, 105)
    axb.set_xlabel("occupancy (%)")
    axb.set_title("Contact frequency", fontsize=9.5)
    clean(axb, grid="x")
    tag(ax, "A")
    tag(axb, "B")

    header = ["residue", "replica_1_occupancy_fraction"]
    rows = [[lab, round(float(o), 4)] for lab, o in zip(labels, d["contact_occ"])]
    finish(fig, "F13_md_contact_occupancy",
           "Residue–ligand contact occupancy for the 1a46 holo trajectory. A residue is counted as "
           "in contact when any of its atoms is within 5 Å of any ligand atom; the left panel shows "
           "per-frame persistence for replica 1 and the right panel the frame-averaged occupancy.",
           header, rows,
           sources=["validation_runs/1a46_pl/md/replica_1/trajectory.dcd"],
           banner="TIER_3_SHORT_MD · QC WARN · PARTIALLY_CONVERGED · 2 replicas · "
                  "contact = any protein atom within 5 Å of ligand")


def fig_md_convergence():
    conv = load_json(VAL / "analysis" / "convergence.json")
    checks = conv["checks"]
    names = ["rmsd_plateau", "bsa_plateau", "contact_plateau"]
    drift = [checks[n]["relative_drift"] for n in names]
    ok = [checks[n]["ok"] for n in names]
    spread = checks["replica_agreement"]["relative_spread"]

    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(8.4, 5.8), width_ratios=[1.35, 1.0])
    labels = ["RMSD\nplateau", "BSA\nplateau", "contact\nplateau"]
    colors = [COL["pass"] if o else COL["fail"] for o in ok]
    ax.barh(np.arange(3), drift, color=colors, height=0.5)
    _dtol = max(0.15, max(drift) * 1.05)
    ax.axvline(0.15, color=MUTED, ls="--", lw=1.1)
    ax.text(0.152, 2.45, "tolerance\n0.15", fontsize=7.2, color=MUTED)
    for i, (d, o) in enumerate(zip(drift, ok)):
        ax.text(d + _dtol * 0.015, i, f"{d:.3f}  {'pass' if o else 'fail'}", va="center",
                fontsize=7.6)
    ax.set_yticks(np.arange(3))
    ax.set_yticklabels(labels)
    ax.set_xlim(0, max(0.28, _dtol * 1.3))
    ax.set_xlabel("relative first/second-half drift")
    ax.set_title("Plateau checks", fontsize=9.5)
    clean(ax, grid="x")
    tag(ax, "A")

    ax2.plot([0, spread], [0, 0], color=COL["warn"], lw=3.0, solid_capstyle="round")
    ax2.plot([spread], [0], marker="o", ms=9, mfc=COL["warn"], mec="white", mew=1.0, zorder=4)
    ax2.axvline(0.25, color=MUTED, ls="--", lw=1.1)
    ax2.text(spread, 0.10, f"relative spread {spread:.3f}", ha="center", fontsize=8,
             color=COL["warn"])
    ax2.annotate("", xy=(0.25, -0.12), xytext=(spread, -0.12),
                 arrowprops=dict(arrowstyle="<->", color=MUTED, lw=1.0))
    ax2.text(0.25, -0.20, "tolerance 0.25", fontsize=7.2, color=MUTED, ha="right")
    ax2.set_ylim(-0.4, 0.4)
    ax2.set_xlim(0, max(0.32, spread * 1.35))
    ax2.set_yticks([])
    ax2.set_xlabel("relative spread of replica mean RMSD")
    ax2.set_title(f"Replica agreement ({conv['n_checks_ok']}/{conv['n_checks']} checks pass)",
                  fontsize=9.5)
    clean(ax2, grid="x")
    tag(ax2, "B")

    header = ["check", "ok", "value", "tolerance"]
    rows = [[n, checks[n]["ok"], checks[n]["relative_drift"], 0.15] for n in names]
    rows.append(["replica_agreement", checks["replica_agreement"]["ok"], spread, 0.25])
    rows.append(["verdict", "", conv["verdict"], ""])
    finish(fig, "F14_md_replica_convergence",
           "Convergence diagnostics stored by the pipeline for 1a46: RMSD, buried-SASA and contact "
           "plateau drift against a 0.15 relative tolerance, and agreement of replica-mean RMSD "
           "against a 0.25 tolerance. Three of four checks pass, so the verdict is "
           "PARTIALLY_CONVERGED and tier escalation is refused.",
           header, rows,
           sources=["validation_runs/1a46_pl/analysis/convergence.json"],
           banner="TIER_3_SHORT_MD · QC WARN · PARTIALLY_CONVERGED · 2 replicas · "
                  "tier escalation not allowed")


def fig_md_sasa_bsa():
    t1, t2 = _ts(1), _ts(2)
    fig, (ax, ax2) = plt.subplots(2, 1, figsize=(7.2, 7.6), sharex=True)
    for ts, color, r in ((t1, COL["r1"], 1), (t2, COL["r2"], 2)):
        ax.plot(ts["frame"], ts["sasa"], color=color, lw=1.4, label=f"replica {r}")
        ax2.plot(ts["frame"], ts["bsa_target_ligand"], color=color, lw=1.4)
    ax.set_ylabel("total SASA (Å²)")
    ax.set_title("Solvent-accessible surface and buried surface")
    clean(ax)
    ax.legend(frameon=False)
    ax2.set_xlabel("frame")
    ax2.set_ylabel("buried SASA, target–ligand (Å²)")
    clean(ax2)
    tag(ax, "A")
    tag(ax2, "B")
    rows = [[int(f), round(float(a), 2), round(float(b), 2), round(float(c), 2), round(float(d), 2)]
            for f, a, b, c, d in zip(t1["frame"], t1["sasa"], t2["sasa"],
                                     t1["bsa_target_ligand"], t2["bsa_target_ligand"])]
    finish(fig, "F15_md_sasa_bsa",
           "Total SASA and target–ligand buried SASA across the two replicas. Buried SASA is a "
           "geometric interface descriptor and is reported separately from any energy estimate.",
           ["frame", "replica_1_sasa_A2", "replica_2_sasa_A2",
            "replica_1_bsa_target_ligand_A2", "replica_2_bsa_target_ligand_A2"], rows,
           sources=["validation_runs/1a46_pl/analysis/timeseries_replica_*.csv"],
           banner="TIER_3_SHORT_MD · QC WARN · PARTIALLY_CONVERGED · 2 replicas")


# ════════════════════════════════════════════════════════════════════════
# 7. Energy figures (only where valid)
# ════════════════════════════════════════════════════════════════════════
def fig_energy_replica_agreement():
    conv = load_json(VAL / "analysis" / "convergence.json")
    inter = load_json(VAL / "energy" / "openmm_interaction.json")
    mmpbsa = load_json(VAL / "energy" / "mmpbsa.json")
    e1, e2 = _energy(1), _energy(2)
    n = min(len(e1["potential"]), len(e2["potential"]))
    p1, p2 = e1["potential"][:n] / 1000.0, e2["potential"][:n] / 1000.0

    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(8.8, 5.8), width_ratios=[1.15, 1.0])
    means = [float(p1.mean()), float(p2.mean())]
    sems = [float(p1.std(ddof=1) / np.sqrt(n)), float(p2.std(ddof=1) / np.sqrt(n))]
    for i, (m, s, color, r) in enumerate(zip(means, sems, (COL["r1"], COL["r2"]), (1, 2))):
        ax.errorbar([i], [m], yerr=[s], fmt="o", ms=6, color=color, capsize=5, lw=1.6)
        ax.annotate(f"{m:.1f}", (i, m), textcoords="offset points", xytext=(0, 10),
                    ha="center", fontsize=8, color=color)
    _lo = min(mm - ss for mm, ss in zip(means, sems))
    _hi = max(mm + ss for mm, ss in zip(means, sems))
    _pad = max((_hi - _lo) * 0.35, 0.05)
    ax.set_ylim(_lo - _pad, _hi + _pad)
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["replica 1", "replica 2"])
    ax.set_ylabel("mean potential energy (10³ kJ mol⁻¹)")
    ax.set_title("OpenMM potential energy, replica agreement")
    clean(ax)
    tag(ax, "A")

    methods = ["OpenMM MD potential energy", "OpenMM interaction energy (surrogate)",
               "MM/GBSA", "MM/PBSA"]
    avail = [True, bool(inter.get("status") == "success"), False, False]
    numeric = [True, False, False, False]
    ypos = np.arange(len(methods))
    for i, (a, nu) in enumerate(zip(avail, numeric)):
        color = COL["pass"] if nu else (COL["warn"] if a else COL["fail"])
        label = "numeric" if nu else ("non-numeric" if a else "unavailable")
        ax2.barh([i], [1], color=color, height=0.5)
        ax2.text(1.05, i, label, va="center", fontsize=7.6, color=color)
    ax2.set_yticks(ypos)
    ax2.set_yticklabels(["OpenMM MD potential E", "OpenMM interaction E*", "MM/GBSA", "MM/PBSA"],
                        fontsize=8)
    ax2.set_xlim(0, 1.9)
    ax2.set_ylim(-0.9, 3.55)
    ax2.set_xticks([])
    ax2.set_title("Energy methods: availability", fontsize=9.5)
    clean(ax2, grid="")
    ax2.text(0, -0.82, "* structural-geometry surrogate; no numeric energy value\n"
                        f"MM/PBSA: {mmpbsa.get('method_label', 'unavailable')}",
             fontsize=7.0, color=MUTED, va="bottom", ha="left")
    tag(ax2, "B")

    header = ["method", "status", "numeric_energy_available", "method_label"]
    rows = [
        ["OpenMM MD potential energy", "success", True, "OPENMM_POTENTIAL_ENERGY"],
        ["OpenMM interaction energy", inter.get("status", ""), False,
         inter.get("method_label", "")],
        ["MM/GBSA", "unavailable", False, "MMGBSA_UNAVAILABLE"],
        ["MM/PBSA", mmpbsa.get("status", "unavailable"), False,
         mmpbsa.get("method_label", "MMPBSA_UNAVAILABLE")],
    ]
    finish(fig, "F16_energy_replica_agreement",
           "Only the OpenMM MD potential energy is a numeric energy for this run; panel A shows its "
           "replica means (error bars are standard error of the mean over matched time points). "
           "Panel B records method availability. MM/GBSA and MM/PBSA were not produced, and the "
           "OpenMM interaction entry is a structural-geometry surrogate with no numeric value, so "
           "no experimental-affinity, error-vs-size or energy-component figure is drawn.",
           header, rows,
           sources=["validation_runs/1a46_pl/md/replica_*/energy.csv",
                    "validation_runs/1a46_pl/energy/openmm_interaction.json",
                    "validation_runs/1a46_pl/energy/mmpbsa.json"],
           banner="TIER_3_SHORT_MD · QC WARN · PARTIALLY_CONVERGED · 2 replicas · "
                  "not binding-affinity validated")


# ════════════════════════════════════════════════════════════════════════
# 8. Supplementary engineering figures
# ════════════════════════════════════════════════════════════════════════
def _capability_rows():
    return load_csv(AUDIT / "tool_capability_matrix.csv")


def fig_capability_maturity():
    import capability_maturity as CM

    table, prov = CM.save_audit_outputs()
    levels = CM.MATURITY_LEVELS
    lcolors = CM.LEVEL_COLORS
    counts = CM.maturity_summary(table)
    n = len(table)
    y = np.arange(n)

    mod_order = []
    blocks = {}
    for i, r in enumerate(table):
        if r["module"] not in mod_order:
            mod_order.append(r["module"])
            blocks[r["module"]] = [i, i]
        blocks[r["module"]][1] = i
    first_rows = {blocks[m][0] for m in mod_order}

    fig = plt.figure(figsize=(12, 12))
    fig.subplots_adjust(top=0.945, bottom=0.085, left=0.035, right=0.985)
    gs = fig.add_gridspec(2, 3, width_ratios=[0.12, 1.0, 0.55],
                          height_ratios=[7.6, 0.9], wspace=0.05, hspace=0.14)
    axg = fig.add_subplot(gs[0, 0])
    axm = fig.add_subplot(gs[0, 1], sharey=axg)
    axs = fig.add_subplot(gs[0, 2], sharey=axg)
    axc = fig.add_subplot(gs[1, 0:2])
    axp = fig.add_subplot(gs[1, 2])

    # module band
    axg.set_xlim(0, 1)
    axg.set_ylim(n - 0.5, -0.5)
    axg.axis("off")
    for k, mod in enumerate(mod_order):
        i0, i1 = blocks[mod]
        axg.add_patch(plt.Rectangle((0.06, i0 - 0.5), 0.88, (i1 - i0) + 1,
                                    facecolor="#eef1f4" if k % 2 == 0 else "#e1e7ec",
                                    edgecolor="white", lw=0.6))
        axg.text(0.5, (i0 + i1) / 2, mod.replace("_", " "), rotation=90, ha="center",
                 va="center", fontsize=6.0, color=INK, fontweight="bold")

    # maturity matrix (one filled cell per capability)
    M = np.zeros((n, len(levels)))
    for i, r in enumerate(table):
        M[i, CM.LEVEL_IDX[r["maturity_level"]]] = CM.LEVEL_IDX[r["maturity_level"]] + 1
    cmap = ListedColormap(["#ffffff"] + [lcolors[l] for l in levels])
    axm.imshow(M, cmap=cmap, vmin=0, vmax=len(levels), aspect="auto",
               interpolation="nearest", origin="upper")
    axm.set_xlim(-0.5, len(levels) - 0.5)
    axm.set_ylim(n - 0.5, -0.5)
    axm.set_xticks(range(len(levels)))
    axm.set_xticklabels([l.replace("-", "-\n") for l in levels], fontsize=6.4)
    axm.set_yticks(y)
    axm.set_yticklabels([r["capability"] for r in table], fontsize=5.2)
    for i, lab in enumerate(axm.get_yticklabels()):
        if i in first_rows:
            lab.set_fontweight("bold")
    axm.set_xticks(np.arange(-0.5, len(levels), 1), minor=True)
    axm.set_yticks(np.arange(-0.5, n, 1), minor=True)
    axm.grid(which="minor", color="#e8ebee", lw=0.35)
    axm.tick_params(which="minor", length=0)
    for m in mod_order[1:]:
        axm.axhline(blocks[m][0] - 0.5, color=INK, lw=0.7)
    axm.set_title("Evidence-based maturity matrix", fontsize=11)

    # successful / attempted sample counts
    att = np.array([r["sample_attempted"] for r in table], float)
    suc = np.array([r["sample_success"] for r in table], float)
    axs.barh(y, att, color="#dfe4e9", height=0.74, zorder=1)
    axs.barh(y, suc, color=[lcolors[r["maturity_level"]] for r in table], height=0.5, zorder=2)
    for i, r in enumerate(table):
        axs.text(att[i] + 0.35, i, f"{int(suc[i])}/{int(att[i])}", va="center",
                 fontsize=4.8, color=MUTED)
    axs.set_xlim(0, max(att.max() if n else 1, 1) * 1.5)
    axs.set_xlabel("successful / attempted cases", fontsize=8)
    axs.set_title("Sample counts", fontsize=11)
    axs.tick_params(labelleft=False)
    clean(axs, grid="x")

    # maturity distribution
    left = 0
    for lv in levels:
        v = counts[lv]
        axc.barh([0], [v], left=left, color=lcolors[lv], height=0.62, edgecolor="white")
        if v:
            axc.text(left + v / 2, 0, str(v), ha="center", va="center", fontsize=9,
                     color="white", fontweight="bold")
        left += v
    axc.set_xlim(0, n)
    axc.set_ylim(-0.6, 0.6)
    axc.set_yticks([])
    axc.set_xlabel("capabilities", fontsize=8)
    axc.set_title("Maturity distribution", fontsize=10)
    clean(axc, grid="x")
    axc.spines["left"].set_visible(False)

    axp.axis("off")
    handles = [Line2D([0], [0], marker="s", color="none", mfc=lcolors[l], mec="white",
                      ms=9, label=f"{l}  ({counts[l]})") for l in levels]
    axp.legend(handles=handles, loc="center left", frameon=False, fontsize=7.0,
               title="maturity level", title_fontsize=7.4)

    fig.suptitle("Capability maturity from installation, smoke-test and benchmark evidence",
                 fontsize=13, y=0.995)

    git, hw = prov["git"], prov["hardware"]
    banner = (
        f"Provenance (automatic): git {git['commit'][:12]}"
        f"{' (dirty)' if git['dirty'] else ''} · generated {prov['generated_at'][:19]}Z · "
        f"{hw['cpu_count']} CPU / {hw['memory_gb']} GB RAM / {len(hw['gpus'])} GPU · "
        f"seeds {prov['seeds']['md_replicas']} · {len(prov['input_hashes'])} evidence files SHA-256 · "
        f"params: docking median ≤ 2 Å, pocket top-1 ≥ 0.50, PPI DockQ ≥ 0.49, MD CONVERGED, "
        f"n_boot = 20000 · provenance digest {prov['provenance_digest'][:16]}"
    )
    import textwrap
    fig.text(0.5, 0.030, "\n".join(textwrap.wrap(banner, 165)), ha="center", va="bottom",
             fontsize=6.8, color=MUTED)

    header = ["module", "capability", "implementation_tool", "version", "installation_test",
              "smoke_test_cases", "successful_cases", "benchmark_dataset", "comparator",
              "evaluation_metrics", "acceptance_threshold", "validation_result",
              "provenance_completeness", "evidence_file", "failure_reason", "maturity_level",
              "sample_success", "sample_attempted", "sample_basis"]
    rows = [[r[h] for h in header] for r in table]

    caption = (
        f"Evidence-based capability maturity matrix for PROTACXtend. Each of the {n} audited "
        "capabilities is placed on one of five ordered levels — absent, installed, smoke-tested, "
        "internally benchmarked, scientifically validated — using installation/health evidence, "
        "capability-level smoke tests plus module test cases, and pre-registered benchmarks that "
        "state a dataset, comparator, metric and acceptance threshold. Status is never inferred "
        "from package availability: 'installed' requires a backend-health or functional check, "
        "'smoke-tested' a passing capability-level smoke or functional check, 'internally "
        "benchmarked' a completed benchmark, and 'scientifically validated' a benchmark that meets "
        "its threshold. Thresholds were frozen before evaluation: docking median top-1 RMSD ≤ 2.0 Å "
        "against the crystal pose (6-complex redocking set); pocket top-1 recovery ≤ 4 Å ≥ 0.50 "
        "(6 complexes); geometric-fallback PPI DockQ ≥ 0.49 (CAPRI acceptable; 1 native complex + "
        "20 decoys); MD convergence verdict CONVERGED with ≥ 3 replicas; MM/GBSA status success "
        "with a reported ΔG. Three capabilities (DiffDock, GNINA, Borda rank consensus) meet the "
        "docking threshold; Vina does not (median 4.223 Å) and is therefore internally benchmarked, "
        "not validated. Partially converged MD (PARTIALLY_CONVERGED; 2 replicas), untested "
        "PPI/ternary workflows and surrogate/failed energetics (MM/GBSA and MM/PBSA failed; the "
        "'interaction energy' is a structural-geometry surrogate with no numeric value) are "
        "explicitly excluded from scientific validation and are capped at internally benchmarked. "
        "The right panel shows successful/attempted sample counts — benchmark cases where a "
        "benchmark exists, otherwise smoke-test cases — with failures retained in the denominator. "
        "Run provenance is generated automatically: git commit "
        f"{git['commit'][:12]}{' (dirty working tree)' if git['dirty'] else ''}, UTC timestamp "
        f"{prov['generated_at'][:19]}Z, {hw['cpu_count']} CPU cores / {hw['memory_gb']} GB RAM / "
        f"{len(hw['gpus'])} GPU(s), tool versions, seeds {prov['seeds']['md_replicas']}, SHA-256 "
        f"hashes of {len(prov['input_hashes'])} evidence files and provenance digest "
        f"{prov['provenance_digest'][:16]} (results/audit/run_provenance.json). Summary: "
        + ", ".join(f"{counts[l]} {l}" for l in levels) + "."
    )
    finish(fig, "F17_capability_maturity_matrix", caption, header, rows,
           sources=["results/audit/tool_capability_matrix.csv",
                    "results/audit/functional_checks.json",
                    "results/audit/pytest_results.json",
                    "results/docking/docking_benchmark.json",
                    "results/pockets/pocket_benchmark.csv",
                    "results/ppi/ppi_benchmark.json",
                    "results/statistics/statistics.json",
                    "validation_runs/1a46_pl/analysis/convergence.json",
                    "validation_runs/1a46_pl/energy/mmpbsa.json"], tight=False)


def fig_fallback_matrix():
    rows = load_csv(FALLBACK / "fallback_scenarios.csv")
    caps = []
    backends = [r["failed_backend"] for r in rows]
    for r in rows:
        if r["capability"] not in caps:
            caps.append(r["capability"])
    mat = np.full((len(caps), len(backends)), np.nan)
    resolved = {}
    for j, r in enumerate(rows):
        i = caps.index(r["capability"])
        av = str(r["fallback_available"]).strip().lower() == "true"
        mat[i, j] = 1.0 if av else 0.0
        if av:
            resolved[(i, j)] = r["resolved_backend"]
    fig, ax = plt.subplots(figsize=(7.6, 5.4))
    cmap = LinearSegmentedColormap.from_list("fb", [COL["fail"], "#f0d9a8", COL["pass"]])
    ax.imshow(mat, cmap=cmap, vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(backends)))
    ax.set_xticklabels(backends, rotation=35, ha="right", fontsize=8)
    ax.set_yticks(range(len(caps)))
    ax.set_yticklabels([c.replace("_", " ") for c in caps], fontsize=8)
    ax.set_title("Fallback availability when a backend fails")
    for j, r in enumerate(rows):
        i = caps.index(r["capability"])
        txt = resolved.get((i, j), "—")
        if len(txt) > 16:
            txt = txt.split(";")[0]
        ax.text(j, i, txt, ha="center", va="center", fontsize=6.4,
                color="white" if mat[i, j] > 0.5 else INK)
    for s in ("top", "right", "left", "bottom"):
        ax.spines[s].set_visible(False)
    ax.set_xticks(np.arange(-0.5, len(backends), 1), minor=True)
    ax.set_yticks(np.arange(-0.5, len(caps), 1), minor=True)
    ax.grid(which="minor", color="white", lw=1.4)
    ax.tick_params(which="minor", length=0)
    tag(ax, "A")
    header = ["failed_backend", "capability", "fallback_available", "resolved_backend",
              "executed", "result_status"]
    out = [[r["failed_backend"], r["capability"], r["fallback_available"],
            r["resolved_backend"], r["executed"], r["result_status"]] for r in rows]
    finish(fig, "F18_fallback_matrix",
           "Fallback resolution matrix for deliberately failed backends. Cells show availability "
           "(green) or absence (red) of a declared fallback and the resolved backend. Most rows "
           "were resolver-only checks; only the OpenMM-CPU row was actually executed.",
           header, out, sources=["results/fallback_benchmark/fallback_scenarios.csv"])


def fig_runtime_decomposition():
    rows = load_csv(RUNTIME / "orchestration_overhead.csv")
    tasks = [r["task"] for r in rows]
    backend = np.array([float(r["t_backend_s"]) for r in rows])
    orch = np.array([float(r["t_orchestration_s"]) for r in rows])
    pct = np.array([float(r["overhead_pct"]) for r in rows])
    y = np.arange(len(tasks))
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(8.8, 5.4), width_ratios=[1.3, 1.0])
    ax.barh(y, backend, left=1e-4, color=COL["accent"], height=0.5, label="backend")
    ax.barh(y, orch, left=backend, color=COL["warn"], height=0.5, label="orchestration")
    ax.set_xscale("log")
    ax.set_xlim(1e-4, max(1e-3, float((backend + orch).max()) * 3))
    ax.set_yticks(y)
    ax.set_yticklabels(tasks)
    ax.set_xlabel("wall time (s, log scale)")
    ax.set_title("Runtime decomposition")
    clean(ax, grid="x")
    ax.legend(frameon=False, loc="lower right")
    tag(ax, "A")
    ax2.barh(y, pct, color=COL["neutral"], height=0.5)
    for i, p in enumerate(pct):
        ax2.annotate(f"{p:.2f}%", (p, i), textcoords="offset points", xytext=(4, 0),
                     va="center", fontsize=8)
    ax2.set_yticks(y)
    ax2.set_yticklabels([])
    ax2.set_xlim(0, max(float(pct.max()) * 1.3, 1.0))
    ax2.set_xlabel("orchestration overhead (%)")
    ax2.set_title("Relative overhead")
    clean(ax2, grid="x")
    tag(ax2, "B")
    header = ["task", "t_backend_s", "t_total_s", "t_orchestration_s", "overhead_pct"]
    out = [[r["task"], r["t_backend_s"], r["t_total_s"], r["t_orchestration_s"],
            r["overhead_pct"]] for r in rows]
    finish(fig, "F19_runtime_decomposition",
           "Backend versus orchestration wall time for three calibrated tasks. Absolute overhead is "
           "small even where the relative overhead is largest (RDKit descriptor), because the "
           "backend itself takes under a millisecond.",
           header, out, sources=["results/runtime/orchestration_overhead.csv"])


def fig_cpu_gpu_throughput():
    rows = _capability_rows()
    cpu = np.array([str(r["cpu_supported"]).strip().lower() == "true" for r in rows])
    gpu = np.array([str(r["gpu_supported"]).strip().lower() == "true" for r in rows])
    cats = {
        "CPU only": int(np.sum(cpu & ~gpu)),
        "GPU only": int(np.sum(~cpu & gpu)),
        "CPU + GPU": int(np.sum(cpu & gpu)),
        "neither": int(np.sum(~cpu & ~gpu)),
    }
    e1, e2 = _energy(1), _energy(2)
    speeds = [s for s in (e1["speed"][1:], e2["speed"][1:]) if len(s)]
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(8.6, 5.4), width_ratios=[1.0, 1.15])
    labels = list(cats)
    vals = [cats[k] for k in labels]
    total = sum(vals) or 1
    yy = np.arange(len(labels))
    ax.barh(yy, vals, color=COL["accent"], height=0.5)
    for i, v in enumerate(vals):
        ax.text(v + 0.4, i, f"{v}  ({v / total * 100:.0f}%)", va="center", fontsize=8)
    ax.set_yticks(yy)
    ax.set_yticklabels(labels)
    ax.set_xlim(0, max(vals) * 1.35)
    ax.set_xlabel("capabilities")
    ax.set_title("Compute support across capabilities")
    clean(ax, grid="x")
    tag(ax, "A")
    for s, color, r in zip(speeds, (COL["r1"], COL["r2"]), (1, 2)):
        ax2.plot(np.arange(len(s)), s, color=color, lw=1.4, marker="o", ms=3,
                 label=f"replica {r}")
    ax2.set_xlabel("energy record")
    ax2.set_ylabel("MD speed (ns/day)")
    ax2.set_title("Measured OpenCL throughput")
    clean(ax2)
    ax2.legend(frameon=False)
    tag(ax2, "B")
    header = ["category", "n_capabilities"]
    out = [[k, v] for k, v in cats.items()]
    finish(fig, "F20_cpu_gpu_throughput",
           "Left: declared CPU/GPU support across audited capabilities. Right: measured OpenCL MD "
           "throughput (ns/day) recorded by OpenMM for the two 1a46 replicas; the first record of "
           "each replica is a warm-up value and is excluded from the plotted series.",
           header, out,
           sources=["results/audit/tool_capability_matrix.csv",
                    "validation_runs/1a46_pl/md/replica_*/energy.csv"])


def fig_disk_footprint():
    rows = load_csv(RAW / "S5_environment_disk.csv")
    envs = [r["environment"] for r in rows]
    sizes = np.array([float(r["disk_mb"]) for r in rows]) / 1024.0
    order = np.argsort(sizes)
    envs = [envs[i] for i in order]
    sizes = sizes[order]
    y = np.arange(len(envs))
    fig, ax = plt.subplots(figsize=(7.0, 5.6))
    ax.hlines(y, 0, sizes, color=GRID, lw=1.6)
    ax.plot(sizes, y, "o", ms=9, mfc=COL["accent"], mec="white", mew=1.0, ls="none")
    for i, s in enumerate(sizes):
        ax.text(s + 0.06, i, f"{s:.2f} GiB", va="center", fontsize=8)
    ax.set_yticks(y)
    ax.set_yticklabels(envs)
    ax.set_xlim(0, sizes.max() * 1.25)
    ax.set_xlabel("on-disk footprint (GiB)")
    ax.set_title("Modular environment footprint")
    clean(ax, grid="x")
    tag(ax, "A")
    header = ["environment", "disk_mb", "disk_gib"]
    out = [[r["environment"], float(r["disk_mb"]),
            round(float(r["disk_mb"]) / 1024.0, 3)] for r in rows]
    finish(fig, "F21_disk_footprint",
           "Disk footprint of the modular conda environments measured on this host. This is a "
           "single-machine installation measurement, not a multi-platform claim.",
           header, out, sources=["results/figures/raw/S5_environment_disk.csv"])


def fig_failure_modes():
    rows = _capability_rows()
    smoke_pass = sum(1 for r in rows if str(r["smoke_test_status"]).strip().upper() == "PASS")
    smoke_fail = sum(1 for r in rows if str(r["smoke_test_status"]).strip().upper() == "FAIL")
    status_counts = {"success": 0, "warning": 0, "error": 0}
    for c in DOCKING_COMPLEXES:
        for e in ENGINES:
            st = ((DOCKING[c].get("engines") or {}).get(e) or {}).get("status")
            if st in status_counts:
                status_counts[st] += 1
    fb = load_csv(FALLBACK / "fallback_scenarios.csv")
    fb_exec = sum(1 for r in fb if str(r["executed"]).strip().lower() == "true")
    fb_resolver = len(fb) - fb_exec
    tests = load_csv(AUDIT / "pytest_results.csv") if (AUDIT / "pytest_results.csv").exists() else None
    pytest_rows = load_json(AUDIT / "pytest_results.json")
    test_pass = sum(1 for t in pytest_rows if t.get("status") == "PASS")
    test_fail = sum(1 for t in pytest_rows if t.get("status") != "PASS")

    categories = ["Docking engine runs", "Capability smoke tests", "Fallback scenarios",
                  "Unit / integration tests"]
    ok = [status_counts["success"], smoke_pass, fb_exec, test_pass]
    warn = [status_counts["warning"], 0, 0, 0]
    bad = [status_counts["error"], smoke_fail, fb_resolver, test_fail]
    y = np.arange(len(categories))[::-1]
    fig, ax = plt.subplots(figsize=(8.0, 5.2))
    ax.barh(y, ok, color=COL["pass"], height=0.5, label="pass / success / executed")
    ax.barh(y, warn, left=ok, color=COL["warn"], height=0.5, label="warning / resolver-only")
    ax.barh(y, bad, left=np.array(ok) + np.array(warn), color=COL["fail"], height=0.5,
            label="fail / error")
    for i, (a, b, c) in enumerate(zip(ok, warn, bad)):
        ax.text(a + b + c + 0.6, y[i], f"n={a + b + c}", va="center", fontsize=8, color=MUTED)
    ax.set_yticks(y)
    ax.set_yticklabels(categories)
    ax.set_xlabel("count")
    ax.set_title("Outcome distribution by artefact class")
    clean(ax, grid="x")
    ax.legend(frameon=False, loc="lower right")
    tag(ax, "A")
    header = ["category", "success", "warning_or_resolver", "failure", "total"]
    out = [[cat, a, b, c, a + b + c] for cat, a, b, c in zip(categories, ok, warn, bad)]
    finish(fig, "F22_failure_mode_distribution",
           "Outcome distribution across four artefact classes. Docking engine errors, capability "
           "smoke-test failures and resolver-only fallback checks are shown separately so that "
           "harness-level and scientific failures are not conflated.",
           header, out,
           sources=["results/docking/*.json", "results/audit/tool_capability_matrix.csv",
                    "results/fallback_benchmark/fallback_scenarios.csv",
                    "results/audit/pytest_results.json"])


# ════════════════════════════════════════════════════════════════════════
def write_metadata():
    COVERAGE["skipped"] = [
        {"requested": "PPI: DockQ distribution",
         "reason": "no PPI/ternary outputs: results/ppi/, validation_runs/1a46_pl/ppi_docking/ "
                   "and validation_runs/1a46_pl/ternary/ are empty"},
        {"requested": "PPI: interface RMSD vs fraction of native contacts",
         "reason": "no modelled PPI interfaces or reference mapping in any structured output"},
        {"requested": "PPI: CAPRI-class distribution",
         "reason": "CAPRI classification requires DockQ/native interface data that does not exist"},
        {"requested": "PPI: native vs predicted contact maps",
         "reason": "no predicted PPI contact map produced"},
        {"requested": "Energy: experimental affinity vs predicted energy",
         "reason": "no experimental affinity values and no numeric predicted binding energy "
                   "(interaction energy is a structural surrogate with null score)"},
        {"requested": "Energy: error vs system size",
         "reason": "requires multiple numeric energy estimates; only OpenMM potential energy exists"},
        {"requested": "Energy: energy-component heatmap",
         "reason": "no MM/GBSA or MM/PBSA component decomposition (both unavailable)"},
        {"requested": "MD reproducibility claim from three independently seeded replicas",
         "reason": "run contains two replicas; no reproducibility claim is made"},
    ]
    COVERAGE["notes"] = [
        "validation_runs/1a46_pl/ is labelled TIER_3_SHORT_MD, QC WARN, PARTIALLY_CONVERGED, "
        "two replicas, MM/PBSA unavailable. It is never described as reproducible, fully "
        "validated or binding-affinity validated.",
        "MD ligand RMSD, Cα RMSF and contact occupancy are recomputed from the stored real "
        "trajectories (topology.pdb + trajectory.dcd); no simulation is re-run and no value is "
        "synthesised.",
        "Docking/pocket benchmark figures use results/docking and results/pockets; audit and "
        "engineering figures use results/audit and related results/ tables.",
        "Success rates retain failed complexes in the denominator, so they differ from "
        "completion-only rates in results/docking/docking_summary.json.",
    ]
    write_json(OUT / "COVERAGE.json", COVERAGE)

    with (OUT / "MANIFEST.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csvmod.writer(fh)
        w.writerow(["figure", "caption", "sources", "source_csv"])
        for m in MANIFEST:
            w.writerow([m["figure"], m["caption"], m["sources"], m["csv"]])

    lines = ["# Figure captions", "",
             "All figures were generated by `scripts/build_publication_figures.py` from real "
             "structured outputs. The single-system run `validation_runs/1a46_pl` is labelled "
             "**TIER_3_SHORT_MD, QC WARN, PARTIALLY_CONVERGED**, has **two replicas**, and its "
             "**MM/PBSA is unavailable**; it is not described as reproducible, fully validated "
             "or binding-affinity validated.", ""]
    for name in [m["figure"] for m in MANIFEST]:
        lines += [f"## {name}", "", CAPTIONS[name], ""]
    if COVERAGE["skipped"]:
        lines += ["# Requested figures not produced (no supporting data)", ""]
        for s in COVERAGE["skipped"]:
            lines += [f"- **{s['requested']}** — {s['reason']}"]
        lines.append("")
    (OUT / "captions.md").write_text("\n".join(lines), encoding="utf-8")

    readme = f"""# Publication figure suite

Generated by `scripts/build_publication_figures.py`.

Principal system: `protacxtend/workflows/validation_pipeline.py`
(docking-only `protacxtend/tools/docking_pipeline.py` is not treated as the complete workflow).

## Layout

- `svg/`, `pdf/`, `png/` — every figure in three formats; PNG is 600 dpi.
- `csv/` — the exact source data behind each figure.
- `MANIFEST.csv` — figure → caption → source directories.
- `captions.md` — captions and the list of requested-but-unsupported figures.
- `COVERAGE.json` — produced/skipped inventory with machine-readable reasons.

## Data provenance

| figure group | source |
|---|---|
| F01 workflow | pipeline module + `validation_runs/1a46_pl/final_report.json` |
| F02 tier retention | `results/docking`, `results/pockets`, `validation_runs/1a46_pl` |
| F03–F05 docking | `results/docking/*.json`, `docking_benchmark.csv` |
| F06–F07 pocket | `results/pockets/pocket_benchmark.csv` |
| F08–F15 MD | `validation_runs/1a46_pl/analysis`, `md/replica_*` |
| F16 energy | `validation_runs/1a46_pl/md/replica_*/energy.csv`, `energy/*.json` |
| F17 maturity matrix | `results/audit`, `results/docking`, `results/pockets`, `results/ppi`, `results/statistics`, `validation_runs/1a46_pl` |
| F18–F22 engineering | `results/audit`, `results/runtime`, `results/fallback_benchmark`, `results/figures/raw` |

## Capability maturity

`F17_capability_maturity_matrix` replaces the earlier availability-based
capability-status chart. Maturity is assigned from installation, smoke-test and
benchmark evidence only — never from package availability. The full per-capability
table is `results/audit/capability_maturity_matrix.csv` (75 capabilities × 19
fields). Partially converged MD, untested PPI/ternary workflows and
surrogate/failed energetics are explicitly capped below scientific validation.

## Automatic run provenance

`scripts/capability_maturity.py` writes `results/audit/run_provenance.json` with
git commit/branch/dirty state, UTC timestamps, hardware (CPU/RAM/GPU), tool
versions, benchmark parameters and acceptance thresholds, random seeds, SHA-256
hashes of every evidence file and a combined provenance digest. The digest and git
state are printed on F17 and in its caption.

## Claim boundary

`validation_runs/1a46_pl/` is **TIER_3_SHORT_MD**, **QC WARN** and **PARTIALLY_CONVERGED**.
It contains **two replicas** and its **MM/PBSA is unavailable**. Accordingly this suite makes
**no reproducibility claim** (that would require three independent replicas) and no
**binding-affinity** or **fully validated** claim. Replica counts, convergence verdicts and
method availability are printed on the relevant figures.

Figures that the request listed but for which no defensible data exists in the
current artefacts (experimental-affinity energy plots, energy-component heatmaps,
three-replica reproducibility) are deliberately **not produced**; see `captions.md`
and `COVERAGE.json`. PPI/DockQ evidence is used quantitatively in the F17 maturity
matrix but is not expanded into a separate PPI figure group.

## Regenerate

```bash
python scripts/build_publication_figures.py
```
"""
    (OUT / "README.md").write_text(readme, encoding="utf-8")


def main():
    builders = [
        fig_workflow,
        fig_tier_retention,
        fig_docking_paired,
        fig_docking_ecdf,
        fig_docking_success_ci,
        fig_pocket_topk,
        fig_pocket_distance,
        fig_md_backbone_rmsd,
        fig_md_ligand_rmsd,
        fig_md_rmsf,
        fig_md_rg,
        fig_md_energy_timeseries,
        fig_md_contact_occupancy,
        fig_md_convergence,
        fig_md_sasa_bsa,
        fig_energy_replica_agreement,
        fig_capability_maturity,
        fig_fallback_matrix,
        fig_runtime_decomposition,
        fig_cpu_gpu_throughput,
        fig_disk_footprint,
        fig_failure_modes,
    ]
    for b in builders:
        b()
        print(f"  built {MANIFEST[-1]['figure']}")
    write_metadata()
    print(f"\n{len(MANIFEST)} figures × 3 formats + {len(MANIFEST)} source CSVs → {OUT}")


if __name__ == "__main__":
    main()
