"""Executable UniProt REST lookup wrappers.

These functions call UniProt REST directly and never fall back to local demo
data. Network failures and empty results are returned as structured errors.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


SOURCE = "UniProt REST"
BASE_URL = "https://rest.uniprot.org/uniprotkb"
USER_AGENT = "PROTACXtend/0.1"
ORGANISM_IDS = {"human": "9606", "homo sapiens": "9606", "mouse": "10090", "rat": "10116"}


def _request_json(url: str, timeout: float) -> tuple[dict[str, Any] | None, str | None]:
    request = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8")), None
    except urllib.error.HTTPError as exc:
        return None, f"UniProt HTTP error {exc.code}: {exc.reason}"
    except urllib.error.URLError as exc:
        return None, f"UniProt network error: {exc.reason}"
    except TimeoutError:
        return None, "UniProt request timed out."
    except json.JSONDecodeError as exc:
        return None, f"UniProt returned invalid JSON: {exc}"


def _organism_query(organism: str) -> str:
    normalized = str(organism or "human").strip().lower()
    return ORGANISM_IDS.get(normalized, organism)


def _gene_fields(item: dict[str, Any]) -> tuple[str | None, list[str]]:
    genes = item.get("genes") or []
    if not genes:
        return None, []
    primary = (genes[0].get("geneName") or {}).get("value")
    synonyms = []
    for gene in genes:
        gene_name = (gene.get("geneName") or {}).get("value")
        if gene_name:
            synonyms.append(gene_name)
        synonyms.extend(syn.get("value") for syn in gene.get("synonyms", []) if syn.get("value"))
        synonyms.extend(name.get("value") for name in gene.get("orderedLocusNames", []) if name.get("value"))
        synonyms.extend(name.get("value") for name in gene.get("orfNames", []) if name.get("value"))
    return primary, sorted({syn for syn in synonyms if syn})


def _protein_name(item: dict[str, Any]) -> str | None:
    description = item.get("proteinDescription") or {}
    recommended = description.get("recommendedName") or {}
    full_name = recommended.get("fullName") or {}
    if full_name.get("value"):
        return full_name["value"]
    submission_names = description.get("submissionNames") or []
    if submission_names:
        return ((submission_names[0].get("fullName") or {}).get("value"))
    return None


def _function_summary(item: dict[str, Any]) -> str | None:
    texts = []
    for comment in item.get("comments", []) or []:
        if comment.get("commentType") != "FUNCTION":
            continue
        texts.extend(text.get("value") for text in comment.get("texts", []) if text.get("value"))
    return " ".join(texts) if texts else None


def _subcellular_location(item: dict[str, Any]) -> list[str]:
    locations = []
    for comment in item.get("comments", []) or []:
        if comment.get("commentType") != "SUBCELLULAR LOCATION":
            continue
        for location in comment.get("subcellularLocations", []) or []:
            value = ((location.get("location") or {}).get("value"))
            if value:
                locations.append(value)
    return sorted(set(locations))


def _sequence(item: dict[str, Any]) -> tuple[str | None, int | None]:
    sequence = (item.get("sequence") or {}).get("value")
    length = (item.get("sequence") or {}).get("length")
    if sequence and length is None:
        length = len(sequence)
    return sequence, length


def _record_from_item(item: dict[str, Any], query: Any, source_url: str) -> dict[str, Any]:
    accession = item.get("primaryAccession")
    gene_name, synonyms = _gene_fields(item)
    sequence, sequence_length = _sequence(item)
    return {
        "source": SOURCE,
        "query": query,
        "accession": accession,
        "gene_name": gene_name,
        "protein_name": _protein_name(item),
        "organism": (item.get("organism") or {}).get("scientificName"),
        "reviewed": item.get("entryType") == "UniProtKB reviewed (Swiss-Prot)",
        "sequence_length": sequence_length,
        "sequence": sequence,
        "synonyms": synonyms,
        "function": _function_summary(item),
        "subcellular_location": _subcellular_location(item),
        "source_url": source_url,
        "success": True,
        "error": None,
    }


def _empty_result(query: Any, source_url: str | None, error: str) -> dict[str, Any]:
    return {
        "source": SOURCE,
        "query": query,
        "accession": None,
        "gene_name": None,
        "protein_name": None,
        "organism": None,
        "reviewed": None,
        "sequence_length": None,
        "sequence": None,
        "synonyms": [],
        "function": None,
        "subcellular_location": [],
        "source_url": source_url,
        "success": False,
        "error": error,
    }


def search_uniprot(query: str, organism: str = "human", reviewed: bool = True, top_k: int = 5, timeout: float = 10.0) -> dict[str, Any]:
    request_query = {"query": query, "organism": organism, "reviewed": reviewed, "top_k": top_k}
    if not query or not str(query).strip():
        return {"source": SOURCE, "query": request_query, "success": False, "error": "Target query is required.", "records": []}
    filters = [f"({query})"]
    organism_id = _organism_query(organism)
    if organism_id:
        filters.append(f"organism_id:{organism_id}")
    if reviewed:
        filters.append("reviewed:true")
    params = urllib.parse.urlencode({"query": " AND ".join(filters), "format": "json", "size": max(int(top_k), 1)})
    url = f"{BASE_URL}/search?{params}"
    payload, error = _request_json(url, timeout=timeout)
    if error:
        return {"source": SOURCE, "query": request_query, "success": False, "error": error, "records": [], "source_url": url}
    records = [_record_from_item(item, request_query, url) for item in payload.get("results", [])]
    return {
        "source": SOURCE,
        "query": request_query,
        "success": bool(records),
        "error": None if records else "UniProt returned no matching records.",
        "records": records,
        "source_url": url,
    }


def get_uniprot_record(accession: str, timeout: float = 10.0) -> dict[str, Any]:
    query = {"accession": accession}
    if not accession or not str(accession).strip():
        return _empty_result(query, None, "UniProt accession is required.")
    accession = str(accession).strip()
    url = f"{BASE_URL}/{urllib.parse.quote(accession)}.json"
    payload, error = _request_json(url, timeout=timeout)
    if error:
        return _empty_result(query, url, error)
    return _record_from_item(payload, query, url)


def get_target_synonyms(query: str, timeout: float = 10.0) -> dict[str, Any]:
    result = search_uniprot(query, timeout=timeout, top_k=1)
    if not result["success"]:
        return {"source": SOURCE, "query": {"query": query}, "success": False, "error": result["error"], "synonyms": []}
    record = result["records"][0]
    return {
        "source": SOURCE,
        "query": {"query": query},
        "accession": record["accession"],
        "success": True,
        "error": None,
        "synonyms": record["synonyms"],
        "source_url": record["source_url"],
    }


def get_protein_sequence(accession: str, timeout: float = 10.0) -> dict[str, Any]:
    record = get_uniprot_record(accession, timeout=timeout)
    return {
        "source": SOURCE,
        "query": {"accession": accession},
        "accession": record["accession"],
        "success": record["success"],
        "error": record["error"],
        "sequence": record["sequence"],
        "sequence_length": record["sequence_length"],
        "source_url": record["source_url"],
    }


def get_subcellular_location(accession: str, timeout: float = 10.0) -> dict[str, Any]:
    record = get_uniprot_record(accession, timeout=timeout)
    return {
        "source": SOURCE,
        "query": {"accession": accession},
        "accession": record["accession"],
        "success": record["success"],
        "error": record["error"],
        "subcellular_location": record["subcellular_location"],
        "source_url": record["source_url"],
    }


def get_function_summary(accession: str, timeout: float = 10.0) -> dict[str, Any]:
    record = get_uniprot_record(accession, timeout=timeout)
    return {
        "source": SOURCE,
        "query": {"accession": accession},
        "accession": record["accession"],
        "success": record["success"],
        "error": record["error"],
        "function": record["function"],
        "source_url": record["source_url"],
    }
