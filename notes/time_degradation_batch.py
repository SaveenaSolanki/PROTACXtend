"""Time the predict_degradation batch path stage by stage (root-cause driver).

Runs in the protacpilot env from the repo root. Prints wall time per stage so
we can see where the degradation node burns minutes / spins CPU.
"""
from __future__ import annotations

import time

import torch

from rdkit import Chem

BASE = "Cc1ncsc1-c1ccc(CNC(=O)[C@@H]2C[C@@H](O)CN2C(=O)[C@@H](NC(=O)COCCCCCCCCCOCC(=O)Nc2ccc(C(=O)Nc3ccc(F)cc3N)cc2)C(C)(C)C)cc1"


def make_batch(n: int) -> list[str]:
    """n candidate SMILES: base PROTAC + alkyl-chain length variants."""
    smiles = [BASE]
    for ln in range(2, 12):
        linker = "O" + "C" * ln + "O"
        variant = (f"Cc1ncsc1-c1ccc(CNC(=O)[C@@H]2C[C@@H](O)CN2C(=O)[C@@H]"
                   f"(NC(=O)C{linker}CC(=O)Nc2ccc(C(=O)Nc3ccc(F)cc3N)cc2)C(C)(C)C)cc1")
        smiles.append(variant)
    out = []
    i = 0
    while len(out) < n:
        out.append(smiles[i % len(smiles)])
        i += 1
    return out


def main() -> None:
    n = int(__import__("sys").argv[1]) if len(__import__("sys").argv) > 1 else 150
    smiles = make_batch(n)
    valid = [s for s in smiles if Chem.MolFromSmiles(s) is not None]
    print(f"n={n} valid={len(valid)} torch={torch.__version__} cuda={torch.cuda.is_available()}", flush=True)

    t0 = time.time()

    # Stage 1: TACK single-call warmup (model load timing)
    from synglue_agent.tools.tack_degradation import predict_tack_degradation
    t1 = time.time()
    r = predict_tack_degradation(BASE, e3="CRBN", cell="MM1.S", poi="BRD4")
    print(f"[tack warmup      ] {time.time()-t1:8.1f}s result={'ok' if r else 'None'}", flush=True)

    # Stage 2: chemprop ensemble + conformal + AD (subprocess)
    from synglue_agent.tools.uncertainty_aware_prediction import predict_with_uncertainty
    t1 = time.time()
    unc = predict_with_uncertainty(valid, use_conformal=True)
    print(f"[chemprop ensemble] {time.time()-t1:8.1f}s rows={len(unc)} "
          f"ok={sum(1 for u in unc if u.get('dc50_nM') is not None)}", flush=True)

    # Stage 3: multitarget chemprop subprocess
    from synglue_agent.tools.degradation_endpoint import _run_multitarget
    t1 = time.time()
    mt = _run_multitarget(valid)
    print(f"[chemprop multi   ] {time.time()-t1:8.1f}s ok={mt.get('ok')} rows={len(mt.get('rows') or [])}", flush=True)

    # Stage 4: TACK loop over all candidates (as in predict_degradation_batch)
    from synglue_agent.tools.degradation_endpoint import _tack_primary
    t1 = time.time()
    n_tack = 0
    for smi in valid:
        if _tack_primary(smi, "CRBN", "MM1.S", "BRD4"):
            n_tack += 1
    print(f"[tack loop x{len(valid)}] {time.time()-t1:8.1f}s success={n_tack}", flush=True)

    print(f"TOTAL {time.time()-t0:.1f}s", flush=True)


if __name__ == "__main__":
    main()