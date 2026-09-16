"""Figura de validacion del metodo sobre la bahia sintetica."""
import sys, os
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))
import climatologia, anomalias, persistencia, adyacencia
from bahia_sintetica import generar, PIXEL_M

NARANJA, AQUA, AZUL = "#eb6834", "#1baf7a", "#2a78d6"
TINTA, TINTA2, TIERRA = "#0b0b0b", "#52514e", "#dedcd5"
RAMPA = LinearSegmentedColormap.from_list(
    "azul", ["#cde2fb", "#9ec5f4", "#5598e7", "#2a78d6", "#184f95", "#0d366b"])

d = generar()
agua, dist, f_tierra = d["agua"], d["dist"], d["f_tierra"]
turb, swir, fechas = d["turbidez"], d["swir"], d["fechas"]
fi, fp, at = d["fuente_intermitente"], d["fuente_permanente"], d["atracadero"]
clim = climatologia.climatologia(turb, fechas, agua)

det, ev, ztm = [], [], []
for i, f in enumerate(fechas):
    ce = clim[climatologia.estacion_de(f)]
    val = agua & np.isfinite(turb[i])
    aj = adyacencia.ajustar_decaimiento(swir[i], dist, val)
    res = adyacencia.residuo_swir(swir[i], dist, aj)
    umb = adyacencia.umbral_robusto(res, val)
    m, zt, zs = anomalias.detectar(turb[i], ce, val, rho_swir=res, umbral_swir=umb)
    det.append(m); ztm.append(zt)
    ev.append(val & ce["evaluable"] & ~anomalias.mascara_buques(res, umb, val))

sitios = persistencia.agregar_sitios(det, fechas, ev, PIXEL_M, ztm)
rec = persistencia.ranking(sitios)
k = persistencia.REJILLA_SITIO_M / PIXEL_M
mapa = np.full(agua.shape, np.nan)
for s in sitios:
    f0, c0 = int(s["celda"][0]*k), int(s["celda"][1]*k)
    mapa[f0:f0+int(k), c0:c0+int(k)] = s["persistencia"]
mapa[~agua] = np.nan
aj0 = adyacencia.ajustar_decaimiento(swir[0], dist, agua)
ctrl = adyacencia.controles_emparejados(rec[:1], dist, f_tierra, agua,
                                        clim["lluviosa"]["evaluable"], n_por_candidato=8)
