"""Aclaraciones sobre la secc. 27 (EXPLORATORIO, sin umbrales nuevos): grupos de la fig. c frente a la tabla 27.2,
limites de las cinco zonas del gradiente y rejilla de profundidad de la carta de 1887.

    python scripts/27_aclaraciones.py                                  # 20 m
    VERTIDOS_PIXEL_M=10 python scripts/27_aclaraciones.py --resultados resultados_10m

Escribe aclaraciones_<res>m.json y datos/no_publicar_carta1887/profundidad_carta1887_<res>m.tif (fuera del deposito: ver secc. 28.1 d) (float32, UTM 17N, norte arriba,
NaN -> -9999 fuera de la malla). Definido en la fila del 18/11/2026 de la secc. 14.
"""
import os, sys, json, argparse, importlib.util
import numpy as np
from osgeo import gdal, osr
gdal.UseExceptions()
from pyproj import Transformer
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "src"))
import anomalias, geo, persistencia


def carga(nombre):
    s = importlib.util.spec_from_file_location(nombre, os.path.join(AQUI, nombre + ".py"))
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


bat, grad, fig = carga("23_batimetria"), carga("24_gradiente"), carga("26_figuras")
BOX = fig.BOX


def grupos_detalle(hot, bahia, E, N):
    etiq_todos = persistencia.grupos(hot, min_px=1)
    gr = persistencia.grupos(hot)
    filas = []
    for k, g in enumerate(gr):
        ij = np.array(g["pixeles"]); cf, cc = g["centroide"]
        cx, cy = float(np.interp(cc, np.arange(E.shape[1]), E[0])), float(np.interp(cf, np.arange(N.shape[0]), N[:, 0]))
        en_bahia = bahia[ij[:, 0], ij[:, 1]]
        filas.append({"id": k, "tam_px": g["tam"], "E": round(cx), "N": round(cy),
                      "en_caja": bool(BOX[0] <= cx <= BOX[1] and BOX[2] <= cy <= BOX[3]),
                      "primer_pixel_en_bahia": bool(bahia[tuple(ij[0])]),
                      "centroide_en_bahia": bool(bahia[int(round(cf)), int(round(cc))]),
                      "pixeles_en_bahia": int(en_bahia.sum())})
    return {"n_componentes_sin_filtro": len(etiq_todos), "n_con_filtro_minimo": len(gr),
            "n_en_caja_fig_c": sum(f["en_caja"] for f in filas),
            "n_primer_pixel_en_bahia": sum(f["primer_pixel_en_bahia"] for f in filas),
            "n_centroide_en_bahia": sum(f["centroide_en_bahia"] for f in filas),
            "n_con_algun_pixel_en_bahia": sum(f["pixeles_en_bahia"] > 0 for f in filas),
            "n_grupos_de_hot_y_bahia": len(persistencia.grupos(hot & bahia)),
            "n_en_caja_y_primer_pixel_en_bahia": sum(f["en_caja"] and f["primer_pixel_en_bahia"] for f in filas),
            "grupos": filas}


def zonas_limites(cl, E, N, agua):
    z = grad.zonas(cl); T = Transformer.from_crs(32617, 4326, always_xy=True); res = {}
    for k in ("mar", "bahia_centro_y_canal", "marimelena", "atares", "guasabacoa"):
        m = (z == k) & agua
        res[k] = {"pixeles_agua": int(m.sum()), "area_km2": round(float(m.sum()) * geo.PIXEL_M ** 2 / 1e6, 3),
                  "E_min": float(E[m].min()), "E_max": float(E[m].max()), "N_min": float(N[m].min()), "N_max": float(N[m].max())}
    ven = {"E_min": geo.ESTE_MIN, "E_max": geo.ESTE_MAX, "N_min": geo.NORTE_MIN, "N_max": geo.NORTE_MAX}
    linea = lambda n: 362350.0 - 0.25 * (2558800.0 - n)
    vert = {"A_linea_en_N=2558800": (linea(2558800.0), 2558800.0), "B_linea_en_N=NORTE_MIN": (linea(geo.NORTE_MIN), geo.NORTE_MIN),
            "C_sur_E=363300_en_N_min": (363300.0, geo.NORTE_MIN), "D_sur_E=363300_en_N=2558800": (363300.0, 2558800.0),
            "E_ventana_SO": (geo.ESTE_MIN, geo.NORTE_MIN), "F_ventana_NO_del_brazo": (geo.ESTE_MIN, 2558800.0)}
    vert_ll = {k: [round(v[0], 1), round(v[1], 1)] + [round(c, 5) for c in T.transform(*v)[::-1]] for k, v in vert.items()}
    return {"ventana_bahia_UTM17N": ven, "zonas": res, "vertices_[E,N,lat,lon]": vert_ll}


