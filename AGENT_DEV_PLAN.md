# Agent Development Plan — What I Need From You

## Can Build Now (no API keys needed)

| Agent | What it needs | Status |
|-------|--------------|--------|
| TargetResolverAgent | UniProt REST API (free, no key) | ✅ Build now |
| WarheadSelectionAgent | Local curated_warheads.csv | ✅ Build now |
| E3LigandSelectionAgent | Local curated_e3_ligands.csv | ✅ Build now |
| ExitVectorDetectionAgent | RDKit (installed) | ✅ Build now |
| LinkerGenerationAgent | Local curated_linkers.csv + RDKit | ✅ Build now |
| MolecularConstructionAgent | RDKit | ✅ Build now |
| CandidateValidationAgent | RDKit + property rules | ✅ Build now |
| ADMETAgent | RDKit descriptors | ✅ Build now |
| NoveltyAgent | Local known_protac_smiles.csv | ✅ Build now |
| RankingAgent | Composite scoring | ✅ Build now |
| ProximityDiversityAgent | RDKit fingerprints | ✅ Build now |
| ReflectionReviewAgent | Rule-based critique | ✅ Build now |
| SafetyAgent | Simple rule checks | ✅ Build now |
| ReportAgent | Template + data | ✅ Build now |
| DegradationPredictionAgent | Heuristic model | ✅ Build now |

## Need API Keys From You

| Agent/Source | What it needs | Where to get it | Free? |
|-------------|--------------|-----------------|-------|
| **ChEMBL** | Bioactivity data for binder retrieval | https://www.ebi.ac.uk/chembl/ws | ✅ Free registration |
| **PubChem** | Compound lookup | https://pubchem.ncbi.nlm.nih.gov/docs/programmatic-access | ✅ Free (no key) |
| **RCSB PDB** | Protein structures | https://data.rcsb.org/ | ✅ Free (no key) |
| **UniProt** | Protein annotation | https://www.uniprot.org/api-documentation | ✅ Free (no key) |
| **BindingDB** | Affinity data | https://www.bindingdb.org/rwd/bind/BindingDBAPI.jsp | ✅ Free |
| **DrugBank** | Drug-target data | https://go.drugbank.com/ | ❌ Licensed ($) |
| **PDB ID mapping** | ID conversion | https://www.uniprot.org/id-mapping | ✅ Free |

**Good news:** ChEMBL, PubChem, PDB, UniProt, BindingDB are all **free with no key or free registration**. I can start building against their public APIs immediately. Only DrugBank requires a paid license.

## Stereochemistry-Aware SMILES

I need to implement:
1. **Isomeric SMILES parser** — detect chiral centers, E/Z geometry from SMILES
2. **Exit vector with stereochemistry** — identify which attachment vector is correct for each enantiomer
3. **Linker attachment with stereo retention** — ensure linker doesn't invert chiral centers
4. **Validation** — compare generated PROTAC SMILES with known isomeric PROTACs

All of this is RDKit-based and can be built now.

---

## Ready to Build

Give me the go-ahead and I'll implement all 15 agents plus the stereochemistry engine. The ones needing APIs will use public REST endpoints (no key needed for ChEMBL, UniProt, PDB, PubChem, BindingDB).
