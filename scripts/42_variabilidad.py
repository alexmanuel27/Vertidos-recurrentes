"""Peticion 3, E1: variabilidad por pixel (CVr) de los focos frente a sus referencias (EXPLORATORIO). Reglas: fila del 20/11/2026 (secc. 14).

    python scripts/42_variabilidad.py                                                   # 20 m
    VERTIDOS_PIXEL_M=10 python scripts/42_variabilidad.py --resultados resultados_10m   # 10 m (+ mapa)

CVr = MAD escalada / mediana por pixel y estacion, de climatologia.npz (evaluable: agua, >= 20 observaciones, MAD > 0).
Focos y referencias como en 30_contraste_escenas.py:preparar; diferencia = CVr del pixel caliente - mediana del CVr de las
referencias a la misma distancia de costa +-20 m (>= 30 referencias). IC 95 %: bootstrap de bloques de 200 x 200 m (2000, semilla 20261120).
Salida: <resultados>/variabilidad_<res>m.json; a 10 m, productos_publicos/figuras/fig_e1_cvr_10m.pdf y .csv.gz (sin profundidad de la carta).
"""
import os, sys, json, csv, gzip, argparse, importlib.util
import numpy as np
from scipy import ndimage
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "src"))
import anomalias, geo


def carga(nombre):
    s = importlib.util.spec_from_file_location(nombre, os.path.join(AQUI, nombre + ".py"))
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


bat, grad, fig = carga("23_batimetria"), carga("24_gradiente"), carga("26_figuras")
SEMILLA, N_BOOT, BLOQUE_M, MIN_BLOQUES = 20261120, 2000, 200, 5
DIST_TOL, PASO_D, LEJOS_M, N_MIN_REF = 20.0, 2.0, 80, 30
ZONAS = ("atares", "guasabacoa", "marimelena", "bahia_centro_y_canal")


def grupos_bloque(b):
    u, inv = np.unique(b, return_inverse=True)
    return np.split(np.argsort(inv), np.cumsum(np.bincount(inv))[:-1])


def boot_mediana(b, x, rng):
    gr = grupos_bloque(b)
    if len(gr) < MIN_BLOQUES:
        return None, len(gr)
    a = np.array([np.nanmedian(x[np.concatenate([gr[i] for i in rng.integers(0, len(gr), len(gr))])]) for _ in range(N_BOOT)])
    return [round(float(np.percentile(a, 2.5)), 4), round(float(np.percentile(a, 97.5)), 4)], len(gr)


def declara(ic):
    if ic is None:
        return "sin IC (< 5 bloques)"
    return "mayor" if ic[0] > 0 else ("menor" if ic[1] < 0 else "no distinguible")


