"""Descarga los L1C del subconjunto RAdCor (peticion 2, bloque C): 10 escenas secas de
2016-2025 fijadas en resultados/radcor_subconjunto_20m.json.

Credenciales SOLO por variables de entorno CDSE_USUARIO / CDSE_CLAVE.
Se niega a bajar nada con fecha de 2026 (peticion 2: nada de 2026 hasta confirmar el commit).

    python scripts/33_descarga_subconjunto.py
"""
import os, sys, json, argparse, time
from pathlib import Path

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import importlib.util
spec = importlib.util.spec_from_file_location("cdse", os.path.join(AQUI, "00_descarga_cdse.py"))
cdse = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cdse)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lista", default="resultados/radcor_subconjunto_20m.json")
    ap.add_argument("--destino", default="datos/crudo_radcor")
    a = ap.parse_args()
    nombres = [e["producto_l1c"].replace(".SAFE", "")
               for e in json.load(open(a.lista))["escenas"]]
    assert all(n.split("_")[2][:4] <= "2025" for n in nombres), "hay una escena de 2026"
    Path(a.destino).mkdir(parents=True, exist_ok=True)

    prods = {p["Name"].replace(".SAFE", ""): p for p in cdse.catalogo()}
    faltan = [n for n in nombres if n not in prods]
    print(f"{len(nombres)} pedidos; en el catalogo: {len(nombres)-len(faltan)}")
    for n in faltan:
        print("  NO ESTA EN EL CATALOGO:", n)
    tk, t_tk = cdse.token(), time.time()
    ok = 0
    for i, n in enumerate(nombres, 1):
        if n not in prods:
            continue
        if time.time() - t_tk > 1200:
            tk, t_tk = cdse.token(), time.time()
        t0 = time.time()
        ruta, estado = cdse.descargar(prods[n]["Id"], prods[n]["Name"].replace(".SAFE", ""),
                                      a.destino, tk)
        print(f"[{i}/{len(nombres)}] {n[:50]} {estado} ({time.time()-t0:.0f} s)", flush=True)
        ok += ruta is not None
    print(f"\n{ok}/{len(nombres)} disponibles en {a.destino}")


if __name__ == "__main__":
    main()
