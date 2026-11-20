"""Peticion 4, E6: perfil de la senal de orilla y longitud de decaimiento (EXPLORATORIO).

    python scripts/46_e6_perfil_orilla.py --productos datos/productos                                      # 20 m
    VERTIDOS_PIXEL_M=10 python scripts/46_e6_perfil_orilla.py --productos datos/productos_10m --resultados resultados_10m

Reglas en la fila del 20/11/2026 (peticion 4) de la secc. 14. E6a: reproduce L de rho(SWIR 1610 nm) (45 m a 20 m, 28 m a 10 m; secc. 11.2/17/23) recalculando
el ajuste por escena con escenas.validez. E6b: misma ecuacion A exp(-d/L)+c ajustada a la turbidez de Dogliotti por intervalos de distancia a costa de
10 m (a 10 m) o 20 m (a 20 m), 0-400 m, version (i) todos los pixeles y (ii) sin los de < 80 m de un pixel caliente; condicion principal: pixeles validos
y fraccion de tierra a 500 m <= 0,5; sensibilidad: solo validos (la del ajuste publicado). Bootstrap de escenas 2000, semilla 20261120.
Con --solo-figura se lee e6_perfil_orilla_{20,10}m.json y se dibuja la figura de las dos resoluciones.
"""
import os, sys, json, argparse, csv, importlib.util, warnings
import numpy as np
from scipy import ndimage
from scipy.optimize import curve_fit
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "src"))
import anomalias, climatologia, escenas, geo
from adyacencia import _modelo

plt.rcParams.update({"pdf.fonttype": 42, "font.family": "DejaVu Sans", "font.size": 7, "axes.linewidth": 0.6})


def carga(nombre):
    s = importlib.util.spec_from_file_location(nombre, os.path.join(AQUI, nombre + ".py"))
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


SEMILLA, N_BOOT, D_MAX, N_MIN_BIN, N_MIN_ESC, R2_MIN, LEJOS_M, F_TIERRA_MAX = 20261120, 2000, 400.0, 10, 5, 0.85, 80, 0.5
COTAS_T = ([0.0, 10.0, 0.0], [200.0, 3000.0, 50.0])
CONDS = ("tierra_le_0.5", "solo_validos")
VERS = ("i_todos", "ii_sin_focos_80m")
COL = {"seca": "#D55E00", "lluviosa": "#0072B2"}
PUBLICO = "productos_publicos/figuras"


def ajuste(d, y, cotas=COTAS_T):
    ok = np.isfinite(y); d, y = d[ok], y[ok]
    if d.size < 5:
        return None
    p0 = [max(y[0] - y[-1], 1e-3), 150.0, float(y[-1])]
    p0 = [min(max(p, lo), hi) for p, lo, hi in zip(p0, cotas[0], cotas[1])]
    try:
        popt, _ = curve_fit(_modelo, d, y, p0=p0, maxfev=20000, bounds=cotas)
    except Exception:
        return None
    ss = np.sum((y - y.mean()) ** 2); r = y - _modelo(d, *popt)
    return {"A": float(popt[0]), "L": float(popt[1]), "c": float(popt[2]), "r2": float(1 - np.sum(r ** 2) / ss) if ss > 0 else np.nan}


def ic(v):
    v = np.asarray(v, float); v = v[np.isfinite(v)]
    return [round(float(np.percentile(v, 2.5)), 2), round(float(np.percentile(v, 97.5)), 2)] if v.size else None


def boot_mediana(L, rng):
    L = np.asarray(L, float); L = L[np.isfinite(L)]
    if L.size < N_MIN_ESC:
        return None
    return ic(np.median(L[rng.integers(0, L.size, (N_BOOT, L.size))], axis=1))


def perfil_resumen(P):
    """Mediana e IQR entre escenas por intervalo (>= N_MIN_ESC escenas con dato)."""
    n = np.isfinite(P).sum(0); ok = n >= N_MIN_ESC
    if P.shape[0] == 0:
        z = np.full(P.shape[1], np.nan); return {"n_escenas": n, "mediana": z, "q25": z, "q75": z}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        f = lambda q: np.where(ok, np.nanpercentile(P, q, axis=0), np.nan)
        return {"n_escenas": n, "mediana": f(50), "q25": f(25), "q75": f(75)}


