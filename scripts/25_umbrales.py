"""Sensibilidad de los focos de turbidez cronica al umbral de z_c (EXPLORATORIO).

    python scripts/25_umbrales.py                                          # 20 m
    VERTIDOS_PIXEL_M=10 python scripts/25_umbrales.py --productos datos/productos_10m \
        --resultados resultados_10m

Definido en la fila del 17/11/2026 de la secc. 14 (peticion del chat del articulo), antes de calcularlo.
Umbrales z_c >= 2,5; 3,0; 3,5 (el fijado); 4,0; 5,0. Por umbral y estacion: grupos calientes (climatologia
completa), distancia de S1-S5 (y de los controles) al pixel caliente mas cercano, probabilidad al azar de quedar a
<= 80 m (fraccion de pixeles de su zona y banda de distancia a costa +-20 m, a > 200 m del sitio) y numero
esperado/observado de sitios a <= 80 m, replicacion A<->B (reglas de 21_replicacion.py) y profundidad de la
carta (reglas de 23_batimetria.py). Escribe umbrales_<res>m.json.
"""
import os, sys, json, argparse, importlib.util
import numpy as np
from scipy import ndimage
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "src"))
import anomalias, climatologia, escenas, geo, persistencia

UMBRALES = (2.5, 3.0, 3.5, 4.0, 5.0)
RADIO_M, DIST_TOL_M, EXCL_M = 80, 20, 200


def cargar(nombre):
    spec = importlib.util.spec_from_file_location(nombre, os.path.join(AQUI, nombre + ".py"))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def poisson_binomial_cola(p, k):
    """P(X >= k) con X suma de Bernoulli(p_i) independientes."""
    pm = np.array([1.0])
    for pi in p:
        pm = np.convolve(pm, [1 - pi, pi])
    return float(pm[k:].sum())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--productos", default="datos/productos"); ap.add_argument("--resultados", default="resultados")
    a = ap.parse_args()
    rep, bat = cargar("21_replicacion"), cargar("23_batimetria")
    cl = np.load(os.path.join(a.resultados, "climatologia.npz"))
    agua, bahia, dist = cl["agua"].astype(bool), cl["bahia"].astype(bool), cl["distancia_costa_m"]
    ft500, x, y = cl["f_tierra_500m"], cl["x"], cl["y"]
    E, N = np.meshgrid(x, y)
    px = float(geo.PIXEL_M); r_px = int(round(RADIO_M / px))
    prof = bat.profundidad_en_rejilla(E, N)
    campo = json.load(open("resultados/campo/campo.json"))
    from pyproj import Transformer
    T = Transformer.from_crs(4326, 32617, always_xy=True)
    puntos = {}
    for rol, lista in (("sitio", campo["sitios"]), ("control", campo["controles"])):
      for s in lista:
        codigo = s["codigo"] if rol == "sitio" else f"ctrl_{s['sitio']}_{s['orden']}"
        sx, sy = T.transform(s["lon"], s["lat"]); d2 = np.hypot(E - sx, N - sy); i = np.unravel_index(np.argmin(d2), d2.shape)
        puntos[codigo] = {"x": sx, "y": sy, "i": i, "d_costa": float(dist[i]) if np.isfinite(dist[i]) else None,
                          "bahia": bool(bahia[i]), "rol": rol}
    zs, evs = {}, {}
    for est in ("seca", "lluviosa"):
        zs[est], evs[est] = bat.zc_estacion(cl, est, agua, bahia, dist, ft500)
    # mitades A/B, como 21_replicacion.py
    acept = set(str(p) for p in cl["productos_l1c"])
    cubos = {"A": [], "B": []}; fechas = {"A": [], "B": []}
    for r in escenas.listar(a.productos):
        e = escenas.cargar(r)
        if e["l1c"] not in acept:
            continue
        v, _ = escenas.validez(e, agua, dist)
        m = "A" if e["fecha"].year <= 2020 else "B"
        cubos[m].append(np.where(v, e["turbidez_dogliotti"], np.nan).astype(np.float32)); fechas[m].append(e["fecha"])
    zh = {m: rep.zc_mitad(np.stack(cubos[m]), fechas[m], agua, bahia, dist, ft500) for m in "AB"}
    res = {"resolucion_m": px, "escenas_mitades": {m: len(c) for m, c in cubos.items()}, "umbrales": {}}
    for thr in UMBRALES:
        anomalias.Z_C_MIN = thr
        r_u = {"estaciones": {}}
        for est in ("seca", "lluviosa"):
            hot = (zs[est] >= thr) & evs[est]
            edt = ndimage.distance_transform_edt(~hot) * px
            g_todos, g_bahia = persistencia.grupos(hot), persistencia.grupos(hot & bahia)
            d = {"pixeles_calientes": int(hot.sum()), "pixeles_calientes_bahia": int((hot & bahia).sum()),
                 "grupos": len(g_todos), "grupos_bahia": len(g_bahia), "puntos": {}}
            pa = {"sitio": [], "control": []}; obs = {"sitio": 0, "control": 0}
            for c, p in puntos.items():
                dm = round(float(edt[p["i"]]), 1)
                zona = bahia if p["bahia"] else ~bahia
                ref = evs[est] & zona & (np.abs(dist - p["d_costa"]) <= DIST_TOL_M) & (np.hypot(E - p["x"], N - p["y"]) > EXCL_M) if p["d_costa"] is not None else None
                p_az = float((edt[ref] <= RADIO_M).mean()) if ref is not None and ref.any() else None
                d["puntos"][c] = {"rol": p["rol"], "dist_al_caliente_mas_cercano_m": dm, "a_80m": bool(dm <= RADIO_M),
                                  "prob_azar_a_80m": None if p_az is None else round(p_az, 4)}
                if p_az is not None:
                    pa[p["rol"]].append(p_az); obs[p["rol"]] += int(dm <= RADIO_M)
            for rol in ("sitio", "control"):
                if pa[rol]:
                    d[f"{rol}s_a_80m"] = {"observados": obs[rol], "de": len(pa[rol]), "esperados_por_azar": round(sum(pa[rol]), 3),
                                          "prob_cola_poisson_binomial": round(poisson_binomial_cola(pa[rol], obs[rol]), 4)}
            d["profundidad"] = bat.comparar(hot, prof, dist, bahia, evs[est], r_px)
            (za, eva), (zb, evb) = zh["A"][est], zh["B"][est]
            ab = rep.comparar(za, eva, zb, evb, dist, bahia, r_px); ba = rep.comparar(zb, evb, za, eva, dist, bahia, r_px)
            ok = all(k["tasa_replicacion"] is not None and k["cobertura_base"] is not None and
                     k["tasa_replicacion"] >= max(3 * k["cobertura_base"], 0.30) for k in (ab, ba))
            d["replicacion"] = {"A_a_B": ab, "B_a_A": ba, "regla_se_cumple_en_los_dos_sentidos": bool(ok)}
            r_u["estaciones"][est] = d
            print(thr, est, json.dumps({k: d[k] for k in ("grupos", "grupos_bahia", "sitios_a_80m", "controles_a_80m")
                                        if k in d}, ensure_ascii=False), "| prof", d["profundidad"].get("rango_percentil_mediano"),
                  d["profundidad"].get("frac_calientes_menos_2m"), "| rep", ab["tasa_replicacion"], ba["tasa_replicacion"], ok, flush=True)
        res["umbrales"][str(thr)] = r_u
    anomalias.Z_C_MIN = 3.5
    json.dump(res, open(os.path.join(a.resultados, f"umbrales_{int(px)}m.json"), "w"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
