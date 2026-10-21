"""Entrega de productos al modelo hidrodinamico SCHISM (repo alexmanuel27/Modelo-hidrodin-mico,
carpeta datos/sentinel2/, contrato en su README.md). Solo exporta: no cambia ningun metodo.

    python scripts/11_entrega_modelo.py --salida "<repo modelo>/datos/sentinel2"

Necesita el entorno conda `acolite` (numpy, scipy, GDAL/osgeo, pyproj, netCDF4) y:
  datos/productos/*.npz, resultados/climatologia.npz, resultados/escenas_qc.csv,
  resultados/sitios.csv, resultados/exploratorio.json, resultados/campo/osm_overpass.json,
  datos/crudo/catalogo.json (consulta OData de CDSE del 16/09/2026, con los Id),
  datos/entrega_modelo/catalogo_atributos.json (la misma consulta con $expand=Attributes,
  para la nubosidad), datos/productos/registro_tandas.jsonl (fechas de descarga).

Rejilla: la NATIVA del proyecto recortada a la ventana de la bahia del protocolo (secc. 1),
20 m, EPSG:32617, sin remuestrear. Filas de sur a norte en el .npz y el .nc; norte arriba
en los GeoTIFF.
"""
import os, sys, csv, json, glob, argparse, datetime, importlib.util
import numpy as np
from osgeo import gdal, ogr, osr
from pyproj import Transformer
import netCDF4

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "src"))
import anomalias

spec = importlib.util.spec_from_file_location("deteccion", os.path.join(AQUI, "06_deteccion.py"))
deteccion = importlib.util.module_from_spec(spec); spec.loader.exec_module(deteccion)

EPSG, PX = 32617, 20.0
REPO = "https://github.com/alexmanuel27/Vertidos-recurrentes/blob"
ODATA = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products({})"
OSM_ACCESO = "2026-10-17"
BOCA_MAX_M = 60.0       # ultimo vertice de un cauce OSM a <= 3 px del agua = desemboca en la bahia
gdal.UseExceptions()

DEFINICION = (
    "persistencia = n_anomalias / n_validas por píxel (NaN fuera del agua y donde n_validas = 0). "
    "n_validas: escenas aceptadas en las que el píxel es válido y evaluable. Escena aceptada: un "
    "producto L1C por paso (el de mayor huella en la ventana), AOT de ACOLITE finito y >= 60 % del "
    "agua de la ventana con píxel válido. Píxel válido: agua (máscara NDWI de la mediana), turbidez "
    "finita, bits 1-4 de l2_flags de ACOLITE sin activar, rho(2200 nm) <= 0,010 y fuera de la máscara "
    "de buques. Evaluable: >= 20 observaciones y MAD > 0 en la climatología de su estación. "
    "Anomalía positiva = z_t >= 3,5 Y z_s >= 3,0, con T = turbidez Dogliotti 2015 (FNU); "
    "z_t = (T - mediana estacional del píxel) / (1,4826 MAD estacional), climatología de las mismas "
    "escenas aceptadas (seca nov-abr, lluviosa may-oct); z_s = (T - mediana del día) / (1,4826 MAD del "
    "día), sobre los píxeles válidos de la ventana. umbral_anomalia = [z_t_min, z_s_min]. Es la "
    "'frecuencia de detección por píxel' (E1) del proyecto, no su 'persistencia' de sitio (celdas de "
    "40 m), que se define distinto.")


def ventana(bahia):
    f = np.where(bahia.any(1))[0]; c = np.where(bahia.any(0))[0]
    return slice(f[0], f[-1] + 1), slice(c[0], c[-1] + 1)


def srs():
    s = osr.SpatialReference(); s.ImportFromEPSG(EPSG); return s


