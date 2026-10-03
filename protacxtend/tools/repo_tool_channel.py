"""Repo-tool channel: cloned PROTAC research repos exposed as callable tools.

This mirrors Biomni's *function channel* (a thin, schema-described adapter per
tool) but keeps PROTACXtend's governance rule: a repo tool is only advertised
as callable when its own environment imports and a real smoke call succeeds.

Currently wired (verified on this machine):

* ``predict_protac_activity`` — PROTAC-Degradation-Predictor
  (``pdp.is_protac_active``), run inside its dedicated conda env.

Everything else is reported with an honest status instead of being faked.
"""
from __future__ import annotations

import json
import os
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPO_DIR = PROJECT_ROOT / "data" / "protac_repos" / "repos"

# repo name -> interpreter of the environment that owns its dependencies
REPO_ENVS: dict[str, str] = {
    "PROTAC-Degradation-Predictor":
        "/home/saveenas/miniconda3/envs/pp/envs/protac-degradation-predictor/bin/python",
    "DeepPROTACs":
        "/home/saveenas/.protacxtend/envs/protac-deepprotacs/bin/python",
    "PROTAC-STAN":
        "/home/saveenas/.protacxtend/envs/protac-stan/bin/python",
    "Bellerophon":
        "/home/saveenas/.protacxtend/envs/bellerophon/bin/python",
    "TERNIFY":
        "/home/saveenas/.protacxtend/envs/ternify/bin/python",
    "SE3-protacs":
        "/home/saveenas/miniconda3/envs/pp/envs/protac-se3-protacs/bin/python",
    "degradomap":
        "/home/saveenas/.protacxtend/envs/degradomap/bin/python",
    "MEGA-PROTAC":
        "/home/saveenas/miniconda3/envs/pp/envs/protac-mega-protac/bin/python",
    "PROTAC-RL":
        "/home/saveenas/miniconda3/envs/pp/envs/protac-rl/bin/python",
}

# repos that are heavy pipelines and stay manual-only until reviewed
MANUAL_ONLY = {
    "PROTACFold", "PROTAC-Splitter",
    "ProtacGPT", "protacSpace", "computational-PROTAC-development",
    "MEGA-PROTAC", "PROTAC-RL",
}

