"""Contraste por escena d de los focos y medianas por zona (peticion 2, bloques A, C y D). Reglas: fila del 18/11/2026 (secc. 14).

    python scripts/30_contraste_escenas.py                                          # 20 m, archivo 2016-2025
    VERTIDOS_PIXEL_M=10 python scripts/30_contraste_escenas.py --productos datos/productos_10m --resultados resultados_10m
    ... --productos DIR --aceptadas LISTA.txt --etiqueta 2026                       # otras escenas, mismos focos y climatologia

Focos = pixeles calientes de la bahia (z_c >= 3,5) de la climatologia de --resultados, por estacion (no se recalculan);
a 10 m, ademas, la union de los 13 grupos de la secc. 28. Referencia = pixeles de la bahia evaluables a > 80 m de cualquier
caliente; d de una escena = mediana, sobre los pixeles de foco validos, de (turbidez - mediana de las referencias validas a la
misma distancia de costa +-20 m, con la distancia redondeada a 2 m); escena utilizable si hay >= 20 pixeles de foco validos.
Placebo: 500 conjuntos fijos (semilla 20261118) en los que cada pixel de foco se sustituye por un pixel al azar de las
referencias de su misma banda de distancia (+-20 m), con el mismo d. Salidas: contraste_escenas_<res>m_<etiqueta>.csv y
contraste_placebo_<res>m_<etiqueta>.npz en --resultados.
"""
import os, sys, csv, json, argparse, importlib.util, warnings
import numpy as np
from scipy import ndimage
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "src"))
import anomalias, geo, escenas, climatologia, persistencia


def carga(nombre):
    s = importlib.util.spec_from_file_location(nombre, os.path.join(AQUI, nombre + ".py"))
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


bat, grad, fig = carga("23_batimetria"), carga("24_gradiente"), carga("26_figuras")
SEMILLA, N_PLACEBO, N_MIN_FOCO, N_MIN_PX, DIST_TOL, PASO_D, LEJOS_M, N_MIN_REF = 20261118, 500, 20, 50, 20.0, 2.0, 80, 30


def preparar(cl, rng):
    """Por estacion: mascaras de focos, de referencia y los 500 conjuntos placebo (indices planos)."""
    agua, bahia, dist, ft500, x, y = cl["agua"].astype(bool), cl["bahia"].astype(bool), cl["distancia_costa_m"], cl["f_tierra_500m"], cl["x"], cl["y"]
    E, N = np.meshgrid(x, y); r_px = int(round(LEJOS_M / geo.PIXEL_M)); out = {}
    for est in ("seca", "lluviosa"):
        zs, ev = bat.zc_estacion(cl, est, agua, bahia, dist, ft500)
        hot_full = (zs >= anomalias.Z_C_MIN) & ev
        ref = bahia & ev & ~ndimage.binary_dilation(hot_full, iterations=r_px) & ~hot_full
        masks = {"focos": hot_full & bahia}
        if geo.PIXEL_M == 10.0:
            g13 = np.zeros(agua.shape, bool)
            for g in persistencia.grupos(hot_full):
                cf, cc = g["centroide"]
                cx, cy = float(np.interp(cc, np.arange(E.shape[1]), E[0])), float(np.interp(cf, np.arange(N.shape[0]), N[:, 0]))
                if fig.BOX[0] <= cx <= fig.BOX[1] and fig.BOX[2] <= cy <= fig.BOX[3]:
                    ij = np.array(g["pixeles"]); g13[ij[:, 0], ij[:, 1]] = True
            masks["grupos13"] = g13
        cand = np.flatnonzero(ref.ravel()); o = np.argsort(dist.ravel()[cand]); cand, dc = cand[o], dist.ravel()[cand][o]
        plac = {}
        for nom, m in masks.items():
            f = np.flatnonzero(m.ravel()); df = dist.ravel()[f]
            a, b = np.searchsorted(dc, df - DIST_TOL), np.searchsorted(dc, df + DIST_TOL)
            ok = b > a; f, a, b = f[ok], a[ok], b[ok]
            u = rng.random((N_PLACEBO, f.size)); plac[nom] = cand[a + np.floor(u * (b - a)).astype(np.int64)]
            masks[nom] = np.zeros(agua.shape, bool); masks[nom].ravel()[f] = True
        out[est] = {"masks": masks, "ref": ref, "placebo": plac, "n_focos": {k: int(v.sum()) for k, v in masks.items()}}
    return out


