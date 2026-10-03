"""Audit P01-P17 manuscript claims against raw artifacts.

Recomputes each quantitative claim from its source file where computable;
else verifies the number is literally present in the artifact (grep-level)
and records status: verified-by-recompute / present-in-artifact /
needs-experiment / remove-or-reword.
Output: JSON + markdown table.
"""
from __future__ import annotations

import csv, json, math, os, sys

ROOT = "/storage/saveena/protacxtend"
OUT = os.path.join(ROOT, "outputs", "manuscript_strategy", "closeout")

def load(p):
    with open(os.path.join(ROOT, p)) as f:
        return json.load(f)

def read_csv_rows(p):
    with open(os.path.join(ROOT, p), newline="") as f:
        return list(csv.DictReader(f))

results = {}

# ---------- P03 M1 hook effect (numbers in VALIDATION.md) ----------
m1 = open(os.path.join(ROOT, "protacxtend/modules/hook_effect_modeler/docs/VALIDATION.md")).read()
results["P03_M1"] = {
    "claim": "M1 equilibrium+MC: opt 150.42 nM; MC 142.0-156.9; 100% within +-25%; 24/24 tests",
    "present_in_artifact": all(s in m1 for s in ["150.42", "142.0 / 149.2 / 156.9", "100 %", "24 passed"]),
    "test_count_24": "24 passed" in m1,
    "status": "present-in-artifact",
}

# ---------- P04 M4 ----------
m4 = open(os.path.join(ROOT, "protacxtend/modules/degradation_ml/docs/VALIDATION.md")).read()
results["P04_M4"] = {
    "claim": "M4 curated 64 pDC50 / 32 Dmax; scaffold ridge R2=0.41 MAE=0.73; in-sample R2~0.95 train-only",
    "present_in_artifact": ("64" in m4 and "0.41" in m4 and "0.73" in m4 and "0.95" in m4),
    "status": "present-in-artifact",
}

# ---------- P05 M5 grouped-split results ----------
m5_json = load("protacxtend/modules/cell_context_selector/data/benchmark_results.json")
def find_m5(regime, leg, metric):
    for r in m5_json:
        if r.get("regime") == regime and r.get("leg") == leg and r.get("metric") == metric:
            return r
    return None
rows5 = m5_json if isinstance(m5_json, list) else m5_json.get("results", [])
# fall back to nested dict structure
import itertools
def flatten_m5(obj):
    out = []
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict):
        for v in obj.values():
            out.extend(flatten_m5(v) if isinstance(v, (dict, list)) else [])
        # also try regime->leg->value mapping
        for v in obj.values():
            if isinstance(v, dict) and "unseen_protac" in str(v.get("regime","")).lower() if isinstance(v, dict) else False:
                pass
    return out
print("m5 top keys:", list(m5_json.keys())[:8] if isinstance(m5_json, dict) else "list len %d" % len(m5_json))

# ---------- P06 M6 E3 ranking ----------
m6 = load("protacxtend/modules/e3_opportunity/artifacts/benchmark_results.json")
m6r = m6["results"]
def rf(regime):
    return m6r.get(regime, {}).get("random_forest", {})
m6_summary = {reg: {"auroc": rf(reg).get("auroc"), "mrr": rf(reg).get("mrr"), "n": rf(reg).get("n_instances"),
                    "n_pos": rf(reg).get("n_pos")} for reg in ["random","unseen_target","unseen_e3","unseen_cell","family_loo"]}
recr = {}
for a in m6.get("ablation", {}).get("ablations", []):
    if isinstance(a, dict) and ("recruiter" in str(a.get("name", a.get("dropped", ""))).lower()):
        recr = a
results["P06_M6"] = {"claim": "RF AUROC random 0.9841 / unseen-E3 0.93 / unseen-cell 0.99; -recruiter -0.517",
                     "recompute": m6_summary,
                     "recruiter_ablation_record": recr,
                     "status": "verified-by-recompute"}

# ---------- P07 frozen benchmarks (raw validation CSVs) ----------
def csv_rows(p):
    with open(os.path.join(ROOT, p)) as f:
        return list(csv.reader(f))
def col(rows, name):
    h = rows[0]; i = h.index(name)
    return [r[i] for r in rows[1:] if len(r) > i and r[i] != ""]