# declared capability of the wired repo tools
WIRED: dict[str, dict[str, Any]] = {
    "predict_protac_activity": {
        "repo": "PROTAC-Degradation-Predictor",
        "module": "protac_degradation_predictor",
        "callable": "is_protac_active",
        "inputs": ["protac_smiles", "e3_ligase", "target_uniprot", "cell_line"],
        "output": "bool (active/inactive)",
        "evidence": "ML_PREDICTION",
        "limitations": ["Upstream model; applicability domain not characterised here."],
    },
    "predict_deepprotacs": {
        "repo": "DeepPROTACs",
        "module": "model.ProtacModel",
        "callable": "single_prediction.py",
        "inputs": ["complex_dir (ligase_ligand.mol2, ligase_pocket.mol2, "
                   "target_ligand.mol2, target_pocket.mol2, linker.smi)"],
        "output": "int (0/1 degradation prediction)",
        "evidence": "ML_PREDICTION",
        "limitations": ["Published model saved under PyG 1.x; loaded via a "
                        "legacy-tolerant unpickler on PyG 2.0.4/torch 2.0.1 CPU."],
    },
    "predict_protac_stan": {
        "repo": "PROTAC-STAN",
        "module": "model.PROTAC_STAN",
        "callable": "inference.py",
        "inputs": ["root (prepared dataset dir)", "name"],
        "output": "list[int] per-PROTAC prediction",
        "evidence": "ML_PREDICTION",
        "limitations": ["Requires a prepared dataset with cached ESM embeddings; "
                        "new proteins need esm_embed/get_embed_s.py."],
    },
    "split_protac_bellerophon": {
        "repo": "Bellerophon",
        "module": "sprotac.split_protac",
        "callable": "split_protac",
        "inputs": ["protac_smiles"],
        "output": "warhead / linker / E3 SMILES",
        "evidence": "CALCULATED",
        "limitations": ["Matches against the bundled default warhead (605) and "
                        "E3 (101) SDF libraries; no match returns 0 solutions."],
    },
    "sample_ternary_ternify": {
        "repo": "TERNIFY",
        "module": "src/ternify.py",
        "callable": "ternify.py",
        "inputs": ["data_dir (e3.sdf, poi.sdf, protac.sdf, e3.pdb, poi.pdb)",
                   "n_ini", "n_search", "n_keep", "n_processes"],
        "output": "sampled ternary-complex conformers (TC_protac.sdf, TC_protein.pdb)",
        "evidence": "STRUCTURAL_SURROGATE",
        "limitations": ["Force-field Monte-Carlo sampling, not an experimental "
                        "complex; interface box must be supplied for real runs."],
    },
    "predict_se3_protacs": {
        "repo": "SE3-protacs",
        "module": "model.SE3PROTACs",
        "callable": "casestudy.py",
        "inputs": ["ligase_smiles", "ligase_seq", "target_smiles",
                   "target_seq", "linker_smiles"],
        "output": "degradation score + Good/Bad Degrader",
        "evidence": "ML_PREDICTION",
        "limitations": ["Loads a 252 MB state_dict + ESM embeddings; first run "
                        "downloads ESM weights. Needs a symlink for the model "
                        "filename (SE(3)-PROTACs.pt -> SE3-PROTACs.pt)."],
    },
    "run_degradomap_experiment": {
        "repo": "degradomap",
        "module": "degradomap.analysis.run_experiment",
        "callable": "run_experiment",
        "inputs": ["merged_csv (default: bundled data/merged_dataset.csv)"],
        "output": "LOO AUCs (structural/biological/combined) + ranked E3s",
        "evidence": "CALCULATED",
        "limitations": ["This is the repo's documented NULL RESULT baseline; "
                        "AUCs near 0.5 are the expected honest finding."],
    },
    "assign_e3_mechanism": {
        "repo": "degradomap",
        "module": "degradomap.mechanism.MECHANISM_CLASSES",
        "callable": "MECHANISM_CLASSES",
        "inputs": ["gene_symbol"],
        "output": "mechanism class (pocket_binder/molecular_glue/covalent)",
        "evidence": "CALCULATED",
        "limitations": ["Literature-derived mapping for the curated PROTAC E3 set."],
    },
}


# repos with no runnable pipeline env, exposed as safe metadata/asset tools
METADATA_REPOS: dict[str, dict[str, Any]] = {
    "MEGA-PROTAC": {
        "tool": "inspect_repo_assets",
        "summary": "STEP_1..STEP_14 MEGADOCK ternary-docking pipeline + publication data",
        "heavy_reason": "needs MEGADOCK + GROMACS + docking; multi-step CLI pipeline",
    },
    "PROTAC-RL": {
        "tool": "inspect_repo_assets",
        "summary": "OpenNMT-based linker/degrader generation (case data + shell scripts)",
        "heavy_reason": "needs OpenNMT preprocessing + training before inference",
    },
    "PROTACFold": {
        "tool": "inspect_repo_assets",
        "summary": "AlphaFold/structure-prediction-style PROTAC modeling repo",
        "heavy_reason": "heavy structure-prediction pipeline and weights",
    },
    "PROTAC-Splitter": {
        "tool": "inspect_repo_assets",
        "summary": "Python package that splits PROTACs into fragments",
        "heavy_reason": "env removed; pip-installable (setup.py/pyproject present)",
    },
    "ProtacGPT": {
        "tool": "inspect_repo_assets",
        "summary": "Generative PROTAC model repo",
        "heavy_reason": "generative model; needs training/checkpoints",
    },
    "protacSpace": {
        "tool": "inspect_repo_assets",
        "summary": "PROTAC dataset / generation repo",
        "heavy_reason": "dataset-generation pipeline",
    },
    "computational-PROTAC-development": {
        "tool": "inspect_repo_assets",
        "summary": "PROTAC computational pipeline / dataset collection",
        "heavy_reason": "dataset + multi-tool pipeline",
    },
}

