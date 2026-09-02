SynGlue API Client

Programmatic interface for AI-driven degrader and multitarget molecule design

Overview

SynGlue is a lightweight Python client for interacting with the SynGlue web platform:

🔗 https://synglue.ahujalab.iiitd.edu.in/

It enables programmatic access to:

PROTAC and multitarget molecule design workflows
Molecule screening pipelines
Job monitoring and retrieval
Automated result download and integration

The client is designed for minimal dependencies, reproducibility, and seamless integration into computational pipelines.

Scientific Context

SynGlue is a fragment-centric generative AI framework for rational design of protein degraders and multitarget therapeutics, integrating:

Fragment-level interaction intelligence (MagnetDB)
TRIE-based scalable fragment retrieval
Linker-aware generative modeling
Quantitative prediction of degradation metrics (DC50, Dmax)

This client provides direct access to these capabilities via API calls.

For full methodological details, refer to the manuscript:


Installation

Install the client and required dependency:

pip install synglue requests
Requirements
Python ≥ 3.7
requests
Quick Start
from synglue import SynGlue

# Initialize client
client = SynGlue()
Design Workflow Example

Submit a PROTAC design job:

design_result = client.submit_design(
    target="EGFR",
    threshold=80
)

print("Design job response:", design_result)
Check Job Status
design_status = client.design_status(
    job_id=design_result["job_id"]
)

print("Design job status:", design_status)
Download Results
client.download_design(
    job_id=design_result["job_id"],
    out_path="design_results.zip"
)
Screening Workflow Example
Submit Molecules
molecules = [
    {"name": "Aspirin", "smiles": "CC(=O)Oc1ccccc1C(=O)O"},
    {"name": "Imatinib", "smiles": "CC1=CC=CC=C1"}
]

screen_result = client.submit_screen(molecules=molecules)
print("Screen job response:", screen_result)
Check Status
screen_status = client.screen_status(
    job_id=screen_result["job_id"]
)

print("Screen job status:", screen_status)
Download Results
client.download_screen(
    job_id=screen_result["job_id"],
    out_path="screen_results.csv"
)
API Methods
Design
Method	Description
submit_design(target, threshold=75.0)	Submit degrader design job
design_status(job_id)	Check design job status
download_design(job_id, out_path)	Download design results
Screening
Method	Description
submit_screen(molecules)	Submit screening job
submit_screen_csv(csv_path)	Submit screening from CSV
screen_status(job_id)	Check screening job status
download_screen(job_id, out_path)	Download screening results
Utilities
Method	Description
health_check()	Verify API availability
Data Format
Molecule Input
{
    "name": "Compound_Name",
    "smiles": "SMILES_STRING"
}
Typical Workflow
Submit Job → Track Status → Retrieve Results → Downstream Analysis
Design Philosophy
Minimal interface, maximal functionality
Designed for pipeline integration (HPC / Docker / workflows)
Supports high-throughput batch processing
Enables reproducible computational design
Use Cases
PROTAC design automation
Multitarget molecule screening
Virtual screening pipelines
AI-driven medicinal chemistry workflows
Integration with SynGlue backend deployments
License

SynGlue API client is released under the MIT License.

See LICENSE file for details.

Citation

If you use SynGlue in your work, please cite:

Solanki et al. — SynGlue: Generative AI Framework for Protein Degrader Design
(Manuscript under submission)

Contact
Gaurav Ahuja — gaurav.ahuja@iiitd.ac.in
Susanta Samajdar — susanta_s@aurigene.com
Repository
git clone https://github.com/the-ahuja-lab/SynGlue.git
Notes for Production Use
Ensure API endpoint availability before submission (health_check())
For large jobs, implement polling with backoff strategy
Store job IDs for reproducibility and audit trails
Integrate with workflow managers (Snakemake, Nextflow, Slurm)