mp = {s["celda"]: s["persistencia"] for s in sitios}
p_ctrl = [mp.get((int(f//k), int(c//k)), 0.0) for f, c in ctrl[0]["controles"]]
p_cand = rec[0]["persistencia"]

plt.rcParams.update({"font.size": 9, "axes.edgecolor": "#c9c8c1", "axes.linewidth": 0.8})
fig, ax = plt.subplots(2, 2, figsize=(9.6, 8.4))

a = ax[0, 0]
a.imshow(agua.astype(float), cmap=LinearSegmentedColormap.from_list("g", [TIERRA, "#cde2fb"]),
         interpolation="nearest")
for p, col, mk, lab in [(fi, NARANJA, "o", "fuente intermitente"),
                        (fp, AQUA, "s", "fuente permanente"),
                        (at, TINTA, "^", "buque atracado")]:
    a.plot(p[1], p[0], mk, ms=9, mfc="none", mec=col, mew=2.2, label=lab)
a.legend(loc="upper left", frameon=False, fontsize=8, labelcolor=TINTA2)
a.set_title("a. Bahía sintética: lo que se planta", loc="left", color=TINTA, fontweight="bold")
a.set_xticks([]); a.set_yticks([])

b = ax[0, 1]
b.plot(aj0["d"], aj0["y"], "o", ms=5, color=AZUL, mec="white", mew=0.8, zorder=3)
dd = np.linspace(0, aj0["d"].max(), 200)
b.plot(dd, aj0["A"]*np.exp(-dd/aj0["L"]) + aj0["c"], "-", lw=2, color=AZUL, zorder=2)
b.axvline(120, color=TINTA2, ls=":", lw=1.2)
b.annotate(f"L ajustada = {aj0['L']:.0f} m\nL plantada = 120 m\nr² = {aj0['r2']:.3f}",
           xy=(0.96, 0.92), xycoords="axes fraction", ha="right", va="top",
           fontsize=8.5, color=TINTA2)
b.set_xlabel("distancia a costa (m)", color=TINTA2)
b.set_ylabel("ρ$_{SWIR}$ mediana por anillo", color=TINTA2)
b.set_title("b. La adyacencia se mide, no se supone", loc="left", color=TINTA, fontweight="bold")
b.grid(alpha=0.25, lw=0.6); b.set_axisbelow(True)
for s in ("top", "right"): b.spines[s].set_visible(False)

c = ax[1, 0]
c.imshow(agua.astype(float), cmap=LinearSegmentedColormap.from_list("g", [TIERRA, "#f2f6fc"]),
         interpolation="nearest")
im = c.imshow(mapa, cmap=RAMPA, vmin=0, vmax=0.05, interpolation="nearest")
c.plot(rec[0]["col_px"], rec[0]["fila_px"], "o", ms=17, mfc="none", mec=NARANJA, mew=2.4)
c.annotate(f"único sitio recurrente\n{p_cand:.2f} · {rec[0]['n_anios']} años",
           xy=(rec[0]["col_px"], rec[0]["fila_px"]), xytext=(10, 54),
           textcoords="offset points", ha="left", va="bottom", fontsize=8.5,
           color=NARANJA, fontweight="bold")
cb = fig.colorbar(im, ax=c, fraction=0.046, pad=0.03, extend="max")
cb.set_label("persistencia", color=TINTA2, fontsize=8); cb.outline.set_visible(False)
cb.ax.tick_params(labelsize=7.5)
c.set_title("c. Persistencia a lo largo de 10 años", loc="left", color=TINTA, fontweight="bold")
c.set_xticks([]); c.set_yticks([])

e = ax[1, 1]
e.barh([1], [p_cand], height=0.40, color=NARANJA, zorder=3)
e.plot(p_ctrl, np.zeros(len(p_ctrl)), "o", ms=8, color=AZUL, mec="white", mew=1.0, zorder=3)
e.text(p_cand+0.008, 1, f"{p_cand:.2f}", va="center", fontsize=9, color=TINTA, fontweight="bold")
e.text(0.012, 0, f"{np.mean(p_ctrl):.3f}   (n={ctrl[0]['n']} píxeles emparejables)",
       va="center", fontsize=8.5, color=TINTA2)
e.set_yticks([0, 1]); e.set_yticklabels(["controles\nemparejados", "candidato"], color=TINTA2)
e.set_xlim(0, p_cand*1.30); e.set_ylim(-0.6, 1.6)
e.set_xlabel("persistencia", color=TINTA2)
e.set_title("d. Falsación: misma geometría, sin vertido", loc="left", color=TINTA, fontweight="bold")
e.grid(axis="x", alpha=0.25, lw=0.6); e.set_axisbelow(True)
for s in ("top", "right", "left"): e.spines[s].set_visible(False)

fig.suptitle("Validación de la cadena de detección sobre una bahía sintética",
             x=0.02, ha="left", fontsize=12.5, fontweight="bold", color=TINTA)
fig.text(0.02, 0.945, "Ningún dato real: los cuatro elementos están plantados y se sabe dónde. "
         "La adyacencia no genera ningún sitio recurrente falso.", fontsize=9, color=TINTA2)
fig.tight_layout(rect=[0, 0, 1, 0.93])
sal = os.path.join(os.path.dirname(__file__), "..", "resultados")
fig.savefig(os.path.join(sal, "validacion_sintetica.png"), dpi=200, bbox_inches="tight",
            facecolor="white")
fig.savefig(os.path.join(sal, "validacion_sintetica.pdf"), bbox_inches="tight", facecolor="white")
print("figura OK | candidato", round(p_cand, 3), "| controles", np.round(p_ctrl, 3))
