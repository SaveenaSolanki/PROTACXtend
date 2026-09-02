#!/usr/bin/env python3
"""P4ward + long-job worker: consumes the job queue and dispatches."""
import sys, logging
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
logging.basicConfig(level=logging.INFO)

from synglue_agent.queue.job_queue import JobQueue, run_worker


def handler(job):
    jt = job["job_type"]
    p = job["payload"]
    if jt == "retrosynthesis":
        from synglue_agent.tools.retrosynthesis import assess_retrosynthesis
        r = assess_retrosynthesis(p.get("smiles", ""), candidate_id=p.get("candidate_id", ""),
                                  use_aizynth=True)
        return r.model_dump(), None
    if jt == "degradation":
        from synglue_agent.tools.degradation_endpoint import predict_degradation_endpoint
        r = predict_degradation_endpoint(p.get("smiles", ""), candidate_id=p.get("candidate_id", ""),
                                         cell_line=p.get("cell_line", "default"),
                                         e3_ligase=p.get("e3_ligase", "CRBN"))
        return r.model_dump(), None
    if jt == "p4ward_run":
        return None, {"reason": "p4ward requires human approval + long compute",
                      "payload": p}
    return None, {"reason": f"unknown job type {jt}", "payload": p}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", type=int, default=0, help="process N jobs then exit (0=forever)")
    args = ap.parse_args()
    run_worker(handler, poll_interval=1.0, max_jobs=args.once or None)