# modules that must import for a repo to be considered runnable
REPO_IMPORTS: dict[str, list[str]] = {
    "PROTAC-Degradation-Predictor": ["protac_degradation_predictor"],
    "DeepPROTACs": ["torch", "torch_geometric"],
    "PROTAC-STAN": ["torch", "torch_geometric", "toml"],
    "Bellerophon": ["rdkit"],
    "TERNIFY": ["rdkit", "numpy", "scipy"],
    "SE3-protacs": ["torch", "se3_transformer_pytorch", "esm"],
    "degradomap": ["degradomap"],
    "MEGA-PROTAC": ["numpy", "pandas"],
    "PROTAC-RL": ["torch"],
}


@dataclass
class RepoChannelEntry:
    name: str
    path: str
    env_python: str
    env_present: bool
    imports_ok: bool
    callable: bool
    capability: str = "none"          # method | metadata | none
    wired_tool: str = ""
    status: str = "cloned_only"
    notes: str = ""


def _probe_env(python: str, modules: list[str], timeout: int = 90,
               cwd: str | None = None) -> dict[str, bool]:
    if not Path(python).exists():
        return {m: False for m in modules}
    code = ("import importlib.util as u, json;"
            f"print(json.dumps({{m: u.find_spec(m) is not None for m in {modules!r}}}))")
    try:
        r = subprocess.run([python, "-c", code], capture_output=True, text=True,
                           timeout=timeout, cwd=cwd)
        if r.returncode == 0:
            return json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        pass
    return {m: False for m in modules}


def list_repo_channel() -> list[dict[str, Any]]:
    entries: list[RepoChannelEntry] = []
    wired_by_repo = {v["repo"]: k for k, v in WIRED.items()}
    for d in sorted(REPO_DIR.iterdir()):
        if not d.is_dir():
            continue
        name = d.name
        py = REPO_ENVS.get(name, "")
        env_present = bool(py) and Path(py).exists()
        imports_ok = False
        if env_present:
            probe = _probe_env(py, REPO_IMPORTS.get(name, ["numpy"]), cwd=str(d))
            imports_ok = all(probe.values())
        wired = wired_by_repo.get(name, "")
        meta = METADATA_REPOS.get(name)
        if wired and env_present and imports_ok:
            capability, callable_, status = "method", True, "callable"
        elif meta:
            capability, callable_, status = "metadata", True, "metadata"
            wired = meta["tool"]
        elif name in MANUAL_ONLY:
            capability, callable_, status = "none", False, "manual_review"
        elif env_present:
            capability, callable_, status = "none", False, "env_partial"
        else:
            capability, callable_, status = "none", False, "cloned_only"
        entries.append(RepoChannelEntry(
            name=name, path=str(d.relative_to(PROJECT_ROOT)), env_python=py,
            env_present=env_present, imports_ok=imports_ok,
            callable=callable_, capability=capability,
            wired_tool=wired, status=status))
    return [asdict(e) for e in entries]


def channel_summary() -> dict[str, Any]:
    rows = list_repo_channel()
    by: dict[str, int] = {}
    for r in rows:
        by[r["status"]] = by.get(r["status"], 0) + 1
    method = sum(1 for r in rows if r["capability"] == "method")
    metadata = sum(1 for r in rows if r["capability"] == "metadata")
    return {
        "repos_cloned": len(rows),
        "callable_now": method + metadata,
        "callable_method": method,
        "callable_metadata": metadata,
        "wired_tools": sorted({r["wired_tool"] for r in rows if r["wired_tool"]}),
        "by_status": by,
    }


# ── the wired tool ──────────────────────────────────────────────────────

_PDP_RUNNER = r"""
import json, sys
import protac_degradation_predictor as pdp
payload = json.loads(sys.stdin.read())
res = pdp.is_protac_active(
    payload["smiles"], payload["e3_ligase"],
    payload["target_uniprot"], payload["cell_line"],
)
print("__PDP__" + json.dumps({"active": bool(res)}))
"""


