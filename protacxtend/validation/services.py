"""Live remote-service verification with explicit connectivity outcomes.

Each declared service is probed with a real HTTP request (short timeout) and
classified as:

    LIVE_VERIFIED   HTTP 2xx from the sanctioned endpoint
    AUTH_REQUIRED   HTTP 401/403 (or a declared key is missing)
    RATE_LIMITED    HTTP 429
    UNAVAILABLE     DNS/connection/timeout or 5xx
    DECLARED_ONLY   no probe URL configured (name exists in the registry only)
"""

from __future__ import annotations

import json
import os
import time
from typing import Any

from protacxtend.audit.provenance import host_fingerprint
from protacxtend.validation.datasets import ROOT
from protacxtend.validation.io import RowWriter, write_summary_json

OUT = ROOT / "results" / "benchmarks" / "services"

# name, kind, url, method, auth_env (API key), json_body
SERVICES: list[dict[str, Any]] = [
    {"name": "ChEMBL", "kind": "database", "url": "https://www.ebi.ac.uk/chembl/api/data/status.json"},
    {"name": "PubChem PUG-REST", "kind": "database",
     "url": "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/ethanol/property/MolecularWeight/JSON"},
    {"name": "UniProt REST", "kind": "database",
     "url": "https://rest.uniprot.org/uniprotkb/P00533.json?size=1"},
    {"name": "RCSB PDB", "kind": "database", "url": "https://files.rcsb.org/download/1A46.pdb"},
    {"name": "RCSB Search API", "kind": "web_service",
     "url": "https://search.rcsb.org/rcsbsearch/v2/query?json=%7B%22query%22%3A%7B%22type%22%3A%22terminal%22%2C%22service%22%3A%22full_text%22%2C%22parameters%22%3A%7B%22value%22%3A%22BRD4%22%7D%7D%2C%22return_type%22%3A%22entry%22%2C%22request_options%22%3A%7B%22paginate%22%3A%7B%22start%22%3A0%2C%22rows%22%3A1%7D%7D%7D"},
    {"name": "AlphaFold DB", "kind": "database",
     "url": "https://alphafold.ebi.ac.uk/api/prediction/P00533"},
    {"name": "BindingDB", "kind": "database",
     "url": "https://www.bindingdb.org/rest/getLigandsByUniprots?uniprot=P00533&response=json"},
    {"name": "Open Targets Platform", "kind": "web_service",
     "url": "https://api.platform.opentargets.org/api/v4/graphql",
     "method": "POST", "json": {"query": "{ target(ensemblId: \"ENSG00000157764\") { id approvedSymbol } }"},
     "headers": {"Content-Type": "application/json"}},
    {"name": "STRING DB", "kind": "database",
     "url": "https://string-db.org/api/json/network?identifiers=BRD4&species=9606"},
    {"name": "BioGRID", "kind": "database",
     "url": "https://webservice.thebiogrid.org/interactions/?geneList=BRD4&accesskey=test&format=json",
     "auth_env": "BIOGRID_API_KEY"},
    {"name": "IntAct", "kind": "database",
     "url": "https://www.ebi.ac.uk/intact/ws/interaction/findInteractions/BRD4?page=0&pageSize=1"},
    {"name": "Complex Portal", "kind": "database",
     "url": "https://www.ebi.ac.uk/intact/complex-ws/search/BRD4?page=0&pageSize=1"},
    {"name": "Europe PMC", "kind": "database",
     "url": "https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=PROTAC&format=json&pageSize=1"},
    {"name": "PubMed E-utilities", "kind": "web_service",
     "url": "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term=PROTAC&retmode=json&retmax=1"},
    {"name": "Crossref", "kind": "web_service", "url": "https://api.crossref.org/works?query=PROTAC&rows=1"},
    {"name": "OpenAlex", "kind": "web_service",
     "url": "https://api.openalex.org/works?search=PROTAC&per-page=1"},
    {"name": "Semantic Scholar", "kind": "web_service",
     "url": "https://api.semanticscholar.org/graph/v1/paper/search?query=PROTAC&limit=1",
     "auth_env": "SEMANTIC_SCHOLAR_API_KEY"},
    {"name": "ClinicalTrials.gov", "kind": "database",
     "url": "https://clinicaltrials.gov/api/v2/studies?query.term=PROTAC&pageSize=1"},
    {"name": "ZINC", "kind": "database", "url": "https://zinc15.docking.org/substances/AAAHCFVXZLMODC-OWOJBTEDSA-N.json"},
    {"name": "PDBe API", "kind": "web_service", "url": "https://www.ebi.ac.uk/pdbe/api/pdb/entry/summary/1a46"},
    {"name": "Human Protein Atlas", "kind": "database",
     "url": "https://www.proteinatlas.org/api/search_download.php?search=BRD4&format=json&columns=g,eg&compress=no"},
    {"name": "GTEx", "kind": "database",
     "url": "https://gtexportal.org/api/v2/reference/gene?geneId=ENSG00000157764"},
    {"name": "PRIDE Archive", "kind": "database",
     "url": "https://www.ebi.ac.uk/pride/ws/archive/v2/search/projects?keyword=BRD4&pageSize=1"},
    {"name": "ProteomicsDB", "kind": "database",
     "url": "https://www.proteomicsdb.org/proteomicsdb/logic/api/protein/BRD4/", "auth_env": "PROTEOMICSDB_KEY"},
    {"name": "PhosphoSitePlus", "kind": "database",
     "url": "https://www.phosphosite.org/api/search?q=BRD4", "auth_env": "PHOSPHOSITE_KEY"},
    {"name": "UbiBrowser", "kind": "database", "url": "http://ubibrowser.ncpsb.org.cn/ubibrowser/api/search?gene=BRD4"},
    {"name": "DrugBank", "kind": "database",
     "url": "https://go.drugbank.com/drugs/DB00001.json", "auth_env": "DRUGBANK_API_KEY"},
    {"name": "Lens.org", "kind": "database", "url": "https://api.lens.org/patent/search",
     "method": "POST", "json": {"query": {"match": {"title": "PROTAC"}}, "size": 1},
     "headers": {"Content-Type": "application/json"}, "auth_env": "LENS_API_KEY"},
    {"name": "SureChEMBL", "kind": "database",
     "url": "https://www.surechembl.org/api/search?q=PROTAC", "auth_env": "SURECHEMBL_KEY"},
    {"name": "SwissADME", "kind": "web_service", "url": "http://www.swissadme.ch/index.php"},
    {"name": "ADMETlab 3.0", "kind": "web_service", "url": "https://admetlab3.scbdd.com/api/" },
    {"name": "Protox-II", "kind": "web_service", "url": "https://tox.newmexicotrials.org/api/"},
    {"name": "HADDOCK web", "kind": "web_service", "url": "https://wenmr.science.uu.nl/haddock2.4/"},
    {"name": "ClusPro", "kind": "web_service", "url": "https://cluspro.org/"},
    {"name": "PatchDock", "kind": "web_service", "url": "https://bioinfo3d.cs.tau.ac.il/PatchDock/"},
    {"name": "NCI CACTUS", "kind": "web_service",
     "url": "https://cactus.nci.nih.gov/chemical/structure/aspirin/smiles"},
    {"name": "OPSIN", "kind": "web_service",
     "url": "https://opsin.ch.cam.ac.uk/opsin/aspirin.json"},
    {"name": "SAbDab", "kind": "database", "url": "https://opig.stats.ox.ac.uk/webapps/newsabdab/sabdab/summary/all/"},
    {"name": "OWL/OPM", "kind": "database", "url": "https://opm.phar.umich.edu/"},
    {"name": "DeepChem MoleculeNet", "kind": "dataset",
     "url": "https://deepchemdata.s3-us-west-1.amazonaws.com/datasets/delaney-processed.csv"},
    # declared-only (no public probe URL / licence-restricted)
    {"name": "PROTAC-DB 3.0", "kind": "database", "url": "", "note": "academic curated download"},
    {"name": "PROTACpedia", "kind": "database", "url": "", "note": "web portal"},
    {"name": "TPDdb", "kind": "database", "url": "", "note": "web portal"},
    {"name": "PROTAC-8K", "kind": "dataset", "url": "", "note": "paper supplement"},
    {"name": "PDBbind", "kind": "database", "url": "", "note": "licence-gated"},
    {"name": "IUPHAR/BPS Guide", "kind": "database", "url": "", "note": "web portal"},
    {"name": "DepMap", "kind": "database", "url": "", "note": "bulk download"},
    {"name": "Enamine REAL", "kind": "database", "url": "", "note": "commercial"},
    {"name": "COSMIC", "kind": "database", "url": "", "note": "registration required"},
    {"name": "OMIM", "kind": "database", "url": "", "note": "registration required"},
]


