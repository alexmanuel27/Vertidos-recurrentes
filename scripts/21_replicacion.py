"""Replicacion de los focos de turbidez cronica en mitades independientes (EXPLORATORIO).

    python scripts/21_replicacion.py                                        # 20 m
    VERTIDOS_PIXEL_M=10 python scripts/21_replicacion.py --productos datos/productos_10m \
        --resultados resultados_10m

Definido en la fila del 17/11/2026 de la secc. 14, antes de calcularlo. Mitades por anio de
adquisicion (A: 2016-2020, B: 2021-2025), climatologia por estacion con n_obs >= 10, z_c como
en --v2 (bahia y mar por separado), caliente = z_c >= 3,5. Escribe replicacion_<res>m.json.
"""
import os, sys, json, argparse, warnings, math
import numpy as np
from scipy import ndimage, stats
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "src"))
import anomalias, climatologia, escenas, geo, persistencia

N_MIN, RADIO_M, BANDA_M = 10, 80, 250


def zc_mitad(cubo, fechas, agua, bahia, dist, ft500):
    """{estacion: (z_c, evaluable)} con n_obs >= N_MIN."""
    climatologia.N_MIN_OBS = N_MIN
    cl = climatologia.climatologia(cubo, fechas, agua)
    out = {}
    for est, ce in cl.items():
        z = np.full(agua.shape, np.nan); ev = np.zeros(agua.shape, bool)
        for zona in (bahia, ~bahia):
            e = ce["evaluable"] & zona
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                zc, _ = anomalias.anomalia_climatologica(ce["mediana"], dist, ft500, e)
            z = np.where(e & np.isfinite(zc), zc, z); ev |= e & np.isfinite(zc)
        out[est] = (z, ev)
    return out


def comparar(za, eva, zb, evb, dist, bahia, r_px):
    """A->B: tasa de replicacion de los grupos calientes de A frente a la cobertura base."""
    ambos = eva & evb
    calA, calB = (za >= anomalias.Z_C_MIN) & eva, (zb >= anomalias.Z_C_MIN) & evb
    grA = persistencia.grupos(calA & ambos)
    disco = persistencia._disco(r_px)
    cerca_B = ndimage.binary_dilation(calB, structure=disco)
    rep = [bool(cerca_B[tuple(np.array(g["pixeles"]).T)].any()) for g in grA]
    ref = ambos & bahia & (dist <= BANDA_M)
    ok = ambos & np.isfinite(za) & np.isfinite(zb)
    rho = float(stats.spearmanr(za[ok & bahia], zb[ok & bahia])[0]) if (ok & bahia).sum() > 30 else None
    return {"grupos_calientes_A": len(grA), "grupos_con_caliente_B_a_80m": int(sum(rep)),
            "tasa_replicacion": round(sum(rep) / len(grA), 3) if grA else None,
            "cobertura_base": round(float(cerca_B[ref].mean()), 4) if ref.any() else None,
            "pixeles_evaluables_ambas": int(ambos.sum()), "spearman_zc_bahia": None if rho is None else round(rho, 3)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--productos", default="datos/productos"); ap.add_argument("--resultados", default="resultados")
    a = ap.parse_args()
    cl = np.load(os.path.join(a.resultados, "climatologia.npz"))
    agua, bahia, dist = cl["agua"].astype(bool), cl["bahia"].astype(bool), cl["distancia_costa_m"]
    ft500 = cl["f_tierra_500m"]; x, y = cl["x"], cl["y"]
    acept = set(str(p) for p in cl["productos_l1c"])
    cubos = {"A": [], "B": []}; fechas = {"A": [], "B": []}
    for r in escenas.listar(a.productos):
        e = escenas.cargar(r)
        if e["l1c"] not in acept:
            continue
        v, _ = escenas.validez(e, agua, dist)
        m = "A" if e["fecha"].year <= 2020 else "B"
        cubos[m].append(np.where(v, e["turbidez_dogliotti"], np.nan).astype(np.float32)); fechas[m].append(e["fecha"])
    print({m: len(c) for m, c in cubos.items()}, flush=True)
    zc = {m: zc_mitad(np.stack(cubos[m]), fechas[m], agua, bahia, dist, ft500) for m in "AB"}
    r_px = int(round(RADIO_M / geo.PIXEL_M))
    res = {"resolucion_m": geo.PIXEL_M, "escenas": {m: len(c) for m, c in cubos.items()}, "n_min_obs": N_MIN, "estaciones": {}}
    sitios = json.load(open("resultados/campo/campo.json"))["sitios"]
    from pyproj import Transformer
    T = Transformer.from_crs(4326, 32617, always_xy=True)
    E, N = np.meshgrid(x, y)
    for est in ("seca", "lluviosa"):
        if est not in zc["A"] or est not in zc["B"]:
            continue
        (za, eva), (zb, evb) = zc["A"][est], zc["B"][est]
        d = {"A_a_B": comparar(za, eva, zb, evb, dist, bahia, r_px), "B_a_A": comparar(zb, evb, za, eva, dist, bahia, r_px), "sitios_zc_max_80m": {}}
        for s in sitios:
            sx, sy = T.transform(s["lon"], s["lat"]); cerca = np.hypot(E - sx, N - sy) <= RADIO_M
            f = lambda z, ev: (round(float(np.nanmax(np.where(cerca & ev, z, np.nan))), 2) if (cerca & ev & np.isfinite(z)).any() else None)
            d["sitios_zc_max_80m"][s["codigo"]] = {"A": f(za, eva), "B": f(zb, evb)}
        res["estaciones"][est] = d
        for k in ("A_a_B", "B_a_A"):
            print(est, k, d[k], flush=True)
        print(est, "sitios", d["sitios_zc_max_80m"], flush=True)
    json.dump(res, open(os.path.join(a.resultados, f"replicacion_{int(geo.PIXEL_M)}m.json"), "w"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
