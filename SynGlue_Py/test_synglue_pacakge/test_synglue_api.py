

from synglue import SynGlue

def test_health_check(client):
    try:
        health = client.health_check()
        print("Health check response:", health)
    except Exception as e:
        print("Health check failed:", e)

def test_submit_design(client):
    try:
        resp = client.submit_design(target="EGFR", threshold=80)
        print("Submit design response:", resp)
        return resp.get("job_id")
    except Exception as e:
        print("Submit design failed:", e)
        return None

def test_design_status(client, job_id):
    try:
        status = client.design_status(job_id=job_id)
        print("Design status response:", status)
        return status
    except Exception as e:
        print("Design status failed:", e)
        return None

def test_download_design(client, job_id):
    try:
        client.download_design(job_id=job_id)
        print("Design results downloaded to design_results.zip")
    except Exception as e:
        print("Download design failed:", e)

def test_submit_screen(client):
    try:
        molecules = [
            {"name": "Aspirin", "smiles": "CC(=O)Oc1ccccc1C(=O)O"},
            {"name": "Imatinib", "smiles": "CC1=CC=CC=C1"}
        ]
        resp = client.submit_screen(molecules=molecules)
        print("Submit screen response:", resp)
        return resp.get("job_id")
    except Exception as e:
        print("Submit screen failed:", e)
        return None

def test_submit_screen_csv(client):
    try:
        # You must have a valid CSV file at this path for this test to work
        resp = client.submit_screen_csv(csv_path="molecules.csv")
        print("Submit screen CSV response:", resp)
        return resp.get("job_id")
    except Exception as e:
        print("Submit screen CSV failed:", e)
        return None

def test_screen_status(client, job_id):
    try:
        status = client.screen_status(job_id=job_id)
        print("Screen status response:", status)
        return status
    except Exception as e:
        print("Screen status failed:", e)
        return None

def test_download_screen(client, job_id):
    try:
        client.download_screen(job_id=job_id, out_path="screen_results.csv")
        print("Screen results downloaded to screen_results.csv")
    except Exception as e:
        print("Download screen failed:", e)

if __name__ == "__main__":
    client = SynGlue()
    print("--- Health Check ---")
    test_health_check(client)

    print("\n--- Submit Design ---")
    design_job_id = test_submit_design(client)
    if design_job_id:
        print("\n--- Design Status ---")
        test_design_status(client, design_job_id)
        # Uncomment to download results when job is complete
        # test_download_design(client, design_job_id)

    print("\n--- Submit Screen ---")
    screen_job_id = test_submit_screen(client)
    if screen_job_id:
        print("\n--- Screen Status ---")
        test_screen_status(client, screen_job_id)
        # Uncomment to download results when job is complete
        # test_download_screen(client, screen_job_id)

    # Uncomment to test CSV upload (requires molecules.csv file)
    # print("\n--- Submit Screen CSV ---")
    # screen_csv_job_id = test_submit_screen_csv(client)
    # if screen_csv_job_id:
    #     print("\n--- Screen Status (CSV) ---")
    #     test_screen_status(client, screen_csv_job_id)
    #     # test_download_screen(client, screen_csv_job_id)



#  (Magnet) saveenas@iiitd-X299-UD4-Pro /storage/savi/saveenas/Projects/SynGlue_Py/synglue_package/pip$ 
# rm -rf build dist synglue.egg-info && python3 setup.py sdist bdist_wheel
# twine upload --verbose -r pypi dist/*
# docker build -t synglue-api .
# docker stop synglue
# docker rm synglue 
# docker exec -it synglue /bin/bash 
# docker logs -f synglue
# uvicorn app:app --host 0.0.0.0 --port 8000 --reload
# docker build --no-cache -t synglue-api .

"""docker run -d --gpus all -p 8000:8000 \
  -v /storage/savi/saveenas/Projects/SynGlue_Py/outputs:/app/outputs \
  -v /storage/savi/saveenas/Projects/SynGlue_Py/data:/app/data \
  -v /storage/savi/saveenas/Projects/SynGlue_Py/models:/app/models \
  -v /storage/savi/saveenas/Projects/SynGlue_Py/repos:/app/repos \
  --name synglue synglue-api
"""

"""ss -tulnp | grep 8000"""