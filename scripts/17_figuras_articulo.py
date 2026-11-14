"""Figuras del articulo en ingles, sin titulo incrustado (lo lleva el pie), en PDF vectorial.

    python scripts/17_figuras_articulo.py --salida "<repo del articulo>/manuscript/figures"

study_area.pdf: ventana, mascara de agua, caja de la bahia, ensenadas (nomenclatura del
21/10/2026) y cauces de OpenStreetMap. detection.pdf: (a) frecuencia de deteccion por pixel
(E1), (b) z_c con bandas de la bahia en estacion seca (E3), (c) sitios recurrentes frente al
margen de costa (secc. 18 y E2). Solo lee resultados congelados y el archivo de escenas.
"""
import os, sys, json, argparse, warnings, importlib.util
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from pyproj import Transformer

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "src"))
import anomalias, persistencia

spec = importlib.util.spec_from_file_location("deteccion", os.path.join(AQUI, "06_deteccion.py"))
deteccion = importlib.util.module_from_spec(spec); spec.loader.exec_module(deteccion)

plt.rcParams.update({"font.size": 8, "axes.labelsize": 8, "axes.edgecolor": "#52514e",
                     "xtick.color": "#52514e", "ytick.color": "#52514e", "pdf.fonttype": 42})
TIERRA, AGUA = "#e9e7e1", "#cfe3f3"
AZUL, NARANJA, AQUA = "#2a78d6", "#eb6834", "#1baf7a"      # paleta de referencia, 3 primeras
TINTA, TINTA2 = "#0b0b0b", "#52514e"
FOCOS = [("Guasabacoa head", 362770.0, 2556710.0), ("Atarés", 361150.0, 2557670.0),
         ("W shore, S arm", 362230.0, 2557630.0)]


def fondo(ax, x, y, agua, km=True):
    ext = [x[0] / 1e3, x[-1] / 1e3, y[-1] / 1e3, y[0] / 1e3] if km else None
    ax.imshow(agua.astype(int), cmap=ListedColormap([TIERRA, AGUA]), extent=ext, interpolation="nearest")
    ax.set_xlabel("Easting (km, UTM 17N)"); ax.set_ylabel("Northing (km)")
    ax.tick_params(length=2)
    return ext


def rios(ax, t, nombres=("Río Luyanó", "Río Martín Pérez", "Tadeo")):
    osm = json.load(open("resultados/campo/osm_overpass.json"))
    for e in osm["elements"]:
        tg = e.get("tags", {})
        if e["type"] == "way" and tg.get("name") in nombres:
            xy = np.array([t.transform(g["lon"], g["lat"]) for g in e["geometry"]]) / 1e3
            ax.plot(xy[:, 0], xy[:, 1], color=AZUL, lw=0.9)


def area(salida, d, t):
    x, y, agua = d["x"], d["y"], d["agua"]
    fig, ax = plt.subplots(figsize=(5.5, 6.0))
    ax.set_facecolor(TIERRA)               # al sur de la ventana solo hay tierra (cauces de OSM)
    ext = fondo(ax, x, y, agua)
    rios(ax, t)
    bx = np.where(d["bahia"].any(0))[0]; by = np.where(d["bahia"].any(1))[0]
    x0, x1, y0, y1 = x[bx[0]] / 1e3 - .01, x[bx[-1]] / 1e3 + .01, y[by[-1]] / 1e3 - .01, y[by[0]] / 1e3 + .01
    ax.add_patch(plt.Rectangle((x0, y0), x1 - x0, y1 - y0, fill=False, ls="--", lw=0.8, ec=TINTA2))
    ax.text(x0 + .05, y1 + .12, "bay box", color=TINTA2, fontsize=7)
    etiquetas = [("Marimelena", 364.95, 2559.75, 366.2, 2559.3), ("Guasabacoa", 362.85, 2557.05, 365.1, 2557.0),
                 ("Atarés", 361.3, 2557.55, 359.6, 2557.0), ("Entrance\nchannel", 361.95, 2560.9, 359.4, 2561.6)]
    for txt, ex, ny, tx, ty in etiquetas:
        ax.annotate(txt, (ex, ny), xytext=(tx, ty), fontsize=8, color=TINTA, ha="center",
                    arrowprops=dict(arrowstyle="-", color=TINTA2, lw=0.6))
    for txt, (ex, ny) in {"R. Luyanó": (360.6, 2554.2), "R. Martín Pérez": (365.0, 2554.0),
                          "A. Tadeo": (365.3, 2558.3)}.items():
        ax.text(ex, ny, txt, fontsize=6.5, color=AZUL, style="italic")
    ax.set_xlim(ext[0], ext[1]); ax.set_ylim(2553.0, ext[3])
    ax.text(358.0, 2566.3, "Straits of Florida", fontsize=8, color=TINTA2, style="italic")
    ax.plot([366.6, 367.6], [2555.6, 2555.6], color=TINTA, lw=2)
    ax.text(367.1, 2555.75, "1 km", ha="center", fontsize=7)
    fig.savefig(os.path.join(salida, "study_area.pdf"), bbox_inches="tight"); plt.close(fig)


