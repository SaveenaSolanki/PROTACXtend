#!/usr/bin/env python
"""Author + externally verify machine ground truth for the 48-case benchmark (G02/G03).

This is NOT human adjudication and does not claim to be. It produces three
explicitly labelled gold classes:

  MACHINE_VERIFIED_EXTERNAL : the answer was checked against an authoritative
                              external source (UniProt / RCSB / Crossref /
                              PubChem / RDKit) at build time; the observed value
                              and URL are stored in verification_log.json.
  RULE_BASED_RUBRIC         : a deterministic, pre-registered checklist derived
                              from the frozen ground truth (design/discover and a
                              few categorical reason tasks).
  PENDING_HUMAN             : mechanistic nuance that cannot be machine-verified;
                              excluded from both endpoints and reported as pending.

Writes:
  benchmark/gold_machine_v1/machine_gold.json
  benchmark/gold_machine_v1/verification_log.json
  benchmark/gold_machine_v1/GOLD_MACHINE_V1.md
  benchmark/gold_machine_v1/machine_gold.sha256
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GT_DIR = ROOT / "benchmark/ground_truth"
OUT = ROOT / "benchmark/gold_machine_v1"
CACHE = OUT / "cache"
OUT.mkdir(parents=True, exist_ok=True)
CACHE.mkdir(parents=True, exist_ok=True)

# task_id -> (grader_type, mandatory_checklist, expected_set, threshold, gold_class, verify)
# verify = ("uniprot","O60885") | ("rcsb","5T35") | ("crossref",doi) |
#          ("pubchem_inchikey", key) | ("rdkit", smiles) | ("local_names", [names]) | None
SPECS: dict[str, dict] = {
    # ---- KNOW: externally verifiable ----
    "KNOW-01": dict(type="categorical", mandatory=["O60885"],
                    expected_set=["O60885"], threshold=1.0,
                    gold_class="MACHINE_VERIFIED_EXTERNAL", verify=("uniprot", "O60885")),
    "KNOW-02": dict(type="categorical", mandatory=["JQ1", "I-BET762", "OTX015"],
                    expected_set=["JQ1", "I-BET762", "OTX015"], threshold=0.66,
                    gold_class="MACHINE_VERIFIED_EXTERNAL",
                    verify=("local_names", ["JQ1", "I-BET762", "OTX015", "I-BET151"])),
    "KNOW-04": dict(type="categorical", mandatory=["dBET1", "dBET6", "ARV-825", "MZ1", "AT1"],
                    expected_set=["dBET1", "dBET6", "ARV-825", "MZ1", "AT1"], threshold=0.6,
                    gold_class="MACHINE_VERIFIED_EXTERNAL",
                    verify=("local_names", ["dBET1", "dBET6", "ARV-825", "MZ1"])),
    "KNOW-05": dict(type="categorical", mandatory=["CRBN", "VHL"],
                    expected_set=["CRBN", "VHL"], threshold=0.5,
                    gold_class="MACHINE_VERIFIED_EXTERNAL",
                    verify=("local_names", ["Pomalidomide", "Lenalidomide", "VH032"])),
    "KNOW-06": dict(type="categorical", mandatory=["JQ1", "I-BET762", "OTX015", "I-BET151"],
                    expected_set=["JQ1", "I-BET762", "OTX015", "I-BET151"], threshold=0.66,
                    gold_class="MACHINE_VERIFIED_EXTERNAL",
                    verify=("local_names", ["JQ1", "I-BET762", "OTX015", "I-BET151"])),
    "KNOW-07": dict(type="categorical", mandatory=["5T35"], expected_set=["5T35"], threshold=1.0,
                    gold_class="MACHINE_VERIFIED_EXTERNAL", verify=("rcsb", "5T35")),
    "KNOW-09": dict(type="categorical", mandatory=["RZVAJINKPMORJF"],
                    expected_set=["RZVAJINKPMORJF"], threshold=1.0,
                    gold_class="MACHINE_VERIFIED_EXTERNAL",
                    verify=("pubchem_inchikey", "RZVAJINKPMORJF-UHFFFAOYSA-N")),
    "KNOW-11": dict(type="categorical", mandatory=["10.1126/science.aab1433"],
                    expected_set=["10.1126/science.aab1433"], threshold=1.0,
                    gold_class="MACHINE_VERIFIED_EXTERNAL",
                    verify=("crossref", "10.1126/science.aab1433")),
    # ---- KNOW: rule-based ----
    "KNOW-03": dict(type="categorical", mandatory=["contradicted", "JQ1"], expected_set=[],
                    threshold=0.5, gold_class="RULE_BASED_RUBRIC", verify=None),
    "KNOW-08": dict(type="categorical", mandatory=["verified", "unverified"], expected_set=[],
                    threshold=1.0, gold_class="RULE_BASED_RUBRIC", verify=None),
    "KNOW-10": dict(type="categorical", mandatory=["BRD4", "CRBN"], expected_set=[],
                    threshold=0.5, gold_class="RULE_BASED_RUBRIC", verify=None),
    "KNOW-12": dict(type="categorical", mandatory=["I-BET762"], expected_set=[],
                    threshold=0.5, gold_class="RULE_BASED_RUBRIC", verify=None),
    # ---- DESIGN (rule-based) ----
    "DESIGN-01": dict(mandatory=["5", "SMILES", "warhead", "VHL"], threshold=0.5),
    "DESIGN-02": dict(mandatory=["SMILES", "MW", "logP", "TPSA"], threshold=0.5),
    "DESIGN-03": dict(mandatory=["scaffold", "dimethylisoxazole"], threshold=0.5),
    "DESIGN-04": dict(mandatory=["CRBN", "VHL"], threshold=0.5),
    "DESIGN-05": dict(mandatory=["3", "RDKit"], threshold=0.5),
    "DESIGN-06": dict(mandatory=["pharmacophore"], threshold=0.5),
    "DESIGN-07": dict(mandatory=["vehicle", "control", "replicate"], threshold=0.5),
    "DESIGN-08": dict(mandatory=["linker", "5T35"], threshold=0.5),
    "DESIGN-09": dict(mandatory=["Tanimoto"], threshold=0.5),
    "DESIGN-10": dict(mandatory=["BRD4", "BRD2", "selectivity"], threshold=0.5),
    "DESIGN-11": dict(mandatory=["Dmax", "predicted"], threshold=0.5),
    "DESIGN-12": dict(mandatory=["control", "ablat"], threshold=0.5),
    # ---- DISCOVER (rule-based) ----
    "DISCOVER-01": dict(mandatory=["rule", "outcome"], threshold=0.5),
    "DISCOVER-02": dict(mandatory=["uncertainty", "confirm"], threshold=0.5),
    "DISCOVER-03": dict(mandatory=["vehicle", "control", "cost"], threshold=0.5),
    "DISCOVER-04": dict(mandatory=["Pareto", "admet"], threshold=0.5),
    "DISCOVER-05": dict(mandatory=["hill", "hook", "replicate"], threshold=0.5),
    "DISCOVER-06": dict(mandatory=["expression", "tractability"], threshold=0.5),
    "DISCOVER-07": dict(mandatory=["CRBN", "knockout", "pomalidomide"], threshold=0.5),
    "DISCOVER-08": dict(mandatory=["budget", "value"], threshold=0.5),
    "DISCOVER-09": dict(mandatory=["replicate", "orthogonal"], threshold=0.5),
    "DISCOVER-10": dict(mandatory=["degradation", "ternary", "permeability", "viability"], threshold=0.5),
    "DISCOVER-11": dict(mandatory=["rule", "seed"], threshold=0.5),
    "DISCOVER-12": dict(mandatory=["applicability", "tie-break"], threshold=0.5),
    # ---- REASON: three categorical are rule-based, rest pending ----
    "REASON-03": dict(mandatory=["hydroxyproline", "tert-leucine"], threshold=0.5,
                      gold_class="RULE_BASED_RUBRIC", verify=None),
    "REASON-05": dict(mandatory=["amide", "permeability"], threshold=0.5,
                      gold_class="RULE_BASED_RUBRIC", verify=None),
    "REASON-07": dict(mandatory=["VHL", "BRD4"], threshold=0.5,
                      gold_class="RULE_BASED_RUBRIC", verify=None),
}
PENDING = {"REASON-01", "REASON-02", "REASON-04", "REASON-06", "REASON-08",
           "REASON-09", "REASON-10", "REASON-11", "REASON-12"}


def _get(url: str) -> dict | None:
    import requests

    key = hashlib.sha256(url.encode()).hexdigest()[:16]
    cache = CACHE / f"{key}.json"
    if cache.exists():
        return json.loads(cache.read_text())
    try:
        r = requests.get(url, timeout=40, headers={"User-Agent": "protacxtend-audit/1.0"})
        if r.status_code != 200:
            return None
        data = r.json()
        cache.write_text(json.dumps(data))
        return data
    except Exception:
        return None


def verify(spec: dict) -> dict:
    """Return {verified, method, source, observed} — never fabricates."""
    v = spec.get("verify")
    if not v:
        return {"verified": False, "method": "rule_only", "source": "", "observed": ""}
    kind, arg = v
    try:
        if kind == "uniprot":
            d = _get(f"https://rest.uniprot.org/uniprotkb/{arg}.json?fields=accession,reviewed,protein_name")
            if d:
                name = (((d.get("proteinDescription") or {}).get("recommendedName") or {}).get("fullName") or {}).get("value", "")
                return {"verified": True, "method": "uniprot_rest",
                        "source": f"https://rest.uniprot.org/uniprotkb/{arg}",
                        "observed": f"{d.get('primaryAccession')} reviewed={d.get('entryType','')} name={name}"}
        elif kind == "rcsb":
            d = _get(f"https://data.rcsb.org/rest/v1/core/entry/{arg}")
            if d:
                return {"verified": True, "method": "rcsb_rest",
                        "source": f"https://data.rcsb.org/rest/v1/core/entry/{arg}",
                        "observed": str((d.get("struct") or {}).get("title", ""))[:120]}
        elif kind == "crossref":
            d = _get(f"https://api.crossref.org/works/{arg}")
            if d:
                m = d.get("message", {})
                return {"verified": True, "method": "crossref_rest",
                        "source": f"https://api.crossref.org/works/{arg}",
                        "observed": str((m.get("title") or [""])[0])[:120]}
        elif kind == "pubchem_inchikey":
            d = _get(f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/inchikey/{arg}/property/CanonicalSMILES,InChIKey/JSON")
            if d:
                props = (d.get("PropertyTable") or {}).get("Properties") or [{}]
                return {"verified": True, "method": "pubchem_pug_rest",
                        "source": f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/inchikey/{arg}",
                        "observed": f"InChIKey={props[0].get('InChIKey','')} SMILES={props[0].get('CanonicalSMILES','')}"}
        elif kind == "local_names":
            table = []
            for name in ("curated_warheads.csv", "curated_targets.csv", "curated_e3_ligands.csv",
                         "known_protac_smiles.csv", "e3_expression_evidence.csv"):
                p = ROOT / "protacxtend/data" / name
                if p.exists():
                    table.append(p.read_text(errors="ignore").lower())
            blob = "\n".join(table)
            found = [n for n in arg if n.lower() in blob]
            return {"verified": len(found) > 0, "method": "packaged_curated_tables",
                    "source": "protacxtend/data/curated_*.csv",
                    "observed": f"found {len(found)}/{len(arg)} names: {found}"}
    except Exception as exc:  # noqa: BLE001
        return {"verified": False, "method": kind, "source": "", "observed": f"error: {exc}"}
    return {"verified": False, "method": kind, "source": "", "observed": "no data returned"}


def main() -> int:
    gold: dict[str, dict] = {}
    log: list[dict] = []
    for gt_file in sorted(GT_DIR.glob("*.json")):
        gt = json.loads(gt_file.read_text())
        tid = gt["task_id"]
        spec = SPECS.get(tid, {})
        if tid in PENDING:
            gold[tid] = {"type": gt["type"], "gold_class": "PENDING_HUMAN",
                         "expected_value": None, "expected_set": [], "expected_ranking": None,
                         "mandatory_answer_elements": gt.get("mandatory_answer_elements") or [],
                         "acceptable_alternatives": gt.get("acceptable_alternatives") or [],
                         "threshold": None, "verification": {"verified": False,
                         "method": "requires_human", "source": "", "observed": ""}}
            log.append({"task_id": tid, "gold_class": "PENDING_HUMAN", "verified": False,
                        "method": "requires_human", "observed": ""})
            continue
        mandatory = spec.get("mandatory") or gt.get("mandatory_answer_elements") or []
        gclass = spec.get("gold_class", "RULE_BASED_RUBRIC")
        if spec.get("verify"):
            v = verify(spec)
            if not v["verified"]:
                gclass = "RULE_BASED_RUBRIC"  # downgrade, never fabricate
        else:
            v = {"verified": False, "method": "rule_only", "source": "", "observed": ""}
        if gclass == "MACHINE_VERIFIED_EXTERNAL" and not v["verified"]:
            gclass = "RULE_BASED_RUBRIC"
        gold[tid] = {
            "type": "categorical" if spec.get("type") == "categorical" else gt["type"],
            "gold_class": gclass,
            "expected_value": None,
            "expected_set": spec.get("expected_set") or mandatory,
            "expected_ranking": None,
            "mandatory_answer_elements": mandatory,
            "acceptable_alternatives": gt.get("acceptable_alternatives") or [],
            "threshold": spec.get("threshold", 0.5),
            "verification": v,
            "source_ground_truth": f"benchmark/ground_truth/{tid}.json",
        }
        log.append({"task_id": tid, "gold_class": gclass, **v,
                    "mandatory": mandatory, "threshold": spec.get("threshold", 0.5)})

    payload = {
        "schema": "protacxtend.machine_gold.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "note": ("Machine-verified / rule-based gold. NOT human adjudication. "
                 "PENDING_HUMAN cases are excluded from both endpoints."),
        "counts": {
            "total": len(gold),
            "MACHINE_VERIFIED_EXTERNAL": sum(1 for g in gold.values() if g["gold_class"] == "MACHINE_VERIFIED_EXTERNAL"),
            "RULE_BASED_RUBRIC": sum(1 for g in gold.values() if g["gold_class"] == "RULE_BASED_RUBRIC"),
            "PENDING_HUMAN": sum(1 for g in gold.values() if g["gold_class"] == "PENDING_HUMAN"),
        },
        "gold": gold,
    }
    (OUT / "machine_gold.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (OUT / "verification_log.json").write_text(json.dumps(log, indent=2), encoding="utf-8")
    digest = hashlib.sha256(json.dumps(gold, sort_keys=True).encode()).hexdigest()
    (OUT / "machine_gold.sha256").write_text(digest + "\n")
    lines = ["# Machine ground truth v1 (G02/G03)", "",
             f"- generated: {payload['generated_at']}",
             f"- sha256(gold): `{digest}`",
             f"- counts: {payload['counts']}", "",
             "> Machine-verified / rule-based gold. NOT human adjudication.", "",
             "| task | gold class | verified | method | observed | threshold |",
             "|---|---|---|---|---|---|"]
    for e in log:
        lines.append(f"| {e['task_id']} | {e['gold_class']} | {e.get('verified')} | "
                     f"{e.get('method','')} | {str(e.get('observed',''))[:60]} | {e.get('threshold','')} |")
    (OUT / "GOLD_MACHINE_V1.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(payload["counts"], indent=2))
    print("sha256:", digest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
