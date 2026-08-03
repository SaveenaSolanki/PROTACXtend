"""Target resolver agent — resolves target name to UniProt ID and structure."""

from __future__ import annotations
import json, os, urllib.request, urllib.error, urllib.parse
from typing import Any
from synglue_agent.agents.base_agent import ReActAgent
from synglue_agent.backend.schemas import WorkflowState

UNIPROT_API = "https://rest.uniprot.org/uniprotkb/search?query={}&format=json&size=1"
ALPHAFOLD_API = "https://alphafold.ebi.ac.uk/api/prediction/{}"

class TargetResolverAgent(ReActAgent):
    name = "TargetResolverAgent"
    thought = "Resolve target gene/protein name to UniProt entry and AlphaFold structure."
    action = "resolve_target"

    def _execute(self, state: WorkflowState) -> WorkflowState:
        objective = state.parsed_objective
        target_name = objective.target_name
        if not target_name:
            state.errors.append("TargetResolverAgent: No target name provided.")
            return state

        # 1. Search UniProt
        record = self._search_uniprot(target_name)
        if not record:
            # Try with "HUMAN" suffix
            record = self._search_uniprot(f"{target_name}+AND+organism_id:9606")
        
        if record:
            from synglue_agent.backend.schemas import TargetRecord
            state.target_record = TargetRecord(
                uniprot_id=record.get("primaryAccession", ""),
                gene_symbol=target_name.upper(),
                target_name=record.get("uniProtkbId", ""),
                organism=record.get("organism", {}).get("scientificName", ""),
            )
            
            # 2. Fetch AlphaFold structure URL
            uniprot_id = state.target_record.uniprot_id
            try:
                req = urllib.request.Request(ALPHAFOLD_API.format(uniprot_id))
                with urllib.request.urlopen(req, timeout=10) as resp:
                    af_data = json.loads(resp.read().decode())
                    if af_data:
                        state.target_record.alphafold_id = af_data[0].get("entryId", "")
                        state.target_record.external_ids["alphafold_url"] = af_data[0].get("cifUrl", "")
                        state.target_record.external_ids["alphafold_pdb_url"] = af_data[0].get("pdbUrl", "")
            except Exception:
                state.warnings.append(f"TargetResolverAgent: AlphaFold fetch failed for {uniprot_id}")
            
            # 3. Load from local curated data
            curated = self.toolbox.load_curated_targets()
            for row in curated:
                if row.get("gene_symbol", "").upper() == target_name.upper() or row.get("target_name", "").upper() == target_name.upper():
                    state.target_record.external_ids["curated_druggability"] = row.get("druggability", "unknown")
                    state.target_record.external_ids["curated_tractability"] = row.get("tractability", "unknown")
                    state.target_record.external_ids["curated_class"] = row.get("class", "")
                    break
            
            state.parsed_objective.target_uniprot_id = state.target_record.uniprot_id
        else:
            state.errors.append(f"TargetResolverAgent: Could not resolve '{target_name}' in UniProt.")
        
        return state

    def _search_uniprot(self, query: str) -> dict | None:
        try:
            url = UNIPROT_API.format(urllib.parse.quote(query))
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
                results = data.get("results", [])
                return results[0] if results else None
        except Exception as e:
            self.toolbox.logger.warning(f"UniProt search failed for '{query}': {e}")
            return None

    def _observation(self, state: WorkflowState) -> str:
        rec = state.target_record
        if rec:
            return f"uniprot={rec.uniprot_id or 'none'}, gene={rec.gene_symbol}"
        return "target_not_resolved"
