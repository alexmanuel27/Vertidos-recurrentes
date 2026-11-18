"""Focos de turbidez cronica frente a la profundidad de la carta (EXPLORATORIO).

    python scripts/23_batimetria.py                                  # 20 m
    VERTIDOS_PIXEL_M=10 python scripts/23_batimetria.py --resultados resultados_10m

Definido en la fila del 17/11/2026 de la secc. 14, antes de calcularlo. Profundidad = malla SCHISM
(cartas de 1879-1889), interpolada linealmente. Para cada pixel caliente (z_c >= 3,5, bandas de la
bahia como --v2) se toma el rango percentil de su profundidad entre los pixeles de la bahia a su
misma distancia de costa (+-20 m) y a > 80 m de cualquier pixel caliente. Escribe batimetria_<res>m.json.
"""
import os, sys, json, argparse, warnings
import numpy as np
from scipy import ndimage
import matplotlib.tri as mtri
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "src"))
import anomalias, geo

MALLA = "/Users/alex/Nube /repos/Modelo-hidrodin-mico/datos/malla/hgrid.gr3"
DIST_TOL_M, LEJOS_M, SOMERO_M, RADIO_M = 20, 80, 2.0, 80


def leer_malla(ruta):
    with open(ruta) as f:
        f.readline(); ne, nn = map(int, f.readline().split())
        nodos = np.array([f.readline().split()[1:4] for _ in range(nn)], float)
        tri = np.array([f.readline().split()[2:5] for _ in range(ne)], int) - 1
    return nodos, tri


def profundidad_en_rejilla(E, N):
    nodos, tri = leer_malla(MALLA)
    t = mtri.Triangulation(nodos[:, 0], nodos[:, 1], tri)
    p = mtri.LinearTriInterpolator(t, nodos[:, 2])(E, N)
    return np.ma.filled(p.astype(float), np.nan)


def zc_estacion(cl, est, agua, bahia, dist, ft500):
    ev0 = cl[f"{est}_evaluable"].astype(bool); med = cl[f"{est}_mediana"]
    z = np.full(agua.shape, np.nan); ev = np.zeros(agua.shape, bool)
    for zona in (bahia, ~bahia):
        e = ev0 & zona
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            zc, _ = anomalias.anomalia_climatologica(med, dist, ft500, e)
        z = np.where(e & np.isfinite(zc), zc, z); ev |= e & np.isfinite(zc)
    return z, ev


def comparar(caliente, prof, dist, bahia, ev, r_lejos_px):
    """Rango percentil de la profundidad de cada pixel caliente entre sus referencias."""
    caliente = caliente & bahia & np.isfinite(prof)
    if not caliente.any():
        return {"n_calientes_con_profundidad": 0}
    lejos = ~ndimage.binary_dilation(caliente, iterations=r_lejos_px)
    ref = bahia & ev & np.isfinite(prof) & lejos & ~caliente
    rd, rp = dist[ref], prof[ref]
    orden = np.argsort(rd); rd, rp = rd[orden], rp[orden]
    rangos = []
    for d, p in zip(dist[caliente], prof[caliente]):
        a, b = np.searchsorted(rd, [d - DIST_TOL_M, d + DIST_TOL_M])
        if b - a >= 30:
            rangos.append(float(((rp[a:b] < p).sum() + 0.5 * (rp[a:b] == p).sum()) / (b - a)))
    pc = prof[caliente]
    return {"n_calientes_con_profundidad": int(caliente.sum()), "n_con_referencia": len(rangos),
            "rango_percentil_mediano": round(float(np.median(rangos)), 3) if rangos else None,
            "profundidad_mediana_calientes_m": round(float(np.median(pc)), 2),
            "profundidad_mediana_referencia_m": round(float(np.median(rp)), 2),
            "frac_calientes_menos_2m": round(float((pc < SOMERO_M).mean()), 3),
            "frac_referencia_menos_2m": round(float((rp < SOMERO_M).mean()), 3),
            "n_referencia": int(ref.sum())}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--resultados", default="resultados")
    a = ap.parse_args()
    cl = np.load(os.path.join(a.resultados, "climatologia.npz"))
    agua, bahia, dist = cl["agua"].astype(bool), cl["bahia"].astype(bool), cl["distancia_costa_m"]
    ft500, x, y = cl["f_tierra_500m"], cl["x"], cl["y"]
    E, N = np.meshgrid(x, y)
    prof = profundidad_en_rejilla(E, N)
    r_px = int(round(LEJOS_M / geo.PIXEL_M))
    res = {"resolucion_m": geo.PIXEL_M, "pixeles_bahia_con_profundidad": int((bahia & np.isfinite(prof)).sum()),
           "pixeles_bahia": int(bahia.sum()), "estaciones": {}}
    print(res, flush=True)
    sitios = json.load(open("resultados/campo/campo.json"))["sitios"]
    from pyproj import Transformer
    T = Transformer.from_crs(4326, 32617, always_xy=True)
    zs, evs = {}, {}
    for est in ("seca", "lluviosa"):
        zs[est], evs[est] = zc_estacion(cl, est, agua, bahia, dist, ft500)
        cal = (zs[est] >= anomalias.Z_C_MIN) & evs[est]
        d = {"calientes": comparar(cal, prof, dist, bahia, evs[est], r_px), "sitios": {}}
        for s in sitios:
            sx, sy = T.transform(s["lon"], s["lat"]); cerca = np.hypot(E - sx, N - sy) <= RADIO_M
            pp = prof[cerca & np.isfinite(prof)]
            d["sitios"][s["codigo"]] = {"prof_mediana_80m": round(float(np.median(pp)), 2) if pp.size else None,
                                        "n_px_con_profundidad": int(pp.size)}
        res["estaciones"][est] = d
        print(est, json.dumps(d, ensure_ascii=False), flush=True)
    ambas = {"calientes": comparar(((zs["seca"] >= anomalias.Z_C_MIN) & evs["seca"]) &
                                   ((zs["lluviosa"] >= anomalias.Z_C_MIN) & evs["lluviosa"]),
                                   prof, dist, bahia, evs["seca"] & evs["lluviosa"], r_px)}
    res["ambas_estaciones"] = ambas; print("ambas", json.dumps(ambas, ensure_ascii=False), flush=True)
    json.dump(res, open(os.path.join(a.resultados, f"batimetria_{int(geo.PIXEL_M)}m.json"), "w"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