def exportar_profundidad(prof, x, y, ruta):
    c = (x >= geo.ESTE_MIN) & (x <= geo.ESTE_MAX); f = (y >= geo.NORTE_MIN) & (y <= geo.NORTE_MAX)
    sub = prof[np.ix_(f, c)].astype(np.float32); sub = np.where(np.isfinite(sub), sub, -9999.0).astype(np.float32)
    ds = gdal.GetDriverByName("GTiff").Create(ruta, sub.shape[1], sub.shape[0], 1, gdal.GDT_Float32, ["COMPRESS=DEFLATE"])
    ds.SetGeoTransform((float(x[c][0]) - geo.PIXEL_M / 2, geo.PIXEL_M, 0, float(y[f][0]) + geo.PIXEL_M / 2, 0, -geo.PIXEL_M))
    sr = osr.SpatialReference(); sr.ImportFromEPSG(32617); ds.SetProjection(sr.ExportToWkt())
    b = ds.GetRasterBand(1); b.SetNoDataValue(-9999.0); b.WriteArray(sub)
    b.SetDescription("depth_m (positive down), H.O. chart 307 surveys to 1887, via SCHISM mesh hgrid.gr3, linear interpolation")
    ds.FlushCache(); ds = None
    return {"ruta": ruta, "filas": int(sub.shape[0]), "columnas": int(sub.shape[1]), "pixeles_con_dato": int((sub > -9000).sum()),
            "min_m": round(float(sub[sub > -9000].min()), 2), "max_m": round(float(sub[sub > -9000].max()), 2),
            "x_primer_centro": float(x[c][0]), "y_primer_centro_norte": float(y[f][0])}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--resultados", default="resultados"); a = ap.parse_args()
    cl = np.load(os.path.join(a.resultados, "climatologia.npz"))
    agua, bahia, dist, ft500, x, y = cl["agua"].astype(bool), cl["bahia"].astype(bool), cl["distancia_costa_m"], cl["f_tierra_500m"], cl["x"], cl["y"]
    E, N = np.meshgrid(x, y); res = {"resolucion_m": geo.PIXEL_M, "tam_min_grupo_px": persistencia.MIN_PX_GRUPO, "z_c_min": anomalias.Z_C_MIN, "caja_fig_c": BOX}
    res["bahia_mascara"] = {"definicion": "rectangulo E [ESTE_MIN, ESTE_MAX] x N [NORTE_MIN, NORTE_MAX] de src/geo.py (src/escenas.mascara_bahia), sin recortar al agua",
                            "pixeles_rectangulo": int(bahia.sum()), "pixeles_rectangulo_con_agua": int((bahia & agua).sum())}
    res["grupos"] = {}
    for est in ("seca", "lluviosa"):
        zs, evs = bat.zc_estacion(cl, est, agua, bahia, dist, ft500)
        hot = (zs >= anomalias.Z_C_MIN) & evs
        d = grupos_detalle(hot, bahia, E, N); d["pixeles_calientes"] = int(hot.sum()); res["grupos"][est] = d
        print(est, {k: v for k, v in d.items() if k != "grupos"}, flush=True)
        for g in d["grupos"]:
            print("  ", g, flush=True)
    res["zonas"] = zonas_limites(cl, E, N, agua); print(json.dumps(res["zonas"], indent=1, ensure_ascii=False), flush=True)
    prof = bat.profundidad_en_rejilla(E, N)
    os.makedirs(os.path.join(AQUI, "..", "datos", "no_publicar_carta1887"), exist_ok=True)
    ruta = os.path.join(AQUI, "..", "datos", "no_publicar_carta1887", f"profundidad_carta1887_{int(geo.PIXEL_M)}m.tif")
    res["profundidad"] = exportar_profundidad(prof, x, y, os.path.abspath(ruta)); print(res["profundidad"], flush=True)
    json.dump(res, open(os.path.join(a.resultados, f"aclaraciones_{int(geo.PIXEL_M)}m.json"), "w"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