def ajuste_perfil_mediano(P, centros, rng):
    r = perfil_resumen(P); a = ajuste(centros, r["mediana"])
    if a is None:
        return None
    Ls = []
    for _ in range(N_BOOT):
        Q = P[rng.integers(0, P.shape[0], P.shape[0])]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            q = np.nanmedian(np.where(np.isfinite(Q).sum(0) >= N_MIN_ESC, Q, np.nan), axis=0)
        f = ajuste(centros, q); Ls.append(f["L"] if f else np.nan)
    return {"L_m": round(a["L"], 2), "A_FNU": round(a["A"], 3), "c_FNU": round(a["c"], 3), "r2": round(a["r2"], 3), "ic95_L_m": ic(Ls), "n_escenas": int(P.shape[0])}


def perfiles_escena(carpeta, aceptadas, agua, dist, ft500, hot_cerca, bins, filtro=None):
    """Recorre las escenas aceptadas: perfiles de turbidez por intervalo (cond x version) y ajuste de rho_SWIR recalculado."""
    filas, perf = [], {(c, v): [] for c in CONDS for v in VERS}
    nb = len(bins) - 1
    for r in escenas.listar(carpeta):
        e = escenas.cargar(r)
        if (aceptadas is not None and e["l1c"] not in aceptadas) or (filtro is not None and e["fecha"].date().isoformat() not in filtro):
            continue
        est = climatologia.estacion_de(e["fecha"])
        v, info = escenas.validez(e, agua, dist)
        t = e["turbidez_dogliotti"]
        reg = {"fecha": e["fecha"].date().isoformat(), "l1c": e["l1c"], "estacion": est, "L_swir": info["L"], "A_swir": info["A"], "r2_swir": info["r2"]}
        for c in CONDS:
            m0 = v & (ft500 <= F_TIERRA_MAX) if c == "tierra_le_0.5" else v
            for ver in VERS:
                m = m0 & ~hot_cerca[est] if ver == "ii_sin_focos_80m" else m0
                k = np.digitize(dist[m], bins) - 1; tv = t[m]; fila = np.full(nb, np.nan); n = np.zeros(nb, int)
                for j in range(nb):
                    s = k == j; n[j] = int(s.sum())
                    if n[j] >= N_MIN_BIN:
                        fila[j] = float(np.median(tv[s]))
                perf[(c, ver)].append((fila, n))
        filas.append(reg); print(reg["fecha"], est, round(info["L"], 1) if np.isfinite(info["L"]) else "nan", flush=True)
    return filas, {k: (np.array([p[0] for p in v]), np.array([p[1] for p in v])) for k, v in perf.items()}


