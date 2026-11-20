"""Peticion 4, E5: distribucion de la profundidad de la carta, calientes frente a referencias (EXPLORATORIO).

    python scripts/45_e5_profundidad_focos.py                                  # 20 m
    VERTIDOS_PIXEL_M=10 python scripts/45_e5_profundidad_focos.py --resultados resultados_10m

Reglas en la fila del 20/11/2026 (peticion 4) de la secc. 14, escrita antes de calcular. Calientes = pixeles de la bahia con
z_c >= 3,5 y profundidad de la malla (como 23_batimetria.py). Referencias de cada caliente = pixeles de la bahia evaluables, a > 80 m
de cualquier caliente, con distancia a costa +-20 m y fraccion de tierra a 500 m +-0,10 (>= 30). Distribucion de referencias = union
con peso 1/n_k. Se calcula tambien la cifra de la secc. 25 (referencias sin emparejar) para reproducirla. IC 95 %: bootstrap de bloques de
200 x 200 m (2000, semilla 20261120). Salidas: e5_profundidad_focos_<res>m.json en --resultados; CSV, npz y PDF en
datos/no_publicar_carta1887/ (profundidad de la carta: no va a productos_publicos/, secc. 29.6).
"""
import os, sys, json, argparse, csv, importlib.util
import numpy as np
from scipy import ndimage
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "src"))
import anomalias, geo

plt.rcParams.update({"pdf.fonttype": 42, "font.family": "DejaVu Sans", "font.size": 7, "axes.linewidth": 0.6})


def carga(nombre):
    s = importlib.util.spec_from_file_location(nombre, os.path.join(AQUI, nombre + ".py"))
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


bat = carga("23_batimetria")
SEMILLA, N_BOOT, BLOQUE_M, MIN_BLOQUES = 20261120, 2000, 200, 5
TOL_D, TOL_F, LEJOS_M, MIN_REF, SOMERO = 20.0, 0.10, 80, 30, 2.0
P0, PASO, NB = -3.0, 0.05, 860                      # histograma fino para el bootstrap: -3 a 40 m en 0,05 m
BORDES_H = np.arange(0, 12.5, 0.5)                  # 0, 0,5, ..., 12
SALIDA = "datos/no_publicar_carta1887"
COL = {"seca": "#D55E00", "lluviosa": "#0072B2"}


def ibin(v):
    return np.clip(np.floor((np.asarray(v) - P0) / PASO + 1e-9).astype(int), 0, NB - 1)


def mediana_pond(v, w):
    o = np.argsort(v, kind="stable"); v, w = v[o], w[o]; c = np.cumsum(w)
    return float(v[np.searchsorted(c, 0.5 * c[-1])])


def mediana_hist(h):
    """Mediana de un histograma fino (interpolada dentro del intervalo)."""
    c = np.cumsum(h); j = int(np.searchsorted(c, 0.5 * c[-1]))
    previo = c[j - 1] if j > 0 else 0.0
    return P0 + PASO * (j + (0.5 * c[-1] - previo) / h[j])


def frac_somera(h):
    return float(h[:ibin(SOMERO)].sum() / h.sum())


def bloques(b):
    u, inv = np.unique(b, return_inverse=True)
    return u, np.split(np.argsort(inv, kind="stable"), np.cumsum(np.bincount(inv))[:-1])


def ic(a):
    return [round(float(np.percentile(a, 2.5)), 3), round(float(np.percentile(a, 97.5)), 3)]


def histograma_tabla(v, w, n_unicos=None):
    """Filas de histograma: '<0', 12 + 12 intervalos de 0,5 m (0-12) y '>12'; n, n ponderado, fraccion y ECDF."""
    tot = w.sum(); filas = []; ec = 0.0
    lim = [(-np.inf, 0.0)] + [(a, a + 0.5) for a in BORDES_H[:-1]] + [(12.0, np.inf)]
    for lo, hi in lim:
        m = (v >= lo) & (v < hi)
        n = int(m.sum()) if n_unicos is None else int(n_unicos[m].sum())
        fw = float(w[m].sum() / tot); ec += fw
        filas.append((lo, hi, n, float(w[m].sum()), fw, min(ec, 1.0)))
    return filas


