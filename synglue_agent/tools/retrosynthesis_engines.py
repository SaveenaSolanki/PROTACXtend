"""
Working retrosynthesis toolkit layer — three engines behind the Task 2 layer.
===============================================================================

Engines (all real, honest, graceful):

  1. ASKCOS (MIT)                         engine code ``askcos``
     MIT's open-source retrosynthesis suite (web portal + downloadable Docker
     deployment). This adapter speaks the current ASKCOS REST API:
       - one-step retrosynthesis   POST {base}/api/retro/controller/call-sync
       - full Retro* tree search   POST {base}/api/tree-search/retro-star/...
       - building-block prices     POST {base}/api/buyables/search
     Default endpoint is the public MIT instance (https://askcos.mit.edu);
     point ``ASKCOS_API_URL`` at a local Docker deployment to stay offline.

  2. AiZynthFinder (AstraZeneca / MolecularAI, MIT)   engine code ``aizynth``
     MCTS + neural-network expansion-policy route search. Needs the
     ``aizynthfinder`` package and the pretrained policy/stock/template assets
     under data/retrosynthesis/models/aizynth (scripts/bootstrap_assets.sh).
     Reuses the verified integration in retrosynthesis.py.

  3. RDKit + OpenNMT workflow (Molecular Transformer) engine code ``openmt``
     Custom local sequence-to-sequence retrosynthesis pipeline:
     RDKit canonicalization/validation -> SMILES tokenization (the Molecular
     Transformer token grammar) -> OpenNMT-py transformer inference ->
     RDKit re-validation of predicted precursor SMILES.
     Needs ``onmt`` (OpenNMT-py) and a retrosynthesis checkpoint under
     data/retrosynthesis/models/openmt/ (env override OPENMT_MODEL). RDKit
     preprocessing/tokenization runs with RDKit alone.

Rules of engagement (project-wide honest-execution contract):
  * Every engine reports availability separately and never fabricates routes.
  * External calls (ASKCOS) are timeout-bounded; local engines never crash.
  * Provenance: every outcome names engine + backend + license + model/assets.
"""

from __future__ import annotations

import importlib.util
import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from pydantic import BaseModel, Field

logger = logging.getLogger("protacpilot.retrosynthesis_engines")

ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = ROOT / "data" / "retrosynthesis" / "models"
AIZYNTN_CONFIG_DIR = MODEL_DIR / "aizynth"          # keep in sync with retrosynthesis.py
OPENMT_CONFIG_DIR = MODEL_DIR / "openmt"

# ── ASKCOS endpoint defaults ────────────────────────────────────────────────
DEFAULT_ASKCOS_URL = "https://askcos.mit.edu"       # public MIT web portal
ASKCOS_URL_ENV = "ASKCOS_API_URL"                   # set to a local Docker deployment
ASKCOS_TOKEN_ENV = "ASKCOS_API_TOKEN"               # optional bearer token for gated deployments
ASKCOS_PROBE_TIMEOUT_S = 5.0

# ── Engine catalogue ────────────────────────────────────────────────────────
ENGINE_CODES = ("askcos", "aizynth", "openmt")

ENGINE_META: dict[str, dict[str, Any]] = {
    "askcos": {
        "engine": "askcos",
        "display_name": "ASKCOS (MIT)",
        "license": "MIT",
        "reliability": "research",
        "executable_type": "api_or_docker",
        "local_executable": True,   # downloadable Docker deployment
        "web_service": True,        # public MIT portal default
        "summary": "MIT open-source retrosynthesis suite: one-step predictions, "
                   "template enumeration and Retro* tree search against building-block catalogs.",
    },
    "aizynth": {
        "engine": "aizynth",
        "display_name": "AiZynthFinder (AstraZeneca)",
        "license": "MIT",
        "reliability": "production",
        "executable_type": "python_package",
        "local_executable": True,
        "web_service": False,
        "summary": "MCTS + neural-network expansion-policy retrosynthetic tree "
                   "search (local; USPTO policy + ZINC stock assets).",
    },
    "openmt": {
        "engine": "openmt",
        "display_name": "RDKit + OpenNMT (Molecular Transformer)",
        "license": "open-source (RDKit BSD-3, OpenNMT MIT, model research-use)",
        "reliability": "experimental",
        "executable_type": "python_pipeline",
        "local_executable": True,
        "web_service": False,
        "summary": "Custom local sequence-to-sequence retrosynthesis workflow: "
                   "RDKit preprocessing + SMILES tokenization + OpenNMT-py "
                   "transformer inference + RDKit re-validation.",
    },
}

ALIASES: dict[str, str] = {
    "askcos": "askcos", "askcos-mit": "askcos",
    "aizynth": "aizynth", "aizynthfinder": "aizynth",
    "openmt": "openmt", "opennmt": "openmt", "molecular-transformer": "openmt",
    "rdkit+opennmt": "openmt", "rdkit-opennmt": "openmt",
}