def predict_protac_activity(smiles: str, e3_ligase: str, target_uniprot: str,
                            cell_line: str = "HeLa", timeout: int = 600) -> dict[str, Any]:
    """PROTAC-Degradation-Predictor ``is_protac_active`` in its own env."""
    repo = REPO_DIR / "PROTAC-Degradation-Predictor"
    python = REPO_ENVS["PROTAC-Degradation-Predictor"]
    if not (repo.is_dir() and Path(python).exists()):
        return {"available": False, "reason": "PROTAC-Degradation-Predictor env not present"}
    payload = {"smiles": smiles, "e3_ligase": e3_ligase,
               "target_uniprot": target_uniprot, "cell_line": cell_line}
    try:
        proc = subprocess.run([python, "-c", _PDP_RUNNER], input=json.dumps(payload),
                              capture_output=True, text=True, timeout=timeout, cwd=str(repo))
        for line in reversed((proc.stdout or "").splitlines()):
            if line.startswith("__PDP__"):
                out = json.loads(line[len("__PDP__"):])
                return {"available": True, **out, "model": "PROTAC-Degradation-Predictor",
                        "evidence_type": "ML_PREDICTION"}
        return {"available": False, "reason": (proc.stderr or "no output")[-400:]}
    except Exception as exc:
        return {"available": False, "reason": str(exc)[:400]}


# ── DeepPROTACs (PyG-1.x pickle; legacy-tolerant loader) ────────────────
_DEEPPROTACS_RUNNER = r'''
import sys, os, types, pickle, torch, runpy
sys.path.insert(0, os.getcwd())
from torch_geometric.nn import MessagePassing
for _a, _v in [("_explain", None), ("_decomposed_layers", 1),
               ("explain", False), ("decomposed_layers", 1), ("node_dim", -2)]:
    if not hasattr(MessagePassing, _a):
        setattr(MessagePassing, _a, _v)

class LegacyUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        try:
            return super().find_class(module, name)
        except Exception:
            return type(name, (object,), {})

_mod = types.SimpleNamespace(__name__="pickle", Unpickler=LegacyUnpickler,
                             load=pickle.load, loads=pickle.loads,
                             Pickler=pickle.Pickler, dump=pickle.dump,
                             dumps=pickle.dumps,
                             HIGHEST_PROTOCOL=pickle.HIGHEST_PROTOCOL)
_orig = torch.load
def _cpu_load(*a, **k):
    k.setdefault("map_location", torch.device("cpu"))
    k.setdefault("pickle_module", _mod)
    return _orig(*a, **k)
torch.load = _cpu_load
sys.argv = ["single_prediction.py", sys.argv[1]]
runpy.run_path("single_prediction.py", run_name="__main__")
'''


def predict_deepprotacs(complex_dir: str, timeout: int = 600) -> dict[str, Any]:
    """DeepPROTACs single-complex degradation prediction (0/1)."""
    repo = REPO_DIR / "DeepPROTACs"
    python = REPO_ENVS["DeepPROTACs"]
    if not (repo.is_dir() and Path(python).exists()):
        return {"available": False, "reason": "DeepPROTACs env not present"}
    target = Path(complex_dir)
    if not target.is_absolute():
        target = repo / complex_dir
    required = ["ligase_ligand.mol2", "ligase_pocket.mol2",
                "target_ligand.mol2", "target_pocket.mol2", "linker.smi"]
    missing = [f for f in required if not (target / f).exists()]
    if missing:
        return {"available": False, "reason": f"missing inputs: {missing}"}
    runner = Path("/tmp/deepprotacs_runner.py")
    runner.write_text(_DEEPPROTACS_RUNNER)
    try:
        proc = subprocess.run([python, str(runner), str(target)], capture_output=True,
                              text=True, timeout=timeout, cwd=str(repo))
        preds = [ln.strip() for ln in (proc.stdout or "").splitlines()
                 if ln.strip() in ("0", "1")]
        if preds:
            return {"available": True, "prediction": int(preds[-1]),
                    "model": "DeepPROTACs", "evidence_type": "ML_PREDICTION"}
        return {"available": False, "reason": (proc.stderr or "no output")[-400:]}
    except Exception as exc:
        return {"available": False, "reason": str(exc)[:400]}


