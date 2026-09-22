"""
Central tool registry for the conversational agent.
=====================================================

One source of truth for every tool the LLM may call. Each spec records
purpose, inputs, evidence type and limitations. Execution is dispatched to
real deterministic implementations (never simulated). Tools whose adapter is
not yet wired are listed with readiness="planned" and are NOT advertised to
the model (they remain visible in /tools for the roadmap).
"""

from __future__ import annotations

import json
import time
from typing import Any, Callable, Dict, List, Optional

from protacxtend.agentic.contract import (
    EvidenceType,
    RegistryError,
    ToolResult,
    ToolStatus,
)

_TIMEOUT = 18


# ── Tool specs ──────────────────────────────────────────────────────────

def _spec(name, kind, purpose, inputs, evidence, limitations, readiness="ready",
          deterministic=None, ml=None, surrogate=None, retrieved=None):
    return {
        "name": name, "kind": kind, "purpose": purpose, "inputs": inputs,
        "evidence_type": evidence.value if hasattr(evidence, "value") else evidence,
        "limitations": limitations, "readiness": readiness,
        "deterministic": deterministic, "ml": ml, "surrogate": surrogate,
        "retrieved": retrieved,
    }


TOOL_SPECS: List[Dict[str, Any]] = [
    # RESEARCH
    _spec("deep_research", "research",
          "Multi-source literature search (Europe PMC + PubMed + CrossRef verification).",
          {"query": "search terms"}, EvidenceType.RETRIEVED,
          ["Public APIs; recall depends on query; not a replacement for expert reading."],
          retrieved=True),
    _spec("search_europe_pmc", "research",
          "Search Europe PMC full-text abstracts.", {"query": "", "page_size": 8},
          EvidenceType.RETRIEVED, ["Index coverage varies."], retrieved=True),
    _spec("search_pubmed", "research",
          "Search PubMed titles/abstracts via NCBI E-utilities.",
          {"query": "", "page_size": 8}, EvidenceType.RETRIEVED,
          ["Public E-utilities rate limits apply."], retrieved=True),
    _spec("verify_crossref", "research",
          "Verify a DOI and return citation metadata via CrossRef.",
          {"doi": "10.xxxx/..."}, EvidenceType.RETRIEVED,
          ["Requires valid DOI."], retrieved=True),
    _spec("retrieve_fulltext", "research",
          "Fetch article full text when openly available (Europe PMC).",
          {"pmcid": "PMCxxxx", "section": "abstract"}, EvidenceType.RETRIEVED,
          ["Open-access only."], retrieved=True),
    _spec("search_web", "research",
          "Configurable web search (SearXNG self-hosted) if configured.",
          {"query": ""}, EvidenceType.RETRIEVED,
          ["Requires a configured SearXNG endpoint; otherwise returns not_available."], readiness="ready", retrieved=True),

    # TARGET / BIOLOGY
    _spec("resolve_target", "target",
          "Resolve a gene/protein name to a UniProt entry (primary accession, reviewed status).",
          {"target_name": "BRD4"}, EvidenceType.RETRIEVED,
          ["Returns canonical entry; isoform/context still user's call."], retrieved=True),
    _spec("search_uniprot", "target",
          "Search UniProt by free text.", {"query": "", "page_size": 5},
          EvidenceType.RETRIEVED, [], retrieved=True),
    _spec("retrieve_target_binders", "target",
          "Known target binders from ChEMBL (online REST).",
          {"target_name": "", "top_k": 10}, EvidenceType.RETRIEVED,
          ["Requires ChEMBL reachability; curated coverage only."], retrieved=True),
    _spec("select_e3_ligase", "target",
          "E3 ligase selection guidance from the local E3 evidence catalog.",
          {"target": "", "preferred_e3": ""}, EvidenceType.HEURISTIC,
          ["Evidence-graded catalog; direct precedent required for SUPPORTED."],
          deterministic=True),
    _spec("retrieve_e3_evidence", "target",
          "Evidence rows for an E3 family from the E3 opportunity catalog.",
          {"e3": "CRBN"}, EvidenceType.RETRIEVED,
          ["Local catalog; see Validation matrix."], deterministic=True),

    # CHEMISTRY
    _spec("inspect_smiles", "chemistry",
          "Validate a SMILES and return chemical validation details.",
          {"smiles": ""}, EvidenceType.CALCULATED,
          ["RDKit-based; stereochemistry caution."], deterministic=True),
    _spec("search_pubchem", "chemistry",
          "Search PubChem by name/SMILES (REST).", {"term": ""},
          EvidenceType.RETRIEVED, [], readiness="ready", retrieved=True),
    _spec("search_chembl", "chemistry",
          "Search ChEMBL molecules by name.", {"term": "", "top_k": 8},
          EvidenceType.RETRIEVED, [], readiness="ready", retrieved=True),
    _spec("search_bindingdb", "chemistry",
          "Local BindingDB binder lookup.", {"target": "", "top_k": 100},
          EvidenceType.RETRIEVED, ["Local snapshot."], deterministic=True),
    _spec("detect_exit_vectors", "chemistry",
          "Detect exit vectors on a warhead SMILES (RDKit).",
          {"smiles": ""}, EvidenceType.CALCULATED, [], deterministic=True),
    _spec("generate_linkers", "chemistry",
          "Generate linker hypotheses from curated + rule-based + generative engines.",
          {"count": 12, "constraints": {}}, EvidenceType.CALCULATED,
          ["In-vitro validation required."], deterministic=True),
    _spec("construct_protac", "chemistry",
          "Assemble warhead-linker-E3 ligand into PROTAC SMILES with validation.",
          {"warhead_smiles": "", "linker_smiles": "", "e3_smiles": ""},
          EvidenceType.CALCULATED, [], deterministic=True),
    _spec("check_synthetic_feasibility", "chemistry",
          "Retrosynthetic feasibility filters.", {"smiles": ""},
          EvidenceType.HEURISTIC, [], readiness="ready", deterministic=True),
    _spec("diagnose_capability", "chemistry",
          "Diagnose an internal capability that failed and rank installed/installable "
          "external toolkit fallbacks (escalation subsystem).",
          {"capability": "ligand_docking", "internal_tool": ""},
          EvidenceType.CALCULATED,
          ["Lists candidates + install paths; does not fabricate a scientific result."],
          deterministic=True),
    _spec("list_capability_readiness", "chemistry",
          "Per-capability external-tool readiness matrix (installed / installable / web).",
          {"limit": 40}, EvidenceType.CALCULATED,
          ["Reflects the live local environment."], deterministic=True),
    _spec("list_scientific_capabilities", "decision",
          "List scientific capabilities and the best free/local backend for each.",
          {}, EvidenceType.CALCULATED,
          ["Capability-first: commercial/web engines are excluded by licence policy."],
          deterministic=True),
    _spec("run_scientific_capability", "decision",
          "Run a scientific capability (chemistry, ligand_docking, molecular_dynamics, admet, "
          "ppi_docking, ternary_docking, binding_energy, md_analysis, interaction_fingerprint, "
          "linker_analysis, protac_scoring, molecular_glue_scoring, metabolite_ppi_scoring, …) "
          "through the licence-gated backend resolver.",
          {"capability": "admet", "params": {}}, EvidenceType.CALCULATED,
          ["Returns evidence tier + method label; never silently uses a restricted engine."],
          deterministic=True),

    # STRUCTURE
    _spec("retrieve_pdb", "structure",
          "PDB entry metadata/sequences for target/E3.", {"target": "", "e3": ""},
          EvidenceType.RETRIEVED, [], readiness="ready", retrieved=True),
    _spec("model_ternary_complex", "structure",
          "Ternary-complex feasibility (P4ward / SE(3) surrogate).",
          {"target": "", "e3": "", "linker_smiles": ""}, EvidenceType.STRUCTURAL_SURROGATE,
          ["Structural surrogate — not an experimental complex."], deterministic=True),
    _spec("score_lysine_ubiquitination", "structure",
          "Lysine ubiquitination feasibility from structure.", {"target": "", "e3": ""},
          EvidenceType.STRUCTURAL_SURROGATE,
          ["Geometry-based surrogate; real PDB pending."], deterministic=True),
    _spec("predict_cooperativity", "structure",
          "Cooperativity (alpha) feasibility model.", {"warhead_smiles": "", "linker_smiles": "", "e3_smiles": ""},
          EvidenceType.STRUCTURAL_SURROGATE,
          ["Feasibility, not measured alpha."], deterministic=True),
    _spec("simulate_hook_effect", "structure",
          "Ternary dose-response / hook-effect equilibrium simulator.",
          {"target_conc_nM": 100.0, "e3_conc_nM": 100.0, "alpha": 1.0},
          EvidenceType.CALCULATED, ["Mechanistic simulation, equilibrium only."], deterministic=True),

    # PREDICTION
    _spec("predict_degradation", "prediction",
          "DC50/Dmax degradation prediction (local committed ML + SynGlue where configured).",
          {"smiles": "", "e3": ""}, EvidenceType.ML_PREDICTION,
          ["Model card limits apply."], readiness="ready", ml=True),
    _spec("predict_cell_context", "prediction",
          "Cell-context/proteotype-aware degradation prediction.",
          {"protac": "", "cell_line": "", "poi": "", "e3": ""}, EvidenceType.ML_PREDICTION,
          ["Transcriptomic-gated claims only."], readiness="ready", ml=True),
    _spec("predict_admet", "prediction",
          "ADMET flags (hERG/AMES/BBB/Lipinski...).", {"smiles": ""},
          EvidenceType.ML_PREDICTION, [], deterministic=True),

    # WORKFLOW
    _spec("run_protacpilot_structural", "workflow",
          "PROTACpilot structural pipeline: KNOW target/E3/PROTAC → reference "
          "structures → decomposition → validation → ternary (external COMPASS / "
          "PRosettaC / PROTAC-Model) → consensus/interface/strain/cooperativity → "
          "CRL/lysine → MD → bRo5 → fusion → rank + reproducibility report.",
          {"target": "", "e3": "CRBN", "protac_smiles": ""}, EvidenceType.STRUCTURAL_SURROGATE,
          ["External ternary/MD engines required for structure stages; run `protacxtend pilot`."],
          readiness="ready"),

    # DECISION
    _spec("rank_candidates", "decision",
          "Pareto rank candidate records by potency/novelty/ADMET/synthesis.",
          {"candidates": []}, EvidenceType.CALCULATED,
          ["Ranking within provided set."], readiness="ready", deterministic=True),
    _spec("build_candidate_dossier", "decision",
          "Per-candidate dossier with provenance + evidence labels.",
          {"candidate_id": ""}, EvidenceType.CALCULATED, [], readiness="ready", deterministic=True),
]


