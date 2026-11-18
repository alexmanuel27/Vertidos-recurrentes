"""QC de las escenas de 2026 con las reglas de la secc. 6 (las de 05_climatologia.py).

Mismo agua, distancia a costa y mascara de la bahia que el archivo 2016-2025 (climatologia.npz):
no se recalcula nada con 2026. Escribe <resultados>/escenas_qc_2026.csv y la lista de
aceptadas para 30_contraste_escenas.py --aceptadas.

    python scripts/36_qc_2026.py --productos datos/productos_2026_20m --resultados resultados
    VERTIDOS_PIXEL_M=10 python scripts/36_qc_2026.py --productos datos/productos_2026_10m --resultados resultados_10m
"""
import os, sys, csv, argparse
import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "src"))
import escenas, climatologia


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--productos", required=True); ap.add_argument("--resultados", default="resultados")
    a = ap.parse_args()
    cl = np.load(os.path.join(a.resultados, "climatologia.npz"))
    agua, bahia, dist = cl["agua"].astype(bool), cl["bahia"].astype(bool), cl["distancia_costa_m"]
    filas, acept = [], []
    for r in escenas.listar(a.productos):
        e = escenas.cargar(r)
        v, info = escenas.validez(e, agua, dist)
        ok, frac = escenas.escena_aceptada(v, agua & bahia, e["aot"])
        filas.append({"fecha": e["fecha"].isoformat(), "producto_l1c": e["l1c"], "estacion": climatologia.estacion_de(e["fecha"]),
                      "frac_valida_bahia": round(frac, 4), "aceptada": int(ok), "aot_550": round(e["aot"], 4),
                      "adyacencia_r2": round(info["r2"], 3), "buque_px": info["buque_px"]})
        if ok:
            acept.append(e["l1c"])
    base = os.path.join(a.resultados, "escenas_qc_2026")
    with open(base + ".csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(filas[0].keys())); w.writeheader(); w.writerows(filas)
    open(os.path.join(a.resultados, f"aceptadas_2026_{int(escenas.PIXEL_M)}m.txt"), "w").write("\n".join(acept) + "\n")
    sec = {s: sum(1 for f in filas if f["aceptada"] and f["estacion"] == s) for s in ("seca", "lluviosa")}
    print(f"{len(filas)} escenas revisadas, {len(acept)} aceptadas {sec}")


if __name__ == "__main__":
    main()
