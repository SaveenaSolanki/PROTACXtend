#!/usr/bin/env python3
"""
SynGlue Environment Diagnostic Tool (Precheck)
Validates all required data directories, files, model weights, config files,
and external repositories for the SynGlue API and batch running processes.
This script is fully compatible with legacy Python 3.5+ (using .format() instead of f-strings).
"""

import os
import sys

# Define color codes for pretty CLI outputs
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYP = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

def print_banner():
    print("\n{0}{1}======================================================================{2}".format(BOLD, CYP, RESET))
    print("{0}{1}            SynGlue Environment Precheck & Diagnostics Tool           {2}".format(BOLD, CYP, RESET))
    print("{0}{1}======================================================================{2}".format(BOLD, CYP, RESET))

def format_size(bytes_size):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024.0:
            return "{0:.2f} {1}".format(bytes_size, unit)
        bytes_size /= 1024.0
    return "{0:.2f} TB".format(bytes_size)

def run_precheck():
    print_banner()
    
    # 1. Resolve path structure (identical to module/app runtime logic)
    BASE_DIR = os.environ.get("SYNGLUE_BASE_DIR", "/app" if os.path.exists("/app/data") else "/storage/savi/saveenas/Projects/SynGlue_Py")
    DATA_DIR = os.environ.get("SYNGLUE_DATA_DIR", os.path.join(BASE_DIR, "data"))
    MODEL_DIR = os.environ.get("SYNGLUE_MODEL_DIR", os.path.join(BASE_DIR, "models"))
    OUTPUT_DIR = os.environ.get("SYNGLUE_OUTPUT_DIR", os.path.join(BASE_DIR, "outputs"))
    REPOS_DIR = os.environ.get("SYNGLUE_REPOS_DIR", os.path.join(BASE_DIR, "repos"))
    
    print("{0}Active Base Path Resolution:{1}".format(BOLD, RESET))
    print("  - base_dir   : {0}".format(BASE_DIR))
    print("  - data_dir   : {0}".format(DATA_DIR))
    print("  - model_dir  : {0}".format(MODEL_DIR))
    print("  - output_dir : {0}".format(OUTPUT_DIR))
    print("  - repos_dir  : {0}".format(REPOS_DIR))
    print("----------------------------------------------------------------------")
    
    warnings = 0
    errors = 0
    
    # 2. Check Directory Structures
    print("\n{0}[1/5] Checking Directory Existence & Write Permissions:{1}".format(BOLD, RESET))
    dirs_to_check = [
        ("Base workspace", BASE_DIR, True),
        ("Data directory", DATA_DIR, False),
        ("Models directory", MODEL_DIR, False),
        ("Outputs directory (Results)", OUTPUT_DIR, True),
        ("Repos directory", REPOS_DIR, False),
        ("REINVENT clone", os.path.join(REPOS_DIR, "reinvent"), False),
        ("GROVER clone", os.path.join(REPOS_DIR, "grover"), False)
    ]
    
    for label, path, write_required in dirs_to_check:
        if not os.path.exists(path):
            print("  [{0}MISSING{1}] {2}: {3}".format(RED, RESET, label, path))
            errors += 1
        else:
            write_status = ""
            if write_required:
                try:
                    test_file = os.path.join(path, ".precheck_write_test")
                    with open(test_file, "w") as f:
                        f.write("test")
                    os.remove(test_file)
                    write_status = " ({0}Writable{1})".format(GREEN, RESET)
                except Exception:
                    write_status = " ({0}Read-only / Permission Denied{1})".format(RED, RESET)
                    errors += 1
            print("  [{0}OK{1}] {2}: {3}{4}".format(GREEN, RESET, label, path, write_status))
            
    # 3. Check Configurations
    print("\n{0}[2/5] Checking Environment Config Files (Project Root):{1}".format(BOLD, RESET))
    configs_to_check = [
        ("FastAPI configuration / launcher", os.path.join(BASE_DIR, "app.py")),
        ("Magnet Conda environment specification", os.path.join(BASE_DIR, "Magnet.yml")),
        ("Reinvent Conda environment specification", os.path.join(BASE_DIR, "reinvent_clean.yml")),
        ("ADMET Conda environment specification", os.path.join(BASE_DIR, "admet.yml")),
        ("Docker Container build instruction", os.path.join(BASE_DIR, "Dockerfile"))
    ]
    
    for label, path in configs_to_check:
        if not os.path.exists(path):
            print("  [{0}MISSING{1}] {2}: {3}".format(RED, RESET, label, path))
            errors += 1
        elif os.path.getsize(path) == 0:
            print("  [{0}EMPTY{1}] {2}: {3}".format(RED, RESET, label, path))
            errors += 1
        else:
            print("  [{0}OK{1}] {2} ({3})".format(GREEN, RESET, label, format_size(os.path.getsize(path))))
            
    # 4. Check Data Files (Magnet DB / Screening and DB selection)
    print("\n{0}[3/5] Checking Essential Data Files (Magnet DB, Fragments, Targets):{1}".format(BOLD, RESET))
    data_to_check = [
        ("Magnet DB Trie (Lean)", os.path.join(DATA_DIR, "Lean_MagnetDB_Trie.pkl"), 100 * 1024 * 1024),
        ("Magnet DB Metadata Hash (Gene Fixed)", os.path.join(DATA_DIR, "Clean_Metadata_Hash_FINAL_GENE_FIXED.pkl"), 400 * 1024 * 1024),
        ("Targets list for MagnetDB", os.path.join(DATA_DIR, "Targets_for_magnetdb.csv"), 100 * 1024),
        ("E3 Ligase Database", os.path.join(DATA_DIR, "e3_ligand.csv"), 5 * 1024),
        ("Warhead Fragment Database (PKL)", os.path.join(DATA_DIR, "warhead_fragments.pkl"), 500 * 1024 * 1024),
        ("GROVER constant E3 vectors", os.path.join(DATA_DIR, "grover_e3.csv"), 1 * 1024 * 1024),
        ("GROVER constant Warhead vectors", os.path.join(DATA_DIR, "grover_warhead.csv"), 10 * 1024 * 1024)
    ]
    
    for label, path, expected_min_size in data_to_check:
        if not os.path.exists(path):
            print("  [{0}MISSING{1}] {2}: {3}".format(RED, RESET, label, path))
            errors += 1
        else:
            sz = os.path.getsize(path)
            if sz < expected_min_size:
                print("  [{0}WARNING{1}] {2}: {3} ({4} - smaller than expected {5})".format(YELLOW, RESET, label, path, format_size(sz), format_size(expected_min_size)))
                warnings += 1
            else:
                print("  [{0}OK{1}] {2} ({3})".format(GREEN, RESET, label, format_size(sz)))
                
    # 5. Check Model Weight Files
    print("\n{0}[4/5] Checking Pretrained Model Weight & Prior Files:{1}".format(BOLD, RESET))
    models_to_check = [
        ("GROVER Deep Learning Checkpoint", os.path.join(MODEL_DIR, "grover_fixed.pt"), 100 * 1024 * 1024),
        ("Linker Classifier Forest Model", os.path.join(MODEL_DIR, "linker_classifier.pkl"), 1 * 1024 * 1024),
        ("Link-INVENT Policy prior", os.path.join(MODEL_DIR, "linkinvent.prior"), 50 * 1024 * 1024),
        ("PROTAC Multitask Transformer weights", os.path.join(MODEL_DIR, "multitask_transformer.pt"), 10 * 1024 * 1024),
        ("Random Forest DC50 predictor", os.path.join(MODEL_DIR, "rf_dc50.joblib"), 10 * 1024 * 1024),
        ("Random Forest DMax predictor", os.path.join(MODEL_DIR, "rf_dmax.joblib"), 10 * 1024 * 1024)
    ]
    
    for label, path, expected_min_size in models_to_check:
        if not os.path.exists(path):
            print("  [{0}MISSING{1}] {2}: {3}".format(RED, RESET, label, path))
            errors += 1
        else:
            sz = os.path.getsize(path)
            if sz < expected_min_size:
                print("  [{0}WARNING{1}] {2}: {3} ({4} - smaller than expected {5})".format(YELLOW, RESET, label, path, format_size(sz), format_size(expected_min_size)))
                warnings += 1
            else:
                print("  [{0}OK{1}] {2} ({3})".format(GREEN, RESET, label, format_size(sz)))
                
    # 6. Check Environment & Code Dependencies
    print("\n{0}[5/5] Checking Python/Conda Execution Environment & Symlinks:{1}".format(BOLD, RESET))
    
    # Check if run_link_invent and grover scripts can be imported or resolved
    if sys.version_info < (3, 6):
        print("  [{0}WARNING{1}] Host Python is older than 3.6 ({2}.{3}.{4}).".format(
            YELLOW, RESET, sys.version_info.major, sys.version_info.minor, sys.version_info.micro))
        print("  Skipping module import checks on Host (they will run successfully inside the container).")
        warnings += 1
    else:
        try:
            sys.path.append(BASE_DIR)
            import savi_module_4 as m4
            print("  [{0}OK{1}] Internal module 'savi_module_4' is importable.".format(GREEN, RESET))
        except Exception as e:
            print("  [{0}ERROR{1}] Cannot import 'savi_module_4': {2}".format(RED, RESET, str(e)))
            errors += 1
            
        try:
            import app
            print("  [{0}OK{1}] FastAPI router 'app' is importable.".format(GREEN, RESET))
        except Exception as e:
            print("  [{0}WARNING{1}] Cannot import 'app.py' directly on Host (probably missing Conda deps, expected if outside Magnet): {2}".format(YELLOW, RESET, str(e)))
            warnings += 1

    # Diagnostics Summary
    print("\n{0}{1}======================================================================{2}".format(BOLD, CYP, RESET))
    print("{0}Diagnostic Report Summary:{1}".format(BOLD, RESET))
    print("  - Total Errors   : {0}{1}{2}".format(RED, errors, RESET))
    print("  - Total Warnings : {0}{1}{2}".format(YELLOW, warnings, RESET))
    
    if errors > 0:
        print("\n{0}{1}❌ Action Required: One or more critical files/directories are missing.{2}".format(BOLD, RED, RESET))
        print("Please ensure all required databases and model weights are placed inside '{0}' and '{1}' respectively.".format(DATA_DIR, MODEL_DIR))
        print("You can also use environment variables to explicitly point to their locations, e.g.:")
        print("  export SYNGLUE_DATA_DIR=/path/to/my/data")
        sys.exit(1)
    else:
        print("\n{0}{1}✅ All System Diagnostics Passed! SynGlue is ready for deployment/execution.{2}".format(BOLD, GREEN, RESET))
        sys.exit(0)

if __name__ == "__main__":
    run_precheck()