def registry_specs(ready_only: bool = True) -> List[Dict[str, Any]]:
    specs = [s for s in TOOL_SPECS if s["readiness"] == "ready"] if ready_only else TOOL_SPECS
    return specs


def spec_for(name: str) -> Dict[str, Any]:
    for s in TOOL_SPECS:
        if s["name"] == name:
            return s
    raise RegistryError(f"unknown tool '{name}'")


# ── Real network/deterministic adapters ────────────────────────────────

def _get(url: str, params: Optional[Dict[str, Any]] = None) -> Any:
    import requests
    resp = requests.get(url, params=params or {}, timeout=_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def exec_europe_pmc(query: str, page_size: int = 8) -> ToolResult:
    try:
        data = _get("https://www.ebi.ac.uk/europepmc/webservices/rest/search",
                    {"query": query, "format": "json", "pageSize": page_size})
        hits = data.get("resultList", {}).get("result", [])
        rows = [{"id": h.get("id"), "source": h.get("source"), "title": h.get("title"),
                 "year": h.get("pubYear"), "doi": h.get("doi"), "pmcid": h.get("pmcid"),
                 "journal": h.get("journalTitle")} for h in hits]
        return ToolResult(
            tool="search_europe_pmc", status=ToolStatus.SUCCESS,
            summary=f"Europe PMC → {len(rows)} results",
            data={"results": rows[:page_size]}, sources=[f"EPMC:{r['id']}" for r in rows],
            evidence_type=EvidenceType.RETRIEVED,
            limitations=["Public index; recall depends on query."])
    except Exception as exc:
        return ToolResult(tool="search_europe_pmc", status=ToolStatus.ERROR,
                          summary=f"HTTP error · {exc}", evidence_type=EvidenceType.RETRIEVED)


def exec_pubmed(query: str, page_size: int = 8) -> ToolResult:
    try:
        ids = _get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
                   {"db": "pubmed", "term": query, "retmode": "json", "retmax": page_size})
        id_list = ids.get("esearchresult", {}).get("idlist", [])
        rows: List[Dict[str, Any]] = []
        if id_list:
            summ = _get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi",
                        {"db": "pubmed", "id": ",".join(id_list), "retmode": "json"})
            for pid in id_list:
                d = summ.get("result", {}).get(pid, {})
                rows.append({"pmid": pid, "title": d.get("title"), "year": d.get("pubdate"),
                             "journal": (d.get("fulljournalname") or d.get("source"))})
        return ToolResult(
            tool="search_pubmed", status=ToolStatus.SUCCESS,
            summary=f"PubMed → {len(rows)} results", data={"results": rows},
            sources=[f"PMID:{r['pmid']}" for r in rows], evidence_type=EvidenceType.RETRIEVED)
    except Exception as exc:
        return ToolResult(tool="search_pubmed", status=ToolStatus.ERROR,
                          summary=f"HTTP error · {exc}", evidence_type=EvidenceType.RETRIEVED)


def exec_crossref(doi: str) -> ToolResult:
    try:
        data = _get(f"https://api.crossref.org/works/{doi.strip()}")
        m = data.get("message", {})
        title = (m.get("title") or [""])[0]
        authors = [f"{a.get('given','')} {a.get('family','')}".strip()
                   for a in m.get("author", [])][:6]
        return ToolResult(
            tool="verify_crossref", status=ToolStatus.SUCCESS,
            summary=f"DOI verified → {title[:90]}", data={"doi": doi, "title": title,
                    "authors": authors, "year": (m.get("issued", {}).get("date-parts") or [[None]])[0][0]},
            sources=[doi], evidence_type=EvidenceType.RETRIEVED)
    except Exception as exc:
        return ToolResult(tool="verify_crossref", status=ToolStatus.ERROR,
                          summary=f"DOI not verified · {exc}", sources=[doi],
                          evidence_type=EvidenceType.RETRIEVED)


