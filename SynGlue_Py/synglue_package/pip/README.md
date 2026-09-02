
git clone <https://github.com/the-ahuja-lab/SynGlue.git>

# SynGlue API Client

**SynGlue** is a minimal Python client for the SynGlue web API at https://synglue.ahujalab.iiitd.edu.in/. It allows you to submit design and screen jobs, check job status, and download results programmatically.

## Installation

Install the package and its only dependency:

```bash
pip install synglue requests
```


## Usage Example

```python
from synglue import SynGlue

# Initialize the client
client = SynGlue()

# Submit a design job
design_result = client.submit_design(target="EGFR", threshold=80)
print("Design job response:", design_result)

# Check design job status
design_status = client.design_status(job_id=design_result["job_id"])
print("Design job status:", design_status)

# Download design results (when job is complete)
# client.download_design(job_id=design_result["job_id"], out_path="design_results.zip")

# --- SCREENING EXAMPLE ---

# Submit a screen job with a list of molecules
molecules = [
	{"name": "Aspirin", "smiles": "CC(=O)Oc1ccccc1C(=O)O"},
	{"name": "Imatinib", "smiles": "CC1=CC=CC=C1"}
]
screen_result = client.submit_screen(molecules=molecules)
print("Screen job response:", screen_result)

# Check screen job status
screen_status = client.screen_status(job_id=screen_result["job_id"])
print("Screen job status:", screen_status)

# Download screen results (when job is complete)
# client.download_screen(job_id=screen_result["job_id"], out_path="screen_results.csv")
```

## Methods

- `submit_design(target, threshold=75.0)`
- `design_status(job_id)`
- `download_design(job_id, out_path)`
- `submit_screen(molecules)`
- `submit_screen_csv(csv_path)`
- `screen_status(job_id)`
- `download_screen(job_id, out_path)`
- `health_check()`

See the source code for full method documentation.

## Prerequisites

- Python 3.7 or higher
- requests (for API calls)

## License

SynGlue is licensed under the MIT License. See LICENSE for more details.

## Dependencies


## Prerequisites

- Python 3.7 or higher
- requests (for API calls)

Install the required package:

```bash
pip install requests
```

No other dependencies are required for the SynGlue API client.

## License

SynGlue is licensed under the MIT License. See [LICENSE](https://www.notion.so/saveenasolanki/LICENSE) for more details.



