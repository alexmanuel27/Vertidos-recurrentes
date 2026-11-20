"""Peticion 3, E2: direccion del viento (norte / resto) y contraste de las zonas, epoca seca (EXPLORATORIO). Reglas: fila del 20/11/2026 (secc. 14).

    python scripts/43_viento_direccion.py                                                  # 20 m
    VERTIDOS_PIXEL_M=10 python scripts/43_viento_direccion.py --productos datos/productos_10m --resultados resultados_10m   # 10 m (+ mapas)

Entrada: <resultados>/marea_viento_escenas_<res>m.csv (31_marea_viento.py; escenas aceptadas 2016-2025) y ERA5 del repo del modelo (solo lectura).
Procedencia = atan2(-u, -v) en grados mod 360; hora de paso = (u, v) interpoladas linealmente; 24 h previas = media de u y de v en (t-24 h, t].
Clase «norte» = procedencia >= 315 o < 45; «resto» = el resto; >= 8 escenas por clase o «insuficiente». Bootstrap de escenas (2000, semilla 20261120).
Salida: <resultados>/viento_direccion_<res>m.json, <resultados>/viento_direccion_escenas_<res>m.csv; a 10 m, fig_e2_mapas_viento_10m.pdf y .csv.gz.
"""
import os, sys, csv, json, argparse, importlib.util
import numpy as np
from datetime import datetime
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "src"))
import geo


def carga(nombre):
    s = importlib.util.spec_from_file_location(nombre, os.path.join(AQUI, nombre + ".py"))
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


mv, grad = carga("31_marea_viento"), carga("24_gradiente")
SEMILLA, N_BOOT, N_MIN = 20261120, 2000, 8
ZN = grad.ZN


def procedencia(u, v):
    return float(np.degrees(np.arctan2(-u, -v)) % 360.0)


def es_norte(d):
    return d >= 315.0 or d < 45.0


def viento_dir(vi, dt):
    t, u, v, pt = vi.serie(dt); ts = (dt - datetime(1970, 1, 1)).total_seconds()
    up, vp = float(np.interp(ts, t, u)), float(np.interp(ts, t, v)); h = (t > ts - 24 * 3600 - 1) & (t <= ts)
    um, vm = float(np.mean(u[h])), float(np.mean(v[h]))
    return procedencia(up, vp), procedencia(um, vm), float(np.hypot(up, vp)), float(np.hypot(um, vm)), int(h.sum())


def medidas(Z, d):
    """Z: escenas x 5 zonas (orden ZN); d: d_focos por escena. Devuelve dict con las cantidades de la peticion."""
    med = np.nanmedian(Z, axis=0); at, gu, ma, ce, mar = med
    br, mid = min(at, gu), max(ma, ce)
    return {"orden": bool(br > mid > mar), "margen_ensenadas": float(br - mid), "margen_bahia_mar": float(mid - mar), "d": float(np.nanmedian(d)) if np.isfinite(d).any() else np.nan}


def boot_una(Z, d, rng):
    n = len(Z); idx = rng.integers(0, n, (N_BOOT, n)); out = []
    for k in range(N_BOOT):
        out.append(medidas(Z[idx[k]], d[idx[k]]))
    return out


def ic(x):
    x = np.array(x, float); x = x[np.isfinite(x)]
    return [round(float(np.percentile(x, 2.5)), 3), round(float(np.percentile(x, 97.5)), 3)] if x.size else None