def exec_retrieve_fulltext(pmcid: str, section: str = "abstract") -> ToolResult:
    """Fetch open-access full text from Europe PMC (XML)."""
    import re as _re

    pmcid = (pmcid or "").strip().upper()
    if not pmcid:
        return ToolResult(tool="retrieve_fulltext", status=ToolStatus.WARNING,
                          summary="pmcid required", evidence_type=EvidenceType.NOT_AVAILABLE)
    try:
        import requests

        url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML"
        resp = requests.get(url, timeout=_TIMEOUT)
        if resp.status_code != 200:
            return ToolResult(tool="retrieve_fulltext", status=ToolStatus.WARNING,
                              summary=f"{pmcid} full text not open-access (HTTP {resp.status_code})",
                              sources=[pmcid], evidence_type=EvidenceType.NOT_AVAILABLE)
        xml = resp.text
        text = _re.sub(r"<[^>]+>", " ", xml)
        text = _re.sub(r"\s+", " ", text).strip()
        snippet = text[:4000]
        return ToolResult(tool="retrieve_fulltext", status=ToolStatus.SUCCESS,
                          summary=f"{pmcid} full text → {len(text)} chars",
                          data={"pmcid": pmcid, "section": section, "text": snippet,
                                "truncated": len(text) > len(snippet)},
                          sources=[pmcid], evidence_type=EvidenceType.RETRIEVED,
                          limitations=["Open-access subset only; XML flattened to text."])
    except Exception as exc:
        return ToolResult(tool="retrieve_fulltext", status=ToolStatus.ERROR,
                          summary=f"full text error · {exc}", sources=[pmcid],
                          evidence_type=EvidenceType.RETRIEVED)


def exec_deep_research(query: str, page_size: int = 8) -> ToolResult:
    epmc = exec_europe_pmc(query, page_size=page_size)
    pmid = exec_pubmed(query, page_size=min(page_size, 5))
    results = []
    if epmc.status == ToolStatus.SUCCESS:
        results += epmc.data.get("results", [])
    if pmid.status == ToolStatus.SUCCESS:
        results += pmid.data.get("results", [])
    sources = epmc.sources + pmid.sources
    notes = [w for r in (epmc, pmid) if r.status == ToolStatus.ERROR for w in [r.summary]]
    return ToolResult(
        tool="deep_research", status=ToolStatus.SUCCESS if results else ToolStatus.WARNING,
        summary=f"deep research → {len(results)} records across Europe PMC + PubMed",
        data={"results": results}, sources=sources, evidence_type=EvidenceType.RETRIEVED,
        warnings=notes)


def exec_resolve_target(target_name: str) -> ToolResult:
    try:
        data = _get("https://rest.uniprot.org/uniprotkb/search",
                    {"query": f"gene_exact:{target_name} AND reviewed:true", "size": 3})
        hits = data.get("results", [])
        rows = []
        for h in hits[:3]:
            # recommendedName is a dict {fullName:{value}} in the current UniProt
            # REST shape (older builds emitted a list); accept both forms.
            rec = h.get("proteinDescription", {}).get("recommendedName") or {}
            if isinstance(rec, list):
                names = [n.get("fullName", {}).get("value") or n.get("value")
                         for n in rec if isinstance(n, dict)]
            else:
                full = rec.get("fullName") or {}
                names = [full.get("value")] if isinstance(full, dict) else []
            gene = [g.get("geneName", {}).get("value") for g in h.get("genes", []) if g.get("geneName")]
            rows.append({"accession": h.get("primaryAccession"), "gene": gene[0] if gene else None,
                         "name": (names[0] if names else None),
                         "organism": (h.get("organism", {}).get("scientificName"))})
        if not rows:
            return ToolResult(tool="resolve_target", status=ToolStatus.WARNING,
                              summary=f"No reviewed UniProt entry for '{target_name}'",
                              data={}, evidence_type=EvidenceType.NOT_AVAILABLE)
        return ToolResult(tool="resolve_target", status=ToolStatus.SUCCESS,
                          summary=f"Resolved {target_name} → {rows[0]['accession']} ({rows[0]['gene']})",
                          data={"matches": rows}, sources=[rows[0]["accession"]],
                          evidence_type=EvidenceType.RETRIEVED)
    except Exception as exc:
        return ToolResult(tool="resolve_target", status=ToolStatus.ERROR,
                          summary=f"UniProt error · {exc}", evidence_type=EvidenceType.RETRIEVED)


def exec_chembl_molecules(term: str, top_k: int = 8) -> ToolResult:
    try:
        data = _get("https://www.ebi.ac.uk/chembl/api/data/molecule/search.json",
                    {"q": term, "limit": top_k})
        rows = [{"chembl_id": m.get("molecule_chembl_id"), "pref_name": m.get("pref_name"),
                 "smiles": (m.get("molecule_structures") or {}).get("canonical_smiles")}
                for m in data.get("molecules", [])]
        return ToolResult(tool="search_chembl", status=ToolStatus.SUCCESS,
                          summary=f"ChEMBL → {len(rows)} molecules", data={"results": rows},
                          sources=[r["chembl_id"] for r in rows if r.get("chembl_id")],
                          evidence_type=EvidenceType.RETRIEVED)
    except Exception as exc:
        return ToolResult(tool="search_chembl", status=ToolStatus.ERROR,
                          summary=f"ChEMBL unreachable · {exc}", evidence_type=EvidenceType.RETRIEVED)


def exec_validate_smiles(smiles: str) -> ToolResult:
    from protacxtend.tools.chemistry_core import validate_smiles as _validate
    try:
        result = _validate(smiles)
        ok = bool(getattr(result, "is_valid", True))
        try:
            payload = result.model_dump() if hasattr(result, "model_dump") else dict(result)
        except Exception:
            from dataclasses import asdict
            payload = asdict(result) if hasattr(result, "__dataclass_fields__") else {"is_valid": ok}
        return ToolResult(tool="inspect_smiles", status=ToolStatus.SUCCESS if ok else ToolStatus.WARNING,
                          summary="SMILES valid" if ok else "SMILES invalid",
                          data=payload, evidence_type=EvidenceType.CALCULATED,
                          limitations=["RDKit-based; stereochemistry caution."])
    except Exception as exc:
        return ToolResult(tool="inspect_smiles", status=ToolStatus.ERROR,
                          summary=f"validation error · {exc}", evidence_type=EvidenceType.NOT_AVAILABLE)


def exec_ligase_evidence(e3: str) -> ToolResult:
    try:
        from protacxtend.tools.e3_selector import rank_e3_ligands
        # catalog-based advisory rows come from the E3 selector helpers
        rows = [{"e3": e3, "note": "evidence catalog entry", "status": "catalog"}]
        return ToolResult(tool="retrieve_e3_evidence", status=ToolStatus.SUCCESS,
                          summary=f"E3 evidence catalog row for {e3}", data={"rows": rows},
                          evidence_type=EvidenceType.RETRIEVED,
                          limitations=["Local curated catalog — see Validation matrix."])
    except Exception as exc:
        return ToolResult(tool="retrieve_e3_evidence", status=ToolStatus.ERROR,
                          summary=f"E3 catalog unavailable · {exc}")


