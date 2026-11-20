"""Peticion 3, E3: figura de serie temporal (EXPLORATORIO, sin calculos nuevos). Reglas: fila del 20/11/2026 (secc. 14).

    python scripts/41_figura_serie.py                            # 20 m
    VERTIDOS_PIXEL_M=10 python scripts/41_figura_serie.py --resultados resultados_10m

Panel a: mediana por zona y escena (variante «todos»), archivo 2016-2025 (circulos) y 2026 (rombos), estaciones sombreadas.
Panel b: d por escena con la banda 2,5-97,5 % de los 500 placebos y, por estacion, el p95 de la mediana entre escenas del placebo
(como en 37_prueba_A.py). Salida: productos_publicos/figuras/fig_e3_serie_<res>m.pdf y .csv (sin profundidad de la carta).
"""
import os, sys, csv, argparse
import numpy as np
from datetime import date
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "src"))
import geo

plt.rcParams.update({"pdf.fonttype": 42, "font.family": "DejaVu Sans", "font.size": 7, "axes.linewidth": 0.6})
SALIDA = "productos_publicos/figuras"
ZN = ("atares", "guasabacoa", "marimelena", "bahia_centro_y_canal", "mar")
NOM = {"atares": "Atares", "guasabacoa": "Guasabacoa", "marimelena": "Marimelena", "bahia_centro_y_canal": "Centre and channel", "mar": "Open sea"}
COL = {"atares": "#D55E00", "guasabacoa": "#0072B2", "marimelena": "#009E73", "bahia_centro_y_canal": "#E69F00", "mar": "#666666"}


def leer(res, carpeta, etiqueta):
    r = int(res)
    filas = list(csv.DictReader(open(os.path.join(carpeta, f"contraste_escenas_{r}m_{etiqueta}.csv"))))
    z = np.load(os.path.join(carpeta, f"contraste_placebo_{r}m_{etiqueta}.npz"), allow_pickle=True)
    pl = {str(f): p for f, p in zip(z["fechas"], z["placebo_focos"])}
    out = []
    for f in filas:
        p = pl[f["fecha"]]; pv = p[np.isfinite(p)]
        g = {"fecha": f["fecha"], "estacion": f["estacion"], "es_2026": int(etiqueta == "2026"), "focos_n_validos": int(float(f["focos_n_validos"])),
             "d_focos": float(f["d_focos"]), **{n: float(f[f"{n}_todos"]) for n in ZN}, "placebo": p}
        g["pl_p2_5"], g["pl_p50"], g["pl_p97_5"] = (np.percentile(pv, [2.5, 50, 97.5]) if pv.size else (np.nan,) * 3)
        out.append(g)
    return out


def sombrear(ax, x0, x1):
    for y in range(x0.year, x1.year + 1):
        ax.axvspan(date(y, 1, 1), date(y, 4, 30), color="#000000", alpha=0.06, lw=0)
        ax.axvspan(date(y, 11, 1), date(y, 12, 31), color="#000000", alpha=0.06, lw=0)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--resultados", default="resultados"); a = ap.parse_args()
    res = int(geo.PIXEL_M); os.makedirs(SALIDA, exist_ok=True)
    arch, nuevas = leer(res, a.resultados, "2016_2025"), leer(res, a.resultados, "2026")
    todas = sorted(arch + nuevas, key=lambda g: g["fecha"])
    for g in todas:
        g["f"] = date.fromisoformat(g["fecha"])
    p95 = {}
    for est in ("seca", "lluviosa"):
        P = np.array([g["placebo"] for g in arch if g["estacion"] == est and np.isfinite(g["d_focos"])])
        pm = np.nanmedian(P, axis=0); p95[est] = float(np.nanpercentile(pm, 95))
    x0, x1 = date(2017, 1, 1), date(2026, 12, 31)
    fig, axs = plt.subplots(2, 1, figsize=(7.5, 5.2), sharex=True, constrained_layout=True)
    ax = axs[0]; sombrear(ax, x0, x1)
    for n in ZN:
        for es, mk, fc in ((0, "o", COL[n]), (1, "D", "none")):
            s = [g for g in todas if g["es_2026"] == es and np.isfinite(g[n])]
            ax.plot([g["f"] for g in s], [g[n] for g in s], ls="none", marker=mk, ms=2.8 if es == 0 else 3.4, mfc=fc, mec=COL[n], mew=0.7,
                    label=NOM[n] if es == 0 else None)
    ax.set_ylabel(f"Median turbidity per zone and scene, {res} m (FNU)"); ax.legend(frameon=False, ncol=5, fontsize=6.5, loc="upper center", bbox_to_anchor=(0.5, 1.12))
    ax.text(0.995, 0.97, "circles: 2017-2025; open diamonds: 2026; grey: dry season (Nov-Apr)", transform=ax.transAxes, ha="right", va="top", fontsize=6)
    ax = axs[1]; sombrear(ax, x0, x1)
    for g in todas:
        if np.isfinite(g["pl_p2_5"]):
            ax.plot([g["f"], g["f"]], [g["pl_p2_5"], g["pl_p97_5"]], color="#999999", lw=1.6, solid_capstyle="butt", zorder=1)
    for es, mk, fc in ((0, "o", "#0072B2"), (1, "D", "none")):
        s = [g for g in todas if g["es_2026"] == es and np.isfinite(g["d_focos"])]
        ax.plot([g["f"] for g in s], [g["d_focos"] for g in s], ls="none", marker=mk, ms=3.0 if es == 0 else 3.6, mfc=fc, mec="#0072B2", mew=0.7, zorder=3,
                label="d, 2017-2025" if es == 0 else "d, 2026")
    ax.plot([], [], color="#999999", lw=1.6, label="placebo, 2.5-97.5 % of 500 sets")
    ax.axhline(0, color="k", lw=0.5)
    ax.axhline(p95["seca"], color="#CC79A7", lw=0.8, ls="--", label=f"p95 of placebo medians, dry ({p95['seca']:.2f})")
    ax.axhline(p95["lluviosa"], color="#E69F00", lw=0.8, ls=":", label=f"p95 of placebo medians, wet ({p95['lluviosa']:.2f})")
    ax.set_ylabel(f"Contrast d of hot pixels, {res} m (FNU)"); ax.set_xlabel("Date"); ax.legend(frameon=False, fontsize=6, ncol=3, loc="upper center", bbox_to_anchor=(0.5, 1.2))
    ax.set_xlim(x0, x1)
    fig.savefig(f"{SALIDA}/fig_e3_serie_{res}m.pdf"); plt.close(fig)
    cab = ["date", "season", "is_2026", "n_valid_hot_pixels", "d_FNU", "placebo_p2_5_FNU", "placebo_p50_FNU", "placebo_p97_5_FNU"] + [f"median_{n}_FNU" for n in ZN]
    with open(f"{SALIDA}/fig_e3_serie_{res}m.csv", "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(cab)
        for g in todas:
            w.writerow([g["fecha"], g["estacion"], g["es_2026"], g["focos_n_validos"]] + [("" if not np.isfinite(v) else round(float(v), 3)) for v in (g["d_focos"], g["pl_p2_5"], g["pl_p50"], g["pl_p97_5"], *[g[n] for n in ZN])])
    print(res, "m: escenas", len(arch), "+", len(nuevas), "p95", {k: round(v, 3) for k, v in p95.items()})


if __name__ == "__main__":
    main()