def declara(c):
    return None if c is None else ("mayor" if c[0] > 0 else ("menor" if c[1] < 0 else "no distinguible"))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--resultados", default="resultados"); ap.add_argument("--productos", default="datos/productos"); a = ap.parse_args()
    res_m = int(geo.PIXEL_M); rng = np.random.default_rng(SEMILLA)
    from pyproj import Transformer
    lon0, lat0 = Transformer.from_crs(32617, 4326, always_xy=True).transform(*mv.BOCA_UTM)[0:2]; vi = mv.Viento(lat0, lon0)
    filas = [f for f in csv.DictReader(open(os.path.join(a.resultados, f"marea_viento_escenas_{res_m}m.csv"))) if f["estacion"] == "seca"]
    esc = []
    for f in filas:
        dt = datetime.fromisoformat(f"{f['fecha']}T{f['hora_utc']}"); dp, d24, vp, v24, nh = viento_dir(vi, dt)
        esc.append({"fecha": f["fecha"], "hora_utc": f["hora_utc"], "dir_paso": dp, "dir_24h": d24, "vel_paso_ms": vp, "vel_media_vectorial_24h_ms": v24, "n_horas_24h": nh,
                    "norte_paso": es_norte(dp), "norte_24h": es_norte(d24), "d": float(f["d_focos"]),
                    **{f"{n}_{var}": float(f[f"{n}_{var}"]) for n in ZN for var in ("todos", "a100m")}})
    with open(os.path.join(a.resultados, f"viento_direccion_escenas_{res_m}m.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(esc[0].keys())); w.writeheader(); w.writerows(esc)
    out = {"resolucion_m": res_m, "n_bootstrap": N_BOOT, "semilla": SEMILLA, "n_min_por_clase": N_MIN, "punto_era5_lat_lon": list(vi.serie(datetime(2020, 1, 15))[3]),
           "n_escenas_seca": len(esc), "clases": {}}
    for tag, key in (("paso", "norte_paso"), ("24h", "norte_24h")):
        dd = {"n_norte": int(sum(e[key] for e in esc)), "n_resto": int(sum(not e[key] for e in esc)), "variantes": {}}
        dd["procedencia_mediana_circular_grados"] = None
        if min(dd["n_norte"], dd["n_resto"]) < N_MIN:
            dd["estado"] = "insuficiente"; out["clases"][tag] = dd; continue
        for var in ("todos", "a100m"):
            Z = {c: np.array([[e[f"{n}_{var}"] for n in ZN] for e in esc if (e[key] == (c == "norte"))], float) for c in ("norte", "resto")}
            D = {c: np.array([e["d"] for e in esc if (e[key] == (c == "norte"))], float) for c in ("norte", "resto")}
            B = {c: boot_una(Z[c], D[c], rng) for c in Z}; v = {}
            for c in Z:
                m = medidas(Z[c], D[c])
                v[c] = {"n_escenas": len(Z[c]), "orden_cumple": m["orden"], "margen_ensenadas": round(m["margen_ensenadas"], 3), "margen_ensenadas_ic95": ic([b["margen_ensenadas"] for b in B[c]]),
                        "margen_bahia_mar": round(m["margen_bahia_mar"], 3), "margen_bahia_mar_ic95": ic([b["margen_bahia_mar"] for b in B[c]]),
                        "d_mediana": round(m["d"], 3), "d_ic95": ic([b["d"] for b in B[c]]), "frac_boot_orden_cumple": round(float(np.mean([b["orden"] for b in B[c]])), 3)}
            dif = {}
            for q in ("margen_ensenadas", "margen_bahia_mar", "d"):
                est = medidas(Z["norte"], D["norte"])[q] - medidas(Z["resto"], D["resto"])[q]
                c_ = ic([bn[q] - br[q] for bn, br in zip(B["norte"], B["resto"])])
                dif[q] = {"norte_menos_resto": round(float(est), 3), "ic95": c_, "declaracion": declara(c_)}
            v["diferencia_norte_menos_resto"] = dif; dd["variantes"][var] = v
        out["clases"][tag] = dd
        print(res_m, tag, dd["n_norte"], dd["n_resto"], {var: dd["variantes"][var]["diferencia_norte_menos_resto"]["margen_ensenadas"] for var in dd["variantes"]}, flush=True)
    json.dump(out, open(os.path.join(a.resultados, f"viento_direccion_{res_m}m.json"), "w"), indent=1, ensure_ascii=False)
    if res_m == 10 and min(out["clases"]["24h"]["n_norte"], out["clases"]["24h"]["n_resto"]) >= N_MIN:
        mapas(a, esc)


def mapas(a, esc):
    import gzip
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import escenas, climatologia
    fig = carga("26_figuras"); cl = np.load(os.path.join(a.resultados, "climatologia.npz"))
    agua, dist, x, y = cl["agua"].astype(bool), cl["distancia_costa_m"], cl["x"], cl["y"]; acept = set(str(p) for p in cl["productos_l1c"])
    clase = {e["fecha"]: ("norte" if e["norte_24h"] else "resto") for e in esc}; pilas = {"norte": [], "resto": []}
    for r in escenas.listar(a.productos):
        e = escenas.cargar(r)
        if e["l1c"] not in acept:
            continue
        f = e["fecha"].date().isoformat()
        if f not in clase:
            continue
        v, _ = escenas.validez(e, agua, dist); pilas[clase[f]].append(np.where(v, e["turbidez_dogliotti"], np.nan).astype(np.float32))
    print({k: len(v) for k, v in pilas.items()}, flush=True)
    M, C = {}, {}
    for k, p in pilas.items():
        S = np.stack(p); C[k] = np.isfinite(S).sum(0)
        with np.errstate(all="ignore"):
            import warnings
            warnings.simplefilter("ignore"); M[k] = np.where(C[k] >= 5, np.nanmedian(S, axis=0), np.nan)
    dif = M["norte"] - M["resto"]; E, N = np.meshgrid(x, y); BOX = fig.BOX
    caja = (E >= BOX[0]) & (E <= BOX[1]) & (N >= BOX[2]) & (N <= BOX[3]); fs, cs = np.where(caja); sl = (slice(fs.min(), fs.max() + 1), slice(cs.min(), cs.max() + 1))
    ext = [x[sl[1]].min() - 5, x[sl[1]].max() + 5, y[sl[0]].min() - 5, y[sl[0]].max() + 5]
    vis = np.concatenate([M[k][sl][np.isfinite(M[k][sl])] for k in M]); vmin, vmax = float(np.percentile(vis, 2)), float(np.percentile(vis, 98))
    dv = dif[sl][np.isfinite(dif[sl])]; lim = float(np.percentile(np.abs(dv), 98))
    f, axs = plt.subplots(1, 3, figsize=(10.5, 3.6), sharex=True, sharey=True, constrained_layout=True)
    paneles = [(M["norte"], f"Wind from the north (n = {len(pilas['norte'])})", "viridis", vmin, vmax), (M["resto"], f"Other directions (n = {len(pilas['resto'])})", "viridis", vmin, vmax),
               (dif, "North minus other", "RdBu_r", -lim, lim)]
    for ax, (arr, tit, cm, lo, hi) in zip(axs, paneles):
        ax.set_facecolor("#E6E6E6"); im = ax.imshow(arr[sl], extent=ext, origin="upper", cmap=cm, vmin=lo, vmax=hi, interpolation="nearest", rasterized=True)
        ax.contour(x[sl[1]], y[sl[0]], agua[sl].astype(float), levels=[0.5], colors="k", linewidths=0.4); ax.set_title(tit, fontsize=8); ax.set_xlabel("Easting, UTM 17N (km)")
        ax.set_xticks(np.arange(361000, 365001, 1000)); ax.set_xticklabels([f"{v/1000:.0f}" for v in np.arange(361000, 365001, 1000)]); fig.escala(ax, ext[0] + 300, ext[2] + 250)
        cb = f.colorbar(im, ax=ax, shrink=0.75, extend="both", pad=0.02); cb.set_label("Median turbidity (FNU)" if cm == "viridis" else "Difference (FNU)", fontsize=6.5)
    axs[0].set_ylabel("Northing, UTM 17N (km)"); axs[0].set_yticks(np.arange(2556000, 2561001, 1000)); axs[0].set_yticklabels([f"{v/1000:.0f}" for v in np.arange(2556000, 2561001, 1000)])
    S = fig.SALIDA; f.savefig(f"{S}/fig_e2_mapas_viento_10m.pdf"); plt.close(f)
    with gzip.open(f"{S}/fig_e2_mapas_viento_10m.csv.gz", "wt", newline="") as fh:
        w = csv.writer(fh); w.writerow(["easting_m", "northing_m", "median_north_FNU", "median_other_FNU", "north_minus_other_FNU", "n_scenes_north", "n_scenes_other"])
        for i, j in zip(*np.where(caja & agua & (np.isfinite(M["norte"]) | np.isfinite(M["resto"])))):
            w.writerow([int(x[j]), int(y[i])] + ["" if not np.isfinite(t[i, j]) else round(float(t[i, j]), 3) for t in (M["norte"], M["resto"], dif)] + [int(C["norte"][i, j]), int(C["resto"][i, j])])
    print("mapas hechos; escalas", round(vmin, 2), round(vmax, 2), "dif +-", round(lim, 3), flush=True)


if __name__ == "__main__":
    main()