def geotiff(ruta, a_norte_arriba, gt, nodata, tipo, descripcion):
    drv = gdal.GetDriverByName("GTiff")
    ds = drv.Create(ruta, a_norte_arriba.shape[1], a_norte_arriba.shape[0], 1, tipo,
                    options=["COMPRESS=DEFLATE", "PREDICTOR=" + ("3" if tipo == gdal.GDT_Float32 else "2")])
    ds.SetGeoTransform(gt); ds.SetProjection(srs().ExportToWkt())
    b = ds.GetRasterBand(1); b.WriteArray(a_norte_arriba); b.SetDescription(descripcion)
    if nodata is not None:
        b.SetNoDataValue(nodata)
    ds.SetMetadata({"LICENCIA": "CC BY 4.0", "ATRIBUCION": ATRIB})
    ds = None


def costa(ruta, mascara_norte_arriba, gt):
    mem = gdal.GetDriverByName("MEM").Create("", mascara_norte_arriba.shape[1],
                                             mascara_norte_arriba.shape[0], 1, gdal.GDT_Byte)
    mem.SetGeoTransform(gt); mem.SetProjection(srs().ExportToWkt())
    b = mem.GetRasterBand(1); b.WriteArray(mascara_norte_arriba)
    if os.path.exists(ruta):
        os.remove(ruta)
    out = ogr.GetDriverByName("GeoJSON").CreateDataSource(ruta)
    capa = out.CreateLayer("agua", srs(), ogr.wkbPolygon, options=["RFC7946=NO", "WRITE_NAME=YES"])
    capa.CreateField(ogr.FieldDefn("agua", ogr.OFTInteger))
    gdal.Polygonize(b, b, capa, 0)            # la propia mascara: solo los poligonos de agua
    out = None


def log_acolite(nombre):
    """Texto de los logs de ACOLITE guardados para un producto (datos/acolite_logs)."""
    txt = ""
    for r in glob.glob(f"datos/acolite_logs/{nombre}*"):
        for f in ([r] if os.path.isfile(r) else glob.glob(r + "/**/*", recursive=True)):
            if os.path.isfile(f):
                txt += open(f, errors="ignore").read()
    return txt


def escenas_csv(ruta, aceptadas_l1c):
    cat = {p["Name"]: p for p in json.load(open("datos/crudo/catalogo.json")) if "R097" in p["Name"]}
    atr = json.load(open("datos/entrega_modelo/catalogo_atributos.json"))
    nubes = {p["Name"]: p["atributos"].get("cloudCover") for p in atr["productos"]}
    reg = {}
    for l in open("datos/productos/registro_tandas.jsonl"):
        r = json.loads(l); reg[r["producto"]] = r            # se queda el ultimo intento
    qc = {r["producto_l1c"]: r for r in csv.DictReader(open("resultados/escenas_qc.csv"))}
    npz = {}
    for f in glob.glob("datos/productos/*.npz"):
        with np.load(f, allow_pickle=False) as z:
            npz[str(z["producto_l1c"])] = str(z["fecha"])
    filas = []
    for nombre in sorted(cat, key=lambda n: (cat[n]["ContentDate"]["Start"], n)):
        p, q = cat[nombre], qc.get(nombre)
        if nombre in reg:
            acceso = reg[nombre]["cuando"][:10]
        else:                                     # piloto del 16/09: el zip sigue en datos/crudo
            z = os.path.join("datos/crudo", nombre + ".zip")
            acceso = datetime.datetime.fromtimestamp(os.path.getmtime(z), datetime.timezone.utc).date().isoformat() \
                if os.path.exists(z) else ""
        fecha = (q["fecha"] if q else npz.get(nombre)) or p["ContentDate"]["Start"][:19]
        if q:
            frac = float(q["frac_valida_bahia"])
            aot = float(q["aot_550"]) if q["aot_550"] not in ("", "nan") else np.nan
            if q["aceptada"] == "1":
                motivo = ""
            elif not np.isfinite(aot):
                motivo = "AOT no finito (DSF no convergido)"
            else:
                motivo = f"agua válida de la ventana {100 * frac:.0f} % < 60 %"
        elif nombre in npz:
            frac, motivo = None, ("otro producto L1C del mismo paso elegido "
                                  "(uno por fecha: el de mayor huella en la ventana)")
        else:
            m_reg = reg.get(nombre, {}).get("motivo", "")
            m = m_reg + log_acolite(nombre)
            frac = None
            paso = nombre.split("_")[2]
            cubierto = any(o.split("_")[2] == paso for o in npz)
            tras = ("; el mismo paso está en otro producto exportado" if cubierto
                    else "; paso perdido (ningún otro producto)")
            motivo = ("no descargable (404 en CDSE; ya no figura en el catálogo)" if "404" in m_reg else
                      "recorte 100 % sin datos (blackfill) en la ventana" + tras if "blackfill" in m else
                      "ACOLITE no produjo L2W en la ventana" + tras if "0 L2W" in m else
                      m or "sin procesar")
        n = nubes.get(nombre)
        filas.append({"fecha_hora_utc": fecha[:19] + "Z", "producto": nombre, "nivel": "L1C",
                      "url": ODATA.format(p["Id"]), "fecha_acceso": acceso,
                      "nubes_pct": "" if n is None else round(float(n), 2),
                      "frac_agua_valida": "" if frac is None else round(frac, 4),
                      "usada": int(nombre in aceptadas_l1c), "motivo_descarte": motivo})
    assert sum(f["usada"] for f in filas) == len(aceptadas_l1c)
    with open(ruta, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(filas[0])); w.writeheader(); w.writerows(filas)
    return filas, atr["consulta_utc"]


