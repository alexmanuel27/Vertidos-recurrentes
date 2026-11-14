"""Test de lluvia (protocolo secc. 20.4): ¿se encienden los sitios despues de llover mas que
sus controles emparejados?

    python scripts/14_lluvia.py                    # 20 m, los cinco sitios de campo
    VERTIDOS_PIXEL_M=10 python scripts/14_lluvia.py --productos datos/productos_10m --resultados resultados_10m

Dato: precipitacion horaria de ERA5 (0,25 grados) bajada de la API de archivo de Open-Meteo
(models=era5, cell_selection=nearest: la celda que contiene el centro de la bahia, 23,133 N
82,333 O). Cada valor horario es la suma de la hora anterior (documentacion de Open-Meteo).
P72 = suma de las 72 horas cuyo valor termina en la ultima hora entera antes de la adquisicion.
Estadistico por punto y escena: maximo de z_t a menos de 80 m (como el test de aerosoles).
Para cada sitio: Spearman rho entre P72 y ese maximo; la misma rho en TODOS sus controles
emparejados; p = (1 + controles con rho >= la del sitio) / (1 + n). Ligado a la lluvia si
rho > 0 y p < 0,05. No evaluable si menos de 10 escenas aceptadas tienen P72 >= 1 mm.
"""
import os, sys, csv, json, argparse, datetime, importlib.util
import numpy as np
import requests
from scipy import ndimage, stats

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "src"))
import adyacencia, geo

spec = importlib.util.spec_from_file_location("deteccion", os.path.join(AQUI, "06_deteccion.py"))
deteccion = importlib.util.module_from_spec(spec); spec.loader.exec_module(deteccion)

URL = "https://archive-api.open-meteo.com/v1/archive"
PARAMS = {"latitude": 23.133, "longitude": -82.333, "start_date": "2016-01-01",
          "end_date": "2025-12-31", "hourly": "precipitation", "models": "era5",
          "timezone": "GMT", "cell_selection": "nearest"}
MIN_LLUVIOSAS, LLUVIA_MIN_MM = 10, 1.0
SITIOS = "resultados/campo/campo.json"     # los cinco sitios de campo (20.5)


def era5(ruta):
    if not os.path.exists(ruta):
        r = requests.get(URL, params=PARAMS, timeout=300); r.raise_for_status()
        j = r.json()
        j["_descarga"] = {"url": r.url, "fecha_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")}
        json.dump(j, open(ruta, "w"))
    j = json.load(open(ruta))
    t = np.array([np.datetime64(x) for x in j["hourly"]["time"]])
    p = np.array([np.nan if v is None else v for v in j["hourly"]["precipitation"]], float)
    return t, p, j


def p72(t, p, fecha):
    fin = np.datetime64(fecha.replace(minute=0, second=0, microsecond=0))  # ultima hora entera
    sel = (t > fin - np.timedelta64(72, "h")) & (t <= fin)
    return float(p[sel].sum()) if sel.sum() == 72 and np.isfinite(p[sel]).all() else np.nan


def maximo_local(zt, radio):
    yy, xx = np.ogrid[-radio:radio + 1, -radio:radio + 1]
    disco = (yy ** 2 + xx ** 2) <= radio ** 2
    m = ndimage.maximum_filter(np.where(np.isfinite(zt), zt, -np.inf), footprint=disco, mode="constant",
                               cval=-np.inf)
    return np.where(np.isfinite(m), m, np.nan)


