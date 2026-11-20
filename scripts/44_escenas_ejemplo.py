"""Peticion 3, E4: tres escenas de ejemplo a 10 m (EXPLORATORIO). Reglas: fila del 20/11/2026 (secc. 14).

    VERTIDOS_PIXEL_M=10 python scripts/44_escenas_ejemplo.py --productos datos/productos_10m --resultados resultados_10m

Eleccion por regla (escenas aceptadas 2016-2025 a 10 m; mayor frac_valida_bahia, empate: fecha mas antigua): (i) seca con viento de
24 h «resto», (ii) seca con viento de 24 h «norte» (clase de 43_viento_direccion.py), (iii) lluviosa. Color real = B04, B03, B02 del L1C (10 m,
reflectancia en el techo de la atmosfera = (DN - 1000) / 10000 para los productos con linea base >= 04.00), estiramiento comun rho/0,20 y gamma 1/2,2.
Turbidez de Dogliotti del .npz, escala comun (percentiles 2-98 de las tres). Focos = pixeles calientes de la estacion de la escena.
Sin el L1C en disco no hay panel de color de esa escena (se dice en el JSON y en el PDF). Sin profundidad de la carta en ninguna salida.
Tercera columna: recuadro de 2 km alrededor de S1, que cae fuera del encuadre de 26_figuras (E 368,8 km, N 2563,2 km).
Salida: <resultados>/escenas_ejemplo_10m.json, productos_publicos/figuras/fig_e4_escenas_ejemplo_10m.pdf y .csv.gz.
"""
import os, sys, csv, json, gzip, glob, argparse, importlib.util
import numpy as np
from scipy import ndimage
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "src"))
import anomalias, escenas, geo


def carga(nombre):
    s = importlib.util.spec_from_file_location(nombre, os.path.join(AQUI, nombre + ".py"))
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


bat, grad, fig = carga("23_batimetria"), carga("24_gradiente"), carga("26_figuras")
CARPETAS_L1C = ["datos/crudo_e4", "datos/crudo_radcor", "datos/crudo", "datos/crudo_2026"]
ESCALA_RHO = 0.20


def elegir(res):
    qc = [r for r in csv.DictReader(open(os.path.join(res, "escenas_qc.csv"))) if r["aceptada"] == "1"]
    w = {r["fecha"]: r for r in csv.DictReader(open(os.path.join(res, "viento_direccion_escenas_10m.csv")))}
    def mejor(filas):
        return sorted(filas, key=lambda r: (-float(r["frac_valida_bahia"]), r["fecha"]))[0]
    seca = [r for r in qc if r["estacion"] == "seca" and r["fecha"][:10] in w]
    return [("i", "seca, viento 24 h resto", mejor([r for r in seca if w[r["fecha"][:10]]["norte_24h"] != "True"]), w),
            ("ii", "seca, viento 24 h norte", mejor([r for r in seca if w[r["fecha"][:10]]["norte_24h"] == "True"]), w),
            ("iii", "lluviosa", mejor([r for r in qc if r["estacion"] == "lluviosa"]), w)]


