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

DATA_SERVER_URL = "http://127.0.0.1:8000/data"

class Mapper:
    
    def __init__(self):
        self.flag = False

    def is_valid_smiles(smiles):
        try:
            mol = Chem.MolFromSmiles(smiles)
            if mol is not None:
                # print(f"Valid SMILES: {smiles}")
                return True
            else:
                # print(f"Invalid SMILES: {smiles} - Molecule is None")
                return False
        except Exception as e:
            # print(f"Error processing SMILES: {smiles} - {e}")
            return False

    def convert_canonical(user_query_smile_list):
        canonical_smiles_list = []
        for smiles in user_query_smile_list:
            molecule = Chem.MolFromSmiles(smiles)
            if molecule is not None:
                # checked whether the smile is a valid molecule
                canonical_smiles = Chem.MolToSmiles(molecule)
                canonical_smiles_list.append(canonical_smiles)

        # Create a list of unique IDs
        query_id_list = [f"ID_{i+1}" for i in range(len(canonical_smiles_list))]

        # Create a DataFrame with the canonical SMILES
        query_canonical_df = pd.DataFrame({
            'queryID': query_id_list,
            'Canonical_SMILES': canonical_smiles_list
            })
        # # Specify the path to save the CSV file
        # csv_file_path = "query_canonical_smiles.csv"
        # # Save the DataFrame to a CSV file
        # query_df.to_csv(csv_file_path, index=False)
        
        return query_canonical_df
    
    # fragmentation
    # ALSO STORE THE NON FRAGMENTABLE MOLECULES IN SEPARATE DICTIONARY
    def frag(query_canonical_df):
        # query_df = pd.read_pickle(query_db_pickle)

        # Process 10 molecules for query_df
        # query_df = query_df.head(10)

        query_frags = [{
            'queryID': row['queryID'],
            'querySMILE': row['Canonical_SMILES'],
            'queryFragID': row['queryID'] + '_Frag_' + str(j+1),
            'queryFragSMILE': Chem.MolToSmiles(data.mol)
        } for i, row in query_canonical_df.iterrows() for j, (fragment, data) in enumerate(Recap.RecapDecompose(Chem.MolFromSmiles(row['Canonical_SMILES'])).children.items())]

        query_frag_df = pd.DataFrame(query_frags, columns=['queryID', 'querySMILE', 'queryFragID', 'queryFragSMILE'])

        # Save the query results DataFrame to a pickle file
        # query_results_df.to_pickle('Query_Fragments.pkl')
        
        # create a dictionary mapping query smile to its list of fragments - {}

        # Save the query fragment dictionary to a pickle file
        # with open('Query_Fragment_Dictionary.pkl', 'wb') as f:
        #     pickle.dump(query_fragment_dict, f)
        
        return query_frag_df

    def preprocessing(query_frag_df):
        # Load the query dataframe from pickle file
        # query_frag_df = pd.read_pickle('Query_Fragments.pkl')

        # Step 1: Remove duplicate rows based on [queryID, queryFragSMILE], keeping the first occurrence
        # uniq_query_frag_df = query_frag_df[query_frag_df['queryFragSMILE'].apply(lambda x: x.count('*') <= 1)]
        uniq_query_frag_df = query_frag_df.drop_duplicates(subset=['queryID', 'queryFragSMILE'], keep='first')

        # write to csv
        # csv_file_path = 'Query_Unique_Fragments.csv'
        # uniq_query_frag_df.to_csv(csv_file_path, index=False)

        # Step 2: Remove rows where 'queryFragSMILE' contains more than one asterisk (*)
        uniq_query_terminals_df = uniq_query_frag_df[uniq_query_frag_df['queryFragSMILE'].apply(lambda x: x.count('*') <= 1)]
        
        # Create a dictionary of fragments with SMILES, source ID, and compound name for the query results
        query_fragment_dict = {
            row['queryFragID']: {
                'fragSMILE': row['queryFragSMILE'],
                'sourceQuerySMILE': row['querySMILE'],
                'sourceQuery_ID': row['queryID']
            } for _, row in uniq_query_terminals_df.iterrows()
        }
        
        # write to csv
        # csv_file_path2 = 'Query_Unique_Terminals.csv'
        # uniq_query_terminals_df.to_csv(csv_file_path2, index=False)
        
        return uniq_query_terminals_df, query_fragment_dict

    def query_magnet_mapping(query_fragment_dict, trie ):
        # Initialize the output CSV file and write the header row
        database = open("Query_Magnet_Mapping.csv", mode='w', newline='')  # query_magnet_mapping
        writer = csv.writer(database)
        writer.writerow(["query_frag_smile", "matched_magnet_frag", "query_frag_id", "Magnet_ID", "query_smile", "query_smile_id"])  # matched_magnet_frag is that frag which was mapped from trie
        database.close()
            
        for fragID in query_fragment_dict.keys():
            # Extract information from the dictionary
            frag_smile = query_fragment_dict[fragID]['fragSMILE']
            query_smile = query_fragment_dict[fragID]['sourceQuerySMILE']
            query_id = query_fragment_dict[fragID]['sourceQuery_ID']
            
            # Check if the trie starts with the reversed fragment string
            if trie.starts_with((frag_smile + "$")[::-1]):
                # Store the fragments in the CSV file
                trie.store_all_fragments((frag_smile + "$")[::-1], query_smile, fragID, query_id, "Query_Magnet_Mapping.csv") # query_magnet_mapping
        
        query_magnet_mapping_df = pd.read_csv('Query_Magnet_Mapping.csv')
        return query_magnet_mapping_df

    def get_tanimoto_similarity_r(query_mol, target_mol):
        fp1 = Chem.RDKFingerprint(query_mol)
        fp2 = Chem.RDKFingerprint(target_mol)
        tanimoto_similarity = DataStructs.TanimotoSimilarity(fp1, fp2)
        return tanimoto_similarity

    def get_tanimoto_similarity_e(query_mol, target_mol, radius=3, nbits=1048):
        query_fp = AllChem.GetMorganFingerprintAsBitVect(query_mol, radius, nBits=nbits)
        target_fp = AllChem.GetMorganFingerprintAsBitVect(target_mol, radius, nBits=nbits)
        tanimoto_similarity = DataStructs.TanimotoSimilarity(query_fp, target_fp)
        return tanimoto_similarity

    def get_mcs_similarity(query_mol, target_mol):
        fp1 = Chem.RDKFingerprint(query_mol)
        fp2 = Chem.RDKFingerprint(target_mol)
        tanimoto_similarity = DataStructs.TanimotoSimilarity(fp1, fp2)
        return tanimoto_similarity

    def get_mcs_smile(query_mol, target_mol):
        mcs = rdFMCS.FindMCS([query_mol, target_mol])
        mcs_smile = Chem.MolToSmiles(Chem.MolFromSmarts(mcs.smartsString), isomericSmiles=True)
        return mcs_smile

    def get_query_terminal_atoms(query_mol):
        query_terminal_atoms = []
        # ans = self.get_mcs_smile(query_mol, query_mol)
        for atom in query_mol.GetAtoms():
            if atom.GetDegree() == 1:
                query_terminal_atoms.append(atom.GetIdx())
        return query_terminal_atoms

    def get_target_terminal_atoms(target_mol):
        target_terminal_atoms = []
        for atom in target_mol.GetAtoms():
            if atom.GetDegree() == 1:
                target_terminal_atoms.append(atom.GetIdx())
        return target_terminal_atoms

    def get_mcs_terminal_atoms(mcs_result):
        mcs_mol = Chem.MolFromSmarts(mcs_result.smartsString)
        terminal_atoms = []
        for atom in mcs_mol.GetAtoms():
            if atom.GetDegree() == 1:
                terminal_atoms.append(atom.GetIdx())
        return terminal_atoms

    # def query_atom_count(query_mol):
    #     return query_mol.GetNumAtoms()


    # def target_atom_count(target_mol):
    #     return target_mol.GetNumAtoms()

    # def get_atom_count(mol):
    #     return mol.GetNumAtoms()

    def get_atom_count(mol):
        return len(mol.GetAtoms())

    def get_atom_count_from_smiles(smile):
        mol = Chem.MolFromSmiles(smile)
        ans = self.get_atom_count(mol)
        return ans

    def get_mcs_atom_count(query_mol, target_mol):
        # Find MCS of query and target molecules
        mcs = rdFMCS.FindMCS([query_mol, target_mol])
        mcs_smiles = Chem.MolFromSmarts(mcs.smartsString)
        return mcs_smiles.GetNumAtoms()


    def get_mcs_sm_score(query_mol, target_mol):
        mcs = rdFMCS.FindMCS([query_mol, target_mol])
        mcs_atom_count = self.get_atom_count(Chem.MolFromSmarts(mcs.smartsString))
        target_atom_count = self.get_atom_count(target_mol)
        mcs_sm_score = mcs_atom_count / target_atom_count
        return mcs_sm_score

    def scoring(query_magnet_mapping_df):
        # Initialize an empty list to store the rows
        data = []
            
        # Loop over the target molecules using tqdm to display a progress bar
        for index, row in tqdm(query_magnet_mapping_df.iterrows(), total=len(query_magnet_mapping_df)):
            target_mol = Chem.MolFromSmiles(row['matched_magnet_frag']) # Magnet Fragment smile
            query_mol = Chem.MolFromSmiles(row['query_frag_smile']) # Query Fragment smile
            # added column of query frag ID
            query_frag_ID = row['query_frag_id']
            query_id = row['query_smile_id'] # query smile ID
            query_smile = row['query_smile']

            # Check for invalid molecules
            if target_mol is None or query_mol is None:
                # print(f"Invalid SMILES for row {index + 1}. Skipping.")
                continue

            # Find the MCS between the target and query molecules
            mcs_result = rdFMCS.FindMCS([query_mol, target_mol])
            mcs_mol = Chem.MolFromSmarts(mcs_result.smartsString)
            mcs_smiles = Chem.MolToSmiles(mcs_mol)

            # Calculate Tanimoto similarity and other metrics
            tanimoto_similarity_E = self.get_tanimoto_similarity_e(query_mol, target_mol)
            tanimoto_similarity_R = self.get_tanimoto_similarity_r(query_mol, target_mol)
            MCS_SM_Score = self.get_mcs_sm_score(query_mol, target_mol)

            # Exclude combinations with MCS_SM_Score less than 0.1
            if MCS_SM_Score >= 0.1:
                # Write the results to the CSV file
                # Append the row to the data list
                data.append([
                    row['Magnet_ID'],
                    row['matched_magnet_frag'],
                    query_id,
                    query_smile,
                    query_frag_ID,
                    row['query_frag_smile'],
                    mcs_smiles,
                    tanimoto_similarity_E,
                    tanimoto_similarity_R,
                    MCS_SM_Score
                ])
        
        # Convert the data list to a DataFrame
        query_magnet_scoring_df = pd.DataFrame(data, columns=[
            "Magnet_ID", "magnet_frag_smile", "query_ID", "query_smile", "query_frag_ID", "query_frag_smile",
            "MCS_Smiles", "Tanimoto_Similiarity_E", "Tanimoto_Similiarity_R", "MCS_SM_Score"
        ])
        return query_magnet_scoring_df

    def percentage_calculator(frag_atom_count, smile_atom_count):
        return ((frag_atom_count / smile_atom_count)*100)

    def percentage_binder(query_magnet_scoring_df, final_magnetDB_dict, direct_binders_dict):
        #input = pd.read_csv("query_magnet_scoring_results.csv", sep=',', skipinitialspace=True) # query magnet mapping
        
        # cols in query_magnet_scoring_results
        # "Magnet_ID", "magnet_frag_smile", "query_ID", 
        # "query_frag_ID", "query_frag_smile",
        # "MCS_Smiles", "Tanimoto_Similiarity_E", 
        # "Tanimoto_Similiarity_R", "MCS_SM_Score"
        #-----------------
        # query_magnet_source_db_mapping.csv
        with open('query_magnet_source_db_mapping.csv', 'w', newline='') as csvfile:

            # Create a CSV writer object
            writer = csv.writer(csvfile)

            # Write the header row to the CSV file
            writer.writerow(["Database_ID", "original_ligand_smile", "Target_ID", "query_frag_ID", "query_frag_smile", "matched_magnet_frag", "Magnet_ID", "query_smile", "query_ID", "query_smile_atom_count", "Query_Percentage", "Target_Percentage", "MCS_Smiles", "Tanimoto_Similiarity_E", "Tanimoto_Similiarity_R", "MCS_SM_Score"])
            # database ID is the source database ID from where the fragment was found originally too
            start = time.time()
            
            absent_source_ids = []
            # Loop over the target molecules using tqdm to display a progress bar
            for index, row in tqdm(query_magnet_scoring_df.iterrows(), total=len(query_magnet_scoring_df)):
                # print(row['Magnet_ID'])
                # print(Final_MagnetDB_dict[row['Magnet_ID']])
                sourceIDs_list = final_magnetDB_dict[row['Magnet_ID']]['Source datbase IDs']
                # print('hi')
                # print(sourceIDs_list)
                query_smile_atom_count = self.get_atom_count_from_smiles(row['query_smile'])
                query_frag_atom_count = self.get_atom_count_from_smiles(row['query_frag_smile'])
                target_frag_atom_count = self.get_atom_count_from_smiles(row['matched_magnet_frag'])
                # print(target_frag_atom_count)
                for sourceID in sourceIDs_list:
                    
                    if sourceID not in direct_binders_dict:
                        absent_source_ids.append(sourceID)
                        # print(sourceID, ' not present in Direct Binders')
                        # print('hi')
                        continue
                    else:
                        # print(direct_binders_dict[sourceID]['SMILE'])
                        target_protein_id = direct_binders_dict[sourceID]['Target ID']
                        original_smile = direct_binders_dict[sourceID]['SMILE']
                        target_smile_atom_count = self.get_atom_count_from_smiles(original_smile)
                        query_percentage = (query_frag_atom_count / query_smile_atom_count)*100
                        target_percentage = (target_frag_atom_count / target_smile_atom_count)*100

                        writer.writerow([sourceID, original_smile, target_protein_id, row['query_frag_id'], row['query_frag_smile'], row['matched_magnet_frag'], row['Magnet_ID'], row['query_smile'], row['query_smile_id'], query_smile_atom_count, query_percentage, target_percentage, row["MCS_Smiles"], row["Tanimoto_Similiarity_E"], row["Tanimoto_Similiarity_R"], row["MCS_SM_Score"]])