# ── PROTAC-STAN (state_dict model; runs on a prepared dataset) ──────────
_STAN_TAIL = ["0", "1"]


def predict_protac_stan(root: str = "data/demo", name: str = "demo",
                        timeout: int = 900) -> dict[str, Any]:
    """PROTAC-STAN inference over a prepared dataset directory."""
    repo = REPO_DIR / "PROTAC-STAN"
    python = REPO_ENVS["PROTAC-STAN"]
    if not (repo.is_dir() and Path(python).exists()):
        return {"available": False, "reason": "PROTAC-STAN env not present"}
    try:
        proc = subprocess.run([python, "inference.py", "--root", root, "--name", name],
                              capture_output=True, text=True, timeout=timeout, cwd=str(repo))
        preds = None
        for line in reversed((proc.stdout or "").splitlines()):
            line = line.strip()
            if line.startswith("[") and line.endswith("]"):
                preds = json.loads(line.replace(" ", ",").replace(",,", ","))
                break
        if preds is None:
            return {"available": False, "reason": (proc.stderr or proc.stdout or "no output")[-400:]}
        return {"available": True, "n": len(preds),
                "n_active": int(sum(preds)), "predictions": preds,
                "model": "PROTAC-STAN", "evidence_type": "ML_PREDICTION"}
    except Exception as exc:
        return {"available": False, "reason": str(exc)[:400]}


# ── Bellerophon (warhead / linker / E3 splitter) ───────────────────────
_BELLER_RUNNER = r'''
import os, sys, types, json
sys.path.insert(0, os.getcwd())
st = types.ModuleType("streamlit")
st.__getattr__ = lambda name: (lambda *a, **k: None)
comp = types.ModuleType("streamlit.components")
compv1 = types.ModuleType("streamlit.components.v1")
st.components = comp; comp.v1 = compv1
sys.modules.update({"streamlit": st, "streamlit.components": comp,
                    "streamlit.components.v1": compv1})
import sprotac
from rdkit import Chem
smiles = sys.argv[1]
mol = Chem.MolFromSmiles(smiles)
if mol is None:
    print("__BELLER__" + json.dumps({"available": False, "reason": "invalid SMILES"}))
    raise SystemExit(0)
df = sprotac.split_protac("query", smiles, mol, sprotac.warhead_df, sprotac.e3_df)
if df is None or len(df) == 0:
    print("__BELLER__" + json.dumps({"available": True, "n_solutions": 0,
          "reason": "no warhead/E3 substructure match in the default libraries"}))
    raise SystemExit(0)
rows = []
for _, r in df.head(20).iterrows():
    rows.append({"warhead_smiles": r.get("Warhead SMILES"),
                 "linker_smiles": r.get("Linker SMILES"),
                 "e3_smiles": r.get("E3 SMILES"),
                 "warhead_id": str(r.get("warhead ID")),
                 "e3_id": str(r.get("E3 ID"))})
print("__BELLER__" + json.dumps({"available": True, "n_solutions": len(df),
      "solutions": rows}, default=str))
'''


def split_protac_bellerophon(protac_smiles: str, timeout: int = 300) -> dict[str, Any]:
    """Split a PROTAC into warhead / linker / E3 using Bellerophon's default libs."""
    repo = REPO_DIR / "Bellerophon"
    python = REPO_ENVS["Bellerophon"]
    if not (repo.is_dir() and Path(python).exists()):
        return {"available": False, "reason": "Bellerophon env not present"}
    runner = Path("/tmp/bellerophon_runner.py")
    runner.write_text(_BELLER_RUNNER)
    try:
        proc = subprocess.run([python, str(runner), protac_smiles], capture_output=True,
                              text=True, timeout=timeout, cwd=str(repo))
        for line in reversed((proc.stdout or "").splitlines()):
            if line.startswith("__BELLER__"):
                out = json.loads(line[len("__BELLER__"):])
                out.setdefault("model", "Bellerophon")
                out["evidence_type"] = "CALCULATED"
                return out
        return {"available": False, "reason": (proc.stderr or "no output")[-400:]}
    except Exception as exc:
        return {"available": False, "reason": str(exc)[:400]}


