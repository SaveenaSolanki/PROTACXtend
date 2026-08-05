"""ABI fix: relink cuik_molmaker's expected rdkit libs to the installed rdkit.

chemprop 2.3.0's cuik_molmaker C++ extension was compiled against rdkit
2023.9.6's hash-named shared libraries. Newer rdkit uses different hashes.
For each hash-named lib cuik's binary NEEDs (via ldd), create a symlink to
the installed rdkit.libs file with the same base name.
"""
import glob
import re
import subprocess
from pathlib import Path

site = Path('/usr/local/lib/python3.11/site-packages')
rlib = site / 'rdkit.libs'
cuik = site / 'cuik_molmaker'
cpp = cuik / 'cuik_molmaker_cpp.cpython-311-x86_64-linux-gnu.so'
libdir = cuik / 'lib'

if not rlib.exists() or not cpp.exists():
    print('rdkit.libs or cuik_molmaker not found — skipping ABI fix')
    raise SystemExit(0)

libdir.mkdir(exist_ok=True)
ldd = subprocess.run(['ldd', str(cpp)], capture_output=True, text=True)
missing = [m.group(1) for m in re.finditer(r'(libRDKit\S+) => not found', ldd.stdout)]
n = 0
for name in missing:
    base = re.sub(r'-[a-f0-9]+\.so\.1$', '.so.1', name)
    targets = glob.glob(str(rlib / base)) + glob.glob(str(rlib / base) + '*')
    if targets:
        link = libdir / name
        if not link.exists():
            link.symlink_to(targets[0])
            n += 1
print(f'ABI symlinks created: {n} (missing={len(missing)})')