def focos_csv(ruta, x, y, agua, pers_full, nval_full, bordes, url_sitios, url_expl):
    oeste, sur, este, norte = bordes
    fuera = lambda E, N: not (oeste <= E <= este and sur <= N <= norte)
    def en_pixel(E, N):
        c = int(np.argmin(np.abs(x - E))); f = int(np.argmin(np.abs(y - N)))
        return pers_full[f, c], nval_full[f, c]
    filas = []
    sit = [r for r in csv.DictReader(open("resultados/sitios.csv"))]
    nombres = {1: "Costa al este de la bahía", 2: "Bocana (canal de entrada)"}
    for r in sit:
        k = int(r["rango"])
        if k not in nombres:          # el rango 3 es el duplicado del 2 (empate, secc. 18 y E4)
            continue
        E, N = float(r["este_utm"]), float(r["norte_utm"])
        filas.append({"nombre": nombres[k], "E": E, "N": N,
                      "tipo": "sitio recurrente preregistrado (anomalías intermitentes); no sobrevive al margen de 40 m",
                      "evidencia": (("fuera de la ventana de la rejilla; " if fuera(E, N) else "")
                                    + f"anomalía positiva en {r['n_detecciones']} de {r['n_ocasiones']} ocasiones "
                                    f"evaluables de su celda de 40 m, {r['n_anios']} años ({r['anios']}); "
                                    f"verificación de campo pendiente; {url_sitios}")})
    e3 = json.load(open("resultados/exploratorio.json"))["E3_permanentes_bahia"]
    expl = [("Cabecera del brazo sur (Atarés)", 362770.0, 2556710.0),
            ("Brazo suroeste", 361150.0, 2557670.0),
            ("Orilla oeste al arrancar el brazo sur", 362230.0, 2557630.0)]
    for nom, E, N in expl:
        zc = []
        for est in ("seca", "lluviosa"):
            g = min(e3[est], key=lambda g: np.hypot(g["este_utm"] - E, g["norte_utm"] - N))
            d = np.hypot(g["este_utm"] - E, g["norte_utm"] - N)
            zc.append(f"{est} {g['z_c_max']:.1f}" if d <= 400 else f"{est} sin grupo")
        p, nv = en_pixel(E, N)
        filas.append({"nombre": nom, "E": E, "N": N,
                      "tipo": "foco permanente exploratorio (E3, definido después de ver los datos)",
                      "evidencia": (f"mediana climatológica de turbidez elevada respecto al agua de la bahía a la "
                                    f"misma distancia de costa, z_c máximo del grupo: {'; '.join(zc)}; "
                                    f"persistencia del píxel en esta entrega {p:.3f} (n_validas {nv}); "
                                    f"verificación de campo pendiente; {url_expl}")})
    t = Transformer.from_crs(4326, EPSG, always_xy=True)
    osm = json.load(open("resultados/campo/osm_overpass.json"))
    fs, cs = np.where(agua); we, wn = x[cs], y[fs]
    for e in osm["elements"]:
        tg = e.get("tags", {})
        if e["type"] != "way" or "waterway" not in tg:
            continue
        E, N = t.transform(e["geometry"][-1]["lon"], e["geometry"][-1]["lat"])  # OSM: sentido del flujo
        if fuera(E, N):
            continue
        d = float(np.min(np.hypot(we - E, wn - N)))
        if d > BOCA_MAX_M:
            continue
        nom = tg.get("name", "")
        clase = {"river": "río", "stream": "arroyo", "canal": "canal", "drain": "drenaje",
                 "ditch": "zanja"}.get(tg["waterway"], tg["waterway"])
        filas.append({"nombre": (f"Desembocadura: {nom}" + ("" if nom.lower().startswith(clase) else f" ({clase})")) if nom else
                      f"Desembocadura: {clase} sin nombre (OSM way {e['id']})",
                      "E": round(E, 1), "N": round(N, 1),
                      "tipo": f"desembocadura de cauce (fuente pública: OpenStreetMap, waterway={tg['waterway']})",
                      "evidencia": (f"último vértice del way {e['id']} a {d:.0f} m del agua; "
                                    f"https://www.openstreetmap.org/way/{e['id']} (consultado {OSM_ACCESO}, "
                                    f"Overpass, instantánea {osm['osm3s']['timestamp_osm_base']}); "
                                    "© colaboradores de OpenStreetMap, ODbL")})
    with open(ruta, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["nombre", "E", "N", "tipo", "evidencia"]); w.writeheader(); w.writerows(filas)
    return filas


