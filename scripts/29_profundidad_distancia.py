"""Peticion 2, bloque B: profundidad frente a distancia a costa (EXPLORATORIO, archivo 2016-2025).

    python scripts/29_profundidad_distancia.py                                  # 20 m
    VERTIDOS_PIXEL_M=10 python scripts/29_profundidad_distancia.py --resultados resultados_10m

Reglas en la fila del 18/11/2026 (peticion 2) de la secc. 14. B1: bandas de distancia x clases de profundidad x estacion;
B2: regresion por rangos z_c ~ prof + dist + f_tierra_500; B3: < 60 m de costa con carta > 5 m frente a < 2 m;
B4: batimetria posterior a 1889 (busqueda en el repo del modelo). Bootstrap de bloques de 200 x 200 m (2000, semilla 20261118).
"""
import os, sys, json, argparse, importlib.util
import numpy as np
from scipy.stats import rankdata
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "src"))
import anomalias, geo


def carga(nombre):
    s = importlib.util.spec_from_file_location(nombre, os.path.join(AQUI, nombre + ".py"))
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


bat, grad = carga("23_batimetria"), carga("24_gradiente")
SEMILLA, N_BOOT, BLOQUE_M = 20261118, 2000, 200
BANDAS = [(0, 40), (40, 80), (80, 160), (160, 320)]
CLASES = [("<2", -np.inf, 2.0), ("2-5", 2.0, 5.0), (">5", 5.0, np.inf)]
MIN_BLOQUES = 5


def grupos_bloque(b):
    u, inv = np.unique(b, return_inverse=True)
    return np.split(np.argsort(inv), np.cumsum(np.bincount(inv))[:-1])


def boot(b, f, rng):
    """IC 95 % de f(indices) (devuelve un vector) por bootstrap de bloques; None si hay < MIN_BLOQUES bloques."""
    gr = grupos_bloque(b)
    if len(gr) < MIN_BLOQUES:
        return None
    a = np.array([f(np.concatenate([gr[i] for i in rng.integers(0, len(gr), len(gr))])) for _ in range(N_BOOT)])
    return [[round(float(np.nanpercentile(a[:, k], 2.5)), 3), round(float(np.nanpercentile(a[:, k], 97.5)), 3)] for k in range(a.shape[1])]


def regresion(R, idx):
    X = R[idx]; X = (X - X.mean(0)) / X.std(0)
    A, y = X[:, 1:], X[:, 0]
    beta = np.linalg.lstsq(A, y, rcond=None)[0]
    r = np.corrcoef(R[idx][:, 1], R[idx][:, 2])[0, 1]     # Spearman prof-dist = Pearson de los rangos
    return np.append(beta, r)