def ecdf_en_bordes(v, w):
    tot = w.sum()
    return np.array([w[v < b].sum() / tot for b in BORDES_H[1:]])        # F(0,5) ... F(12)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--resultados", default="resultados"); a = ap.parse_args()
    res_m = int(geo.PIXEL_M); os.makedirs(SALIDA, exist_ok=True)
    cl = np.load(os.path.join(a.resultados, "climatologia.npz"))
    agua, bahia, dist = cl["agua"].astype(bool), cl["bahia"].astype(bool), cl["distancia_costa_m"]
    ft500, x, y = cl["f_tierra_500m"], cl["x"], cl["y"]
    E, N = np.meshgrid(x, y); prof = bat.profundidad_en_rejilla(E, N)
    bloque = np.floor(E / BLOQUE_M).astype(np.int64) * 100000 + np.floor(N / BLOQUE_M).astype(np.int64)
    r_px = int(round(LEJOS_M / geo.PIXEL_M)); rng = np.random.default_rng(SEMILLA)
    previo = json.load(open(os.path.join(a.resultados, f"batimetria_{res_m}m.json")))
    out = {"resolucion_m": res_m, "bloque_m": BLOQUE_M, "n_bootstrap": N_BOOT, "semilla": SEMILLA, "tolerancia_distancia_m": TOL_D,
           "tolerancia_f_tierra_500m": TOL_F, "min_referencias_por_caliente": MIN_REF, "distancia_lejos_m": LEJOS_M,
           "pixeles_bahia_con_profundidad": int((bahia & np.isfinite(prof)).sum()), "estaciones": {}}
    ecdfs, hist_filas = {}, []
    for est in ("seca", "lluviosa"):
        zc, ev = bat.zc_estacion(cl, est, agua, bahia, dist, ft500)
        cal_todos = (zc >= anomalias.Z_C_MIN) & ev
        # --- cifra de la secc. 25 recalculada con el mismo codigo (referencias sin emparejar)
        s25 = bat.comparar(cal_todos, prof, dist, bahia, ev, r_px)
        s25_prev = previo["estaciones"][est]["calientes"]
        cal = cal_todos & bahia & np.isfinite(prof)
        lejos = ~ndimage.binary_dilation(cal, iterations=r_px)
        ref = bahia & ev & np.isfinite(prof) & lejos & ~cal
        ph, dh, fh, bh = prof[cal], dist[cal], ft500[cal], bloque[cal]
        pr_, dr_, fr_, br_ = prof[ref], dist[ref], ft500[ref], bloque[ref]
        o = np.argsort(dr_, kind="stable"); pr_, dr_, fr_, br_ = pr_[o], dr_[o], fr_[o], br_[o]
        idr = np.flatnonzero(ref.ravel())[o]            # indice plano de cada referencia (ordenado por distancia)
        # --- emparejamiento por caliente
        filas_H, vals, pesos, usado, keep = [], [], [], np.zeros(pr_.size, bool), np.zeros(ph.size, bool)
        for k in range(ph.size):
            i0, i1 = np.searchsorted(dr_, [dh[k] - TOL_D, dh[k] + TOL_D])
            s = np.abs(fr_[i0:i1] - fh[k]) <= TOL_F
            if s.sum() < MIN_REF:
                continue
            v = pr_[i0:i1][s]; keep[k] = True; usado[i0:i1][s] = True
            hk = np.bincount(ibin(v), minlength=NB).astype(float); filas_H.append(hk / hk.sum())
            vals.append(v); pesos.append(np.full(v.size, 1.0 / v.size))
        H = np.array(filas_H); vals = np.concatenate(vals); pesos = np.concatenate(pesos)
        hv, hb = ph[keep], bh[keep]
        # unicidad de las referencias para el recuento por intervalo
        vu, wu_k = pr_[usado], None
        # peso por referencia unica: suma de 1/n_k sobre los calientes que la usan -> se acumula aparte
        wref = np.zeros(pr_.size)
        for k in np.flatnonzero(keep):
            i0, i1 = np.searchsorted(dr_, [dh[k] - TOL_D, dh[k] + TOL_D])
            s = np.abs(fr_[i0:i1] - fh[k]) <= TOL_F
            wref[i0:i1][s] += 1.0 / s.sum()
        wu = wref[usado]; vu = pr_[usado]
        # --- estadisticos exactos
        med_h, med_r = float(np.median(hv)), mediana_pond(vals, pesos)
        f_h, f_r = float((hv < SOMERO).mean()), float(pesos[vals < SOMERO].sum() / pesos.sum())
        # --- bootstrap por bloques de los calientes (con sus referencias emparejadas)
        ub, gr = bloques(hb); nb = len(gr)
        d = {"n_calientes_con_profundidad": int(cal.sum()), "n_calientes_emparejados": int(keep.sum()),
             "n_calientes_sin_referencias_suficientes": int(cal.sum() - keep.sum()), "n_referencias_unicas": int(usado.sum()),
             "n_bloques_calientes": int(nb), "n_bloques_referencias_unicas": int(np.unique(br_[usado]).size),
             "profundidades_negativas_calientes": int((hv < 0).sum()), "profundidades_negativas_referencias_peso": round(float(pesos[vals < 0].sum()), 2),
             "e5_emparejado": {"mediana_calientes_m": round(med_h, 3), "mediana_referencias_m": round(med_r, 3),
                               "fraccion_menos_2m_calientes": round(f_h, 4), "fraccion_menos_2m_referencias": round(f_r, 4)}}
        if nb >= MIN_BLOQUES:
            mh, mr, fh_, fr__ = [], [], [], []
            for _ in range(N_BOOT):
                idx = np.concatenate([gr[i] for i in rng.integers(0, nb, nb)])
                hsum = H[idx].sum(0)
                mh.append(np.median(hv[idx])); fh_.append((hv[idx] < SOMERO).mean())
                mr.append(mediana_hist(hsum)); fr__.append(frac_somera(hsum))
            mh, mr, fh_, fr__ = map(np.array, (mh, mr, fh_, fr__))
            d["e5_emparejado"].update({"ic95_mediana_calientes_m": ic(mh), "ic95_mediana_referencias_m": ic(mr), "ic95_diferencia_medianas_ref_menos_cal_m": ic(mr - mh),
                                       "ic95_fraccion_menos_2m_calientes": ic(fh_), "ic95_fraccion_menos_2m_referencias": ic(fr__)})
        else:
            d["e5_emparejado"]["ic95"] = None
        # --- cifra de la secc. 25 con IC (calientes: sus bloques; referencias sin emparejar: sus bloques)
        ph_all = ph
        ubr, grr = bloques(br_); Bh = np.array([np.bincount(ibin(pr_[g]), minlength=NB) for g in grr], float)
        ubc, grc = bloques(bh)
        s25n = {"mediana_calientes_m": round(float(np.median(ph_all)), 3), "mediana_referencias_m": round(float(np.median(pr_)), 3),
                "fraccion_menos_2m_calientes": round(float((ph_all < SOMERO).mean()), 4), "fraccion_menos_2m_referencias": round(float((pr_ < SOMERO).mean()), 4),
                "n_calientes": int(ph_all.size), "n_referencias": int(pr_.size), "n_bloques_calientes": int(len(grc)), "n_bloques_referencias": int(len(grr))}
        if len(grc) >= MIN_BLOQUES and len(grr) >= MIN_BLOQUES:
            a1, a2, a3, a4 = [], [], [], []
            for _ in range(N_BOOT):
                ic_ = np.concatenate([grc[i] for i in rng.integers(0, len(grc), len(grc))])
                hs = Bh[rng.integers(0, len(grr), len(grr))].sum(0)
                a1.append(np.median(ph_all[ic_])); a2.append((ph_all[ic_] < SOMERO).mean()); a3.append(mediana_hist(hs)); a4.append(frac_somera(hs))
            s25n.update({"ic95_mediana_calientes_m": ic(a1), "ic95_fraccion_menos_2m_calientes": ic(a2), "ic95_mediana_referencias_m": ic(a3), "ic95_fraccion_menos_2m_referencias": ic(a4)})
        d["secc25_recalculada_con_ic"] = s25n
        d["secc25_comparar"] = s25
        d["secc25_publicada_json"] = s25_prev
        d["secc25_diferencia_maxima_con_el_json_publicado"] = round(max(abs(s25[k] - s25_prev[k]) for k in s25_prev if isinstance(s25_prev[k], (int, float)) and k in s25), 6)
        # --- histogramas y ECDF
        for grupo, v, w, nu in (("hot", hv, np.ones(hv.size), None), ("reference_matched", vu, wu, np.ones(vu.size)), ("reference_sec25", pr_, np.ones(pr_.size), None)):
            for lo, hi, n, nw, fr, ec in histograma_tabla(v, w, nu):
                hist_filas.append({"resolution_m": res_m, "season": est, "group": grupo, "bin_lo_m": lo, "bin_hi_m": hi, "n_pixels": n, "weighted_n": round(nw, 4),
                                   "fraction": round(fr, 6), "ecdf": round(ec, 6)})
        Fh = ecdf_en_bordes(hv, np.ones(hv.size)); Fr = ecdf_en_bordes(vals, pesos)
        d["prediccion"] = {"mediana_calientes_menor": bool(med_h < med_r), "ecdf_calientes_mayor_o_igual_en_todos_los_bordes_0p5m": bool(np.all(Fh >= Fr - 1e-12)),
                           "ecdf_dif_min_cal_menos_ref": round(float((Fh - Fr).min()), 4), "ecdf_dif_max_cal_menos_ref": round(float((Fh - Fr).max()), 4),
                           "bordes_donde_falla_m": [round(float(b), 1) for b, f, r in zip(BORDES_H[1:], Fh, Fr) if f < r - 1e-12]}
        d["prediccion"]["cumple"] = d["prediccion"]["mediana_calientes_menor"] and d["prediccion"]["ecdf_calientes_mayor_o_igual_en_todos_los_bordes_0p5m"]
        out["estaciones"][est] = d
        ecdfs[est] = {"hot": (np.sort(hv), None), "ref": (vals, pesos)}
        print(est, json.dumps({k: d[k] for k in ("n_calientes_con_profundidad", "n_calientes_emparejados", "n_referencias_unicas", "n_bloques_calientes", "e5_emparejado", "secc25_recalculada_con_ic", "secc25_diferencia_maxima_con_el_json_publicado", "prediccion")}, ensure_ascii=False), flush=True)
    json.dump(out, open(os.path.join(a.resultados, f"e5_profundidad_focos_{res_m}m.json"), "w"), indent=1, ensure_ascii=False)
    with open(os.path.join(SALIDA, f"e5_histograma_profundidad_{res_m}m.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(hist_filas[0])); w.writeheader(); w.writerows(hist_filas)
    np.savez_compressed(os.path.join(SALIDA, f"e5_ecdf_{res_m}m.npz"),
                        **{f"{est}_{g}_{c}": arr for est in ecdfs for g in ("hot", "ref") for c, arr in zip(("v", "w"), ecdfs[est][g]) if arr is not None})
    # --- figura (cuando existen las dos resoluciones)
    ficheros = {r: os.path.join(SALIDA, f"e5_ecdf_{r}m.npz") for r in (20, 10)}
    if all(os.path.exists(f) for f in ficheros.values()):
        fig, ejes = plt.subplots(1, 2, figsize=(7.0, 2.9), sharey=True)
        for ax, r in zip(ejes, (20, 10)):
            z = np.load(ficheros[r])
            for est in ("seca", "lluviosa"):
                vh = z[f"{est}_hot_v"]; ax.step(vh, np.arange(1, vh.size + 1) / vh.size, where="post", color=COL[est], lw=1.1)
                vr, wr = z[f"{est}_ref_v"], z[f"{est}_ref_w"]; o = np.argsort(vr, kind="stable")
                ax.step(vr[o], np.cumsum(wr[o]) / wr.sum(), where="post", color=COL[est], lw=1.1, ls="--")
            ax.axvline(SOMERO, color="0.6", lw=0.5, ls=":"); ax.set_xlim(0, 12); ax.set_ylim(0, 1.0)
            ax.set_title(f"{r} m pixels", fontsize=7.5); ax.set_xlabel("Chart depth (m)")
            ax.spines[["top", "right"]].set_visible(False)
        ejes[0].set_ylabel("Cumulative fraction")
        h = [plt.Line2D([], [], color=COL["seca"], lw=1.1), plt.Line2D([], [], color=COL["lluviosa"], lw=1.1),
             plt.Line2D([], [], color="k", lw=1.1), plt.Line2D([], [], color="k", lw=1.1, ls="--")]
        ejes[1].legend(h, ["dry season", "wet season", "hot pixels", "matched references"], frameon=False, loc="lower right", fontsize=6.5)
        fig.tight_layout(); fig.savefig(os.path.join(SALIDA, "fig_e5_ecdf_profundidad.pdf"))
        os.makedirs("datos/previsualizaciones", exist_ok=True); fig.savefig("datos/previsualizaciones/fig_e5_ecdf_profundidad.png", dpi=200); plt.close(fig)
        print("figura escrita", flush=True)


if __name__ == "__main__":
    main()
