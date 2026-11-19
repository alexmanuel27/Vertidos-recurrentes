"""Comprobaciones del articulo (29.7): solo lectura de datos y resultados existentes.
No recalcula ningun analisis ni cambia umbrales; escribe resultados/comprobaciones_articulo.json."""
import csv, glob, json, os, collections
import numpy as np
from pyproj import Transformer

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(R, *a)
out = {"nota": "Solo lectura de datos y resultados; ningun analisis recalculado, ningun umbral cambiado. Generado por scripts/39_comprobaciones_articulo.py"}

# 1. ventana de analisis
v = {}
for res, f in (("20m", "resultados/climatologia.npz"), ("10m", "resultados_10m/climatologia.npz")):
    z = np.load(P(f), allow_pickle=True)
    x, y = z["x"], z["y"]
    dx, dy = abs(float(x[1] - x[0])), abs(float(y[1] - y[0]))
    v[res] = {"fuente": f + " (campos x, y)", "n_x": len(x), "n_y": len(y), "pixel_m": dx,
              "extension_E_O_km": round(len(x) * dx / 1000, 3), "extension_N_S_km": round(len(y) * dy / 1000, 3),
              "x_min_centro": float(x.min()), "x_max_centro": float(x.max()),
              "y_min_centro": float(y.min()), "y_max_centro": float(y.max())}
    if res == "20m":
        bahia = z["bahia"].astype(bool)
        tr = Transformer.from_crs(32617, 4326, always_xy=True)
        X, Y = np.meshgrid(x, y)
        def cen(m):
            lon, lat = tr.transform(float(X[m].mean()), float(Y[m].mean()))
            return {"n_pixeles": int(m.sum()), "lat": round(lat, 4), "lon": round(lon, 4)}
        out["4_coordenadas_bahia"] = {
            "fuente": "resultados/climatologia.npz, campos bahia y agua (booleanos); centroide de x, y, UTM 17N -> WGS84",
            "agua_de_la_bahia_(bahia_y_agua)": cen(bahia & z["agua"].astype(bool)),
            "poligono_bahia_(bahia, incluye tierra)": cen(bahia)}
        # caja nominal en UTM
        t2 = Transformer.from_crs(4326, 32617, always_xy=True)
        (x0, y0), (x1, y1) = t2.transform(-82.400, 23.100), t2.transform(-82.280, 23.210)
        v["caja_nominal_lat_lon"] = {"limites": "23.100-23.210 N, 82.400-82.280 O",
                                     "E_O_km_en_UTM17N": round((x1 - x0) / 1000, 2), "N_S_km_en_UTM17N": round((y1 - y0) / 1000, 2)}
out["1_ventana"] = v

# 2. escenas por ano
cat = json.load(open(P("datos/crudo/catalogo.json")))
prod = collections.Counter(c["Name"][11:15] for c in cat)
fechas = collections.defaultdict(set)
for c in cat:
    fechas[c["Name"][11:15]].add(c["Name"][11:19])
qc = list(csv.DictReader(open(P("resultados/escenas_qc.csv"))))
qa = collections.Counter(r["fecha"][:4] for r in qc)
qacc = collections.Counter(r["fecha"][:4] for r in qc if r["aceptada"] == "1")
anos = sorted(prod)
out["2_escenas_por_ano"] = {
    "fuentes": {"catalogo": "datos/crudo/catalogo.json (campo Name, caracteres 11-14 = ano)",
                "qc": "resultados/escenas_qc.csv (columna fecha; aceptada)"},
    "n_productos_catalogo": len(cat), "n_filas_qc": len(qc), "n_aceptadas_qc": sum(qacc.values()),
    "por_ano": {a: {"productos_catalogo": prod[a], "fechas_distintas_catalogo": len(fechas[a]),
                    "filas_qc": qa[a], "aceptadas_qc": qacc[a]} for a in anos}}

# 3. AOT 2020-11-29
a = {}
for res, d in (("20m", "datos/productos"), ("10m", "datos/productos_10m")):
    fs = glob.glob(P(d, "*2020_11_29*"))
    if fs:
        n = np.load(fs[0], allow_pickle=True)
        a[res] = {"fuente": os.path.relpath(fs[0], R) + " (campo aot_550)", "aot_550": float(np.ravel(n["aot_550"])[0])}
a["protocolo"] = "PROTOCOLO_CONGELADO.md sec. 14, fila 2026-11-13 (c): 2020-11-29, 0,0045 a 20 m y 0,028 a 10 m"
out["3_aot_2020_11_29"] = a

# 5. fig_b
rows = list(csv.DictReader(open(P("productos_publicos/figuras/fig_b_perfil_brazos.csv"))))
fb = {}
for s in ("seca", "lluviosa"):
    bins = sorted({int(r["bin_center_m"]) for r in rows if r["season"] == s})
    tab = []
    for b in bins:
        g = {r["arm"]: r for r in rows if r["season"] == s and int(r["bin_center_m"]) == b}
        arms = list(g)
        med = {k: float(g[k]["median_FNU"]) for k in arms}
        lo = {k: float(g[k]["ci95_low_FNU"]) for k in arms}
        hi = {k: float(g[k]["ci95_high_FNU"]) for k in arms}
        disj = [(p, q) for i, p in enumerate(arms) for q in arms[i + 1:] if lo[p] > hi[q] or lo[q] > hi[p]]
        tab.append({"bin_m": b, "medianas": med, "rango_medianas": round(max(med.values()) - min(med.values()), 3),
                    "pares_con_IC_disjuntos": disj})
    fb[s] = tab
out["5_fig_b"] = {"fuente": "productos_publicos/figuras/fig_b_perfil_brazos.csv (arm, season, bin_center_m, median_FNU, ci95_*)", "por_estacion": fb}

# 6. B3
b3 = {}
for res, f in (("20m", "resultados/prof_dist_20m.json"), ("10m", "resultados_10m/prof_dist_10m.json")):
    d = json.load(open(P(f)))
    r = []
    for s in ("seca", "lluviosa"):
        for e in d["estaciones"][s]["B3"]:
            if e["clase_prof_m"] == ">5" and e["n_pixeles"] > 0:
                r.append({"estacion": s, "banda_m": e["banda_m"], "n": e["n_pixeles"],
                          "fraccion_caliente": e["fraccion_caliente_z_c>=3.5"], "z_c_mediana": e["z_c_percentiles_10_25_50_75_90"][2]})
    fr = [x["fraccion_caliente"] for x in r]
    b3[res] = {"fuente": f + " (estaciones.*.B3[clase_prof_m='>5'])", "celdas": r,
               "rango_fraccion_caliente": [min(fr), max(fr)], "z_c_mediana_max": max(x["z_c_mediana"] for x in r)}
out["6_B3_profundo_cerca_de_costa"] = b3

json.dump(out, open(P("resultados/comprobaciones_articulo.json"), "w"), indent=1, ensure_ascii=False)
print(json.dumps(out, indent=1, ensure_ascii=False)[:6000])