def spearman(x, y):
    ok = np.isfinite(x) & np.isfinite(y)
    if ok.sum() < 8 or np.std(y[ok]) == 0:
        return np.nan
    return float(stats.spearmanr(x[ok], y[ok])[0])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--productos", default="datos/productos")
    ap.add_argument("--resultados", default="resultados")
    ap.add_argument("--era5", default="datos/era5_precipitacion_horaria.json")
    a = ap.parse_args()
    t, p, j = era5(a.era5)
    d, clim, det, evs, zts, fechas, aots, lat, lon = deteccion.anomalias_por_escena(a.productos, a.resultados)
    agua, dist, ft = d["agua"], d["distancia_costa_m"], d["f_tierra_500m"]
    lluvia = np.array([p72(t, p, f) for f in fechas])
    n_llov = int(np.sum(lluvia >= LLUVIA_MIN_MM))
    rho_aot = spearman(lluvia, np.array(aots, float))

    # sitios: los de campo, situados en la rejilla de esta resolucion
    sit = json.load(open(SITIOS))["sitios"]
    cand = []
    for s in sit:
        dd = np.where(agua, np.hypot((lat - s["lat"]) * 110574, (lon - s["lon"]) * 111320 * np.cos(np.radians(s["lat"]))), np.inf)
        f, c = np.unravel_index(np.argmin(dd), dd.shape)
        cand.append({"codigo": s["codigo"], "nombre": s["nombre"], "fila_px": f + 0.5, "col_px": c + 0.5,
                     "celda": s["codigo"]})
    radio = int(round(80 / geo.PIXEL_M))
    cubo = np.stack([maximo_local(z, radio) for z in zts])          # escena x fila x col
    ev_alguna = clim["seca"]["evaluable"] | clim["lluviosa"]["evaluable"]
    filas = []
    for c, ct in zip(cand, adyacencia.controles_emparejados(cand, dist, ft, agua, ev_alguna)):
        f0, c0 = int(c["fila_px"]), int(c["col_px"])
        r_sitio = spearman(lluvia, cubo[:, f0, c0])
        r_ctrl = [r for r in (spearman(lluvia, cubo[:, f, cc]) for f, cc in ct["controles"]) if np.isfinite(r)]
        pv = adyacencia.p_controles(r_sitio, r_ctrl) if np.isfinite(r_sitio) else np.nan
        filas.append({"sitio": c["codigo"], "nombre": c["nombre"], "rho_sitio": round(r_sitio, 4),
                      "n_controles": len(r_ctrl),
                      "rho_controles_mediana": round(float(np.median(r_ctrl)), 4) if r_ctrl else np.nan,
                      "p_controles": round(pv, 4) if np.isfinite(pv) else np.nan,
                      "ligado_a_lluvia": bool(np.isfinite(r_sitio) and r_sitio > 0 and pv < 0.05)})
    evaluable = n_llov >= MIN_LLUVIOSAS
    res = {"resolucion_m": geo.PIXEL_M, "escenas": len(fechas),
           "escenas_con_P72_ge_1mm": n_llov, "evaluable": evaluable,
           "P72_mm_p50_p90_max": [round(float(np.nanpercentile(lluvia, q)), 2) for q in (50, 90, 100)],
           "spearman_P72_AOT": round(rho_aot, 4),
           "era5": {"celda_lat_lon": [j["latitude"], j["longitude"]], **j["_descarga"]},
           "sitios": filas if evaluable else "no evaluable: menos de 10 escenas con P72 >= 1 mm"}
    os.makedirs(a.resultados, exist_ok=True)
    json.dump(res, open(os.path.join(a.resultados, f"lluvia_{int(geo.PIXEL_M)}m.json"), "w"), indent=1,
              ensure_ascii=False)
    with open(os.path.join(a.resultados, f"lluvia_p72_{int(geo.PIXEL_M)}m.csv"), "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["fecha_utc", "P72_mm", "aot_550"])
        for f, l, ao in zip(fechas, lluvia, aots):
            w.writerow([f.isoformat(), round(l, 2), round(float(ao), 4)])
    print(json.dumps(res, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    # autocomprobacion de la ventana de 72 h
    _t = np.arange(np.datetime64("2020-01-01T00"), np.datetime64("2020-01-05T00"), np.timedelta64(1, "h"))
    assert p72(_t, np.ones(len(_t)), datetime.datetime(2020, 1, 4, 16, 17)) == 72.0
    main()