def osm_portuario(E, N):
    """Marca de muelle/zona portuaria de OSM (consulta guardada de 15_diagnosticos_sitios); None si no existe."""
    ruta = os.path.join(AQUI, "..", "resultados", "campo", "osm_portuario.json")
    if not os.path.exists(ruta):
        return None, "no existe resultados/campo/osm_portuario.json"
    from pyproj import Transformer
    from scipy.spatial import cKDTree
    from matplotlib.path import Path
    T = Transformer.from_crs(4326, 32617, always_xy=True); d = json.load(open(ruta)); pts, polis = [], []
    for e in d["elements"]:
        g = e.get("geometry"); tg = e.get("tags", {})
        if not g:
            continue
        xy = np.array([T.transform(p["lon"], p["lat"]) for p in g])
        if tg.get("man_made") in ("pier", "quay", "breakwater"):
            for a, b in zip(xy[:-1], xy[1:]):
                k = max(2, int(np.hypot(*(b - a)) // 5)); pts.append(a + (b - a) * np.linspace(0, 1, k)[:, None])
        elif tg.get("landuse") == "port" and len(xy) > 3:
            polis.append(Path(xy))
    cerca = np.zeros(E.shape, bool)
    if pts:
        dd, _ = cKDTree(np.vstack(pts)).query(np.c_[E.ravel(), N.ravel()]); cerca |= (dd <= 40).reshape(E.shape)
    for p in polis:
        cerca |= p.contains_points(np.c_[E.ravel(), N.ravel()]).reshape(E.shape)
    return cerca, f"{len(pts)} tramos muelle/espigon y {len(polis)} poligonos portuarios de OSM (a <= 40 m o dentro); no es informacion de dragados"


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--resultados", default="resultados"); a = ap.parse_args()
    cl = np.load(os.path.join(a.resultados, "climatologia.npz"))
    agua, bahia, dist, ft500, x, y = cl["agua"].astype(bool), cl["bahia"].astype(bool), cl["distancia_costa_m"], cl["f_tierra_500m"], cl["x"], cl["y"]
    E, N = np.meshgrid(x, y); prof = bat.profundidad_en_rejilla(E, N); z_ = grad.zonas(cl)
    bloque = np.floor(E / BLOQUE_M).astype(np.int64) * 100000 + np.floor(N / BLOQUE_M).astype(np.int64)
    marca, nota_osm = osm_portuario(E, N); rng = np.random.default_rng(SEMILLA)
    res = {"resolucion_m": geo.PIXEL_M, "n_bootstrap": N_BOOT, "bloque_m": BLOQUE_M, "min_bloques_para_ic": MIN_BLOQUES,
           "marca_muelles": nota_osm, "estaciones": {}}
    for est in ("seca", "lluviosa"):
        zc, ev = bat.zc_estacion(cl, est, agua, bahia, dist, ft500); med = cl[f"{est}_mediana"]
        base = bahia & ev & np.isfinite(prof) & np.isfinite(zc) & np.isfinite(med)
        d = {"n_pixeles_bahia_con_profundidad_y_z_c": int(base.sum()), "B1": [], "B2": {}, "B3": []}
        # ---- B1
        for (d0, d1) in BANDAS:
            for (nc, p0, p1) in CLASES:
                m = base & (dist >= d0) & (dist < d1) & (prof >= p0) & (prof < p1)
                c = {"banda_m": f"{d0}-{d1}", "clase_prof_m": nc, "n_pixeles": int(m.sum())}
                if m.sum() >= 1:
                    mv, zv, bv = med[m], zc[m], bloque[m]
                    c.update({"mediana_clim_FNU": round(float(np.median(mv)), 3), "mediana_z_c": round(float(np.median(zv)), 3), "n_bloques": int(np.unique(bv).size)})
                    ic = boot(bv, lambda i: np.array([np.median(mv[i]), np.median(zv[i])]), rng)
                    c["ic95_mediana_clim"], c["ic95_mediana_z_c"] = (ic[0], ic[1]) if ic else (None, None)
                d["B1"].append(c)
        # ---- B2
        idx = np.where(base.ravel())[0]
        R = np.column_stack([rankdata(v.ravel()[idx]) / idx.size for v in (zc, prof, dist, ft500)])
        beta = regresion(R, np.arange(idx.size)); bv = bloque.ravel()[idx]
        ic = boot(bv, lambda i: regresion(R, i), rng)
        nombres = ["rango_prof", "rango_dist", "rango_f_tierra_500"]
        d["B2"] = {"n": int(idx.size), "n_bloques": int(np.unique(bv).size),
                   "coef_estandarizados": {n: round(float(b), 3) for n, b in zip(nombres, beta[:3])},
                   "ic95": {n: (ic[k] if ic else None) for k, n in enumerate(nombres)},
                   "spearman_prof_dist": round(float(beta[3]), 3), "ic95_spearman_prof_dist": ic[3] if ic else None}
        # ---- B2b (anadido el 18/11 tras ver B2: z_c ya esta corregida por distancia a costa, asi que el coeficiente de la
        # distancia no es informativo; mismo modelo con la mediana climatologica de turbidez, sin corregir, como resultado)
        R2 = np.column_stack([rankdata(v.ravel()[idx]) / idx.size for v in (med, prof, dist, ft500)])
        beta2 = regresion(R2, np.arange(idx.size)); ic2 = boot(bv, lambda i: regresion(R2, i), rng)
        d["B2b_mediana_climatologica"] = {"n": int(idx.size), "coef_estandarizados": {n: round(float(b), 3) for n, b in zip(nombres, beta2[:3])},
                                          "ic95": {n: (ic2[k] if ic2 else None) for k, n in enumerate(nombres)}}
        # ---- B3
        for (d0, d1) in [(0, 20), (20, 40), (40, 60)]:
            for nc, p0, p1 in (("<2", -np.inf, 2.0), (">5", 5.0, np.inf)):
                m = base & (dist < 60) & (dist >= d0) & (dist < d1) & (prof >= p0) & (prof < p1)
                c = {"banda_m": f"{d0}-{d1}", "clase_prof_m": nc, "n_pixeles": int(m.sum())}
                if m.sum() >= 1:
                    zv = zc[m]; zonas, cuenta = np.unique(z_[m], return_counts=True)
                    c.update({"zonas": {str(k): int(v) for k, v in zip(zonas, cuenta)}, "z_c_percentiles_10_25_50_75_90": [round(float(q), 2) for q in np.percentile(zv, [10, 25, 50, 75, 90])],
                              "fraccion_caliente_z_c>=3.5": round(float((zv >= anomalias.Z_C_MIN).mean()), 3), "profundidad_mediana_m": round(float(np.median(prof[m])), 2)})
                    ic = boot(bloque[m], lambda i: np.array([np.median(zv[i])]), rng); c["ic95_mediana_z_c"] = ic[0] if ic else None
                    if marca is not None:
                        c["fraccion_en_muelle_o_zona_portuaria_OSM"] = round(float(marca[m].mean()), 3)
                d["B3"].append(c)
        res["estaciones"][est] = d
        print(est, json.dumps(d["B2"], ensure_ascii=False), flush=True)
        for c in d["B1"]:
            print("  B1", c, flush=True)
        for c in d["B3"]:
            print("  B3", c, flush=True)
    json.dump(res, open(os.path.join(a.resultados, f"prof_dist_{int(geo.PIXEL_M)}m.json"), "w"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