def nc(ruta, fechas, productos, zt, det, ev, xs, ys):
    with netCDF4.Dataset(ruta, "w", format="NETCDF4") as d:
        d.createDimension("time", len(fechas)); d.createDimension("y", len(ys)); d.createDimension("x", len(xs))
        t = d.createVariable("time", "f8", ("time",))
        t.units = "seconds since 1970-01-01 00:00:00"; t.calendar = "standard"; t.standard_name = "time"
        t[:] = [f.replace(tzinfo=datetime.timezone.utc).timestamp() for f in fechas]
        for nom, val, std in (("x", xs, "projection_x_coordinate"), ("y", ys, "projection_y_coordinate")):
            v = d.createVariable(nom, "f8", (nom,)); v[:] = val
            v.standard_name = std; v.units = "m"; v.long_name = f"{nom} del centro de pixel, EPSG:{EPSG}"
        crs = d.createVariable("crs", "i4")
        crs.grid_mapping_name = "transverse_mercator"
        crs.scale_factor_at_central_meridian = 0.9996; crs.longitude_of_central_meridian = -81.0
        crs.latitude_of_projection_origin = 0.0; crs.false_easting = 500000.0; crs.false_northing = 0.0
        crs.semi_major_axis = 6378137.0; crs.inverse_flattening = 298.257223563
        crs.crs_wkt = srs().ExportToWkt(); crs.spatial_ref = crs.crs_wkt; crs.epsg_code = f"EPSG:{EPSG}"
        p = d.createVariable("producto", str, ("time",)); p.long_name = "producto Sentinel-2 L1C de origen"
        for i, s in enumerate(productos):
            p[i] = s
        z = d.createVariable("z_t", "f4", ("time", "y", "x"), zlib=True, complevel=4, fill_value=np.float32(np.nan))
        z.long_name = "anomalía temporal de turbidez z_t = (T - mediana estacional) / (1,4826 MAD estacional)"
        z.units = "1"; z.grid_mapping = "crs"
        z.comment = "NaN donde el píxel no es válido o no es evaluable en esa escena"
        z[:] = np.where(ev, zt, np.nan).astype(np.float32)
        a = d.createVariable("anomalia_positiva", "u1", ("time", "y", "x"), zlib=True, complevel=4,
                             fill_value=np.uint8(255))
        a.long_name = "anomalía positiva de turbidez (z_t >= 3,5 y z_s >= 3,0)"
        a.flag_values = np.array([0, 1], "u1"); a.flag_meanings = "sin_anomalia anomalia_positiva"
        a.grid_mapping = "crs"; a.comment = "255 = píxel no válido o no evaluable en esa escena"
        a[:] = np.where(ev, det.astype(np.uint8), 255).astype(np.uint8)
        d.Conventions = "CF-1.8"
        d.title = "Anomalías de turbidez Sentinel-2 por escena, Bahía de La Habana"
        d.institution = "Proyecto Vertidos-recurrentes (github.com/alexmanuel27/Vertidos-recurrentes)"
        d.source = "Sentinel-2 MSI L1C (Copernicus Data Space), ACOLITE DSF, turbidez Dogliotti et al. (2015)"
        d.references = "doi:10.1016/j.rse.2014.09.020; doi:10.1016/j.rse.2018.07.015; doi:10.1016/j.rse.2019.03.010"
        d.license = "CC BY 4.0"; d.attribution = ATRIB
        d.history = f"{datetime.date.today().isoformat()}: scripts/11_entrega_modelo.py"