def resumir(filas, perf, centros, rng):
    out = {"swir": {}, "turbidez": {}}
    for sel_nombre, sel in (("ambas", lambda f: True), ("seca", lambda f: f["estacion"] == "seca"), ("lluviosa", lambda f: f["estacion"] == "lluviosa")):
        idx = np.array([i for i, f in enumerate(filas) if sel(f)])
        L = np.array([filas[i]["L_swir"] for i in idx]); r2 = np.array([filas[i]["r2_swir"] for i in idx]); ok = np.isfinite(r2) & (r2 > R2_MIN)
        out["swir"][sel_nombre] = {"n_escenas": int(idx.size), "n_r2_mayor_085": int(ok.sum()),
                                   "L_m_mediana": round(float(np.median(L[ok])), 2) if ok.any() else None,
                                   "L_m_p10_p50_p90": [round(float(q), 2) for q in np.percentile(L[ok], [10, 50, 90])] if ok.any() else None,
                                   "ic95_L_m_bootstrap_escenas": boot_mediana(L[ok], rng)}
        for (c, ver), (P, N) in perf.items():
            Ps = P[idx]; Ls, r2s = [], []
            for fila in Ps:
                f = ajuste(centros, fila); Ls.append(f["L"] if f else np.nan); r2s.append(f["r2"] if f else np.nan)
            Ls, r2s = np.array(Ls), np.array(r2s); oks = np.isfinite(r2s) & (r2s > R2_MIN)
            d = {"n_escenas": int(idx.size), "n_ajustes_validos": int(np.isfinite(Ls).sum()), "n_r2_mayor_085": int(oks.sum()),
                 "L_m_mediana_escenas_r2_mayor_085": round(float(np.median(Ls[oks])), 2) if oks.any() else None,
                 "L_m_p10_p50_p90": [round(float(q), 2) for q in np.percentile(Ls[oks], [10, 50, 90])] if oks.any() else None,
                 "ic95_L_m_bootstrap_escenas": boot_mediana(Ls[oks], rng),
                 "L_m_mediana_todas_las_escenas_con_ajuste": round(float(np.nanmedian(Ls)), 2) if np.isfinite(Ls).any() else None,
                 "ajuste_al_perfil_mediano": ajuste_perfil_mediano(Ps, centros, rng) if sel_nombre != "ambas" and idx.size >= N_MIN_ESC else None}
            out["turbidez"].setdefault(f"{c}|{ver}", {})[sel_nombre] = d
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--productos", default="datos/productos"); ap.add_argument("--resultados", default="resultados")
    ap.add_argument("--solo-figura", action="store_true"); a = ap.parse_args()
    if a.solo_figura:
        return figura()
    res_m = int(geo.PIXEL_M); ancho = 10.0 if res_m == 10 else 20.0
    bins = np.arange(0, D_MAX + ancho, ancho); centros = (bins[:-1] + bins[1:]) / 2
    bat = carga("23_batimetria")
    cl = np.load(os.path.join(a.resultados, "climatologia.npz"))
    agua, bahia, dist, ft500 = cl["agua"].astype(bool), cl["bahia"].astype(bool), cl["distancia_costa_m"], cl["f_tierra_500m"]
    aceptadas = set(str(p) for p in cl["productos_l1c"]); r_px = int(round(LEJOS_M / geo.PIXEL_M)); rng = np.random.default_rng(SEMILLA)
    hot_cerca, n_hot = {}, {}
    for est in ("seca", "lluviosa"):
        zc, ev = bat.zc_estacion(cl, est, agua, bahia, dist, ft500)
        cal = (zc >= anomalias.Z_C_MIN) & ev; n_hot[est] = int(cal.sum())
        hot_cerca[est] = ndimage.binary_dilation(cal, iterations=r_px)
    print("calientes (toda el agua evaluable):", n_hot, flush=True)
    filas, perf = perfiles_escena(a.productos, aceptadas, agua, dist, ft500, hot_cerca, bins)
    # --- comparacion con escenas_qc.csv (E6a)
    qc = {r["producto_l1c"]: r for r in csv.DictReader(open(os.path.join(a.resultados, "escenas_qc.csv")))}
    dif = [abs(f["L_swir"] - float(qc[f["l1c"]]["adyacencia_L_m"])) for f in filas if np.isfinite(f["L_swir"]) and np.isfinite(float(qc[f["l1c"]]["adyacencia_L_m"]))]
    pub = json.load(open(os.path.join(a.resultados, "climatologia.json")))["adyacencia_r2_mayor_085"]
    out = {"resolucion_m": res_m, "ancho_intervalo_m": ancho, "d_max_m": D_MAX, "n_min_px_por_intervalo": N_MIN_BIN, "n_min_escenas_por_intervalo": N_MIN_ESC,
           "r2_min": R2_MIN, "f_tierra_500m_max": F_TIERRA_MAX, "n_bootstrap": N_BOOT, "semilla": SEMILLA, "n_escenas_aceptadas_procesadas": len(filas),
           "n_calientes_por_estacion": n_hot, "condicion_publicada_del_ajuste_swir": "solo pixeles validos de escenas.validez (sin condicion de fraccion de tierra)",
           "publicado_climatologia_json": pub,
           "reproduccion_L_swir_por_escena": {"n_comparadas": len(dif), "diferencia_maxima_m": round(float(max(dif)), 6) if dif else None},
           "centros_intervalo_m": [float(c) for c in centros]}
    out.update(resumir(filas, perf, centros, rng))
    out["perfiles"] = {}
    for (c, ver), (P, N) in perf.items():
        out["perfiles"][f"{c}|{ver}"] = {}
        for est in ("seca", "lluviosa"):
            idx = np.array([i for i, f in enumerate(filas) if f["estacion"] == est]); r = perfil_resumen(P[idx])
            out["perfiles"][f"{c}|{ver}"][est] = {"n_escenas_por_intervalo": r["n_escenas"].tolist(), **{k: [None if not np.isfinite(x) else round(float(x), 4) for x in r[k]] for k in ("mediana", "q25", "q75")}}
    # --- RAdCor (solo 20 m: la salida existe en las 10 escenas secas, ventana ampliada)
    if res_m == 20 and os.path.isdir("datos/productos_radcor_ampliada_20m_recorte"):
        rc_json = json.load(open(os.path.join(a.resultados, "radcor_subconjunto_20m.json")))
        f_rc = {e["fecha"][:10] for e in rc_json["escenas"]}      # se empareja por fecha (el campo producto_l1c de los recortes RAdCor no lleva .SAFE)
        filas_rc, perf_rc = perfiles_escena("datos/productos_radcor_ampliada_20m_recorte", None, agua, dist, ft500, hot_cerca, bins, filtro=f_rc)
        orden_rc = {f["fecha"]: i for i, f in enumerate(filas_rc)}
        idx_dsf = np.array(sorted([i for i, f in enumerate(filas) if f["fecha"] in f_rc], key=lambda i: orden_rc[filas[i]["fecha"]]))
        rcres = {"n_escenas_radcor": len(filas_rc), "n_escenas_dsf_mismas": int(idx_dsf.size), "perfiles": {}, "L": {}}
        for (c, ver) in perf:
            Pd, Pr = perf[(c, ver)][0][idx_dsf], perf_rc[(c, ver)][0]
            for nom, P in (("dsf", Pd), ("radcor", Pr)):
                r = perfil_resumen(P)
                rcres["perfiles"][f"{c}|{ver}|{nom}"] = {"n_escenas_por_intervalo": r["n_escenas"].tolist(), **{k: [None if not np.isfinite(x) else round(float(x), 4) for x in r[k]] for k in ("mediana", "q25", "q75")}}
                rcres["L"][f"{c}|{ver}|{nom}"] = ajuste_perfil_mediano(P, centros, rng)
        rcres["L_swir_mediana_m"] = {"dsf": round(float(np.nanmedian([filas[i]["L_swir"] for i in idx_dsf])), 2), "radcor": round(float(np.nanmedian([f["L_swir"] for f in filas_rc])), 2)}
        out["radcor_10_escenas_secas"] = rcres
    json.dump(out, open(os.path.join(a.resultados, f"e6_perfil_orilla_{res_m}m.json"), "w"), indent=1, ensure_ascii=False)
    # --- perfiles por escena (condicion principal)
    with open(os.path.join(a.resultados, f"e6_perfiles_escena_{res_m}m.csv"), "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["date", "season", "version", "bin_lo_m", "bin_hi_m", "n_px", "median_turbidity_FNU"])
        for ver in VERS:
            P, N = perf[("tierra_le_0.5", ver)]
            for i, f in enumerate(filas):
                for j in range(len(centros)):
                    w.writerow([f["fecha"], f["estacion"], ver, bins[j], bins[j + 1], int(N[i, j]), "" if not np.isfinite(P[i, j]) else round(float(P[i, j]), 4)])
    print(json.dumps({"swir": out["swir"], "reproduccion": out["reproduccion_L_swir_por_escena"], "turb_principal_i": out["turbidez"]["tierra_le_0.5|i_todos"],
                      "turb_principal_ii": out["turbidez"]["tierra_le_0.5|ii_sin_focos_80m"]}, ensure_ascii=False, indent=1), flush=True)
    if all(os.path.exists(os.path.join(d, f"e6_perfil_orilla_{r}m.json")) for d, r in (("resultados", 20), ("resultados_10m", 10))):
        figura()


def figura():
    J = {20: json.load(open("resultados/e6_perfil_orilla_20m.json")), 10: json.load(open("resultados_10m/e6_perfil_orilla_10m.json"))}
    os.makedirs(PUBLICO, exist_ok=True); filas_csv = []
    fig, ejes = plt.subplots(1, 3, figsize=(7.2, 2.7), sharey=False)
    X_MAX = 200
    for ax, r in zip(ejes[:2], (20, 10)):
        j = J[r]; cen = np.array(j["centros_intervalo_m"]); px = float(r)
        for c in (1, 2, 3):      # la distancia es al centro del pixel de tierra mas cercano: el primer anillo de agua esta a 1 pixel
            ax.axvline(c * px, color="0.55", lw=0.6, ls=":", zorder=0)
            ax.text(c * px, 1.01, f"{c}", transform=ax.get_xaxis_transform(), ha="center", va="bottom", fontsize=5.5, color="0.35")
        ax.text(0.0, 1.075, "pixels:", transform=ax.get_xaxis_transform(), ha="right", va="bottom", fontsize=5.5, color="0.35")
        for est in ("seca", "lluviosa"):
            for ver, ls in (("i_todos", "-"), ("ii_sin_focos_80m", "--")):
                p = j["perfiles"][f"tierra_le_0.5|{ver}"][est]
                med, q25, q75 = (np.array([np.nan if x is None else x for x in p[k]], float) for k in ("mediana", "q25", "q75"))
                if ver == "i_todos":
                    ax.fill_between(cen, q25, q75, color=COL[est], alpha=0.18, lw=0)
                ax.plot(cen, med, color=COL[est], ls=ls, lw=1.0)
                for b in range(cen.size):
                    filas_csv.append({"resolution_m": r, "season": est, "version": ver, "correction": "DSF", "bin_center_m": cen[b], "n_scenes": p["n_escenas_por_intervalo"][b],
                                      "median_FNU": "" if not np.isfinite(med[b]) else round(float(med[b]), 4), "q25_FNU": "" if not np.isfinite(q25[b]) else round(float(q25[b]), 4),
                                      "q75_FNU": "" if not np.isfinite(q75[b]) else round(float(q75[b]), 4)})
        ax.set_xlim(0, X_MAX); ax.set_title(f"{r} m", fontsize=7.5, pad=10); ax.set_xlabel("Distance to shore (m)"); ax.spines[["top", "right"]].set_visible(False)
    ejes[0].set_ylabel("Turbidity (FNU), median and IQR across scenes")
    h = [plt.Line2D([], [], color=COL["seca"]), plt.Line2D([], [], color=COL["lluviosa"]), plt.Line2D([], [], color="k"), plt.Line2D([], [], color="k", ls="--")]
    ejes[1].legend(h, ["dry", "wet", "all water", "excl. <80 m from hot pixels"], frameon=False, fontsize=5.5, loc="upper right")
    ax = ejes[2]; rc = J[20].get("radcor_10_escenas_secas")
    if rc:
        cen = np.array(J[20]["centros_intervalo_m"])
        for nom, col, lab in (("dsf", "0.35", "DSF"), ("radcor", "#CC79A7", "RAdCor")):
            p = rc["perfiles"][f"tierra_le_0.5|i_todos|{nom}"]
            med, q25, q75 = (np.array([np.nan if x is None else x for x in p[k]], float) for k in ("mediana", "q25", "q75"))
            ax.fill_between(cen, q25, q75, color=col, alpha=0.18, lw=0); ax.plot(cen, med, color=col, lw=1.0, label=lab)
            for b in range(cen.size):
                filas_csv.append({"resolution_m": 20, "season": "dry (10 scenes)", "version": "i_todos", "correction": lab, "bin_center_m": cen[b], "n_scenes": p["n_escenas_por_intervalo"][b],
                                  "median_FNU": "" if not np.isfinite(med[b]) else round(float(med[b]), 4), "q25_FNU": "" if not np.isfinite(q25[b]) else round(float(q25[b]), 4),
                                  "q75_FNU": "" if not np.isfinite(q75[b]) else round(float(q75[b]), 4)})
        ax.set_xlim(0, X_MAX); ax.set_title("20 m, dry, same 10 scenes", fontsize=7.5, pad=10); ax.set_xlabel("Distance to shore (m)"); ax.legend(frameon=False, fontsize=6)
        ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(); fig.savefig(os.path.join(PUBLICO, "fig_e6_perfil_orilla.pdf"))
    os.makedirs("datos/previsualizaciones", exist_ok=True); fig.savefig("datos/previsualizaciones/fig_e6_perfil_orilla.png", dpi=200); plt.close(fig)
    with open(os.path.join(PUBLICO, "fig_e6_perfil_orilla.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(filas_csv[0])); w.writeheader(); w.writerows(filas_csv)
    print("figura y CSV escritos", flush=True)


if __name__ == "__main__":
    main()