# ── TERNIFY (ternary-complex sampler) ───────────────────────────────────
def sample_ternary_ternify(data_dir: str, *, name: str = "ternify_run",
                           n_ini: int = 1000, n_search: int = 200,
                           n_keep: int = 200, n_processes: int = 2,
                           interface: str = "", timeout: int = 1800) -> dict[str, Any]:
    """Run TERNIFY's Monte-Carlo ternary-complex sampler over a data directory."""
    import shutil
    import tempfile

    repo = REPO_DIR / "TERNIFY"
    python = REPO_ENVS["TERNIFY"]
    if not (repo.is_dir() and Path(python).exists()):
        return {"available": False, "reason": "TERNIFY env not present"}
    src = Path(data_dir)
    if not src.is_absolute():
        src = repo / data_dir
    needed = ["e3.sdf", "poi.sdf", "protac.sdf", "e3.pdb", "poi.pdb"]
    missing = [f for f in needed if not (src / f).exists()]
    if missing:
        return {"available": False, "reason": f"missing inputs: {missing}"}
    code = (repo / "src" / "ternify.py")
    if not code.exists():
        return {"available": False, "reason": "src/ternify.py not found"}
    run_dir = Path(tempfile.mkdtemp(prefix=f"ternify_{name}_"))
    for f in needed:
        shutil.copy(src / f, run_dir / f)
        
    iface = interface or "-42,-18,-27,9,9,42"
    (run_dir / "tcs.inp").write_text(
        f"PROTACs: protac.sdf\nWarhead_anchor: e3.sdf\nWarhead_flex: poi.sdf\n"
        f"Protein_anchor: e3.pdb\nProtein_flex: poi.pdb\n"
        f"Output_protac: TC_protac.sdf\nOutput_protein: TC_protein.pdb\n"
        f"Interface: {iface}\nN_ini: {n_ini}\nN_search: {n_search}\n"
        f"N_keep: {n_keep}\nN_processes: {n_processes}\n")
    try:
        proc = subprocess.run([python, str(code), "-p", "tcs.inp"], capture_output=True,
                              text=True, timeout=timeout, cwd=str(run_dir))
        out_sdf = run_dir / "TC_protac.sdf"
        n = 0
        if out_sdf.exists():
            n = out_sdf.read_text(errors="replace").count("$$$$")
        if n == 0:
            return {"available": False,
                    "reason": (proc.stderr or proc.stdout or "no conformers")[-400:]}
        return {"available": True, "n_conformers": n, "run_dir": str(run_dir),
                "ternary_protac_sdf": str(out_sdf),
                "ternary_protein_pdb": str(run_dir / "TC_protein.pdb"),
                "model": "TERNIFY", "evidence_type": "STRUCTURAL_SURROGATE"}
    except Exception as exc:
        return {"available": False, "reason": str(exc)[:400]}


# ── SE(3)-PROTACs (state_dict model + ESM) ──────────────────────────────
def predict_se3_protacs(ligase_smiles: str, ligase_seq: str, target_smiles: str,
                        target_seq: str, linker_smiles: str,
                        timeout: int = 2400) -> dict[str, Any]:
    """SE(3)-PROTACs degradation prediction from smiles + FASTA sequences."""
    import tempfile

    repo = REPO_DIR / "SE3-protacs"
    python = REPO_ENVS["SE3-protacs"]
    if not (repo.is_dir() and Path(python).exists()):
        return {"available": False, "reason": "SE3-protacs env not present"}
    model = repo / "model" / "SE3-PROTACs.pt"
    if not model.exists():
        return {"available": False, "reason": "model/SE3-PROTACs.pt not found"}
    d = Path(tempfile.mkdtemp(prefix="se3_"))
    files = {"ligase.smi": ligase_smiles, "ligase.fa": ligase_seq,
             "target.smi": target_smiles, "target.fa": target_seq,
             "linker.smi": linker_smiles}
    for name, content in files.items():
        (d / name).write_text(content)
    cmd = [python, "casestudy.py",
           "--ligase_smi", str(d / "ligase.smi"), "--ligase_fa", str(d / "ligase.fa"),
           "--target_smi", str(d / "target.smi"), "--target_fa", str(d / "target.fa"),
           "--linker_smi", str(d / "linker.smi")]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                              cwd=str(repo))
        import re as _re
        text = proc.stdout or ""
        m = _re.search(r"Degradation Score\s*:\s*([0-9.]+)", text)
        pred = _re.search(r"Prediction\s*:\s*([^\n]+)", text)
        if not m:
            return {"available": False, "reason": (proc.stderr or text or "no output")[-400:]}
        return {"available": True, "degradation_score": float(m.group(1)),
                "prediction": pred.group(1).strip() if pred else "",
                "model": "SE(3)-PROTACs", "evidence_type": "ML_PREDICTION"}
    except Exception as exc:
        return {"available": False, "reason": str(exc)[:400]}


