"""Dice, escena por escena, hasta donde llego ACOLITE y por que.

    conda activate acolite
    python scripts/97_inspeccionar.py
"""
import os, re, sys, argparse
from collections import defaultdict
import numpy as np
from netCDF4 import Dataset


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--acolite", default="datos/acolite")
    a = ap.parse_args()

    ncs = sorted(f for f in os.listdir(a.acolite) if f.endswith(".nc"))
    por_escena = defaultdict(dict)
    for f in ncs:
        m = re.match(r"(.+)_(L1R|L2R|L2W)\.nc$", f)
        if m:
            por_escena[m.group(1)][m.group(2)] = os.path.join(a.acolite, f)

    print(f"{len(por_escena)} escenas\n")
    print(f"{'escena':42s} {'etapas':14s} {'rejilla':>12s} {'val%':>6s}  orbita")
    print("-" * 92)
    completas = 0
    for esc in sorted(por_escena):
        etapas = por_escena[esc]
        marca = "".join(e if e in etapas else "  ." for e in ("L1R", "L2R", "L2W"))
        ruta = etapas.get("L2W") or etapas.get("L2R") or etapas.get("L1R")
        rejilla, val = "?", float("nan")
        try:
            with Dataset(ruta) as d:
                ny = len(d.dimensions.get("y", []))
                nx = len(d.dimensions.get("x", []))
                rejilla = f"{ny}x{nx}"
                cand = [v for v in d.variables
                        if v.startswith(("rhot_6", "rhos_6", "TUR_", "rhot_5"))]
                if cand:
                    arr = np.array(d.variables[sorted(cand)[0]][:], dtype=float)
                    val = 100.0 * np.isfinite(arr).sum() / max(arr.size, 1)
        except Exception as e:
            rejilla = f"error: {e}"[:20]
        orb = "R054" if "_16_0" in esc else "R097" if "_16_1" in esc else "?"
        print(f"{esc[:42]:42s} {marca:14s} {rejilla:>12s} {val:6.1f}  {orb}")
        if "L2W" in etapas:
            completas += 1

    print(f"\n{completas}/{len(por_escena)} llegaron a L2W")

    print("\n--- variables de un L2W, si hay ---")
    algun = next((e["L2W"] for e in por_escena.values() if "L2W" in e), None)
    if algun:
        with Dataset(algun) as d:
            for v in sorted(d.variables):
                print("   ", v)
    else:
        print("  ninguna escena llego a L2W")


if __name__ == "__main__":
    main()
