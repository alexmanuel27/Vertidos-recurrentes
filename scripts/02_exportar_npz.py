"""Exporta los productos de ACOLITE a .npz, para que el analisis no necesite netCDF4.

SE EJECUTA EN TU macOS, dentro del entorno conda 'bahia' (el que tiene netCDF4).
A partir de aqui el resto del pipeline solo necesita numpy y scipy, y puedo correrlo yo
sin tocar la red.

    conda activate bahia
    python scripts/02_exportar_npz.py

Escribe un .npz por escena en datos/productos/ y un manifiesto con los nombres de
variable que ACOLITE uso realmente en cada una.
"""
import os, sys, json, argparse
import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "src"))
import acolite_io

CLAVES = ("turbidez_dogliotti", "turbidez_nechad", "spm", "swir", "verde", "nir")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--acolite", default="datos/acolite")
    ap.add_argument("--salida", default="datos/productos")
    a = ap.parse_args()
    os.makedirs(a.salida, exist_ok=True)

    ncs = sorted(f for f in os.listdir(a.acolite) if f.endswith(".nc"))
    if not ncs:
        sys.exit(f"No hay .nc en {a.acolite}")

    manifiesto = []
    for nombre in ncs:
        nc = os.path.join(a.acolite, nombre)
        disponibles = acolite_io.variables(nc)
        mapa = acolite_io.mapear(disponibles)
        claves = [c for c in CLAVES if c in mapa]
        if "turbidez_dogliotti" not in claves or "swir" not in claves:
            print(f"  SALTADA {nombre}: faltan productos. Hay: {sorted(disponibles)[:12]}")
            manifiesto.append({"escena": nombre, "ok": False, "variables": disponibles})
            continue
        d = acolite_io.leer(nc, tuple(claves))
        fecha = acolite_io.fecha_de(nc)
        destino = os.path.join(a.salida, nombre.replace(".nc", ".npz"))
        np.savez_compressed(destino, fecha=np.array(fecha.isoformat()),
                            **{c: d[c].astype(np.float32) for c in claves})
        forma = d[claves[0]].shape
        print(f"  OK {nombre[:44]}  {forma}  {fecha:%Y-%m-%d}  -> {os.path.basename(destino)}")
        manifiesto.append({"escena": nombre, "ok": True, "fecha": fecha.isoformat(),
                           "forma": list(forma), "mapa": d["_mapa"]})

    with open(os.path.join(a.salida, "manifiesto.json"), "w") as f:
        json.dump(manifiesto, f, indent=1)
    n_ok = sum(1 for m in manifiesto if m["ok"])
    print(f"\n{n_ok}/{len(ncs)} escenas exportadas a {a.salida}/")
    if n_ok < len(ncs):
        print("Manda el manifiesto: los nombres de variable dicen que falta pedirle a ACOLITE.")


if __name__ == "__main__":
    main()
