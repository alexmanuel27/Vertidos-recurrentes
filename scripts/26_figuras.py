"""Figuras del articulo a 10 m (EXPLORATORIO): climatologia, perfil de los brazos y focos cronicos.

    VERTIDOS_PIXEL_M=10 python scripts/26_figuras.py --productos datos/productos_10m --resultados resultados_10m

Definido en la fila del 17/11/2026 de la secc. 14 (peticion del chat del articulo), antes de calcularlo.
Salidas en productos_publicos/figuras/: fig_a_climatologia_10m.pdf (+ .csv.gz), fig_b_perfil_brazos.pdf (+ .csv),
fig_c_focos_10m.pdf (+ .csv), NOTA_pies_de_figura.txt. Paleta Okabe-Ito / viridis (segura para daltonismo).
Eje de cada brazo: camino mas corto por el agua desde la entrada del canal (BOCA de 09_malla.py) hasta el pixel mas
lejano de la zona; corredor de +-150 m; coordenada = distancia geodesica por el agua desde la entrada del canal.
"""
import os, sys, json, argparse, csv, gzip, importlib.util
import numpy as np
from scipy import ndimage
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra
import matplotlib, matplotlib.colors
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "src"))
import anomalias, climatologia, escenas, geo, persistencia

plt.rcParams.update({"pdf.fonttype": 42, "font.family": "DejaVu Sans", "font.size": 7, "axes.linewidth": 0.6})
BOX = (360000.0, 365000.0, 2555900.0, 2561900.0)   # E min, E max, N min, N max (UTM 17N): bahia, canal y algo de mar
BOCA = (361000.0, 2560900.0)
ANCHO_CORREDOR_M, BIN_M, N_MIN_PX_BIN, N_BOOT, SEMILLA = 150, 250, 20, 2000, 20261117
OKABE = {"atares": "#D55E00", "guasabacoa": "#0072B2"}
SALIDA = "productos_publicos/figuras"


def cargar(nombre):
    spec = importlib.util.spec_from_file_location(nombre, os.path.join(AQUI, nombre + ".py"))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def grafo(mask, px):
    H, W = mask.shape; ids = -np.ones(mask.shape, np.int64); ids[mask] = np.arange(int(mask.sum()))
    r, c, w = [], [], []
    for di, dj, wt in ((0, 1, px), (1, 0, px), (1, 1, px * 2 ** .5), (1, -1, px * 2 ** .5)):
        j0, j1 = (slice(0, W - dj), slice(dj, W)) if dj >= 0 else (slice(-dj, W), slice(0, W + dj))
        a, b = ids[0:H - di, j0], ids[di:H, j1]; ok = (a >= 0) & (b >= 0)
        r.append(a[ok]); c.append(b[ok]); w.append(np.full(int(ok.sum()), wt))
    r, c, w = np.concatenate(r), np.concatenate(c), np.concatenate(w); n = int(mask.sum())
    return csr_matrix((w, (r, c)), shape=(n, n)), ids