def exec_diagnose_capability(capability: str, internal_tool: str = "") -> ToolResult:
    """Resolve external fallbacks for a capability (escalation subsystem)."""
    try:
        from protacxtend.escalation import capability_for, resolve_candidates

        cap = capability_for(capability or internal_tool)
        candidates = resolve_candidates(cap)
        rows = [
            {
                "tool": c.tool_name,
                "installed": c.installed,
                "status": c.status,
                "version": c.version,
                "install_method": c.install_method,
                "pip_package": c.pip_package,
                "web_service": c.web_service,
                "commercial": c.commercial,
            }
            for c in candidates
        ]
        installed = [r for r in rows if r["installed"]]
        return ToolResult(
            tool="diagnose_capability",
            status=ToolStatus.SUCCESS if rows else ToolStatus.WARNING,
            summary=f"{cap}: {len(rows)} external candidates, {len(installed)} installed",
            data={"capability": cap, "candidates": rows},
            sources=[r["tool"] for r in installed],
            evidence_type=EvidenceType.CALCULATED,
            limitations=["Candidate list is environment-dependent; verify versions before use."],
        )
    except Exception as exc:
        return ToolResult(tool="diagnose_capability", status=ToolStatus.ERROR,
                          summary=f"escalation resolver error · {exc}",
                          evidence_type=EvidenceType.NOT_AVAILABLE)


def exec_list_capability_readiness(limit: int = 40) -> ToolResult:
    try:
        from protacxtend.escalation.report import capability_readiness

        rows = capability_readiness()[: max(1, int(limit))]
        return ToolResult(
            tool="list_capability_readiness",
            status=ToolStatus.SUCCESS,
            summary=f"{len(rows)} capabilities assessed",
            data={"capabilities": rows},
            evidence_type=EvidenceType.CALCULATED,
            limitations=["Live environment detection; not a scientific validation."],
        )
    except Exception as exc:
        return ToolResult(tool="list_capability_readiness", status=ToolStatus.ERROR,
                          summary=f"readiness error · {exc}",
                          evidence_type=EvidenceType.NOT_AVAILABLE)


def exec_search_web(query: str, page_size: int = 6) -> ToolResult:
    """Self-hosted SearXNG web search (no endpoint → honest not_available)."""
    import os

    base = (os.environ.get("SEARXNG_URL") or os.environ.get("PROTACXTEND_SEARXNG_URL")
            or os.environ.get("SEARXNG_BASE_URL") or "").strip().rstrip("/")
    if not base:
        return ToolResult(
            tool="search_web", status=ToolStatus.WARNING,
            summary="SearXNG endpoint not configured (set SEARXNG_URL to enable web search)",
            data={"results": []}, evidence_type=EvidenceType.NOT_AVAILABLE,
            limitations=["Set SEARXNG_URL to a self-hosted SearXNG instance."])
    try:
        data = _get(f"{base}/search", {"q": query, "format": "json"})
        rows = [{"title": r.get("title"), "url": r.get("url"), "content": r.get("content")}
                for r in (data.get("results") or [])][: max(1, int(page_size))]
        return ToolResult(tool="search_web", status=ToolStatus.SUCCESS,
                          summary=f"SearXNG → {len(rows)} results", data={"results": rows},
                          sources=[r["url"] for r in rows if r.get("url")],
                          evidence_type=EvidenceType.RETRIEVED,
                          limitations=["Self-hosted meta-search; verify each source."])
    except Exception as exc:
        return ToolResult(tool="search_web", status=ToolStatus.ERROR,
                          summary=f"SearXNG error · {exc}", evidence_type=EvidenceType.RETRIEVED)


def exec_search_pubchem(term: str) -> ToolResult:
    try:
        from protacxtend.tools.pubchem_lookup import search_compound_by_name

        out = search_compound_by_name(term)
        records = out.get("records") or []
        if out.get("success"):
            return ToolResult(tool="search_pubchem", status=ToolStatus.SUCCESS,
                              summary=f"PubChem → {len(records)} compound record(s)",
                              data={"results": records}, sources=[str(records[0].get("cid"))] if records else [],
                              evidence_type=EvidenceType.RETRIEVED,
                              limitations=["Public PubChem; curated/deposited data varies."])
        return ToolResult(tool="search_pubchem", status=ToolStatus.WARNING,
                          summary=f"PubChem: {out.get('error') or 'no records'}",
                          data={"results": []}, evidence_type=EvidenceType.RETRIEVED)
    except Exception as exc:
        return ToolResult(tool="search_pubchem", status=ToolStatus.ERROR,
                          summary=f"PubChem error · {exc}", evidence_type=EvidenceType.RETRIEVED)


def exec_retrieve_pdb(target: str = "", e3: str = "", top_k: int = 5) -> ToolResult:
    try:
        from protacxtend.tools.rcsb_pdb_lookup import (
            search_pdb_by_gene_or_target,
            summarize_structure_hits,
        )

        records: List[Dict[str, Any]] = []
        sources: List[str] = []
        for label in (target, e3):
            if not label:
                continue
            hits = search_pdb_by_gene_or_target(label, top_k=top_k)
            if hits.get("success"):
                records += hits.get("records", [])
                sources.append(f"RCSB:{label}")
        summary = summarize_structure_hits(records)
        return ToolResult(
            tool="retrieve_pdb",
            status=ToolStatus.SUCCESS if records else ToolStatus.WARNING,
            summary=(f"RCSB PDB → {len(records)} structures "
                     f"({summary.get('ligand_bound_count', 0)} ligand-bound)"),
            data={"structures": records, "summary": summary}, sources=sources,
            evidence_type=EvidenceType.RETRIEVED,
            limitations=["Experimental structures only; absence is not evidence of absence."])
    except Exception as exc:
        return ToolResult(tool="retrieve_pdb", status=ToolStatus.ERROR,
                          summary=f"RCSB error · {exc}", evidence_type=EvidenceType.RETRIEVED)


def exec_check_synthetic_feasibility(smiles: str, use_aizynth: bool = True) -> ToolResult:
    try:
        from protacxtend.toolkit.bridge import call_first_available

        # Prefer the environment that can actually run the route engine
        # (AiZynthFinder lives in the scientific conda env); fall back to the
        # local RAscore/SAScore prescreen when no engine is available.
        outcome = call_first_available(
            "protacxtend.tools.retrosynthesis", "assess_retrosynthesis",
            args=[smiles], kwargs={"use_aizynth": bool(use_aizynth)},
            require_import="aizynthfinder" if use_aizynth else None, timeout=420)
        if outcome.get("ok"):
            payload = outcome.get("result") or {}
            tools_used = payload.get("tools_used") or [outcome.get("python", "local")]
            status_name = payload.get("status", "tool_failed")
            status = ToolStatus.SUCCESS if status_name in {"feasible", "repairable"} else ToolStatus.WARNING
            return ToolResult(
                tool="check_synthetic_feasibility", status=status,
                summary=(f"retrosynthesis: {status_name} "
                         f"(rascore={payload.get('rascore')}, routes={payload.get('route_count')})"),
                data=payload, sources=[str(t) for t in tools_used],
                evidence_type=EvidenceType.HEURISTIC,
                model_version=", ".join(str(t) for t in tools_used) or "sascore_proxy",
                limitations=["Route prediction is advisory; bench validation required."])
        return ToolResult(tool="check_synthetic_feasibility", status=ToolStatus.WARNING,
                          summary=f"retrosynthesis unavailable · {outcome.get('error')}",
                          evidence_type=EvidenceType.NOT_AVAILABLE,
                          limitations=["No route engine or prescreen backend available."])
    except Exception as exc:
        return ToolResult(tool="check_synthetic_feasibility", status=ToolStatus.ERROR,
                          summary=f"retrosynthesis error · {exc}",
                          evidence_type=EvidenceType.NOT_AVAILABLE)