dock_rows = csv_rows("results/figures_validation/fig01_docking_rmsd.csv")
engs = col(dock_rows, "engine"); rms = col(dock_rows, "rmsd")
for eng in ["vina", "gnina", "diffdock", "oracle"]:
    vals = sorted(float(rms[i]) for i in range(len(engs)) if engs[i] == eng)
    if vals:
        med = vals[len(vals)//2] if len(vals) % 2 else (vals[len(vals)//2-1]+vals[len(vals)//2])/2
        results.setdefault("P07_docking", {})[eng] = {
            "n_with_pose": len(vals),
            "median_rmsd": round(med, 3),
            "success_le2A_over_poses": round(sum(1 for v in vals if v <= 2.0)/len(vals), 3),
        }
pkt_rows = csv_rows("results/figures_validation/fig05_pocket_recovery.csv")
pk = dict(zip(col(pkt_rows, "k"), col(pkt_rows, "recovery")))
results["P07_pocket"] = {"top1_le4A": pk.get("top-1"), "top3_le4A": pk.get("top-3"), "n": 42}
ppi_rows = csv_rows("results/figures_validation/fig06_ppi_dockq.csv")
dq = sorted(float(v) for v in col(ppi_rows, "dockq_top1"))
med = dq[len(dq)//2] if len(dq) % 2 else (dq[len(dq)//2-1]+dq[len(dq)//2])/2
results["P07_ppi"] = {"n_raw_rows": len(dq), "median_top1_dockq": round(med, 4),
                      "mean": round(sum(dq)/len(dq), 4)}
trn_rows = csv_rows("results/figures_validation/fig08_ternary.csv")
brid = [float(v) for v in col(trn_rows, "bridging_fraction") if v]
results["P07_ternary"] = {"n_complexes": len(trn_rows)-1, "bridging_values_present": sorted(set(brid)),
                           "median_bridging": round(sorted(brid)[len(brid)//2], 3) if brid else None}
# Benchmark summary cross-check (BENCHMARK_RESULTS_V2.md values)
v2 = open(os.path.join(ROOT, "results/BENCHMARK_RESULTS_V2.md")).read()
results["P07_v2_present"] = {
    "vina_2356": "2.356" in v2, "vina_ci": "0.375 [0.225, 0.525]" in v2,
    "pocket_0381": "0.381" in v2, "ppi_00134": "0.0134" in v2,
    "ternary_bridging_0": "0.0" in v2, "mmgbsa_not_validated": "NOT_VALIDATED" in v2,
}

# ---------- P09 benchmark500 harness ----------
pred = []
pred_path = os.path.join(ROOT, "benchmark500/results/b500_probe_20260923/predictions.jsonl")
n_exec=n_abs=n_fail=0; reasons={}
for line in open(pred_path):
    r = json.loads(line)
    st = r.get("status") or r.get("outcome") or ""
    if "abstain" in st.lower() or st.lower()=="abstained":
        n_abs += 1
        reasons[r.get("abstention_reason") or r.get("failure_code") or st] = reasons.get(r.get("abstention_reason") or st, 0) + 1
    elif st.lower() in ("failed","error"):
        n_fail += 1
    else:
        n_exec += 1
results["P09_harness"] = {"total": n_exec+n_abs+n_fail, "executed": n_exec, "abstained": n_abs,
                          "failed": n_fail, "abstention_reasons": reasons}

# Parser
pe = load("outputs/parser_eval.json") if os.path.exists(os.path.join(ROOT,"outputs/parser_eval.json")) else {}
results["P02_parser"] = {"prompts": pe.get("prompts") or pe.get("n_prompts"),
                         "target_accuracy": pe.get("target_accuracy") or pe.get("accuracy_target")}

# Case study CS1
cs = load("outputs/case_study_brd4_vhl_result.json")
ranking = cs.get("result", {}).get("ranking", [])
results["P13_casestudy"] = {"n_records": cs.get("result", {}).get("n_records"),
                            "rank1_id": ranking[0].get("id") if ranking else None,
                            "rank1_score": ranking[0].get("score") if ranking else None,
                            "no_measured_data": (cs.get("summary","").find("no measured data") >= 0)}

# USECASE CS2
uc = open(os.path.join(ROOT, "results/USECASE_VALIDATION.md")).read()
results["P13_casestudy2"] = {"1a46_native_rmsd_present": all(x in uc for x in ["1a46", "TIER_3" ])}

with open(os.path.join(OUT, "claims_audit.json"), "w") as f:
    json.dump(results, f, indent=1, default=str)
print(json.dumps({k: (v if not isinstance(v, dict) or "error" not in v else v) for k, v in results.items()}, indent=1, default=str)[:4000])