def deteccion_fig(salida, d, clim, det, evs, t):
    x, y, agua, bahia, dist, ft = d["x"], d["y"], d["agua"], d["bahia"], d["distancia_costa_m"], d["f_tierra_500m"]
    n_det, n_ev = np.sum(det, axis=0), np.sum(evs, axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        freq = np.where((n_ev >= 20) & agua, n_det / n_ev, np.nan)
    ce = clim["seca"]; ev_b = ce["evaluable"] & agua & bahia
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        zc, _ = anomalias.anomalia_climatologica(ce["mediana"], dist, ft, ev_b)
    zc = np.where(ev_b, zc, np.nan)
    by, bx = np.where(bahia.any(1))[0], np.where(bahia.any(0))[0]
    fy, fx = slice(by[0], by[-1] + 1), slice(bx[0], bx[-1] + 1)
    fig = plt.figure(figsize=(7.4, 3.4))
    gs = fig.add_gridspec(1, 3, width_ratios=[1, 1, 1.15], wspace=0.28)
    for k, (mapa, cmap, vmax, etq) in enumerate([(freq, "Blues", 0.08, "Detection frequency"),
                                                  (zc, "Oranges", 8, "$z_c$, dry season")]):
        ax = fig.add_subplot(gs[k])
        ext = fondo(ax, x[fx], y[fy], agua[fy, fx])
        im = ax.imshow(mapa[fy, fx], cmap=cmap, vmin=0, vmax=vmax, extent=ext, interpolation="nearest")
        for nom, E, N in FOCOS:
            ax.plot(E / 1e3, N / 1e3, "o", ms=6, mfc="none", mec=TINTA, mew=1.0)
        cb = fig.colorbar(im, ax=ax, orientation="horizontal", shrink=0.9, pad=0.2, aspect=25)
        cb.ax.tick_params(labelsize=7, length=2)
        cb.set_label(etq, fontsize=7); cb.outline.set_linewidth(0.4)
        ax.text(0.02, 0.98, "ab"[k], transform=ax.transAxes, va="top", fontweight="bold")
        if k == 1:
            ax.set_ylabel(""); ax.set_yticklabels([])
    ax = fig.add_subplot(gs[2])
    e2 = json.load(open("resultados/exploratorio.json"))["E2_sensibilidad"]
    pre = json.load(open("resultados/deteccion.json"))["recurrentes_por_margen_m"]
    mg = [0, 20, 40, 60, 100, 200, 400]; xs = np.arange(len(mg))
    series = [("Preregistered (≥0.10, ≥5 yr)", [pre[str(m)] for m in mg], AZUL),
              ("Relaxed (≥0.05, ≥3 yr), all", [e2[f"margen {m} m | pers >= 0.05 | anios >= 3"]["total"] for m in mg], NARANJA),
              ("Relaxed, inside the bay", [e2[f"margen {m} m | pers >= 0.05 | anios >= 3"]["bahia"] for m in mg], AQUA)]
    for nom, v, c in series:
        ax.plot(xs, v, "-o", color=c, lw=2, ms=4, mec="white", mew=0.8, label=nom)
    ax.axvline(2, color=TINTA2, lw=0.6, ls=":")
    ax.text(2.28, 9.3, "40 m criterion", fontsize=6.5, color=TINTA2, rotation=90, va="bottom")
    ax.set_xticks(xs); ax.set_xticklabels(mg); ax.set_xlabel("Shore buffer (m)"); ax.set_ylabel("Recurrent sites")
    ax.set_ylim(0, 29); ax.grid(axis="y", color="#e2e1dc", lw=0.5); ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.legend(fontsize=6.5, frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.17), ncol=1)
    ax.text(0.02, 0.98, "c", transform=ax.transAxes, va="top", fontweight="bold")
    fig.savefig(os.path.join(salida, "detection.pdf"), bbox_inches="tight"); plt.close(fig)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--salida", required=True); a = ap.parse_args()
    os.makedirs(a.salida, exist_ok=True)
    t = Transformer.from_crs(4326, 32617, always_xy=True)
    d, clim, det, evs, zts, fechas, aots, lat, lon = deteccion.anomalias_por_escena("datos/productos", "resultados")
    area(a.salida, d, t)
    deteccion_fig(a.salida, d, clim, det, evs, t)
    print("escritas:", sorted(os.listdir(a.salida)))


if __name__ == "__main__":
    main()