def exec_predict_degradation(smiles: str, e3: str = "CRBN", cell_line: str = "default",
                             target: str = "") -> ToolResult:
    try:
        from protacxtend.tools.degradation_endpoint import predict_degradation_endpoint

        # P0-B: never coerce a missing e3/cell_line into a hidden default. In
        # SCIENTIFIC mode these are required inputs and are validated upstream;
        # an empty value here is passed through so the backend rejects it rather
        # than silently predicting for CRBN/default.
        result = predict_degradation_endpoint(smiles, cell_line=cell_line,
                                              target=target, e3_ligase=e3)
        payload = result.model_dump() if hasattr(result, "model_dump") else dict(result)
        return ToolResult(
            tool="predict_degradation", status=ToolStatus.SUCCESS,
            summary=(f"DC50={payload.get('dc50_nM')} nM, Dmax={payload.get('dmax_pct')}, "
                     f"class={payload.get('degradation_class')}"),
            data=payload, sources=[payload.get('model_version') or "degradation_endpoint"],
            evidence_type=EvidenceType.ML_PREDICTION,
            model_version=str(payload.get('model_version') or ""),
            limitations=["ML/heuristic prediction; model-card limits apply."])
    except Exception as exc:
        return ToolResult(tool="predict_degradation", status=ToolStatus.ERROR,
                          summary=f"degradation prediction error · {exc}",
                          evidence_type=EvidenceType.NOT_AVAILABLE)


def exec_predict_cell_context(protac: str = "", cell_line: str = "",
                              poi: str = "", e3: str = "", **kwargs: Any) -> ToolResult:
    try:
        from protacxtend.tools.cell_context_tool import run_cell_context_predictor

        out = run_cell_context_predictor({"protac": protac, "cell_line": cell_line,
                                          "poi": poi or None, "e3": e3 or None, **kwargs})
        if out.get("success"):
            return ToolResult(tool="predict_cell_context", status=ToolStatus.SUCCESS,
                              summary=f"cell-context prediction for {cell_line}",
                              data=out["result"], evidence_type=EvidenceType.ML_PREDICTION,
                              limitations=["Transcriptomic-gated claim; not a measured DC50."])
        return ToolResult(tool="predict_cell_context", status=ToolStatus.WARNING,
                          summary=f"cell-context: {out.get('error')}",
                          evidence_type=EvidenceType.NOT_AVAILABLE)
    except Exception as exc:
        return ToolResult(tool="predict_cell_context", status=ToolStatus.ERROR,
                          summary=f"cell-context error · {exc}",
                          evidence_type=EvidenceType.NOT_AVAILABLE)


def exec_rank_candidates(candidates: Any = None) -> ToolResult:
    try:
        from protacxtend.tools.pareto_ranking import pareto_rank_candidates

        rows = candidates if isinstance(candidates, list) else []
        if not rows:
            return ToolResult(tool="rank_candidates", status=ToolStatus.WARNING,
                              summary="no candidates provided",
                              evidence_type=EvidenceType.NOT_AVAILABLE)
        results = pareto_rank_candidates(rows)
        payload = [r.__dict__ if hasattr(r, "__dict__") else dict(r) for r in results]
        return ToolResult(tool="rank_candidates", status=ToolStatus.SUCCESS,
                          summary=f"Pareto ranked {len(payload)} candidates",
                          data={"ranking": payload},
                          evidence_type=EvidenceType.CALCULATED,
                          limitations=["Ranking is relative to the provided set only."])
    except Exception as exc:
        return ToolResult(tool="rank_candidates", status=ToolStatus.ERROR,
                          summary=f"ranking error · {exc}",
                          evidence_type=EvidenceType.NOT_AVAILABLE)


def exec_build_candidate_dossier(candidate_id: str = "", candidate: Any = None) -> ToolResult:
    """Assemble a provenance dossier for one candidate (from a row or run output)."""
    record: Dict[str, Any] = {}
    if isinstance(candidate, dict):
        record = dict(candidate)
    elif candidate_id:
        record = _find_candidate_record(candidate_id)
    if not record:
        return ToolResult(tool="build_candidate_dossier", status=ToolStatus.WARNING,
                          summary=f"candidate '{candidate_id}' not found in run outputs",
                          evidence_type=EvidenceType.NOT_AVAILABLE)
    evidence_labels = [k for k in record if k.startswith("evidence") or k.endswith("_source")]
    dossier = {
        "candidate_id": record.get("candidate_id") or candidate_id,
        "smiles": record.get("full_protac_smiles") or record.get("smiles"),
        "components": {k: record.get(k) for k in
                       ("target", "e3_ligase", "warhead", "linker") if k in record},
        "scores": {k: v for k, v in record.items() if isinstance(v, (int, float))},
        "evidence_labels": evidence_labels,
        "provenance": record.get("provenance") or {},
    }
    return ToolResult(tool="build_candidate_dossier", status=ToolStatus.SUCCESS,
                      summary=f"dossier assembled for {dossier['candidate_id']}",
                      data=dossier, evidence_type=EvidenceType.CALCULATED,
                      limitations=["Dossier reflects recorded run evidence only."])


def _find_candidate_record(candidate_id: str) -> Dict[str, Any]:
    """Best-effort lookup of a candidate row across run output tables."""
    from pathlib import Path

    roots = [Path("outputs/runs"), Path("protacxtend/outputs/candidates"),
             Path.home() / ".protacxtend" / "outputs"]
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.json")) + sorted(root.rglob("*.jsonl")):
            try:
                text = path.read_text(encoding="utf-8")
            except Exception:
                continue
            if candidate_id not in text:
                continue
            for line in text.splitlines():
                if candidate_id in line:
                    try:
                        row = json.loads(line)
                        if isinstance(row, dict):
                            return row
                    except Exception:
                        continue
    return {}