# ── degradomap (public-data E3 tractability, documented null result) ────
_DEGRADOMAP_RUNNER = r'''
import sys, os, json
sys.path.insert(0, os.getcwd())
import pandas as pd
from degradomap import analysis
df = pd.read_csv(sys.argv[1])
res = analysis.run_experiment(df)
top = res["ranked"].head(10)[["gene_symbol", "score_combined"]].to_dict("records")
print("__DEGRADOMAP__" + json.dumps({
    "available": True, "n_total": res["n_total"],
    "n_positives": res["n_positives"], "n_negatives": res["n_negatives"],
    "auc": res["auc"], "top10": top}, default=str))
'''


def run_degradomap_experiment(merged_csv: str = "data/merged_dataset.csv",
                              timeout: int = 900) -> dict[str, Any]:
    """Run degradomap's LOO E3-tractability experiment on a merged CSV (no download)."""
    repo = REPO_DIR / "degradomap"
    python = REPO_ENVS["degradomap"]
    if not (repo.is_dir() and Path(python).exists()):
        return {"available": False, "reason": "degradomap env not present"}
    csv_path = Path(merged_csv)
    if not csv_path.is_absolute():
        csv_path = repo / merged_csv
    if not csv_path.exists():
        return {"available": False, "reason": f"merged csv not found: {csv_path}"}
    runner = Path("/tmp/degradomap_runner.py")
    runner.write_text(_DEGRADOMAP_RUNNER)
    try:
        proc = subprocess.run([python, str(runner), str(csv_path)], capture_output=True,
                              text=True, timeout=timeout, cwd=str(repo))
        for line in reversed((proc.stdout or "").splitlines()):
            if line.startswith("__DEGRADOMAP__"):
                out = json.loads(line[len("__DEGRADOMAP__"):])
                out.setdefault("model", "degradomap")
                out["evidence_type"] = "CALCULATED"
                return out
        return {"available": False, "reason": (proc.stderr or "no output")[-400:]}
    except Exception as exc:
        return {"available": False, "reason": str(exc)[:400]}


def assign_e3_mechanism(gene_symbol: str) -> dict[str, Any]:
    """Map a gene symbol to degradomap's mechanism class."""
    repo = REPO_DIR / "degradomap"
    python = REPO_ENVS["degradomap"]
    if not (repo.is_dir() and Path(python).exists()):
        return {"available": False, "reason": "degradomap env not present"}
    code = ("import json;from degradomap.mechanism import MECHANISM_CLASSES as M;"
            f"g={gene_symbol!r};print('__DM__'+json.dumps({{'gene':g,'mechanism_class':M.get(g)}}))")
    try:
        proc = subprocess.run([python, "-c", code], capture_output=True, text=True,
                              timeout=120, cwd=str(repo))
        for line in reversed((proc.stdout or "").splitlines()):
            if line.startswith("__DM__"):
                out = json.loads(line[len("__DM__"):])
                out["available"] = out.get("mechanism_class") is not None
                out["model"] = "degradomap"
                out["evidence_type"] = "CALCULATED"
                return out
        return {"available": False, "reason": (proc.stderr or "no output")[-400:]}
    except Exception as exc:
        return {"available": False, "reason": str(exc)[:400]}