def escala(ax, x0, y0, largo=1000):
    ax.plot([x0, x0 + largo], [y0, y0], "k-", lw=1.4, solid_capstyle="butt"); ax.text(x0 + largo / 2, y0 + 90, "1 km", ha="center", fontsize=6)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--productos", default="datos/productos_10m"); ap.add_argument("--resultados", default="resultados_10m")
    a = ap.parse_args()
    assert geo.PIXEL_M == 10, "usar VERTIDOS_PIXEL_M=10"
    os.makedirs(SALIDA, exist_ok=True)
    grad, bat, rep = cargar("24_gradiente"), cargar("23_batimetria"), cargar("21_replicacion")
    cl = np.load(os.path.join(a.resultados, "climatologia.npz"))
    agua, bahia, dist = cl["agua"].astype(bool), cl["bahia"].astype(bool), cl["distancia_costa_m"]
    ft500, x, y = cl["f_tierra_500m"], cl["x"], cl["y"]
    E, N = np.meshgrid(x, y)
    caja = (E >= BOX[0]) & (E <= BOX[1]) & (N >= BOX[2]) & (N <= BOX[3])
    fs, cs = np.where(caja); sl = (slice(fs.min(), fs.max() + 1), slice(cs.min(), cs.max() + 1))
    ext = [x[sl[1]].min() - 5, x[sl[1]].max() + 5, y[sl[0]].min() - 5, y[sl[0]].max() + 5]
    pts = {r["punto"]: r for r in csv.DictReader(open("resultados/campo/clave.csv"))}
    from pyproj import Transformer
    T = Transformer.from_crs(4326, 32617, always_xy=True)
    P = {k: T.transform(float(v["lon"]), float(v["lat"])) for k, v in pts.items()}
    # ---------- a: climatologia
    ev = {est: cl[f"{est}_evaluable"].astype(bool) for est in ("seca", "lluviosa")}
    med = {est: np.where(ev[est] & agua, cl[f"{est}_mediana"], np.nan) for est in ev}
    todos = np.concatenate([med[e][sl][np.isfinite(med[e][sl])] for e in med])
    vmin, vmax = float(np.percentile(todos, 2)), float(np.percentile(todos, 98))
    fig, axs = plt.subplots(1, 2, figsize=(7.5, 3.5), sharex=True, sharey=True, constrained_layout=True)
    for ax, est, tit in zip(axs, ("seca", "lluviosa"), ("Dry season (Nov-Apr)", "Wet season (May-Oct)")):
        ax.set_facecolor("#E6E6E6")
        im = ax.imshow(med[est][sl], extent=ext, origin="upper", cmap="viridis", vmin=vmin, vmax=vmax, interpolation="nearest", rasterized=True)
        ax.contour(x[sl[1]], y[sl[0]], agua[sl].astype(float), levels=[0.5], colors="k", linewidths=0.4)
        ax.set_title(tit, fontsize=8); ax.set_xlabel("Easting, UTM 17N (km)")
        ax.set_xticks(np.arange(361000, 365001, 1000)); ax.set_xticklabels([f"{v/1000:.0f}" for v in np.arange(361000, 365001, 1000)])
        escala(ax, ext[0] + 300, ext[2] + 250)
    axs[0].set_ylabel("Northing, UTM 17N (km)"); axs[0].set_yticks(np.arange(2556000, 2561001, 1000))
    axs[0].set_yticklabels([f"{v/1000:.0f}" for v in np.arange(2556000, 2561001, 1000)])
    cb = fig.colorbar(im, ax=axs, shrink=0.8, extend="both", pad=0.02); cb.set_label("Median turbidity, 10 m (FNU)")
    fig.savefig(f"{SALIDA}/fig_a_climatologia_10m.pdf"); plt.close(fig)
    with gzip.open(f"{SALIDA}/fig_a_climatologia_10m.csv.gz", "wt", newline="") as fh:
        w = csv.writer(fh); w.writerow(["easting_m", "northing_m", "median_turbidity_dry_FNU", "median_turbidity_wet_FNU"])
        for i, j in zip(*np.where(caja & agua & (np.isfinite(med["seca"]) | np.isfinite(med["lluviosa"])))):
            w.writerow([int(x[j]), int(y[i]), "" if not np.isfinite(med["seca"][i, j]) else round(float(med["seca"][i, j]), 3),
                        "" if not np.isfinite(med["lluviosa"][i, j]) else round(float(med["lluviosa"][i, j]), 3)])
    print("a hecho; escala", round(vmin, 2), round(vmax, 2), flush=True)
    # ---------- ejes de los brazos (geodesica por el agua desde la entrada del canal)
    z = grad.zonas(cl)
    cerca_boca = np.hypot(E - BOCA[0], N - BOCA[1]) <= 1500
    cuerpo = caja & agua & (bahia | cerca_boca)
    G, ids = grafo(cuerpo, geo.PIXEL_M)
    d2 = np.where(cuerpo, np.hypot(E - BOCA[0], N - BOCA[1]), np.inf); src = ids[np.unravel_index(np.argmin(d2), d2.shape)]
    dg_v, pred = dijkstra(G, directed=False, indices=src, return_predecessors=True)
    dg = np.full(agua.shape, np.nan); dg[cuerpo] = dg_v[ids[cuerpo]]
    inv = np.zeros(int(cuerpo.sum()), np.int64); inv_f, inv_c = np.where(cuerpo); inv = (inv_f, inv_c)
    corr, largo = {}, {}
    for brazo in ("atares", "guasabacoa"):
        zz = np.where((z == brazo) & cuerpo & np.isfinite(dg), dg, -1); cabeza = np.unravel_index(np.argmax(zz), zz.shape)
        nodo, cam = int(ids[cabeza]), np.zeros(agua.shape, bool)
        while nodo >= 0 and nodo != src:
            cam[inv_f[nodo], inv_c[nodo]] = True; nodo = int(pred[nodo])
        corr[brazo] = cuerpo & (ndimage.distance_transform_edt(~cam) * geo.PIXEL_M <= ANCHO_CORREDOR_M)
        largo[brazo] = float(zz[cabeza]); print(brazo, "cabeza", float(x[cabeza[1]]), float(y[cabeza[0]]), "largo m", round(largo[brazo]), "px corredor", int(corr[brazo].sum()), flush=True)
    bordes = np.arange(0, max(largo.values()) + BIN_M, BIN_M); centros = (bordes[:-1] + bordes[1:]) / 2
    # ---------- b: perfil por escena
    acept = set(str(p) for p in cl["productos_l1c"]); filas = []
    for r in escenas.listar(a.productos):
        e = escenas.cargar(r)
        if e["l1c"] not in acept:
            continue
        v, _ = escenas.validez(e, agua, dist); t = np.where(v, e["turbidez_dogliotti"], np.nan)
        f = {"estacion": climatologia.estacion_de(e["fecha"]), "perfil": {}}
        for brazo in corr:
            pr = np.full(centros.size, np.nan)
            for k in range(centros.size):
                m = corr[brazo] & (dg >= bordes[k]) & (dg < bordes[k + 1]); s = t[m & np.isfinite(t)]
                if s.size >= N_MIN_PX_BIN:
                    pr[k] = np.median(s)
            f["perfil"][brazo] = pr
        filas.append(f)
    print("escenas perfil", len(filas), flush=True)
    rng = np.random.default_rng(SEMILLA); salida_b = []
    fig, axs = plt.subplots(1, 2, figsize=(7.5, 2.8), sharey=True, constrained_layout=True)
    for ax, est, tit in zip(axs, ("seca", "lluviosa"), ("Dry season", "Wet season")):
        fe = [f for f in filas if f["estacion"] == est]
        for brazo, nom in (("atares", "Atares (SW arm)"), ("guasabacoa", "Guasabacoa (S arm)")):
            M = np.array([f["perfil"][brazo] for f in fe]); m_, lo_, hi_ = [], [], []
            for k in range(centros.size):
                col = M[:, k]; col = col[np.isfinite(col)]
                if col.size < 5 or bordes[k] > largo[brazo]:
                    m_.append(np.nan); lo_.append(np.nan); hi_.append(np.nan); continue
                bs = np.median(col[rng.integers(0, col.size, (N_BOOT, col.size))], axis=1)
                m_.append(float(np.median(col))); lo_.append(float(np.percentile(bs, 2.5))); hi_.append(float(np.percentile(bs, 97.5)))
                salida_b.append([brazo, est, int(centros[k]), round(m_[-1], 3), round(lo_[-1], 3), round(hi_[-1], 3), int(col.size)])
            ax.plot(centros / 1000, m_, color=OKABE[brazo], lw=1.2, label=nom)
            ax.fill_between(centros / 1000, lo_, hi_, color=OKABE[brazo], alpha=0.25, lw=0)
        ax.set_title(tit, fontsize=8); ax.set_xlabel("Distance along arm axis from the channel entrance (km)")
    axs[0].set_ylabel("Turbidity, median across scenes (FNU)"); axs[0].legend(frameon=False, fontsize=6.5, loc="upper left")
    fig.savefig(f"{SALIDA}/fig_b_perfil_brazos.pdf"); plt.close(fig)
    with open(f"{SALIDA}/fig_b_perfil_brazos.csv", "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["arm", "season", "bin_center_m", "median_FNU", "ci95_low_FNU", "ci95_high_FNU", "n_scenes"]); w.writerows(salida_b)
    print("b hecho", flush=True)
    # ---------- c: focos con replicacion y profundidad de la carta de 1887
    prof = bat.profundidad_en_rejilla(E, N)
    zs, evs = {}, {}
    for est in ("seca", "lluviosa"):
        zs[est], evs[est] = bat.zc_estacion(cl, est, agua, bahia, dist, ft500)
    cache = os.path.join(a.resultados, "zc_mitades.npz")
    cubos = {"A": [], "B": []}; fechas = {"A": [], "B": []}
    if not os.path.exists(cache):
        for r in escenas.listar(a.productos):
            e = escenas.cargar(r)
            if e["l1c"] not in acept:
                continue
            v, _ = escenas.validez(e, agua, dist); m = "A" if e["fecha"].year <= 2020 else "B"
            cubos[m].append(np.where(v, e["turbidez_dogliotti"], np.nan).astype(np.float32)); fechas[m].append(e["fecha"])
        zh = {m: rep.zc_mitad(np.stack(cubos[m]), fechas[m], agua, bahia, dist, ft500) for m in "AB"}
        np.savez_compressed(cache, **{f"{m}_{est}_{k}": zh[m][est][i] for m in "AB" for est in ("seca", "lluviosa") for i, k in enumerate(("z", "ev"))})
    zc_ = np.load(cache); r_px = int(round(80 / geo.PIXEL_M)); disco = persistencia._disco(r_px)
    fig, axs = plt.subplots(1, 2, figsize=(7.5, 4.8), sharex=True, sharey=True, constrained_layout=True)
    col = {0: "#999999", 1: "#E69F00", 2: "#0072B2"}; salida_c = []
    z2 = np.where(np.isfinite(prof), prof, np.nan)
    for ax, est, tit in zip(axs, ("seca", "lluviosa"), ("Dry season", "Wet season")):
        ax.set_facecolor("#E6E6E6"); ax.imshow(np.where(agua, 1.0, np.nan)[sl], extent=ext, origin="upper", cmap=matplotlib.colors.ListedColormap(["#FFFFFF"]), vmin=0, vmax=1, rasterized=True)
        ax.contour(x[sl[1]], y[sl[0]], np.ma.masked_invalid(z2[sl]), levels=[2.0], colors="#56B4E9", linewidths=0.6)
        ax.contour(x[sl[1]], y[sl[0]], agua[sl].astype(float), levels=[0.5], colors="k", linewidths=0.4)
        hot = (zs[est] >= anomalias.Z_C_MIN) & evs[est]; gr = persistencia.grupos(hot)
        cerca = {m: ndimage.binary_dilation((zc_[f"{m}_{est}_z"] >= anomalias.Z_C_MIN) & zc_[f"{m}_{est}_ev"].astype(bool), structure=disco) for m in "AB"}
        for k, g in enumerate(gr):
            ij = np.array(g["pixeles"]); cx, cy = float(x[ij[:, 1]].mean()), float(y[ij[:, 0]].mean())
            if not (BOX[0] <= cx <= BOX[1] and BOX[2] <= cy <= BOX[3]):
                continue
            rA, rB = bool(cerca["A"][tuple(ij.T)].any()), bool(cerca["B"][tuple(ij.T)].any()); n = int(rA) + int(rB)
            pp = prof[np.hypot(E - cx, N - cy) <= 80]; pp = pp[np.isfinite(pp)]; dm = float(np.median(pp)) if pp.size else None
            mk = "^" if dm is None else ("o" if dm < 2.0 else "s")
            ax.scatter([cx], [cy], s=8 + 3.0 * len(ij) ** 0.5, c=col[n], marker=mk, edgecolors="k", linewidths=0.3, zorder=3)
            salida_c.append([est, k, int(cx), int(cy), len(ij), round(float(np.nanmax(zs[est][tuple(ij.T)])), 2), int(rA), int(rB), n,
                             "" if dm is None else round(dm, 2), int(bahia[tuple(ij[0])])])
        for kk, (xx, yy) in P.items():
            rol = pts[kk]["rol"]
            if not (ext[0] <= xx <= ext[1] and ext[2] <= yy <= ext[3]):
                continue
            ax.plot(xx, yy, marker="D" if rol == "sitio" else "d", ms=4.5, mfc="#CC79A7" if rol == "sitio" else "none", mec="#CC79A7", mew=0.9, ls="none", zorder=4)
            ax.text(xx + 90, yy + 60, (pts[kk]["sitio"] if rol == "sitio" else kk), fontsize=5.5, color="#7a2d5e", zorder=5)
        ax.set_title(tit, fontsize=8); ax.set_xlim(ext[0], ext[1]); ax.set_ylim(ext[2], ext[3]); ax.set_xlabel("Easting, UTM 17N (km)")
        ax.set_xticks(np.arange(361000, 365001, 1000)); ax.set_xticklabels([f"{v/1000:.0f}" for v in np.arange(361000, 365001, 1000)])
        escala(ax, ext[0] + 300, ext[2] + 250)
    axs[0].set_ylabel("Northing, UTM 17N (km)"); axs[0].set_yticks(np.arange(2556000, 2561001, 1000))
    axs[0].set_yticklabels([f"{v/1000:.0f}" for v in np.arange(2556000, 2561001, 1000)])
    h = [Line2D([], [], marker="o", ls="none", mfc=col[n], mec="k", mew=0.3, ms=5, label=f"replicates in {n} of 2 halves") for n in (0, 1, 2)]
    h += [Line2D([], [], marker=m, ls="none", mfc="w", mec="k", mew=0.5, ms=5, label=l) for m, l in (("o", "chart depth < 2 m"), ("s", "chart depth >= 2 m"), ("^", "outside chart mesh"))]
    h += [Line2D([], [], color="#56B4E9", lw=0.8, label="2 m isobath (1887 chart)"),
          Line2D([], [], marker="D", ls="none", mfc="#CC79A7", mec="#CC79A7", ms=4, label="site S1-S5"),
          Line2D([], [], marker="d", ls="none", mfc="none", mec="#CC79A7", ms=4, label="control point")]
    fig.legend(handles=h, loc="lower center", ncol=5, frameon=False, fontsize=6, bbox_to_anchor=(0.5, -0.06))
    fig.savefig(f"{SALIDA}/fig_c_focos_10m.pdf", bbox_inches="tight"); plt.close(fig)
    with open(f"{SALIDA}/fig_c_focos_10m.csv", "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["season", "group_id", "easting_m", "northing_m", "size_px", "zc_max", "replicates_half_A", "replicates_half_B",
                                         "halves_replicating", "in_bay"]); w.writerows([r[:9] + r[10:] for r in salida_c])   # sin profundidad de la carta: no se redistribuye (secc. 29.6)
    open(f"{SALIDA}/NOTA_pies_de_figura.txt", "w").write(
        "Maps are limited to the study-area box (UTM 17N, E 360.0-365.0 km, N 2555.9-2561.9 km). No administrative boundaries are drawn. "
        "The boundaries shown are for reference only (coastline derived from the water mask of the Sentinel-2 scenes).\n"
        "a: median turbidity per pixel (Dogliotti et al. 2015 algorithm, ACOLITE DSF), 85 accepted scenes at 10 m; colour scale clipped to the 2nd-98th percentile; FNU values are not calibrated against in situ data.\n"
        "b: median across scenes of the per-scene median in 250 m bins along the arm axis (+-150 m corridor); band = 95 % bootstrap over scenes.\n"
        "c: groups of pixels with climatological z_c >= 3.5; colour = number of independent halves (2016-2020, 2021-2025) with a hot pixel within 80 m; "
        "depth = median of the 1887 chart (no dredging) within 80 m; chart error sigma 0.9 m, datum uncertainty 0 to +0.5 m."
        " The chart depths are not included in the CSV or redistributed here; to reproduce panel c, obtain the chart and read the soundings: U.S. Hydrographic Office, chart no. 307, \"West Indies, Cuba, harbor of Havana: from the most recent Spanish surveys to 1887\", ed. 1898, Boston Public Library, Leventhal Map & Education Center (call no. G9096.P5 svar .U55 no. 307 1898; https://collections.leventhalmap.org/search/commonwealth:g445ht01p, as recorded on 2 Oct 2026 in the model repository; not re-verified on 19 Nov 2026). Sounding positions were georeferenced on the 1889 edition of the Harbor of Havana chart (Harvard Geospatial Library, https://hgl.harvard.edu/catalog/harvard-g4924-h3-1889-u5; check its terms of use). The procedure and its parameters are in the repository Modelo-hidrodin-mico (commit 72095a8, docs/procedencia_datos.md).\n")
    print("c hecho; grupos", len(salida_c), flush=True)


if __name__ == "__main__":
    main()