def _probe(service: dict[str, Any], timeout: int = 20) -> dict[str, Any]:
    url = service.get("url")
    auth_env = service.get("auth_env")
    if not url:
        return {"outcome": "DECLARED_ONLY", "http_status": None, "latency_s": 0.0,
                "detail": service.get("note", "no probe URL")}
    if auth_env and not os.environ.get(auth_env):
        return {"outcome": "AUTH_REQUIRED", "http_status": None, "latency_s": 0.0,
                "detail": f"missing credential env {auth_env}"}
    import requests

    headers = dict(service.get("headers") or {})
    if auth_env:
        headers["Authorization"] = f"Bearer {os.environ[auth_env]}"
    t0 = time.time()
    try:
        method = service.get("method", "GET")
        if method == "POST":
            resp = requests.post(url, json=service.get("json"), headers=headers, timeout=timeout)
        else:
            resp = requests.get(url, headers=headers, timeout=timeout)
        latency = round(time.time() - t0, 3)
        status = resp.status_code
        if 200 <= status < 300:
            outcome = "LIVE_VERIFIED"
        elif status in (401, 403):
            outcome = "AUTH_REQUIRED"
        elif status == 429:
            outcome = "RATE_LIMITED"
        elif status >= 500:
            outcome = "UNAVAILABLE"
        else:
            outcome = "UNAVAILABLE"
        return {"outcome": outcome, "http_status": status, "latency_s": latency,
                "detail": f"HTTP {status}"}
    except requests.exceptions.Timeout:
        return {"outcome": "UNAVAILABLE", "http_status": None,
                "latency_s": round(time.time() - t0, 3), "detail": "timeout"}
    except Exception as exc:  # noqa: BLE001
        return {"outcome": "UNAVAILABLE", "http_status": None,
                "latency_s": round(time.time() - t0, 3),
                "detail": f"{type(exc).__name__}: {exc}"[:160]}


