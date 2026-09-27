"""Figura del piloto: lo que 13 escenas reales permiten concluir y lo que no."""
import sys, glob, os
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
sys.path.insert(0, "src")
import mascara, adyacencia

NARANJA, AQUA, AZUL = "#eb6834", "#1baf7a", "#2a78d6"
TINTA, TINTA2, TIERRA = "#0b0b0b", "#52514e", "#dedcd5"
RAMPA = LinearSegmentedColormap.from_list("azul",
    ["#cde2fb", "#9ec5f4", "#5598e7", "#2a78d6", "#184f95", "#0d366b"])

fs = sorted(glob.glob("datos/productos/*.npz")); ds = [np.load(f) for f in fs]
ndwi = np.stack([mascara.ndwi(d["verde"], d["nir"]) for d in ds])
agua, _ = mascara.mascara_agua(ndwi)
dist = mascara.distancia_a_costa(agua, 20.0)

reg = []
for d in ds:
    b = d["banderas"].astype(np.int64)
    v = agua & np.isfinite(d["turbidez_dogliotti"]) & ((b & 30) == 0)
    contam = agua & np.isfinite(d["swir2"]) & (d["swir2"] > 0.010)
    v &= ~contam
    v &= (d["turbidez_dogliotti"] >= 0) & (d["turbidez_dogliotti"] <= 1000)
    reg.append({"fecha": str(d["fecha"])[:10], "d": d, "v": v,
                "contam": contam.sum() / agua.sum(), "frac": v.sum() / agua.sum()})
buenas = [r for r in reg if r["frac"] >= 0.40]

plt.rcParams.update({"font.size": 9, "axes.edgecolor": "#c9c8c1", "axes.linewidth": 0.8})
fig, ax = plt.subplots(2, 2, figsize=(10.2, 8.8))

# (a) ventana y mascara de agua
a = ax[0, 0]
a.imshow(agua.astype(float), cmap=LinearSegmentedColormap.from_list("g", [TIERRA, "#cde2fb"]),
         interpolation="nearest")
a.contour(dist, levels=[100, 400], colors=[NARANJA, AQUA], linewidths=1.2)
a.plot([], [], color=NARANJA, lw=1.5, label="100 m de la costa")
a.plot([], [], color=AQUA, lw=1.5, label="400 m de la costa")
a.legend(loc="lower left", frameon=False, fontsize=8, labelcolor=TINTA2)
a.set_title(f"a. Ventana ampliada: {agua.sum()*400/1e6:.0f} km² de agua",
            loc="left", color=TINTA, fontweight="bold")
a.text(0.98, 0.02, f"distancia máx. a costa {dist.max():.0f} m",
       transform=a.transAxes, ha="right", fontsize=8, color=TINTA2)
a.set_xticks([]); a.set_yticks([])

# (b) el test de contaminacion
b = ax[0, 1]
y = np.arange(len(reg))
col = [AQUA if r["frac"] >= 0.40 else NARANJA for r in reg]
b.barh(y, [100*r["contam"] for r in reg], color=col, height=0.62, zorder=3)
b.set_yticks(y); b.set_yticklabels([r["fecha"] for r in reg], fontsize=7.5, color=TINTA2)
b.invert_yaxis(); b.set_xlim(0, 105)
b.set_xlabel("% del agua con ρ(2200 nm) > 0,010", color=TINTA2)
b.set_title("b. Corrección atmosférica: sana o fallida", loc="left",
            color=TINTA, fontweight="bold")
b.plot([], [], "s", color=AQUA, label="usable (5)")
b.plot([], [], "s", color=NARANJA, label="descartada (8)")
b.legend(loc="lower right", frameon=False, fontsize=8, labelcolor=TINTA2)
b.grid(axis="x", alpha=0.25, lw=0.6); b.set_axisbelow(True)
for s in ("top", "right", "left"): b.spines[s].set_visible(False)

# (c) el perfil de adyacencia, la medida que hacia falta
c = ax[1, 0]
Ls = []
for i, r in enumerate(buenas):
    aj = adyacencia.ajustar_decaimiento(r["d"]["swir"], dist, r["v"], d_max=3000)
    if not aj: continue
    Ls.append((r["fecha"], aj))
    alfa = 1.0 if aj["r2"] > 0.85 else 0.35
    c.plot(aj["d"], aj["y"], "o", ms=3, color=AZUL, alpha=alfa*0.7, zorder=3)
    dd = np.linspace(0, 3000, 300)
    c.plot(dd, aj["A"]*np.exp(-dd/aj["L"]) + aj["c"], "-", lw=1.8, alpha=alfa,
           color=AZUL if aj["r2"] > 0.85 else TINTA2, zorder=2,
           label=f"{r['fecha']}  L={aj['L']:.0f} m  r²={aj['r2']:.2f}")
c.set_xlim(0, 1200); c.set_xlabel("distancia a costa (m)", color=TINTA2)
c.set_ylabel("ρ(1610 nm) mediana por anillo", color=TINTA2)
c.set_title("c. La adyacencia, medida por primera vez", loc="left",
            color=TINTA, fontweight="bold")
c.legend(frameon=False, fontsize=7.5, labelcolor=TINTA2, loc="upper right")
c.grid(alpha=0.25, lw=0.6); c.set_axisbelow(True)
for s in ("top", "right"): c.spines[s].set_visible(False)

# (d) turbidez mediana de las escenas limpias
e = ax[1, 1]
cubo = np.stack([np.where(r["v"], r["d"]["turbidez_dogliotti"], np.nan) for r in buenas])
med = np.nanmedian(cubo, axis=0); med[~agua] = np.nan
e.imshow(agua.astype(float), cmap=LinearSegmentedColormap.from_list("g", [TIERRA, "#f2f6fc"]),
         interpolation="nearest")
im = e.imshow(med, cmap=RAMPA, vmin=0, vmax=6, interpolation="nearest")
cb = fig.colorbar(im, ax=e, fraction=0.046, pad=0.03, extend="max")
cb.set_label("turbidez (FNU)", color=TINTA2, fontsize=8); cb.outline.set_visible(False)
cb.ax.tick_params(labelsize=7.5)
e.set_title(f"d. Turbidez mediana, {len(buenas)} escenas limpias", loc="left",
            color=TINTA, fontweight="bold")
e.set_xticks([]); e.set_yticks([])

fig.suptitle("Piloto sobre 13 escenas reales de la Bahía de La Habana",
             x=0.02, ha="left", fontsize=12.5, fontweight="bold", color=TINTA)
fig.text(0.02, 0.945, "La cadena produce valores físicos y la adyacencia ya es medible. "
         "Lo que 13 escenas NO pueden dar es la climatología por píxel.",
         fontsize=9, color=TINTA2)
fig.tight_layout(rect=[0, 0, 1, 0.93])
os.makedirs("resultados", exist_ok=True)
fig.savefig("resultados/piloto.png", dpi=200, bbox_inches="tight", facecolor="white")
fig.savefig("resultados/piloto.pdf", bbox_inches="tight", facecolor="white")
print("figura escrita | L:", [(f, round(a['L'])) for f, a in Ls])
print("turbidez mediana de la bahia:", round(float(np.nanmedian(med[agua & (dist<1500)])), 2), "FNU")