def main():
    global ATRIB
    ap = argparse.ArgumentParser()
    ap.add_argument("--salida", required=True)
    ap.add_argument("--productos", default="datos/productos")
    ap.add_argument("--resultados", default="resultados")
    a = ap.parse_args()
    os.makedirs(a.salida, exist_ok=True)
    d, clim, det, evs, zts, fechas, aots, lat, lon = deteccion.anomalias_por_escena(a.productos, a.resultados)
    x, y, agua, bahia = d["x"], d["y"], d["agua"], d["bahia"]
    productos = [str(p) for p in d["productos_l1c"]]
    orden = sorted(range(len(productos)), key=lambda i: productos[i].split("_")[2])
    productos = [productos[i] for i in orden]       # mismo orden que anomalias_por_escena
    assert [p.split("_")[2][:8] for p in productos] == [f.strftime("%Y%m%d") for f in fechas]

    anios = sorted({int(n.split("_")[2][:4]) for n in productos})
    ATRIB = f"Contains modified Copernicus Sentinel data [{anios[0]}-{anios[-1]}]"
    n_det_full = np.sum(det, axis=0).astype(np.int16)
    n_ev_full = np.sum(evs, axis=0).astype(np.int16)
    with np.errstate(invalid="ignore", divide="ignore"):
        pers_full = np.where(agua & (n_ev_full > 0), n_det_full / n_ev_full, np.nan).astype(np.float32)

    fs, cs = ventana(bahia)
    sn = lambda m: m[fs, cs][::-1]                   # filas de sur a norte
    e, n = x[cs], y[fs][::-1]
    oeste, este = e[0] - PX / 2, e[-1] + PX / 2
    sur, norte = n[0] - PX / 2, n[-1] + PX / 2
    pers, nval, ndet, mag = sn(pers_full), sn(n_ev_full), sn(n_det_full), sn(agua).astype(np.uint8)
    np.savez_compressed(os.path.join(a.salida, "rejilla.npz"),
                        persistencia=pers, n_validas=nval, n_anomalias=ndet, mascara_agua=mag, e=e, n=n,
                        umbral_anomalia=np.array([anomalias.Z_T_MIN, anomalias.Z_S_MIN], np.float32),
                        definicion=np.array(DEFINICION), epsg=np.int32(EPSG), pixel_m=np.float32(PX),
                        bordes_oeste_sur_este_norte=np.array([oeste, sur, este, norte]),
                        orden_filas=np.array("filas de sur a norte (n creciente), columnas de oeste a este"),
                        atribucion=np.array(ATRIB), licencia=np.array("CC BY 4.0"))
    gt = (oeste, PX, 0.0, norte, 0.0, -PX)
    geotiff(os.path.join(a.salida, "persistencia_anomalias.tif"), pers[::-1], gt, float("nan"),
            gdal.GDT_Float32, "fracción de escenas válidas con anomalía positiva de turbidez")
    geotiff(os.path.join(a.salida, "mascara_agua.tif"), mag[::-1], gt, None, gdal.GDT_Byte,
            "1 = agua, 0 = tierra")
    costa(os.path.join(a.salida, "costa.geojson"), mag[::-1], gt)

    filas, consulta = escenas_csv(os.path.join(a.salida, "escenas.csv"), set(productos))
    focos = focos_csv(os.path.join(a.salida, "focos.csv"), x, y, agua, pers_full, n_ev_full,
                      (oeste, sur, este, norte), f"{REPO}/d816c8a/resultados/sitios.csv",
                      f"{REPO}/60532a2/resultados/exploratorio.json")
    nc(os.path.join(a.salida, "anomalias.nc"), fechas, productos,
       np.stack([z[fs, cs][::-1] for z in zts]), np.stack([m[fs, cs][::-1] for m in det]),
       np.stack([m[fs, cs][::-1] for m in evs]), e, n)

    usadas = [f for f in filas if f["usada"]]
    resumen = {
        "rejilla": {"columnas": len(e), "filas": len(n), "bordes_oeste_sur_este_norte": [oeste, sur, este, norte],
                    "centros_e": [float(e[0]), float(e[-1])], "centros_n": [float(n[0]), float(n[-1])]},
        "agua_px": int(mag.sum()), "agua_sin_validas_px": int((mag.astype(bool) & (nval == 0)).sum()),
        "persistencia_p50_p90_p99": [round(float(np.nanpercentile(pers, q)), 4) for q in (50, 90, 99)],
        "n_validas_min_p50_max": [int(nval[mag > 0].min()), int(np.median(nval[mag > 0])), int(nval.max())],
        "productos": len(filas), "fechas": len({f["fecha_hora_utc"][:10] for f in filas}),
        "usadas": len(usadas), "primera_usada": usadas[0]["fecha_hora_utc"], "ultima_usada": usadas[-1]["fecha_hora_utc"],
        "archivo_desde_hasta": [filas[0]["fecha_hora_utc"], filas[-1]["fecha_hora_utc"]],
        "baselines": sorted({f["producto"].split("_")[3] for f in filas}),
        "baselines_usadas": sorted({f["producto"].split("_")[3] for f in usadas}),
        "acceso_desde_hasta": [min(f["fecha_acceso"] for f in filas if f["fecha_acceso"]),
                               max(f["fecha_acceso"] for f in filas if f["fecha_acceso"])],
        "catalogo_nubes_consulta_utc": consulta, "atribucion": ATRIB, "focos": len(focos),
        "motivos": {m: sum(f["motivo_descarte"].startswith(m[:20]) for f in filas)
                    for m in sorted({f["motivo_descarte"] for f in filas if f["motivo_descarte"]
                                     and not f["motivo_descarte"].startswith("agua válida")})},
        "descarte_por_agua_valida": sum(f["motivo_descarte"].startswith("agua válida") for f in filas),
    }
    json.dump(resumen, open("datos/entrega_modelo/resumen.json", "w"), indent=1, ensure_ascii=False)
    print(json.dumps(resumen, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
