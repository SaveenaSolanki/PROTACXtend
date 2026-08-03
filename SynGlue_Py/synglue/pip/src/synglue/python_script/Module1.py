import pandas as pd

# Define the file path
file_path = "/storage/savi/saveenas/Projects/Magnet/Dataset/Species_Specific_Magnet_DB/Direct_Binders_Magnet_DB.pkl"

class MagnetDBBrowser:
    def __init__(self, file_path):
        self.file_path = file_path
        self.database = pd.read_pickle(file_path)
        self.organism_list = self.list_all_organisms()

    def list_all_organisms(self):
        """List all unique organisms in the database."""
        return self.database['Organism'].unique()

    def get_organism_compounds(self, organism_name):
        """Get all unique compounds for a specific organism."""
        compounds = self.database[self.database['Organism'] == organism_name]['Ligand Name'].unique()
        return compounds

    def get_organism_targets(self, organism_name):
        """Get all unique targets for a specific organism."""
        targets = self.database[self.database['Organism'] == organism_name]['Target'].unique()
        return targets

    def get_unique_database_ids(self, organism_name):
        """Get all unique database IDs for a specific organism."""
        return self.database[self.database['Organism'] == organism_name]['Database ID'].unique()

    def get_unique_target_ids(self, organism_name):
        """Get all unique target IDs for a specific organism."""
        return self.database[self.database['Organism'] == organism_name]['Target ID'].unique()

    def get_targets_for_ligand(self, ligand_name):
        """Get all targets associated with a specific ligand."""
        targets = self.database[self.database['Ligand Name'] == ligand_name]['Target'].unique()
        return targets

    def get_ligands_for_target(self, target_name):
        """Get all ligands associated with a specific target."""
        ligands = self.database[self.database['Target'] == target_name]['Ligand Name'].unique()
        return ligands

    def list_compounds_and_targets_by_organism(self, organism_name):
        """List all compounds and their associated targets for a specific organism."""
        organism_data = self.database[self.database['Organism'] == organism_name]
        compounds_targets = organism_data[['Ligand Name', 'Target']].drop_duplicates()
        return compounds_targets

    def workflow(self):
        """Automated workflow for selecting an organism and displaying related data."""
        print("Select an organism from the list below:")
        for i, organism in enumerate(self.organism_list):
            print(f"{i + 1}. {organism}")

        while True:
            choice = input("Enter the number or name corresponding to the organism: ").strip()
            
            if choice.isdigit():
                choice = int(choice)
                if 1 <= choice <= len(self.organism_list):
                    selected_organism = self.organism_list[choice - 1]
                    break
                else:
                    print("Please enter a valid number corresponding to an organism.")
            else:
                if choice in self.organism_list:
                    selected_organism = choice
                    break
                else:
                    print("Invalid input. Please enter a valid organism number or name.")
        
        print(f"\nYou selected: {selected_organism}\n")

        unique_compounds = self.get_organism_compounds(selected_organism)
        unique_targets = self.get_organism_targets(selected_organism)
        unique_database_ids = self.get_unique_database_ids(selected_organism)
        unique_target_ids = self.get_unique_target_ids(selected_organism)
        

        print(f"Total unique compounds for {selected_organism}: {len(unique_database_ids)}")
        print(f"Total unique targets for {selected_organism}: {len(unique_target_ids)}")

        organism_data = self.list_compounds_and_targets_by_organism(selected_organism)
        print(f"\nDisplaying first 20 entries for {selected_organism}:")
        print(organism_data.head(20))

# Example Usage
if __name__ == "__main__":
    browser = MagnetDBBrowser(file_path)
    browser.workflow()
