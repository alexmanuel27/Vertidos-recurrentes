"""Corre ACOLITE sobre los productos descargados, con los ajustes CONGELADOS.

SE EJECUTA EN TU macOS, en el entorno de ACOLITE.

    conda activate acolite
    python scripts/03_correr_acolite.py --acolite-src externo/acolite

Los ajustes salen de src/acolite_io.AJUSTES y no se tocan desde la linea de comandos:
la correccion atmosferica esta fijada por protocolo (seccion 3).
"""
import os, sys, glob, argparse

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "src"))
import acolite_io


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--crudo", default="datos/crudo")
    ap.add_argument("--salida", default="datos/acolite")
    ap.add_argument("--acolite-src", default="externo/acolite",
                    help="carpeta donde clonaste ACOLITE")
    a = ap.parse_args()
    os.makedirs(a.salida, exist_ok=True)

    entradas = sorted(glob.glob(os.path.join(a.crudo, "*.zip"))
                      + glob.glob(os.path.join(a.crudo, "*.SAFE")))
    if not entradas:
        sys.exit(f"No hay productos en {a.crudo}")

    limite = acolite_io.limite_bahia()
    print(f"{len(entradas)} productos | limite (S,O,N,E) = {limite}")
    print("ajustes congelados:", acolite_io.AJUSTES)

    fallos = []
    for i, e in enumerate(entradas, 1):
        nombre = os.path.basename(e)
        try:
            salidas = acolite_io.lanzar_acolite(e, a.salida, limite, a.acolite_src)
            print(f"[{i}/{len(entradas)}] {nombre[:46]} -> {len(salidas)} fichero(s) L2W")
        except Exception as exc:
            print(f"[{i}/{len(entradas)}] {nombre[:46]} FALLO: {exc}")
            fallos.append((nombre, str(exc)))

    print(f"\n{len(entradas)-len(fallos)}/{len(entradas)} procesados")
    if fallos:
        print("fallos:")
        for n, m in fallos:
            print(f"  {n}: {m[:120]}")


if __name__ == "__main__":
    main()
