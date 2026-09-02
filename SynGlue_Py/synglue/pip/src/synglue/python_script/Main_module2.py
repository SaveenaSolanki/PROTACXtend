import requests
from io import StringIO
import pandas as pd
import time
import matplotlib.pyplot as plt
import seaborn as sns
import csv
from tqdm import tqdm
import pickle
import multiprocessing
from rdkit import Chem
from rdkit import DataStructs
from rdkit.Chem import AllChem
from rdkit.Chem import rdFMCS
from rdkit.Chem.Draw import IPythonConsole
from rdkit.Chem import Draw
from rdkit.Chem import Recap
from rdkit.Chem import rdDepictor
from IPython.display import display

from Trie import Trie, TrieNode
from local_python_notebook.Mapper import Mapper

DATA_SERVER_URL = "http://127.0.0.1:8000/data" 
# keep this function in main.py file, along with main function
def fetch_data_from_server_b(filename):
    url = f"{DATA_SERVER_URL}/{filename}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()["data"]
        return data  # No need to convert, as the data is already a dictionary
    else:
        raise Exception(f"Failed to fetch {filename}: {response.status_code}")

def main(input_csv):
    
    # input_csv - is a one column csv file, where 1st col name is 'SMILES'
    # this column is converted to a list 
    df = pd.read_csv(input_csv)
    smiles_list = df['SMILES'].tolist()
    
    # create object of module 2 mapper
    query_mapper = Mapper()
    
    # converting to canonincal smile
    query_canonical_df = query_mapper.convert_canonical(smiles_list)
    
    # fragmentation
    query_frag_df = query_mapper.frag(query_canonical_df)
    
    # removing duplicate fragments and filtering valid terminals
    uniq_query_terminals_df, query_fragment_dict = query_mapper.preprocessing(query_frag_df)
    
    # loading dataset
    # Fetch the data files from the local FastAPI server
    # load TRIE (keep trie class in different file.py, import trie class from there)
    trie = Trie()
    trie = fetch_data_from_server_b("trie.pkl") # will get error on this
    final_magnetDB_dict = fetch_data_from_server_b("Final_MagnetDB_Dictionary.pkl")
    # dataset=pd.read_csv(csv_file_path)
    # hash_map = {}
    frag_magnetID_hashmap = fetch_data_from_server_b("frag_magnetID_hashmap.pkl")
    
    # creating query magnet mapping
    query_magnet_mapping_df = query_mapper.query_magnet_mapping(query_fragment_dict, trie )
    
    # scoring
    query_magnet_scoring_df = query_mapper.scoring(query_magnet_mapping_df)
    
    # load direct_binders_dict
    direct_binders_dict = fetch_data_from_server_b("Direct_Binders_Dictionary.pkl")
    
    # direct binders - target mapping
    # gives the final ouptut csv with all smimilarity scores, targets, ligand names, percenatges, query frags, magnet id, database/source ID. 
    query_mapper.percentage_binder(query_magnet_scoring_df, final_magnetDB_dict, direct_binders_dict)
    
    

    