def contraste(T, ref, dist, dgrid):
    m = ref & np.isfinite(T); d, t = dist[m], T[m]; o = np.argsort(d); d, t = d[o], t[o]
    a, b = np.searchsorted(d, dgrid - DIST_TOL), np.searchsorted(d, dgrid + DIST_TOL)
    med = np.full(dgrid.size, np.nan)
    for k in np.where(b - a >= N_MIN_REF)[0]:
        med[k] = np.median(t[a[k]:b[k]])
    return T - med[np.clip(np.rint(dist / PASO_D).astype(int), 0, dgrid.size - 1)]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--productos", default="datos/productos"); ap.add_argument("--resultados", default="resultados")
    ap.add_argument("--aceptadas", default=None); ap.add_argument("--etiqueta", default="2016_2025"); a = ap.parse_args()
    cl = np.load(os.path.join(a.resultados, "climatologia.npz"))
    agua, bahia, dist = cl["agua"].astype(bool), cl["bahia"].astype(bool), cl["distancia_costa_m"]
    z = grad.zonas(cl); lejos = dist >= 100; rng = np.random.default_rng(SEMILLA)
    acept = set(str(p) for p in cl["productos_l1c"]) if a.aceptadas is None else set(l.strip() for l in open(a.aceptadas) if l.strip())
    dgrid = np.arange(0.0, float(np.nanmax(dist[bahia & agua])) + 2 * PASO_D, PASO_D)
    prep = preparar(cl, rng); filas, plac = [], {"focos": [], "grupos13": []}
    for r in escenas.listar(a.productos):
        e = escenas.cargar(r)
        if e["l1c"] not in acept:
            continue
        v, _ = escenas.validez(e, agua, dist); T = np.where(v, e["turbidez_dogliotti"], np.nan)
        est = climatologia.estacion_de(e["fecha"]); P = prep[est]
        f = {"fecha": e["fecha"].date().isoformat(), "hora_utc": e["fecha"].strftime("%H:%M:%S"), "anio": e["fecha"].year, "estacion": est, "l1c": e["l1c"]}
        C = contraste(T, P["ref"], dist, dgrid); Cf = C.ravel()
        for nom in ("focos", "grupos13"):
            if nom not in P["masks"]:
                continue
            vals = C[P["masks"][nom]]; n = int(np.isfinite(vals).sum())
            f[f"{nom}_n_validos"] = n; f[f"d_{nom}"] = float(np.median(vals[np.isfinite(vals)])) if n >= N_MIN_FOCO else float("nan")
            pv = Cf[P["placebo"][nom]]; ok = np.isfinite(pv).sum(1) >= N_MIN_FOCO
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning); pm = np.nanmedian(pv, axis=1)
            plac[nom].append(np.where(ok & (n >= N_MIN_FOCO), pm, np.nan))
        for n in grad.ZN:
            for var, m in (("todos", z == n), ("a100m", (z == n) & lejos)):
                xx = T[m & np.isfinite(T)]; f[f"{n}_{var}_n"] = int(xx.size); f[f"{n}_{var}"] = float(np.median(xx)) if xx.size >= N_MIN_PX else float("nan")
        filas.append(f); print(f["fecha"], f["hora_utc"], est, f.get("focos_n_validos"), round(f["d_focos"], 3) if np.isfinite(f["d_focos"]) else "nan", flush=True)
    base = os.path.join(a.resultados, f"contraste_escenas_{int(geo.PIXEL_M)}m_{a.etiqueta}")
    with open(base + ".csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(filas[0].keys())); w.writeheader(); w.writerows(filas)
    np.savez_compressed(os.path.join(a.resultados, f"contraste_placebo_{int(geo.PIXEL_M)}m_{a.etiqueta}.npz"),
                        fechas=np.array([f["fecha"] for f in filas]), estacion=np.array([f["estacion"] for f in filas]),
                        **{f"placebo_{k}": np.array(v) for k, v in plac.items() if v})
    json.dump({"n_focos_por_estacion": {e: prep[e]["n_focos"] for e in prep}, "n_escenas": len(filas), "semilla": SEMILLA, "n_placebo": N_PLACEBO},
              open(base + "_meta.json", "w"), indent=1)
    print("escenas", len(filas), {e: prep[e]["n_focos"] for e in prep}, flush=True)


if __name__ == "__main__":
    main()