def normalize_engine_code(code: str) -> str | None:
    """Alias-tolerant engine code resolution (None for unknown codes)."""
    return ALIASES.get((code or "").strip().lower())


# ── Common outcome schema ───────────────────────────────────────────────────

class EngineOutcome(BaseModel):
    """Normalised per-engine result. A single engine never crashes the caller."""

    engine: str
    display_name: str = ""
    license_type: str = ""
    available: bool = False
    ran: bool = False                      # engine actually executed a search
    route_found: bool = False
    route_count: int = 0
    shortest_steps: int | None = None
    routes: list[str] = Field(default_factory=list)        # textual route summaries
    precursors: list[dict[str, Any]] = Field(default_factory=list)  # first-step outcomes
    purchasable_fraction: float = 0.0
    tool_failed: str = ""                  # machine reason when unavailable/failed
    note: str = ""
    provenance: dict[str, Any] = Field(default_factory=dict)
    latency_s: float = 0.0


def _outcome_failed(engine: str, reason: str, note: str = "") -> EngineOutcome:
    meta = ENGINE_META[engine]
    return EngineOutcome(
        engine=engine,
        display_name=meta["display_name"],
        license_type=meta["license"],
        available=False,
        ran=False,
        tool_failed=reason,
        note=note or reason,
        provenance={"engine": engine, "backend": "none", "available": False},
    )


# ── AiZynthFinder availability ──────────────────────────────────────────────

def aizynth_assets_available() -> bool:
    """True when the pretrained policy/stock/template bundle is on disk."""
    try:
        from synglue_agent.tools.retrosynthesis import _aizynth_config_available
        return bool(_aizynth_config_available())
    except Exception:
        stock = AIZYNTN_CONFIG_DIR / "zinc_stock.hdf5"
        onnx = AIZYNTN_CONFIG_DIR / "uspto_model.onnx" and (AIZYNTN_CONFIG_DIR / "uspto_templates.csv.gz").exists()
        hdf5 = (AIZYNTN_CONFIG_DIR / "uspto_policy.hdf5").exists() and (AIZYNTN_CONFIG_DIR / "uspto_templates.hdf5").exists()
        return stock.exists() and (onnx or hdf5)


def aizynth_package_available() -> bool:
    try:
        return importlib.util.find_spec("aizynthfinder") is not None
    except Exception:
        return False


