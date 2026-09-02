from fastapi import FastAPI, HTTPException
import os
import pickle
import numpy as np


app = FastAPI()

DATA_DIR = "./data"  # Local path to your data files


def convert_values_for_json(obj):
    """
    Recursively convert non-JSON-compliant values (like NaN, inf) to None
    """
    if isinstance(obj, dict):
        return {k: convert_values_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_values_for_json(i) for i in obj]
    elif isinstance(obj, float) and (np.isnan(obj) or np.isinf(obj)):
        return None
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()  # Convert numpy arrays to lists
    else:
        return obj


@app.get("/data/{filename}")
async def get_data(filename: str):
    file_path = os.path.join(DATA_DIR, filename)
    if os.path.exists(file_path):
        try:
            # Open the pickle file in binary mode and load the data
            with open(file_path, 'rb') as file:
                data = pickle.load(file)
            # Convert non-JSON-compliant values to JSON-compliant ones
            data = convert_values_for_json(data)
            return {"filename": filename, "data": data}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error reading {filename}: {str(e)}")
    else:
        raise HTTPException(status_code=404, detail="File not found")

# @app.get("/data/{filename}")
# async def get_data(filename: str):
#     file_path = os.path.join(DATA_DIR, filename)
#     if os.path.exists(file_path):
#         with open(file_path, 'r') as file:
#             data = file.read()
#         return {"filename": filename, "data": data}
#     else:
#         raise HTTPException(status_code=404, detail="File not found")