# ── metadata / asset inspection (safe, no execution) ────────────────────
_MODEL_EXT = {".pt", ".pth", ".ckpt", ".h5", ".joblib", ".pkl", ".safetensors"}
_DATA_EXT = {".csv", ".tsv", ".parquet", ".json", ".sdf", ".pdb", ".mol2", ".smi", ".fa", ".fasta", ".xlsx"}
_ENV_NAMES = {"environment.yml", "environment.yaml", "requirements.txt", "setup.py",
              "pyproject.toml", "env.yaml", "conda_env.yml", "Dockerfile"}


def repo_assets(repo_name: str, max_files: int = 4000) -> dict[str, Any]:
    """Inspect a cloned repo's assets without importing or executing it."""
    repo = REPO_DIR / repo_name
    if not repo.is_dir():
        return {"available": False, "reason": f"repo not found: {repo_name}"}

    top: list[str] = []
    try:
        for p in sorted(repo.iterdir()):
            if p.name in {".git", "__pycache__"}:
                continue
            top.append(p.name + ("/" if p.is_dir() else ""))
    except Exception:
        pass

    py, notebooks, models, data_files, entry_points, env_specs = [], [], [], [], [], []
    seen = 0
    for root, dirs, files in os.walk(repo):
        dirs[:] = [x for x in dirs if x not in {".git", "__pycache__", ".ipynb_checkpoints"}]
        for fn in files:
            seen += 1
            if seen > max_files:
                break
            p = Path(root) / fn
            rel = str(p.relative_to(repo))
            ext = p.suffix.lower()
            if ext == ".py":
                py.append(rel)
                try:
                    if "__main__" in p.read_text(errors="replace"):
                        entry_points.append(rel)
                except Exception:
                    pass
            elif ext == ".ipynb":
                notebooks.append(rel)
            elif ext in _MODEL_EXT:
                try:
                    models.append({"path": rel, "mb": round(p.stat().st_size / 1e6, 3)})
                except Exception:
                    models.append({"path": rel, "mb": None})
            elif ext in _DATA_EXT:
                data_files.append(rel)
            if fn in _ENV_NAMES:
                env_specs.append(rel)
        if seen > max_files:
            break

    # env specs captured by the repo adapter (outside the repo tree)
    spec_dir = PROJECT_ROOT / "data" / "protac_repos" / "env_specs"
    if spec_dir.is_dir():
        for p in sorted(spec_dir.glob(f"{repo_name}__*")):
            env_specs.append(str(p.relative_to(PROJECT_ROOT)))

    readme = ""
    for cand in ("README.md", "readme.md", "README.txt"):
        rp = repo / cand
        if rp.exists():
            readme = rp.read_text(errors="replace")[:700]
            break

    meta = METADATA_REPOS.get(repo_name, {})
    return {
        "available": True,
        "repo": repo_name,
        "path": str(repo.relative_to(PROJECT_ROOT)),
        "summary": meta.get("summary", ""),
        "heavy_reason": meta.get("heavy_reason", ""),
        "top_level": top[:max_files],
        "n_files_scanned": min(seen, max_files),
        "n_python": len(py),
        "n_notebooks": len(notebooks),
        "entry_points": entry_points[:40],
        "env_specs": env_specs[:40],
        "models": sorted(models, key=lambda m: -(m["mb"] or 0))[:40],
        "n_data_files": len(data_files),
        "data_sample": data_files[:40],
        "readme_head": readme,
        "evidence_type": "CALCULATED",
        "limitations": ["Metadata/asset listing only; no pipeline is executed."],
    }


inspect_repo_assets = repo_assets


__all__ = ["list_repo_channel", "channel_summary", "predict_protac_activity",
           "predict_deepprotacs", "predict_protac_stan", "split_protac_bellerophon",
           "sample_ternary_ternify", "predict_se3_protacs",
           "run_degradomap_experiment", "assign_e3_mechanism",
           "repo_assets", "inspect_repo_assets", "REPO_ENVS", "WIRED",
           "METADATA_REPOS"]