def ref_mediana(valor, refm, dist, dgrid):
    """Mediana del valor de las referencias a distancia de costa +-20 m, en una rejilla de 2 m (>= 30 referencias)."""
    c = np.flatnonzero(refm.ravel() & np.isfinite(valor.ravel())); o = np.argsort(dist.ravel()[c]); c = c[o]; dc = dist.ravel()[c]
    a, b = np.searchsorted(dc, dgrid - DIST_TOL), np.searchsorted(dc, dgrid + DIST_TOL); v = valor.ravel()[c]
    med = np.full(dgrid.size, np.nan)
    for k in np.where(b - a >= N_MIN_REF)[0]:
        med[k] = np.median(v[a[k]:b[k]])
    return med


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--resultados", default="resultados"); a = ap.parse_args()
    res_m = int(geo.PIXEL_M); rng = np.random.default_rng(SEMILLA)
    cl = np.load(os.path.join(a.resultados, "climatologia.npz"))
    agua, bahia, dist, ft500, x, y = cl["agua"].astype(bool), cl["bahia"].astype(bool), cl["distancia_costa_m"], cl["f_tierra_500m"], cl["x"], cl["y"]
    E, N = np.meshgrid(x, y); zona = grad.zonas(cl); r_px = int(round(LEJOS_M / geo.PIXEL_M))
    bloque = np.floor(E / BLOQUE_M).astype(np.int64) * 100000 + np.floor(N / BLOQUE_M).astype(np.int64)
    dgrid = np.arange(0.0, float(np.nanmax(dist[bahia & agua])) + 2 * PASO_D, PASO_D)
    out = {"resolucion_m": res_m, "n_bootstrap": N_BOOT, "semilla": SEMILLA, "bloque_m": BLOQUE_M, "min_bloques": MIN_BLOQUES,
           "n_min_referencias": N_MIN_REF, "estaciones": {}}
    cvr_mapa = {}
    for est in ("seca", "lluviosa"):
        ev0 = cl[f"{est}_evaluable"].astype(bool); med = cl[f"{est}_mediana"].astype(float); mad = cl[f"{est}_mad"].astype(float)
        with np.errstate(invalid="ignore", divide="ignore"):
            cv = np.where(ev0 & (med > 0), mad / med, np.nan)
        cvr_mapa[est] = np.where(agua, cv, np.nan); madv = np.where(ev0, mad, np.nan)
        zs, ev = bat.zc_estacion(cl, est, agua, bahia, dist, ft500)
        hot_full = (zs >= anomalias.Z_C_MIN) & ev
        ref = bahia & ev & ~ndimage.binary_dilation(hot_full, iterations=r_px) & ~hot_full; focos = hot_full & bahia
        mcv, mmad = ref_mediana(cv, ref, dist, dgrid), ref_mediana(madv, ref, dist, dgrid)
        k = np.clip(np.rint(dist / PASO_D).astype(int), 0, dgrid.size - 1)
        dcv, dmad = cv - mcv[k], madv - mmad[k]
        d = {"n_focos": int(focos.sum()), "n_referencias": int(ref.sum()), "zonas_cvr_mediana_todos_los_pixeles": {},
             "n_pixeles_evaluables_con_cvr": int(np.isfinite(cv).sum())}
        for n in grad.ZN:
            m = np.isfinite(cv) & (zona == n); d["zonas_cvr_mediana_todos_los_pixeles"][n] = {"n": int(m.sum()), "cvr_mediana": round(float(np.median(cv[m])), 4) if m.any() else None}
        sets = {"todas": focos, **{z: focos & (zona == z) for z in ZONAS}}
        for nom, m in sets.items():
            ok = m & np.isfinite(dcv)
            if ok.sum() == 0:
                d[nom] = {"n_focos_con_referencia": 0}; continue
            ic, nb = boot_mediana(bloque[ok], dcv[ok], rng); icm, _ = boot_mediana(bloque[ok], dmad[ok], rng)
            d[nom] = {"n_focos": int(m.sum()), "n_focos_con_referencia": int(ok.sum()), "n_bloques": nb,
                      "cvr_mediana_focos": round(float(np.median(cv[ok])), 4), "cvr_mediana_de_las_referencias_emparejadas": round(float(np.median((cv - dcv)[ok])), 4),
                      "dif_cvr_mediana": round(float(np.median(dcv[ok])), 4), "dif_cvr_ic95": ic, "declaracion": declara(ic),
                      "frac_focos_con_cvr_mayor_que_su_referencia": round(float((dcv[ok] > 0).mean()), 3),
                      "mad_escalada_mediana_focos_FNU": round(float(np.median(madv[ok])), 4), "dif_mad_escalada_mediana_FNU": round(float(np.median(dmad[ok])), 4), "dif_mad_ic95": icm}
        out["estaciones"][est] = d
        print(est, {k_: (v["dif_cvr_mediana"], v["dif_cvr_ic95"], v["declaracion"], v["n_focos_con_referencia"]) for k_, v in d.items() if isinstance(v, dict) and "declaracion" in v}, flush=True)
    json.dump(out, open(os.path.join(a.resultados, f"variabilidad_{res_m}m.json"), "w"), indent=1, ensure_ascii=False)
    if res_m == 10:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        S = fig.SALIDA; os.makedirs(S, exist_ok=True); BOX = fig.BOX
        caja = (E >= BOX[0]) & (E <= BOX[1]) & (N >= BOX[2]) & (N <= BOX[3]); fs, cs = np.where(caja); sl = (slice(fs.min(), fs.max() + 1), slice(cs.min(), cs.max() + 1))
        ext = [x[sl[1]].min() - 5, x[sl[1]].max() + 5, y[sl[0]].min() - 5, y[sl[0]].max() + 5]
        todos = np.concatenate([cvr_mapa[e][sl][np.isfinite(cvr_mapa[e][sl])] for e in cvr_mapa]); vmin, vmax = float(np.percentile(todos, 2)), float(np.percentile(todos, 98))
        f, axs = plt.subplots(1, 2, figsize=(7.5, 3.5), sharex=True, sharey=True, constrained_layout=True)
        for ax, est, tit in zip(axs, ("seca", "lluviosa"), ("Dry season (Nov-Apr)", "Wet season (May-Oct)")):
            ax.set_facecolor("#E6E6E6")
            im = ax.imshow(cvr_mapa[est][sl], extent=ext, origin="upper", cmap="viridis", vmin=vmin, vmax=vmax, interpolation="nearest", rasterized=True)
            ax.contour(x[sl[1]], y[sl[0]], agua[sl].astype(float), levels=[0.5], colors="k", linewidths=0.4)
            ax.set_title(tit, fontsize=8); ax.set_xlabel("Easting, UTM 17N (km)")
            ax.set_xticks(np.arange(361000, 365001, 1000)); ax.set_xticklabels([f"{v/1000:.0f}" for v in np.arange(361000, 365001, 1000)])
            fig.escala(ax, ext[0] + 300, ext[2] + 250)
        axs[0].set_ylabel("Northing, UTM 17N (km)"); axs[0].set_yticks(np.arange(2556000, 2561001, 1000)); axs[0].set_yticklabels([f"{v/1000:.0f}" for v in np.arange(2556000, 2561001, 1000)])
        cb = f.colorbar(im, ax=axs, shrink=0.8, extend="both", pad=0.02); cb.set_label("Robust coefficient of variation, 10 m (1.4826 MAD / median)")
        f.savefig(f"{S}/fig_e1_cvr_10m.pdf"); plt.close(f)
        with gzip.open(f"{S}/fig_e1_cvr_10m.csv.gz", "wt", newline="") as fh:
            w = csv.writer(fh); w.writerow(["easting_m", "northing_m", "cvr_dry", "cvr_wet"])
            for i, j in zip(*np.where(caja & agua & (np.isfinite(cvr_mapa["seca"]) | np.isfinite(cvr_mapa["lluviosa"])))):
                w.writerow([int(x[j]), int(y[i])] + ["" if not np.isfinite(cvr_mapa[e][i, j]) else round(float(cvr_mapa[e][i, j]), 4) for e in ("seca", "lluviosa")])
        print("mapa hecho; escala", round(vmin, 3), round(vmax, 3))


if __name__ == "__main__":
    main()