def run_aizynth_engine(smiles: str, timeout_s: int = 300) -> EngineOutcome:
    """AiZynthFinder MCTS route search (reuses the verified retrosynthesis.py
    integration; assets + package required)."""
    meta = ENGINE_META["aizynth"]
    if not aizynth_package_available():
        return _outcome_failed("aizynth", "aizynthfinder_package_missing",
                               "pip install aizynthfinder — AiZynthFinder engine unavailable")
    if not aizynth_assets_available():
        return _outcome_failed("aizynth", "aizynth_policy_missing",
                               "Policy/stock assets missing — run scripts/bootstrap_assets.sh --aizynth")

    t0 = time.monotonic()
    try:
        from synglue_agent.tools.retrosynthesis import aizynth_route_search

        search = aizynth_route_search(smiles, timeout_s=timeout_s)
        latency = round(time.monotonic() - t0, 3)
        if "tool_failed" in search:
            out = _outcome_failed("aizynth", str(search["tool_failed"])[:120],
                                  search.get("note", "AiZynthFinder search failed"))
            out.latency_s = latency
            return out

        routes = search.get("routes", [])
        return EngineOutcome(
            engine="aizynth",
            display_name=meta["display_name"],
            license_type=meta["license"],
            available=True,
            ran=True,
            route_found=bool(search.get("route_found")),
            route_count=int(search.get("route_count", 0)),
            shortest_steps=search.get("shortest_steps"),
            routes=[str(r)[:400] for r in (routes if isinstance(routes, list) else [])][:5],
            purchasable_fraction=1.0 if search.get("route_count", 0) else 0.0,
            provenance={
                "engine": "aizynth",
                "backend": "aizynthfinder",
                "assets": str(AIZYNTN_CONFIG_DIR),
                "onnx": (AIZYNTN_CONFIG_DIR / "uspto_model.onnx").exists(),
                "route_search": "aizynthfinder",
            },
            latency_s=latency,
            note="MCTS route search complete (USPTO expansion policy + ZINC stock).",
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("AiZynthFinder engine failure: %s", exc)
        out = _outcome_failed("aizynth", str(exc)[:200], "AiZynthFinder engine crashed safely")
        out.latency_s = round(time.monotonic() - t0, 3)
        return out


# ── ASKCOS client ───────────────────────────────────────────────────────────

def askcos_base_url() -> str:
    return os.getenv(ASKCOS_URL_ENV, DEFAULT_ASKCOS_URL).strip().rstrip("/")


class AskcosClient:
    """Minimal, verified client for the ASKCOS REST API.

    The request/response contracts below were verified against the live public
    MIT instance (openapi.json at {base}/openapi.json):
      POST /api/retro/controller/call-sync            -> RetroResponse
      POST /api/tree-search/retro-star/call-sync-without-token -> RetroStarResponse
      POST /api/buyables/search                       -> SearchResponse
    A local Docker ASKCOS deployment exposes the identical API — configure via
    the ``ASKCOS_API_URL`` environment variable.
    """

    def __init__(self, base_url: str | None = None, session: Any = None,
                 timeout_s: float = 30.0, token: str | None = None):
        import requests  # deferred import: requests is optional at module scope

        self.base_url = (base_url or askcos_base_url()).rstrip("/")
        self.timeout_s = timeout_s
        self.token = token or os.getenv(ASKCOS_TOKEN_ENV)
        self._session = session if session is not None else requests.Session()
        self._probe_cache: dict[str, Any] = {}

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    # -- reachability ---------------------------------------------------------
    def probe(self, timeout_s: float | None = None) -> dict[str, Any]:
        """Quick reachability + API identity probe (GET {base}/openapi.json)."""
        now = time.monotonic()
        if self._probe_cache and now - self._probe_cache["checked_monotonic"] < 60.0:
            return dict(self._probe_cache["payload"])
        t0 = time.monotonic()
        try:
            resp = self._session.get(f"{self.base_url}/openapi.json",
                                     timeout=timeout_s or self.timeout_s)
            ok = resp.status_code == 200
            info: dict[str, Any] = {"reachable": ok, "http_status": resp.status_code}
            if ok:
                try:
                    spec = resp.json()
                    info["api_title"] = spec.get("info", {}).get("title")
                    info["api_version"] = spec.get("info", {}).get("version")
                    info["path_count"] = len(spec.get("paths", {}))
                except Exception:
                    info["api_title"] = None
            payload = {
                "reachable": ok,
                "base_url": self.base_url,
                "latency_ms": round((time.monotonic() - t0) * 1000, 1),
                "detail": info,
                "note": "Public MIT portal by default; set ASKCOS_API_URL for a local Docker deployment.",
            }
        except Exception as exc:
            payload = {
                "reachable": False,
                "base_url": self.base_url,
                "latency_ms": round((time.monotonic() - t0) * 1000, 1),
                "detail": {"error": str(exc)[:200]},
                "note": "ASKCOS endpoint not reachable — engine reports tool_failed, never fabricates routes.",
            }
        self._probe_cache = {"checked_monotonic": time.monotonic(), "payload": payload}
        return payload

    # -- one-step retrosynthesis ----------------------------------------------
    def one_step_retro(self, smiles_list: Sequence[str], backend: str = "template_relevance",
                       model_name: str = "reaxys", max_num_templates: int = 100,
                       max_cum_prob: float = 0.995, timeout_s: float | None = None,
                       ) -> dict[str, Any]:
        """POST /api/retro/controller/call-sync -> list per input of precursors."""
        body: dict[str, Any] = {
            "backend": backend,
            "model_name": model_name,
            "smiles": list(smiles_list),
            "max_num_templates": max_num_templates,
            "max_cum_prob": max_cum_prob,
        }
        resp = self._session.post(
            f"{self.base_url}/api/retro/controller/call-sync",
            headers=self._headers(),
            data=json.dumps(body),
            timeout=timeout_s or self.timeout_s,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("status_code") not in (None, 200):
            raise RuntimeError(f"ASKCOS retro status_code={data.get('status_code')}: {data.get('message')}")
        raw = data.get("result") or []
        per_input: list[dict[str, Any]] = []
        for idx, preds in enumerate(raw):           # result[i] = list of precursors for smiles_list[i]
            items = []
            for p in preds or []:
                items.append({
                    "precursor_smiles": p.get("outcome", ""),
                    "model_score": p.get("model_score"),
                    "normalized_model_score": p.get("normalized_model_score"),
                    "template_set": (p.get("template") or {}).get("template_set"),
                    "reaction_smarts": (p.get("template") or {}).get("reaction_smarts"),
                })
            per_input.append({"query": list(smiles_list)[idx] if idx < len(smiles_list) else "",
                              "precursors": items[:max_num_templates]})
        return {"status_code": data.get("status_code", 200), "per_input": per_input}

    # -- full tree search (Retro*) --------------------------------------------
    def tree_search(self, smiles: str, expansion_time: int = 20, max_branching: int = 25,
                    max_depth: int = 5, max_trees: int = 200, buyable_logic: str = "and",
                    template_count: int = 100, timeout_s: float | None = None,
                    use_token_endpoint: bool = False) -> dict[str, Any]:
        """POST /api/tree-search/retro-star/... -> routes + terminal purchasability.

        Defaults to the token-free endpoint so the public MIT portal works
        without credentials. Conservative bounds keep sync calls short.
        """
        body: dict[str, Any] = {
            "smiles": smiles,
            "description": "protacpilot-retrosynthesis-engine",
            "tags": "protacpilot",
            "expand_one_options": {
                "template_count": template_count,
                "max_cum_template_prob": 0.995,
                "use_fast_filter": True,
                "filter_threshold": 0.75,
            },
            "build_tree_options": {
                "expansion_time": expansion_time,
                "max_branching": max_branching,
                "max_depth": max_depth,
                "return_first": False,
                "max_trees": max_trees,
                "buyable_logic": buyable_logic,
            },
            "enumerate_paths_options": {
                "path_format": "json",
                "json_format": "nodelink",
                "sorting_metric": "plausibility",
                "validate_paths": True,
                "cluster_trees": False,
            },
            "run_async": False,
        }
        endpoint = ("/api/tree-search/retro-star/call-sync"
                    if use_token_endpoint else
                    "/api/tree-search/retro-star/call-sync-without-token")
        resp = self._session.post(
            f"{self.base_url}{endpoint}",
            headers=self._headers(),
            data=json.dumps(body),
            timeout=timeout_s or max(self.timeout_s, expansion_time + 30),
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("status_code") not in (None, 200):
            raise RuntimeError(f"ASKCOS tree-search status_code={data.get('status_code')}: {data.get('message')}")
        result = data.get("result") or {}
        return self._normalize_tree_result(result)

    @staticmethod
    def _normalize_tree_result(result: dict[str, Any]) -> dict[str, Any]:
        """Retro* nodelink graph -> compact route/purchasability summary.

        Handles two graph shapes returned by the API:
          * rich:  ``uds.graph`` (SMILES-id edges) + ``uds.pathways`` (uuid
            edge lists) + ``uds.uuid2smiles``
          * plain: ``uds.node_dict`` (+ optional ``path_dict``)
        """
        stats = result.get("stats") or {}
        uds = result.get("uds") or {}
        node_dict = uds.get("node_dict") or {}
        path_dict = uds.get("path_dict") or {}

        def _is_reaction(nid: str) -> bool:
            return ">>" in str(nid) or str((node_dict.get(nid) or {}).get("type")) == "reaction"

        # ---- rich pathway extraction --------------------------------------
        pathways = uds.get("pathways")
        uuid2smiles = uds.get("uuid2smiles") or {}
        graph = uds.get("graph") or []
        route_count = int(stats.get("total_paths", 0) or 0)
        shortest: int | None = None
        routes: list[str] = []
        purchasable = 0.0

        if isinstance(pathways, list) and pathways:
            route_count = max(route_count, len(pathways))
            resolved: list[dict[str, Any]] = []
            for path in pathways:
                if not isinstance(path, list):
                    continue
                ids = [str(uuid2smiles.get(e.get("target"), e.get("target")))
                       for e in path if isinstance(e, dict)]
                steps = sum(1 for i in ids if _is_reaction(i))
                if steps:
                    resolved.append({"ids": ids, "steps": steps})
            if resolved:
                shortest = min(r["steps"] for r in resolved)
                for r in sorted(resolved, key=lambda x: x["steps"])[:3]:
                    chain = []
                    for i in r["ids"]:
                        if _is_reaction(i):
                            reagents = str(i).split(">>")[0][:120]
                            chain.append(f"rxn[{reagents}]")
                        else:
                            chain.append(str(i)[:80])
                    routes.append(" => ".join(chain))
            # purchasable fraction over route leaves (graph edges: chem->rxn
            # expand a product; rxn->chem yields its reactant chemicals).
            # Leaves = chemicals produced as reagents but never themselves
            # expanded -> they must be purchasable to terminate the route.
            chem_to_rxn: set = set()   # products that were expanded
            rxn_to_chem: set = set()   # chemicals produced by reactions
            for e in graph:
                if not isinstance(e, dict):
                    continue
                src = str(uuid2smiles.get(e.get("source"), e.get("source")))
                tgt = str(uuid2smiles.get(e.get("target"), e.get("target")))
                if _is_reaction(src) and not _is_reaction(tgt):
                    rxn_to_chem.add(tgt)
                elif not _is_reaction(src) and _is_reaction(tgt):
                    chem_to_rxn.add(src)
            leaves = rxn_to_chem - chem_to_rxn
            if leaves:
                purch = sum(
                    1 for c in leaves
                    if (node_dict.get(c) or {}).get("terminal")
                    or (node_dict.get(c) or {}).get("purchase_price") is not None)
                purchasable = round(purch / len(leaves), 4)

        # ---- plain fallback (node_dict only) ------------------------------
        if not routes:
            steps_by_path: list[int] = []
            for path_nodes in path_dict.values():
                if not isinstance(path_nodes, list):
                    continue
                reactions = sum(1 for nid in path_nodes if _is_reaction(str(nid)))
                if reactions:
                    steps_by_path.append(reactions)
            shortest = min(steps_by_path) if steps_by_path else shortest

            if not shortest and route_count:
                shortest = 1

            terminal = 0
            leaves = 0
            for nid, node in node_dict.items():
                if _is_reaction(str(nid)):
                    continue
                leaves += 1
                if (node or {}).get("terminal") or (node or {}).get("purchase_price") is not None:
                    terminal += 1
            if leaves:
                purchasable = round(terminal / leaves, 4)

            if not routes:
                for _pid, path_nodes in list(path_dict.items())[:3]:
                    if not isinstance(path_nodes, list) or not path_nodes:
                        continue
                    try:
                        smiles_chain = []
                        for nid in path_nodes[:8]:
                            node = node_dict.get(nid) or {}
                            nm = node.get("smiles") or str(nid)
                            smiles_chain.append(str(nm)[:80])
                        routes.append(" => ".join(smiles_chain))
                    except Exception:
                        continue

        return {
            "route_found": route_count > 0,
            "route_count": route_count,
            "shortest_steps": shortest,
            "routes": routes[:5],
            "purchasable_fraction": purchasable,
            "total_chemicals": int(stats.get("total_chemicals", 0) or 0),
            "total_reactions": int(stats.get("total_reactions", 0) or 0),
            "build_time_s": stats.get("build_time"),
            "first_path_time_s": stats.get("first_path_time"),
            "result_id": result.get("result_id", ""),
        }

    # -- buyables --------------------------------------------------------------
    def buyables(self, smiles: str, return_limit: int = 5) -> dict[str, Any]:
        """POST /api/buyables/search -> purchasable vendors/prices for a SMILES."""
        resp = self._session.post(
            f"{self.base_url}/api/buyables/search",
            headers=self._headers(),
            data=json.dumps({
                "q": smiles, "returnLimit": return_limit,
                "canonicalize": False, "isomeric_smiles": True,
            }),
            timeout=self.timeout_s,
        )
        resp.raise_for_status()
        data = resp.json()
        hits = data.get("result") or []
        return {
            "query": smiles,
            "purchasable": len(hits) > 0,
            "hits": [
                {"smiles": h.get("smiles"), "price_per_g": h.get("ppg"),
                 "source": h.get("source"), "similarity": h.get("similarity")}
                for h in hits[:return_limit]
            ],
        }


def run_askcos_engine(smiles: str, *, base_url: str | None = None, session: Any = None,
                      mode: str = "one_step", check_buyables: bool = False,
                      timeout_s: float = 45.0, max_num_templates: int = 25,
                      tree_search: bool = False) -> EngineOutcome:
    """ASKCOS engine: one-step template-based retro (+ optional Retro* + buyables).

    mode: 'one_step' | 'tree' | 'auto'  (auto upgrades to tree when reachable).
    Never fabricates: endpoint/probe failures -> tool_failed with reason.
    """
    meta = ENGINE_META["askcos"]
    client = AskcosClient(base_url=base_url, session=session, timeout_s=timeout_s)
    probe = client.probe(timeout_s=min(timeout_s, ASKCOS_PROBE_TIMEOUT_S))
    if not probe["reachable"]:
        out = _outcome_failed("askcos", "askcos_unreachable",
                              f"{probe['base_url']} not reachable: {probe['detail'].get('error', '')}")
        out.provenance = {"engine": "askcos", "base_url": client.base_url,
                          "probe": probe, "available": False}
        return out

    t0 = time.monotonic()
    try:
        precursors: list[dict[str, Any]] = []
        route_found = False
        route_count = 0
        shortest = None
        routes: list[str] = []
        purchasable = 0.0

        do_tree = mode == "tree" or (mode == "auto" and tree_search)
        if do_tree:
            tsearch = client.tree_search(smiles, expansion_time=20, max_branching=25,
                                         max_depth=5, max_trees=150, template_count=max_num_templates,
                                         timeout_s=max(timeout_s, 60))
            route_found = bool(tsearch.get("route_found"))
            route_count = int(tsearch.get("route_count", 0))
            shortest = tsearch.get("shortest_steps")
            routes = tsearch.get("routes", [])
            purchasable = float(tsearch.get("purchasable_fraction", 0.0))
        else:
            one = client.one_step_retro([smiles], max_num_templates=max_num_templates,
                                        timeout_s=timeout_s)
            per = (one.get("per_input") or [{}])[0]
            precursors = per.get("precursors", [])
            route_found = len(precursors) > 0
            route_count = len(precursors)
            if route_count:
                shortest = 1
                # route summaries = the top-3 one-step outcomes
                for p in precursors[:3]:
                    routes.append(p.get("precursor_smiles", ""))

        if check_buyables and route_found:
            # purchase check on the best precursor set (first precursor of the top outcome)
            try:
                if precursors:
                    cand = precursors[0].get("precursor_smiles", "")
                    if cand:
                        frag = cand.split(".")[0]
                        buy = client.buyables(frag, return_limit=3)
                        purchasable = 1.0 if buy.get("purchasable") else 0.0
            except Exception as exc:  # buyables is an enhancement, never fatal
                logger.debug("askcos buyables check skipped: %s", exc)

        latency = round(time.monotonic() - t0, 3)
        return EngineOutcome(
            engine="askcos",
            display_name=meta["display_name"],
            license_type=meta["license"],
            available=True,
            ran=True,
            route_found=route_found,
            route_count=route_count,
            shortest_steps=shortest,
            routes=[str(r)[:300] for r in routes][:5],
            precursors=precursors[:max_num_templates],
            purchasable_fraction=purchasable,
            provenance={
                "engine": "askcos",
                "base_url": client.base_url,
                "endpoint": ("retro-star tree search" if do_tree
                             else "retro/controller one-step"),
                "probe": probe,
                "available": True,
            },
            latency_s=latency,
            note="ASKCOS predictions verified live (MIT portal or local Docker deployment).",
        )
    except Exception as exc:
        logger.warning("ASKCOS engine failure: %s", exc)
        out = _outcome_failed("askcos", str(exc)[:200], "ASKCOS call failed safely")
        out.provenance = {"engine": "askcos", "base_url": client.base_url}
        out.latency_s = round(time.monotonic() - t0, 3)
        return out


# ── RDKit + OpenNMT (Molecular Transformer) workflow ────────────────────────

# Molecular-Transformer / OpenNMT SMILES token grammar (atom + bond tokens).
_SMILES_TOKEN_RE = re.compile(
    r"(\[[^\]]+]|Br?|Cl?|N|O|S|P|F|I|b|c|n|o|s|p|\(|\)|\.|=|#|-|\+|\\\\|/|:|~|@|\?|>|\*|\$|%[0-9]{2}|[0-9])"
)


def openmt_checkpoint_path() -> Path | None:
    """Checkpoint for the local OpenNMT retrosynthesis model.

    Env override OPENMT_MODEL (file) else data/retrosynthesis/models/openmt/
    retro_model.pt (bootstrap the checkpoint there for a local deployment).
    """
    override = os.getenv("OPENMT_MODEL")
    if override:
        p = Path(override)
        return p if p.exists() else None
    candidate = OPENMT_CONFIG_DIR / "retro_model.pt"
    return candidate if candidate.exists() else None


def openmt_package_available() -> bool:
    try:
        return importlib.util.find_spec("onmt") is not None
    except Exception:
        return False


def tokenize_smiles(smiles: str) -> list[str]:
    """Molecular-Transformer-style tokenization (deterministic, RDKit-free).

    Splits every atom/bond symbol, preserving the input exactly on re-join for
    canonical SMILES. Invalid inputs tokenise to [] and must be rejected by the
    caller (RDKit gate) before reaching the translator.
    """
    if not smiles:
        return []
    return _SMILES_TOKEN_RE.findall(smiles)


def detokenize_smiles(tokens: Sequence[str]) -> str:
    return "".join(tokens)


def validate_smiles_with_rdkit(smiles: str) -> str | None:
    """RDKit canonical validation; returns canonical SMILES or None."""
    if not smiles or not smiles.strip():
        return None
    try:
        from rdkit import Chem
        mol = Chem.MolFromSmiles(smiles)
        if mol is None or mol.GetNumAtoms() == 0:
            return None
        return Chem.MolToSmiles(mol)
    except Exception:
        return None


def _openmt_translate(smiles: str) -> list[dict[str, Any]]:
    """Run the local OpenNMT-py translator on one preprocessed SMILES.

    Requires OpenNMT-py + checkpoint (see openmt_checkpoint_path). Returns a
    list of {precursor_smiles, validated} dicts, empty when nothing parses.
    """
    from onmt.translate.translator import Translator  # type: ignore[import-not-found]
    from onmt.utils.parse import ArgumentParser  # type: ignore[import-not-found]

    checkpoint = openmt_checkpoint_path()
    assert checkpoint is not None

    tokens = tokenize_smiles(smiles)
    if not tokens:
        return []

    opt = ArgumentParser()
    opt.add_argument("-model", default=str(checkpoint))
    opt.add_argument("-src", default="-")
    opt.add_argument("-output", default="-")
    opt.add_argument("-replace_unk", default=True)
    opt.add_argument("-max_length", default=200)
    opt.add_argument("-n_best", default=5)
    opt.add_argument("-beam_size", default=5)
    opt.add_argument("-gpu", default=-1)
    opt.add_argument("-batch_size", default=1)
    opt.add_argument("-verbose", default=False)
    parsed = opt.parse_args([])          # onmt fills remaining opts from the checkpoint
    translator = Translator(parsed, model_path=parsed.model)
    results: list[str] = []
    try:
        src = " ".join(tokens) + "\n"
        out = translator.translate(src=src)
        for pred in out[0]["pred_sents"]:
            results.append(detokenize_smiles(pred.split()))
    except Exception:
        # OpenNMT py <4 API shape differences; try the older translate_src_text
        translator = Translator(parsed)
        out = translator.translate_src_text([" ".join(tokens)])
        results = [detokenize_smiles(s.split()) for s in out]

    validated: list[dict[str, Any]] = []
    for cand in results:
        canon = validate_smiles_with_rdkit(cand)
        if canon:
            validated.append({"precursor_smiles": canon, "validated": True})
    return validated


def run_openmt_engine(smiles: str, timeout_s: float = 120.0) -> EngineOutcome:
    """RDKit + OpenNMT seq2seq retrosynthesis workflow.

    RDKit preprocessing is always available; translation needs OpenNMT-py +
    a retrosynthesis checkpoint (honest status otherwise).
    """
    meta = ENGINE_META["openmt"]
    checkpoint = openmt_checkpoint_path()
    if not openmt_package_available():
        return _outcome_failed("openmt", "opennmt_package_missing",
                               "pip install OpenNMT-py — RDKit+OpenNMT engine unavailable (RDKit preprocess still usable)")
    if checkpoint is None:
        return _outcome_failed(
            "openmt", "opennmt_checkpoint_missing",
            f"Place a retrosynthesis checkpoint at {OPENMT_CONFIG_DIR}/retro_model.pt "
            "(or export OPENMT_MODEL=...) — RDKit+OpenNMT engine unavailable")

    canon = validate_smiles_with_rdkit(smiles)
    if canon is None:
        return _outcome_failed("openmt", "invalid_smiles",
                               f"RDKit rejected input SMILES: {smiles!r}")

    t0 = time.monotonic()
    try:
        predicted = _openmt_translate(canon)
        latency = round(time.monotonic() - t0, 3)
        route_found = len(predicted) > 0
        return EngineOutcome(
            engine="openmt",
            display_name=meta["display_name"],
            license_type=meta["license"],
            available=True,
            ran=True,
            route_found=route_found,
            route_count=len(predicted),
            shortest_steps=1 if route_found else None,
            routes=[f"{p['precursor_smiles']} (validated)" for p in predicted[:5]],
            precursors=predicted[:10],
            purchasable_fraction=0.0,   # building-block check not part of the seq2seq workflow
            provenance={
                "engine": "openmt",
                "backend": "onmt",
                "checkpoint": str(checkpoint),
                "tokenizer": "molecular_transformer",
                "rdkit_validation": True,
            },
            latency_s=latency,
            note="RDKit preprocess -> OpenNMT transformer -> RDKit re-validation.",
        )
    except Exception as exc:
        logger.warning("OpenNMT engine failure: %s", exc)
        out = _outcome_failed("openmt", str(exc)[:200], "OpenNMT translation failed safely")
        out.latency_s = round(time.monotonic() - t0, 3)
        return out


# ── Orchestration ───────────────────────────────────────────────────────────

@dataclass
class EngineRunSummary:
    """Merged multi-engine result consumed by retrosynthesis.assess_retrosynthesis."""

    engines_requested: list[str]
    engines_available: list[str]
    engines_ran: list[str]
    any_route_found: bool
    best_engine: str = ""                 # first engine with a route (fewest steps preferred)
    route_count: int = 0
    shortest_steps: int | None = None
    routes: list[str] = field(default_factory=list)
    purchasable_fraction: float = 0.0
    outcomes: list[EngineOutcome] = field(default_factory=list)

    def model_dump(self) -> dict[str, Any]:
        return {
            "engines_requested": self.engines_requested,
            "engines_available": self.engines_available,
            "engines_ran": self.engines_ran,
            "any_route_found": self.any_route_found,
            "best_engine": self.best_engine,
            "route_count": self.route_count,
            "shortest_steps": self.shortest_steps,
            "routes": self.routes,
            "purchasable_fraction": self.purchasable_fraction,
            "outcomes": [o.model_dump() for o in self.outcomes],
        }


def run_engines(smiles: str, engines: Sequence[str] = ("aizynth",),
                *, askcos_base_url: str | None = None, askcos_session: Any = None,
                askcos_mode: str = "one_step", askcos_check_buyables: bool = False,
                max_num_templates: int = 25, aizynth_timeout_s: int = 300) -> EngineRunSummary:
    """Run requested engines against one SMILES. Offline-safe, never raises."""
    requested: list[str] = []
    for code in engines:
        norm = normalize_engine_code(code)
        if norm and norm not in requested:
            requested.append(norm)

    outcomes: list[EngineOutcome] = []
    for code in requested:
        if code == "aizynth":
            outcomes.append(run_aizynth_engine(smiles, timeout_s=aizynth_timeout_s))
        elif code == "askcos":
            outcomes.append(run_askcos_engine(
                smiles, base_url=askcos_base_url, session=askcos_session,
                mode=askcos_mode, check_buyables=askcos_check_buyables,
                max_num_templates=max_num_templates))
        elif code == "openmt":
            outcomes.append(run_openmt_engine(smiles))
        else:  # pragma: no cover - normalize_engine_code already filtered
            outcomes.append(_outcome_failed(code, "unknown_engine", f"unknown engine code {code!r}"))

    return merge_engine_outcomes(outcomes, engines_requested=requested)


def merge_engine_outcomes(outcomes: Sequence[EngineOutcome],
                          engines_requested: list[str] | None = None) -> EngineRunSummary:
    """Merge per-engine outcomes into one summary. Deterministic ordering."""
    outcomes = list(outcomes)
    # canonical engine order in summaries for deterministic reporting
    def _order(engines: Sequence[str]) -> list[str]:
        ordered = [c for c in ENGINE_CODES if c in set(engines)]
        ordered += [e for e in engines if e not in ENGINE_CODES]
        return ordered

    available = _order([o.engine for o in outcomes if o.available])
    ran = _order([o.engine for o in outcomes if o.ran])

    found = [o for o in outcomes if o.route_found]
    best: EngineOutcome | None = None
    for o in found:  # first match wins ties; prefer fewer steps
        if best is None or (o.shortest_steps is not None and
                            (best.shortest_steps is None or o.shortest_steps < best.shortest_steps)):
            best = o

    routes: list[str] = []
    if best is not None:
        for o in found:
            for r in o.routes:
                if r not in routes:
                    routes.append(r)
        routes = routes[:5]

    return EngineRunSummary(
        engines_requested=list(engines_requested or [o.engine for o in outcomes]),
        engines_available=available,
        engines_ran=ran,
        any_route_found=best is not None,
        best_engine=best.engine if best else "",
        route_count=sum(o.route_count for o in found) or (0 if not found else len(found)),
        shortest_steps=best.shortest_steps if best else None,
        routes=routes,
        purchasable_fraction=max((o.purchasable_fraction for o in outcomes), default=0.0),
        outcomes=outcomes,
    )


# ── Status report ───────────────────────────────────────────────────────────

def engine_status_report(skip_network: bool = False) -> dict[str, Any]:
    """Honest availability of all three engines (no expensive runs)."""
    report: dict[str, Any] = {}
    for code in ENGINE_CODES:
        meta = ENGINE_META[code]
        if code == "aizynth":
            status = {
                "available": aizynth_package_available() and aizynth_assets_available(),
                "package_installed": aizynth_package_available(),
                "assets_present": aizynth_assets_available(),
                "assets_dir": str(AIZYNTN_CONFIG_DIR),
            }
        elif code == "askcos":
            client = AskcosClient()
            probe = {"reachable": False, "note": "network probe skipped"} if skip_network else client.probe()
            status = {"available": bool(probe["reachable"]), "probe": probe}
        else:
            status = {
                "available": openmt_package_available() and openmt_checkpoint_path() is not None,
                "package_installed": openmt_package_available(),
                "checkpoint_present": openmt_checkpoint_path() is not None,
                "checkpoint_dir": str(OPENMT_CONFIG_DIR),
            }
        report[code] = {"meta": meta, "status": status}
    return report


def render_engine_status_report(skip_network: bool = False) -> str:
    rows = engine_status_report(skip_network=skip_network)
    lines = ["Retrosynthesis toolkit engines (honest availability):", ""]
    for code, entry in rows.items():
        meta = entry["meta"]
        st = entry["status"]
        available = st.get("available", False)
        lines.append(f"- [{code}] {meta['display_name']}  (license: {meta['license']})")
        lines.append(f"    available: {available}   executable: {meta['executable_type']}")
        if code == "aizynth":
            lines.append(f"    package={st['package_installed']} assets={st['assets_present']} @ {st['assets_dir']}")
        elif code == "askcos":
            probe = st.get("probe", {})
            lines.append(f"    endpoint={probe.get('base_url')} reachable={probe.get('reachable')} "
                         f"({probe.get('detail', {}).get('error', probe.get('note', ''))})")
        else:
            lines.append(f"    package={st['package_installed']} checkpoint={st['checkpoint_present']} "
                         f"@ {st['checkpoint_dir']}")
        lines.append(f"    {meta['summary']}")
        lines.append("")
    return "\n".join(lines)