def rgb_l1c(l1c, box):
    from osgeo import gdal
    gdal.UseExceptions()
    zips = [z for c in CARPETAS_L1C for z in glob.glob(os.path.join(c, l1c.replace(".SAFE", "") + ".zip"))]
    if not zips:
        return None, "L1C no esta en disco"
    zp = zips[0]; nom = l1c.replace(".SAFE", ".SAFE")
    from zipfile import ZipFile
    with ZipFile(zp) as z:
        n = {b: [m for m in z.namelist() if m.endswith(f"_{b}.jp2") and "IMG_DATA" in m and "R10m" not in m or m.endswith(f"_{b}_10m.jp2")] for b in ("B04", "B03", "B02")}
    bandas = []
    for b in ("B04", "B03", "B02"):
        ds = gdal.Open(f"/vsizip/{zp}/{n[b][0]}"); gt = ds.GetGeoTransform()
        c0, c1 = int(round((box[0] - gt[0]) / gt[1])), int(round((box[1] - gt[0]) / gt[1])); r0, r1 = int(round((gt[3] - box[3]) / -gt[5])), int(round((gt[3] - box[2]) / -gt[5]))
        a = ds.GetRasterBand(1).ReadAsArray(c0, r0, c1 - c0, r1 - r0).astype(np.float32); bandas.append(a)
    rho = (np.stack(bandas, -1) - 1000.0) / 10000.0
    return np.clip(rho / ESCALA_RHO, 0, 1) ** (1 / 2.2), "ok"


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--productos", default="datos/productos_10m"); ap.add_argument("--resultados", default="resultados_10m"); a = ap.parse_args()
    assert geo.PIXEL_M == 10, "usar VERTIDOS_PIXEL_M=10"
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from pyproj import Transformer
    cl = np.load(os.path.join(a.resultados, "climatologia.npz"))
    agua, bahia, dist, ft500, x, y = cl["agua"].astype(bool), cl["bahia"].astype(bool), cl["distancia_costa_m"], cl["f_tierra_500m"], cl["x"], cl["y"]
    E, N = np.meshgrid(x, y); BOX = fig.BOX
    caja = (E >= BOX[0]) & (E <= BOX[1]) & (N >= BOX[2]) & (N <= BOX[3]); fs, cs = np.where(caja); sl = (slice(fs.min(), fs.max() + 1), slice(cs.min(), cs.max() + 1))
    ext = [x[sl[1]].min() - 5, x[sl[1]].max() + 5, y[sl[0]].min() - 5, y[sl[0]].max() + 5]
    r_px = int(round(80 / geo.PIXEL_M)); focos = {}
    for est in ("seca", "lluviosa"):
        zs, ev = bat.zc_estacion(cl, est, agua, bahia, dist, ft500); focos[est] = (zs >= anomalias.Z_C_MIN) & ev & bahia
    pts = {r["punto"]: r for r in csv.DictReader(open("resultados/campo/clave.csv"))}; T = Transformer.from_crs(4326, 32617, always_xy=True)
    S = {pts[k]["sitio"]: T.transform(float(v["lon"]), float(v["lat"])) for k, v in pts.items() if v["rol"] == "sitio"}
    elegidas = elegir(a.resultados); info = []; datos = []
    acept = set(str(p) for p in cl["productos_l1c"]); rutas = {}
    necesarias = {q["producto_l1c"] for _, _, q, _ in elegidas}
    for r in escenas.listar(a.productos):
        with np.load(r) as d:
            if str(d["producto_l1c"]) in necesarias:
                e = escenas.cargar(r); rutas[e["l1c"]] = e
    for cod, desc, q, w in elegidas:
        e = rutas[q["producto_l1c"]]; v, _ = escenas.validez(e, agua, dist); t = np.where(v, e["turbidez_dogliotti"], np.nan)
        rgb, estado = rgb_l1c(q["producto_l1c"], (x[sl[1]].min() - 5, x[sl[1]].max() + 5, y[sl[0]].min() - 5, y[sl[0]].max() + 5))
        if rgb is not None and rgb.shape[:2] != t[sl].shape:
            estado = f"forma distinta {rgb.shape[:2]} frente a {t[sl].shape}: no se usa"; rgb = None
        w_ = w.get(q["fecha"][:10])
        info.append({"codigo": cod, "regla": desc, "fecha": q["fecha"][:10], "producto_l1c": q["producto_l1c"], "estacion": q["estacion"], "frac_valida_bahia": float(q["frac_valida_bahia"]),
                     "viento_24h_procedencia_grados": round(float(w_["dir_24h"]), 1) if w_ else None, "viento_24h_vel_media_vectorial_ms": round(float(w_["vel_media_vectorial_24h_ms"]), 2) if w_ else None, "color": estado,
                     "n_focos_de_la_estacion_en_el_encuadre": int(focos[q["estacion"]][sl].sum())})
        datos.append((cod, q, t, rgb))
    pool = np.concatenate([t[sl][np.isfinite(t[sl]) & agua[sl]] for _, _, t, _ in datos]); vmin, vmax = float(np.percentile(pool, 2)), float(np.percentile(pool, 98))
    f = plt.figure(figsize=(10.4, 10.2), constrained_layout=True); gs = f.add_gridspec(3, 3, width_ratios=[5, 5, 3.6]); axs = np.empty((3, 3), object)
    for k in range(3):
        for j in range(3):
            axs[k, j] = f.add_subplot(gs[k, j])
    zx, zy = S["S1"]; ZOOM = 1000.0; fz, cz = np.where((E >= zx - ZOOM) & (E <= zx + ZOOM) & (N >= zy - ZOOM) & (N <= zy + ZOOM)); slz = (slice(fz.min(), fz.max() + 1), slice(cz.min(), cz.max() + 1))
    extz = [x[slz[1]].min() - 5, x[slz[1]].max() + 5, y[slz[0]].min() - 5, y[slz[0]].max() + 5]
    for k, (cod, q, t, rgb) in enumerate(datos):
        for j in (0, 1, 2):
            ax = axs[k, j]; ax.set_facecolor("#E6E6E6"); s_, e_ = (slz, extz) if j == 2 else (sl, ext)
            if j == 0 and rgb is not None:
                ax.imshow(rgb, extent=ext, origin="upper", interpolation="nearest", rasterized=True)
            elif j == 0:
                ax.text(0.5, 0.5, "L1C not on disk:\nno true-colour panel", transform=ax.transAxes, ha="center", va="center", fontsize=7)
            else:
                im = ax.imshow(np.where(agua[s_], t[s_], np.nan), extent=e_, origin="upper", cmap="viridis", vmin=vmin, vmax=vmax, interpolation="nearest", rasterized=True)
            ax.contour(x[s_[1]], y[s_[0]], agua[s_].astype(float), levels=[0.5], colors="k" if j else "w", linewidths=0.3)
            fi, ci = np.where(focos[q["estacion"]][s_]); ax.scatter(x[s_[1]][ci], y[s_[0]][fi], s=0.8 if j < 2 else 3.0, c="#D55E00", marker="s", linewidths=0, zorder=3)
            for nom, (xx, yy) in S.items():
                if e_[0] <= xx <= e_[1] and e_[2] <= yy <= e_[3]:
                    ax.plot(xx, yy, marker="D", ms=3.8, mfc="#CC79A7", mec="k", mew=0.4, ls="none", zorder=5); ax.text(xx + (80 if j < 2 else 40), yy + (50 if j < 2 else 30), nom, fontsize=6, color="#CC79A7" if j == 0 else "#FFFFFF", zorder=6, fontweight="bold")
            ax.set_xlim(e_[0], e_[1]); ax.set_ylim(e_[2], e_[3])
            tit = ("true colour" if j == 0 else "turbidity" if j == 1 else "turbidity, S1 area")
            ax.set_title(f"({cod}) {q['fecha'][:10]}, {'dry' if q['estacion'] == 'seca' else 'wet'} season, {tit}", fontsize=6.5)
            if j < 2:
                xt = np.arange(361000, 365001, 1000); ax.set_xticks(xt); ax.set_xticklabels([f"{v/1000:.0f}" for v in xt]); yt = np.arange(2556000, 2561001, 1000); ax.set_yticks(yt); ax.set_yticklabels([f"{v/1000:.0f}" if j == 0 else "" for v in yt])
            else:
                xt = np.arange(np.ceil(e_[0] / 500) * 500, e_[1], 500); ax.set_xticks(xt); ax.set_xticklabels([f"{v/1000:.1f}" for v in xt], fontsize=5.5); yt = np.arange(np.ceil(e_[2] / 500) * 500, e_[3], 500); ax.set_yticks(yt); ax.set_yticklabels([f"{v/1000:.1f}" for v in yt], fontsize=5.5)
            if k == 2:
                ax.set_xlabel("Easting, UTM 17N (km)")
            if j == 0:
                ax.set_ylabel("Northing, UTM 17N (km)")
    fig.escala(axs[2, 1], ext[0] + 300, ext[2] + 250)
    cb = f.colorbar(im, ax=axs[:, 2], shrink=0.5, extend="both", pad=0.03); cb.set_label("Turbidity, 10 m (FNU), common scale")
    S_ = fig.SALIDA; os.makedirs(S_, exist_ok=True); f.savefig(f"{S_}/fig_e4_escenas_ejemplo_10m.pdf"); plt.close(f)
    with gzip.open(f"{S_}/fig_e4_escenas_ejemplo_10m.csv.gz", "wt", newline="") as fh:
        w = csv.writer(fh); w.writerow(["scene", "date", "easting_m", "northing_m", "turbidity_FNU", "hot_pixel"])
        for cod, q, t, _ in datos:
            hot = focos[q["estacion"]]
            zoom = (E >= zx - 1000.0) & (E <= zx + 1000.0) & (N >= zy - 1000.0) & (N <= zy + 1000.0)
            for i, j in zip(*np.where((caja | zoom) & agua & np.isfinite(t))):
                w.writerow([cod, q["fecha"][:10], int(x[j]), int(y[i]), round(float(t[i, j]), 3), int(hot[i, j])])
    json.dump({"escala_turbidez_fnu_p2_p98": [round(vmin, 3), round(vmax, 3)], "escenas": info}, open(os.path.join(a.resultados, "escenas_ejemplo_10m.json"), "w"), indent=1, ensure_ascii=False)
    print(json.dumps(info, ensure_ascii=False, indent=1)[:2500], "\nescala", round(vmin, 2), round(vmax, 2))


if __name__ == "__main__":
    main()