def run(services: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    services = services or SERVICES
    OUT.mkdir(parents=True, exist_ok=True)
    row = RowWriter("service_rows", OUT)
    for service in services:
        result = _probe(service)
        row.add({
            "benchmark": "services", "name": service["name"], "kind": service["kind"],
            "url": service.get("url", ""), "outcome": result["outcome"],
            "status": result["outcome"], "success": result["outcome"] == "LIVE_VERIFIED",
            "http_status": result["http_status"], "latency_s": result["latency_s"],
            "detail": result["detail"],
            "requires_auth": bool(service.get("auth_env")),
            "reason": service.get("note", ""),
            **row.provenance(dataset="service_inventory_v1",
                             source="declared service registry",
                             software="requests", command="HTTP probe",
                             output_path=str(OUT)),
        })
        print(f"[services] {service['name']}: {result['outcome']} ({result['detail']})")
    summary = _summary(row.rows)
    row.finalize(summary)
    write_summary_json(OUT / "services_summary.json", summary)
    print("\n" + str(summary))
    return summary


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    from collections import Counter

    counts = Counter(r["outcome"] for r in rows)
    live = [r for r in rows if r["outcome"] == "LIVE_VERIFIED"]
    return {
        "n_services": len(rows), "outcomes": dict(counts),
        "live_verified": counts.get("LIVE_VERIFIED", 0),
        "declared_only": counts.get("DECLARED_ONLY", 0),
        "auth_required": counts.get("AUTH_REQUIRED", 0),
        "unavailable": counts.get("UNAVAILABLE", 0),
        "rate_limited": counts.get("RATE_LIMITED", 0),
        "live_verified_names": [r["name"] for r in live],
        "median_latency_s": round(sorted(r["latency_s"] for r in live)[len(live) // 2], 3) if live else None,
        "host": host_fingerprint(),
    }


__all__ = ["run", "OUT", "SERVICES"]