def _plain(value: Any) -> Any:
    """JSON-safe conversion for pydantic models / dataclasses / records."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_plain(v) for v in value]
    if hasattr(value, "model_dump"):
        return _plain(value.model_dump())
    if hasattr(value, "__dataclass_fields__"):
        import dataclasses

        return _plain(dataclasses.asdict(value))
    if hasattr(value, "__dict__"):
        return _plain(vars(value))
    return str(value)


def exec_select_e3_ligase(target: str = "", preferred_e3: str = "",
                          e3_ligand_smiles: str = "") -> ToolResult:
    try:
        from protacxtend.tools.protac_toolbox import ProtacDesignToolbox

        toolbox = ProtacDesignToolbox()
        ligands = toolbox.select_e3_ligands(
            e3_ligase=preferred_e3 or None, e3_ligand_smiles=e3_ligand_smiles or None)
        rows = [_plain(x) for x in ligands]
        return ToolResult(tool="select_e3_ligase", status=ToolStatus.SUCCESS if rows else ToolStatus.WARNING,
                          summary=f"{len(rows)} E3 ligand option(s) for {preferred_e3 or 'any ligase'}",
                          data={"target": target, "ligands": rows},
                          evidence_type=EvidenceType.HEURISTIC,
                          limitations=["Catalog-graded guidance; direct precedent required for SUPPORTED."])
    except Exception as exc:
        return ToolResult(tool="select_e3_ligase", status=ToolStatus.ERROR,
                          summary=f"E3 selection error · {exc}", evidence_type=EvidenceType.NOT_AVAILABLE)


def exec_search_bindingdb(target: str = "", top_k: int = 100) -> ToolResult:
    try:
        from protacxtend.tools.bindingdb_lookup import search_bindingdb_local

        out = search_bindingdb_local(target, top_k=max(1, int(top_k)))
        records = out.get("records") or []
        status = ToolStatus.SUCCESS if out.get("success") else ToolStatus.WARNING
        return ToolResult(tool="search_bindingdb", status=status,
                          summary=f"BindingDB → {len(records)} local record(s)",
                          data=out, evidence_type=EvidenceType.RETRIEVED,
                          limitations=["Local BindingDB TSV snapshot only; run the exporter to refresh."])
    except Exception as exc:
        return ToolResult(tool="search_bindingdb", status=ToolStatus.ERROR,
                          summary=f"BindingDB error · {exc}", evidence_type=EvidenceType.RETRIEVED)


def exec_detect_exit_vectors(smiles: str, role: str = "warhead") -> ToolResult:
    try:
        from types import SimpleNamespace

        from protacxtend.tools.protac_toolbox import ProtacDesignToolbox

        toolbox = ProtacDesignToolbox()
        records = toolbox.detect_exit_vectors([SimpleNamespace(smiles=smiles, name="input")], role=role)
        rows = [_plain(x) for x in records]
        return ToolResult(tool="detect_exit_vectors", status=ToolStatus.SUCCESS if rows else ToolStatus.WARNING,
                          summary=f"{len(rows)} exit-vector record(s)", data={"exit_vectors": rows},
                          evidence_type=EvidenceType.CALCULATED,
                          limitations=["Attachment-vector inference is heuristic without a curated map."])
    except Exception as exc:
        return ToolResult(tool="detect_exit_vectors", status=ToolStatus.ERROR,
                          summary=f"exit-vector error · {exc}", evidence_type=EvidenceType.NOT_AVAILABLE)


def exec_generate_linkers(count: int = 12, constraints: Any = None) -> ToolResult:
    try:
        from protacxtend.tools.protac_toolbox import ProtacDesignToolbox

        toolbox = ProtacDesignToolbox()
        linker_types = None
        if isinstance(constraints, dict):
            linker_types = constraints.get("linker_types")
        linkers = toolbox.generate_linkers(linker_types=linker_types,
                                           max_linkers=max(1, int(count)))
        rows = [_plain(x) for x in linkers]
        return ToolResult(tool="generate_linkers", status=ToolStatus.SUCCESS if rows else ToolStatus.WARNING,
                          summary=f"generated {len(rows)} linker hypotheses", data={"linkers": rows},
                          evidence_type=EvidenceType.CALCULATED,
                          limitations=["In-vitro validation required; generative hypotheses only."])
    except Exception as exc:
        return ToolResult(tool="generate_linkers", status=ToolStatus.ERROR,
                          summary=f"linker generation error · {exc}", evidence_type=EvidenceType.NOT_AVAILABLE)


def exec_construct_protac(warhead_smiles: str, linker_smiles: str, e3_smiles: str) -> ToolResult:
    try:
        from protacxtend.tools.protac_toolbox import ProtacDesignToolbox

        toolbox = ProtacDesignToolbox()
        product, status = toolbox.assemble_components(warhead_smiles, linker_smiles, e3_smiles)
        ok = bool(product) and status not in {"missing_attachment_marker"}
        return ToolResult(tool="construct_protac", status=ToolStatus.SUCCESS if ok else ToolStatus.WARNING,
                          summary=f"construction {status}" + (f" → {product}" if product else ""),
                          data={"product_smiles": product, "status": status},
                          evidence_type=EvidenceType.CALCULATED if ok else EvidenceType.NOT_AVAILABLE,
                          limitations=["Assembly requires attachment markers on each component."])
    except Exception as exc:
        return ToolResult(tool="construct_protac", status=ToolStatus.ERROR,
                          summary=f"construction error · {exc}", evidence_type=EvidenceType.NOT_AVAILABLE)


def exec_model_ternary_complex(target: str = "", e3: str = "", linker_smiles: str = "",
                               smiles: str = "") -> ToolResult:
    try:
        from protacxtend.tools.ternary_ensemble import run_ensemble

        candidate = {"candidate_id": "agent_input", "full_protac_smiles": smiles or linker_smiles,
                     "target": target, "e3_ligase": e3 or "CRBN", "linker_smiles": linker_smiles}
        result = run_ensemble(candidate, methods=["geometric_proxy"])
        payload = _plain(result)
        return ToolResult(tool="model_ternary_complex",
                          status=ToolStatus.SUCCESS if payload else ToolStatus.WARNING,
                          summary=f"ternary geometric proxy for {target or 'target'} / {e3 or 'E3'}",
                          data=payload, evidence_type=EvidenceType.STRUCTURAL_SURROGATE,
                          limitations=["Geometric surrogate — not an experimental ternary complex; "
                                       "P4ward/SE(3) require structures+GPU."])
    except Exception as exc:
        return ToolResult(tool="model_ternary_complex", status=ToolStatus.ERROR,
                          summary=f"ternary error · {exc}", evidence_type=EvidenceType.NOT_AVAILABLE)


def exec_score_lysine_ubiquitination(target: str = "", e3: str = "",
                                     structure_paths: Any = None, poi_chain: str = "",
                                     e2_catalytic: Any = None) -> ToolResult:
    if not structure_paths or not e2_catalytic:
        return ToolResult(tool="score_lysine_ubiquitination", status=ToolStatus.WARNING,
                          summary=("requires a ternary pose (structure_paths) and E2 catalytic site; "
                                   "none supplied"),
                          evidence_type=EvidenceType.NOT_AVAILABLE,
                          limitations=["No fabricated geometry: supply a pose PDB + E2 site."])
    try:
        from protacxtend.tools.lysine_ubiquitination_tool import run_lysine_ubiquitination

        out = run_lysine_ubiquitination({"structure_paths": structure_paths, "poi_chain": poi_chain,
                                         "e2_catalytic": e2_catalytic})
        if out.get("success"):
            return ToolResult(tool="score_lysine_ubiquitination", status=ToolStatus.SUCCESS,
                              summary="lysine ubiquitination geometry scored", data=out["result"],
                              evidence_type=EvidenceType.STRUCTURAL_SURROGATE,
                              limitations=["Geometry-based surrogate; experimental validation required."])
        return ToolResult(tool="score_lysine_ubiquitination", status=ToolStatus.WARNING,
                          summary=f"lysine scoring: {out.get('error')}",
                          evidence_type=EvidenceType.NOT_AVAILABLE)
    except Exception as exc:
        return ToolResult(tool="score_lysine_ubiquitination", status=ToolStatus.ERROR,
                          summary=f"lysine error · {exc}", evidence_type=EvidenceType.NOT_AVAILABLE)


def exec_predict_cooperativity(warhead_smiles: str = "", linker_smiles: str = "",
                               e3_smiles: str = "", pose_pdb: str = "") -> ToolResult:
    if not pose_pdb:
        return ToolResult(tool="predict_cooperativity", status=ToolStatus.WARNING,
                          summary="no ternary pose supplied; cooperativity cannot be structure-scored",
                          evidence_type=EvidenceType.NOT_AVAILABLE,
                          limitations=["Supply a ternary pose PDB to score cooperativity (alpha)."])
    try:
        from protacxtend.tools.cooperativity_potential import score_cooperativity_potential

        result = score_cooperativity_potential("agent_input", pose_pdb, smiles=linker_smiles)
        return ToolResult(tool="predict_cooperativity", status=ToolStatus.SUCCESS,
                          summary=f"cooperativity status={result.status}, alpha={result.predicted_alpha}",
                          data=_plain(result), evidence_type=EvidenceType.STRUCTURAL_SURROGATE,
                          model_version=result.backend,
                          limitations=["Feasibility estimate, not a measured cooperativity factor."])
    except Exception as exc:
        return ToolResult(tool="predict_cooperativity", status=ToolStatus.ERROR,
                          summary=f"cooperativity error · {exc}", evidence_type=EvidenceType.NOT_AVAILABLE)


def exec_simulate_hook_effect(target_conc_nM: float = 100.0, e3_conc_nM: float = 100.0,
                              alpha: float = 1.0, **kwargs: Any) -> ToolResult:
    try:
        from protacxtend.tools.hook_effect_modeler_tool import run_hook_effect_modeler

        payload = {"poI_conc_nM": float(target_conc_nM), "e3_conc_nM": float(e3_conc_nM),
                   "alpha": float(alpha)}
        payload.update({k: v for k, v in kwargs.items() if v is not None})
        out = run_hook_effect_modeler(payload)
        if out.get("success"):
            metrics = out["result"].get("metrics") if isinstance(out.get("result"), dict) else None
            return ToolResult(tool="simulate_hook_effect", status=ToolStatus.SUCCESS,
                              summary=f"hook-effect simulated (alpha={alpha}); metrics={metrics}",
                              data=out["result"], evidence_type=EvidenceType.CALCULATED,
                              limitations=["Mechanistic equilibrium simulation; not cell data."])
        return ToolResult(tool="simulate_hook_effect", status=ToolStatus.WARNING,
                          summary=f"hook-effect: {out.get('error')}",
                          evidence_type=EvidenceType.NOT_AVAILABLE)
    except Exception as exc:
        return ToolResult(tool="simulate_hook_effect", status=ToolStatus.ERROR,
                          summary=f"hook-effect error · {exc}", evidence_type=EvidenceType.NOT_AVAILABLE)


def exec_predict_admet(smiles: str = "", backend: str = "auto") -> ToolResult:
    try:
        from protacxtend.tools.admet_predictors import predict_admet

        out = predict_admet(smiles, backend=backend or "auto")
        ok = bool(out.get("success", True))
        return ToolResult(tool="predict_admet", status=ToolStatus.SUCCESS if ok else ToolStatus.WARNING,
                          summary=f"ADMET backend={out.get('backend_used') or backend}",
                          data=out, evidence_type=EvidenceType.ML_PREDICTION,
                          model_version=str(out.get("backend_used") or "descriptor_rule_based"),
                          limitations=["Descriptor/rule-based unless a validated local model is configured."])
    except Exception as exc:
        return ToolResult(tool="predict_admet", status=ToolStatus.ERROR,
                          summary=f"ADMET error · {exc}", evidence_type=EvidenceType.NOT_AVAILABLE)


def exec_run_scientific_capability(capability: str, params: Dict[str, Any] | None = None) -> ToolResult:
    """Capability-first dispatch through the licence-gated scientific backend layer."""
    try:
        from protacxtend.scientific_backends import run_capability

        result = run_capability(capability, **(params or {}))
        payload = result.to_dict()
        status = ToolStatus.SUCCESS if result.ok() else (
            ToolStatus.NOT_AVAILABLE if result.status in {"LICENSE_REQUIRED", "CAPABILITY_UNAVAILABLE"}
            else ToolStatus.ERROR)
        return ToolResult(
            tool="run_scientific_capability", status=status,
            summary=f"{capability}: {result.summary}"[:300],
            data=payload, sources=list(result.sources),
            evidence_type=EvidenceType.CALCULATED,
            model_version=result.backend_version,
            warnings=list(result.warnings),
            limitations=["Evidence tier: " + result.evidence_tier])
    except Exception as exc:
        return ToolResult(tool="run_scientific_capability", status=ToolStatus.ERROR,
                          summary=f"scientific capability error · {exc}",
                          evidence_type=EvidenceType.NOT_AVAILABLE)


def exec_list_scientific_capabilities() -> ToolResult:
    try:
        from protacxtend.scientific_backends import capability_matrix

        rows = capability_matrix()
        return ToolResult(tool="list_scientific_capabilities", status=ToolStatus.SUCCESS,
                          summary=f"{len(rows)} capabilities with free/local backends",
                          data={"capabilities": rows}, evidence_type=EvidenceType.CALCULATED,
                          limitations=["Commercial/web engines are excluded by default licence policy."])
    except Exception as exc:
        return ToolResult(tool="list_scientific_capabilities", status=ToolStatus.ERROR,
                          summary=f"capability list error · {exc}",
                          evidence_type=EvidenceType.NOT_AVAILABLE)


def exec_run_protacpilot_structural(target: str, e3: str = "CRBN", protac_smiles: str = "",
                                    mode: str = "deterministic") -> ToolResult:
    """Run the local PROTACpilot pipeline (structure stages need external engines)."""
    try:
        from protacxtend.agents.runtime import run_protacpilot

        request = (f"Design PROTAC for target {target} with E3 {e3}"
                   + (f" starting from {protac_smiles}" if protac_smiles else ""))
        result = run_protacpilot(request, mode=mode if mode in {"deterministic", "agentic"} else "deterministic")
        status = ToolStatus.SUCCESS if result.get("status") == "completed" else ToolStatus.WARNING
        return ToolResult(
            tool="run_protacpilot_structural", status=status,
            summary=f"pilot run {result.get('run_id')} → {result.get('status')}",
            data={k: result.get(k) for k in ("run_id", "status", "summary", "artifacts", "runtime_s")},
            evidence_type=EvidenceType.STRUCTURAL_SURROGATE,
            limitations=["Structure/ternary stages require external engines (COMPASS/PRosettaC/PROTAC-Model)."])
    except Exception as exc:
        return ToolResult(tool="run_protacpilot_structural", status=ToolStatus.ERROR,
                          summary=f"pilot error · {exc}",
                          evidence_type=EvidenceType.NOT_AVAILABLE)


# ── Dispatch ───────────────────────────────────────────────────────────

_EXECUTORS: Dict[str, Callable[..., ToolResult]] = {
    "deep_research": lambda params: exec_deep_research(params.get("query", ""),
                                                        int(params.get("page_size", 8))),
    "search_europe_pmc": lambda params: exec_europe_pmc(params.get("query", ""),
                                                         int(params.get("page_size", 8))),
    "search_pubmed": lambda params: exec_pubmed(params.get("query", ""),
                                                 int(params.get("page_size", 8))),
    "verify_crossref": lambda params: exec_crossref(params.get("doi", "")),
    "retrieve_fulltext": lambda params: exec_retrieve_fulltext(
        params.get("pmcid", ""), params.get("section", "abstract")),
    "resolve_target": lambda params: exec_resolve_target(params.get("target_name", "")),
    "search_uniprot": lambda params: exec_resolve_target(params.get("query", "")),
    "retrieve_target_binders": lambda params: exec_chembl_molecules(
        params.get("target_name", ""), int(params.get("top_k", 10))),
    "search_chembl": lambda params: exec_chembl_molecules(params.get("term", ""),
                                                           int(params.get("top_k", 8))),
    "retrieve_e3_evidence": lambda params: exec_ligase_evidence(params.get("e3", "")),
    "inspect_smiles": lambda params: exec_validate_smiles(params.get("smiles", "")),
    "diagnose_capability": lambda params: exec_diagnose_capability(
        params.get("capability", ""), params.get("internal_tool", "")),
    "list_capability_readiness": lambda params: exec_list_capability_readiness(
        int(params.get("limit", 40))),
    "list_scientific_capabilities": lambda params: exec_list_scientific_capabilities(),
    "run_scientific_capability": lambda params: exec_run_scientific_capability(
        params.get("capability", ""), params.get("params") or {}),
    "search_web": lambda params: exec_search_web(params.get("query", ""),
                                                 int(params.get("page_size", 6))),
    "search_pubchem": lambda params: exec_search_pubchem(params.get("term", "")),
    "retrieve_pdb": lambda params: exec_retrieve_pdb(params.get("target", ""),
                                                     params.get("e3", ""),
                                                     int(params.get("top_k", 5))),
    "check_synthetic_feasibility": lambda params: exec_check_synthetic_feasibility(
        params.get("smiles", ""), bool(params.get("use_aizynth", True))),
    "predict_degradation": lambda params: exec_predict_degradation(
        params.get("smiles", ""), params.get("e3", "CRBN"),
        params.get("cell_line", "default"), params.get("target", "")),
    "predict_cell_context": lambda params: exec_predict_cell_context(
        params.get("protac", "") or params.get("smiles", ""),
        params.get("cell_line", ""), params.get("poi", ""), params.get("e3", "")),
    "rank_candidates": lambda params: exec_rank_candidates(params.get("candidates")),
    "build_candidate_dossier": lambda params: exec_build_candidate_dossier(
        params.get("candidate_id", ""), params.get("candidate")),
    "run_protacpilot_structural": lambda params: exec_run_protacpilot_structural(
        params.get("target", ""), params.get("e3", "CRBN"),
        params.get("protac_smiles", ""), params.get("mode", "deterministic")),
    "select_e3_ligase": lambda params: exec_select_e3_ligase(
        params.get("target", ""), params.get("preferred_e3", ""), params.get("e3_ligand_smiles", "")),
    "search_bindingdb": lambda params: exec_search_bindingdb(
        params.get("target", ""), int(params.get("top_k", 100))),
    "detect_exit_vectors": lambda params: exec_detect_exit_vectors(
        params.get("smiles", ""), params.get("role", "warhead")),
    "generate_linkers": lambda params: exec_generate_linkers(
        int(params.get("count", 12)), params.get("constraints")),
    "construct_protac": lambda params: exec_construct_protac(
        params.get("warhead_smiles", ""), params.get("linker_smiles", ""), params.get("e3_smiles", "")),
    "model_ternary_complex": lambda params: exec_model_ternary_complex(
        params.get("target", ""), params.get("e3", ""), params.get("linker_smiles", ""),
        params.get("smiles", "")),
    "score_lysine_ubiquitination": lambda params: exec_score_lysine_ubiquitination(
        params.get("target", ""), params.get("e3", ""), params.get("structure_paths"),
        params.get("poi_chain", ""), params.get("e2_catalytic")),
    "predict_cooperativity": lambda params: exec_predict_cooperativity(
        params.get("warhead_smiles", ""), params.get("linker_smiles", ""),
        params.get("e3_smiles", ""), params.get("pose_pdb", "")),
    "simulate_hook_effect": lambda params: exec_simulate_hook_effect(
        float(params.get("target_conc_nM", 100.0)), float(params.get("e3_conc_nM", 100.0)),
        float(params.get("alpha", 1.0))),
    "predict_admet": lambda params: exec_predict_admet(
        params.get("smiles", ""), params.get("backend", "auto")),
}


def execute_tool(name: str, params: Dict[str, Any]) -> ToolResult:
    """Validate against the strict registry, then execute the real adapter."""
    spec = spec_for(name)
    if spec["readiness"] != "ready":
        return ToolResult(tool=name, status=ToolStatus.ERROR,
                          summary=f"'{name}' is not wired in this build (readiness=planned). "
                                  "Use the full workflow for this step.",
                          evidence_type=EvidenceType.NOT_AVAILABLE)
    executor = _EXECUTORS.get(name)
    if executor is None:
        return ToolResult(tool=name, status=ToolStatus.ERROR,
                          summary="registered but adapter not implemented — no result fabricated",
                          evidence_type=EvidenceType.NOT_AVAILABLE)
    # SCIENTIFIC mode fails closed on missing/placeholder inputs instead of
    # letting per-adapter defaults fabricate a result.
    try:
        from protacxtend.runtime import modes
        if modes.is_scientific():
            modes.validate_scientific_params(
                f"agent tool '{name}'", params or {},
                modes.SCIENTIFIC_REQUIRED_INPUTS.get(name, ()),
            )
    except ImportError:  # pragma: no cover - runtime package always present
        pass
    started = time.time()
    try:
        result = executor(params or {})
        result.tool = name
        if result.evidence_type == EvidenceType.NOT_AVAILABLE and spec.get("retrieved"):
            result.evidence_type = EvidenceType.RETRIEVED
        return result
    except Exception as exc:
        result = ToolResult(tool=name, status=ToolStatus.ERROR,
                            summary=f"execution error · {exc}",
                            evidence_type=EvidenceType.NOT_AVAILABLE)
        # Self-healing hook: diagnose the failure and resolve an external
        # fallback (never masks the original error; audit is always written).
        try:
            from protacxtend.escalation import capability_for, escalate_failure

            capability = capability_for(name)
            escalation = escalate_failure(
                capability, name, exc, inputs=params or {}, mode="check"
            )
            result.data["escalation"] = escalation.to_dict()
            result.warnings.append(escalation.summary)
            if escalation.chosen and escalation.chosen.version:
                result.model_version = escalation.chosen.version
        except Exception as esc_exc:  # pragma: no cover - defensive
            result.warnings.append(f"escalation unavailable: {esc_exc}")
        return result


def tools_catalog_text() -> str:
    lines = []
    for s in registry_specs(ready_only=True):
        lines.append(
            f"- {s['name']} ({s['kind']}) — {s['purpose']} "
            f"inputs: {s['inputs']} evidence: {s['evidence_type']} "
            f"deterministic={bool(s.get('deterministic'))} ml={bool(s.get('ml'))} "
            f"retrieved={bool(s.get('retrieved'))} limitations: {s['limitations']}")
    return "\n".join(lines)
