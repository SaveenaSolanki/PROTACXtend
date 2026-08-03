
import requests
from typing import List, Dict, Optional

BASE_URL = "https://synglue.ahujalab.iiitd.edu.in"

class SynGlue:
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url

    def submit_design(self, target: str, threshold: float = 75.0) -> Dict:
        url = f"{self.base_url}/synglue/api/design/submit/"
        payload = {"target": target, "threshold": threshold}
        resp = requests.post(url, json=payload)
        resp.raise_for_status()
        return resp.json()

    def design_status(self, job_id: str) -> Optional[Dict]:
        url = f"{self.base_url}/synglue/api/design/status/?job_id={job_id}"
        resp = requests.get(url)
        try:
            resp.raise_for_status()
        except requests.HTTPError as e:
            if resp.status_code == 404:
                print(f"Warning: Design job {job_id} does not exist.")
                return None
            else:
                raise
        return resp.json()

    def download_design(self, job_id: str, out_path: str) -> Optional[str]:
        url = f"{self.base_url}/synglue/api/design/download/?job_id={job_id}"
        resp = requests.get(url)
        try:
            resp.raise_for_status()
        except requests.HTTPError as e:
            if resp.status_code == 404:
                print(f"Warning: Design job {job_id} does not exist or results are not available.")
                return None
            else:
                raise
        with open(out_path, "wb") as f:
            f.write(resp.content)
        return out_path

    def submit_screen(self, molecules: List[Dict[str, str]]) -> Dict:
        url = f"{self.base_url}/synglue/api/screen/submit/"
        payload = {"molecules": molecules}
        resp = requests.post(url, json=payload)
        resp.raise_for_status()
        return resp.json()

    def submit_screen_csv(self, csv_path: str) -> Dict:
        url = f"{self.base_url}/synglue/api/screen/submit_csv/"
        with open(csv_path, "rb") as f:
            files = {"file": f}
            resp = requests.post(url, files=files)
        resp.raise_for_status()
        return resp.json()

    def screen_status(self, job_id: str) -> Optional[Dict]:
        url = f"{self.base_url}/synglue/api/screen/status/?job_id={job_id}"
        resp = requests.get(url)
        try:
            resp.raise_for_status()
        except requests.HTTPError as e:
            if resp.status_code == 404:
                print(f"Warning: Screen job {job_id} does not exist.")
                return None
            else:
                raise
        return resp.json()

    def download_screen(self, job_id: str, out_path: str) -> Optional[str]:
        url = f"{self.base_url}/synglue/api/screen/download/?job_id={job_id}"
        resp = requests.get(url)
        try:
            resp.raise_for_status()
        except requests.HTTPError as e:
            if resp.status_code == 404:
                print(f"Warning: Screen job {job_id} does not exist or results are not available.")
                return None
            else:
                raise
        with open(out_path, "wb") as f:
            f.write(resp.content)
        return out_path

    def health_check(self) -> Dict:
        url = f"{self.base_url}/"
        resp = requests.get(url)
        resp.raise_for_status()
        return resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {"status": resp.text}
