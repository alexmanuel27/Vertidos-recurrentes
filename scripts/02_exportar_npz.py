"""Exporta los productos de ACOLITE a .npz, para que el analisis no necesite netCDF4.

SE EJECUTA EN TU macOS, en un entorno con netCDF4 ('acolite' o 'bahia').
A partir de aqui el resto del pipeline solo necesita numpy y scipy.

    conda activate acolite
    python scripts/02_exportar_npz.py

Escribe un .npz por escena en datos/productos/ y un manifiesto con los nombres de
variable que ACOLITE uso realmente en cada una. La logica de exportacion vive en
src/exportar.py y es la misma que usa el bucle por tandas (04_archivo_por_tandas.py).
"""
import os, sys, json, argparse

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "src"))
import exportar


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--acolite", default="datos/acolite")
    ap.add_argument("--salida", default="datos/productos")
    a = ap.parse_args()
    os.makedirs(a.salida, exist_ok=True)

    ncs = sorted(f for f in os.listdir(a.acolite) if f.endswith("_L2W.nc"))
    if not ncs:
        sys.exit(f"No hay *_L2W.nc en {a.acolite}. Si solo hay L1R, ACOLITE no\n"
                 f"llego a producto de agua: corre scripts/97_inspeccionar.py.")

    manifiesto = []
    for nombre in ncs:
        m = exportar.exportar(os.path.join(a.acolite, nombre), a.salida)
        if m["ok"]:
            print(f"  OK {nombre[:44]}  {tuple(m['forma'])}  {m['fecha'][:10]}  "
                  f"AOT550={m['aot_550']:.3f}  -> {m['npz']}")
        else:
            print(f"  SALTADA {nombre}: {m['motivo']}. Hay: {sorted(m['variables'])[:12]}")
        manifiesto.append(m)

    with open(os.path.join(a.salida, "manifiesto.json"), "w") as f:
        json.dump(manifiesto, f, indent=1)
    n_ok = sum(1 for m in manifiesto if m["ok"])
    print(f"\n{n_ok}/{len(ncs)} escenas exportadas a {a.salida}/")
    if n_ok < len(ncs):
        print("Manda el manifiesto: los nombres de variable dicen que falta pedirle a ACOLITE.")


if __name__ == "__main__":
    main()
