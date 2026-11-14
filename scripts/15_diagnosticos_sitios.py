"""Diagnosticos pendientes de los sitios: anisotropia (protocolo 11.3d) y anotacion de
atracaderos (secc. 9). Sobre los cinco sitios de campo (20.5): S1 y S2 son los candidatos
preregistrados; S3-S5, los focos exploratorios. Ninguno es criterio de fracaso: se reportan.

    python scripts/15_diagnosticos_sitios.py

Anisotropia: en cada escena aceptada, los grupos de deteccion con algun pixel a <= 80 m del
sitio; razon de extension paralela/perpendicular a la costa (raiz del cociente de varianzas
de las posiciones proyectadas sobre la tangente y la normal locales del sitio), mediana sobre
escenas; y Spearman entre z_t y f_tierra(500 m) sobre todos esos pixeles juntos. Marca
«amplitud escala con f_tierra» si rho > 0 y p < 0,05 (pixeles no independientes: el p es
optimista, es decir, marca de mas).
Atracaderos: OpenStreetMap (Overpass, consulta guardada con su fecha): man_made=pier|quay|
breakwater, waterway=dock y seamark:type=berth|mooring a <= 80 m del sitio -> «candidato de
atracadero»; y si el sitio cae a <= 80 m de landuse=port, «en zona portuaria».
"""
import os, sys, json, math, time, datetime, importlib.util
import numpy as np
import requests
from scipy import ndimage, stats
from pyproj import Transformer

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "src"))
import geo, persistencia

spec = importlib.util.spec_from_file_location("deteccion", os.path.join(AQUI, "06_deteccion.py"))
deteccion = importlib.util.module_from_spec(spec); spec.loader.exec_module(deteccion)

RADIO_M = 80.0
OVERPASS = "https://overpass-api.de/api/interpreter"
CONSULTA = ('[out:json][timeout:90];('
            'way["man_made"~"^(pier|quay|breakwater)$"](23.09,-82.41,23.22,-82.26);'
            'way["waterway"="dock"](23.09,-82.41,23.22,-82.26);'
            'nwr["seamark:type"~"^(berth|mooring)$"](23.09,-82.41,23.22,-82.26);'
            'way["landuse"="port"](23.09,-82.41,23.22,-82.26);'
            'relation["landuse"="port"](23.09,-82.41,23.22,-82.26););out geom tags;')
CACHE = "resultados/campo/osm_portuario.json"


def osm():
    if not os.path.exists(CACHE):
        for intento in range(4):          # Overpass da 502/504 cuando va cargado
            r = requests.post(OVERPASS, data={"data": CONSULTA}, timeout=180,
                              headers={"User-Agent": "Vertidos-recurrentes/1.0 (investigacion)"})
            if r.status_code < 500:
                break
            time.sleep(60)
        r.raise_for_status(); json.dump(r.json(), open(CACHE, "w"))
    return json.load(open(CACHE))


def distancia_a_elemento(E, N, e, t):
    """Distancia (m) del punto a la geometria del elemento (vertices y segmentos)."""
    geoms = []
    if "geometry" in e:
        geoms.append(e["geometry"])
    for m in e.get("members", []):
        if "geometry" in m:
            geoms.append(m["geometry"])
    if "lat" in e:
        geoms.append([{"lat": e["lat"], "lon": e["lon"]}])
    best = math.inf
    for g in geoms:
        xy = [t.transform(v["lon"], v["lat"]) for v in g]
        if len(xy) == 1:
            best = min(best, math.hypot(xy[0][0] - E, xy[0][1] - N)); continue
        for (x0, y0), (x1, y1) in zip(xy[:-1], xy[1:]):
            dx, dy = x1 - x0, y1 - y0; L = dx * dx + dy * dy
            u = 0 if L == 0 else max(0, min(1, ((E - x0) * dx + (N - y0) * dy) / L))
            best = min(best, math.hypot(x0 + u * dx - E, y0 + u * dy - N))
    return best


def main():
    d, clim, det, evs, zts, fechas, aots, lat, lon = deteccion.anomalias_por_escena(
        "datos/productos", "resultados")
    agua, ft, normal, x, y = d["agua"], d["f_tierra_500m"], d["normal_costa_rad"], d["x"], d["y"]
    PX = geo.PIXEL_M
    t = Transformer.from_crs(4326, 32617, always_xy=True)
    o = osm()
    sitios = json.load(open("resultados/campo/campo.json"))["sitios"]
    fs, cs = np.indices(agua.shape)
    salida = []
    for s in sitios:
        f0, c0 = s["f"], s["c"]
        E, N = float(x[c0]), float(y[f0])
        th = float(normal[f0, c0]); nvec = np.array([math.cos(th), math.sin(th)]); tvec = np.array([-nvec[1], nvec[0]])
        cerca = np.hypot(fs - f0, cs - c0) * PX <= RADIO_M
        razones, zz, ff = [], [], []
        for m, z in zip(det, zts):
            if not (m & cerca).any():
                continue
            etq, _ = ndimage.label(m, structure=np.ones((3, 3), bool))
            for k in np.unique(etq[m & cerca]):
                px = np.argwhere(etq == k)
                if len(px) < persistencia.MIN_PX_GRUPO:
                    continue
                rel = (px - px.mean(0)) * PX
                vt, vn = np.var(rel @ tvec), np.var(rel @ nvec)
                if vn > 0:
                    razones.append(math.sqrt(vt / vn))
                zz += list(z[px[:, 0], px[:, 1]]); ff += list(ft[px[:, 0], px[:, 1]])
        zz, ff = np.array(zz, float), np.array(ff, float)
        ok = np.isfinite(zz) & np.isfinite(ff)
        rho, p = (stats.spearmanr(zz[ok], ff[ok]) if ok.sum() >= 10 and np.std(ff[ok]) > 0 else (np.nan, np.nan))
        cerca_osm = []
        zona_port = False
        for e in o["elements"]:
            tg = e.get("tags", {})
            dd = distancia_a_elemento(E, N, e, t)
            if dd > RADIO_M:
                continue
            if tg.get("landuse") == "port":
                zona_port = True
            else:
                tipo = tg.get("man_made") or ("dock" if tg.get("waterway") == "dock" else tg.get("seamark:type"))
                cerca_osm.append(f"{e['type']}/{e['id']} {tipo} a {dd:.0f} m")
        salida.append({"sitio": s["codigo"], "nombre": s["nombre"], "E": E, "N": N,
                       "escenas_con_grupo": len(razones),
                       "razon_paralela_perpendicular_mediana": round(float(np.median(razones)), 2) if razones else None,
                       "razon_p25_p75": [round(float(np.percentile(razones, q)), 2) for q in (25, 75)] if razones else None,
                       "pixeles": int(ok.sum()), "spearman_zt_ftierra": None if not np.isfinite(rho) else round(float(rho), 3),
                       "p": None if not np.isfinite(p) else float(f"{p:.3g}"),
                       "amplitud_escala_con_ftierra": bool(np.isfinite(rho) and rho > 0 and p < 0.05),
                       "candidato_de_atracadero": bool(cerca_osm), "elementos_portuarios_a_80m": cerca_osm,
                       "en_zona_portuaria_osm": zona_port})
    res = {"fecha": datetime.date.today().isoformat(), "resolucion_m": PX,
           "osm_instantanea": o["osm3s"]["timestamp_osm_base"], "sitios": salida}
    json.dump(res, open("resultados/diagnosticos_sitios.json", "w"), indent=1, ensure_ascii=False)
    print(json.dumps(res, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
