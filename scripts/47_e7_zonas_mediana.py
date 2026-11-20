"""Peticion 4, E7: datos del panel de zonas de la Fig. 2 (NO recalcula nada; EXPLORATORIO).

    python scripts/47_e7_zonas_mediana.py

Lee resultados/gradiente_20m.json y resultados_10m/gradiente_10m.json (24_gradiente.py, secc. 28), variante «todos»: mediana entre escenas de la
mediana por zona, IC 95 % por bootstrap de escenas, n de pixeles de la climatologia y mediana de la climatologia por pixel. Compara cada celda con
la Tabla 1 de series-Sentinel-2/manuscript/main.tex (tab:zones; tolerancia 0,005 FNU = redondeo a 2 decimales). Escribe
productos_publicos/figuras/fig_zonas_mediana.csv (sin profundidad) y e7_zonas_mediana_<res>m.json con la comparacion.
"""
import os, re, json, csv
import numpy as np

TEX = "/Users/alex/Nube /repos/publication plan/series-Sentinel-2/manuscript/main.tex"
ZN = ("atares", "guasabacoa", "marimelena", "bahia_centro_y_canal", "mar")
NOMBRE = {"atares": "Atarés", "guasabacoa": "Guasabacoa", "marimelena": "Marimelena", "bahia_centro_y_canal": "Centre and channel", "mar": "Open sea"}
FILAS_TABLA = {"Atar\\'es": "atares", "Guasabacoa": "guasabacoa", "Marimelena": "marimelena", "Centre and channel": "bahia_centro_y_canal", "Open sea": "mar"}
COLS = [(20, "seca"), (20, "lluviosa"), (10, "seca"), (10, "lluviosa")]      # orden de columnas de la Tabla 1
PUBLICO = "productos_publicos/figuras"


def tabla1():
    t = open(TEX, encoding="utf-8").read(); i = t.index("\\label{tab:zones}"); t = t[i:t.index("\\end{tabular}", i)]
    out = {}
    for linea in t.splitlines():
        celdas = [c.strip().rstrip("\\").strip() for c in linea.split("&")]
        if len(celdas) == 5 and celdas[0] in FILAS_TABLA:
            vals = []
            for c in celdas[1:]:
                m = re.match(r"([\d.]+) \[([\d.]+)--([\d.]+)\]", c); assert m, c
                vals.append(tuple(float(g) for g in m.groups()))
            out[FILAS_TABLA[celdas[0]]] = dict(zip(COLS, vals))
    assert set(out) == set(ZN), out.keys()
    return out


def main():
    G = {20: json.load(open("resultados/gradiente_20m.json")), 10: json.load(open("resultados_10m/gradiente_10m.json"))}
    T = tabla1(); filas, comp = [], {20: [], 10: []}
    for (r, est) in COLS:
        e = G[r]["estaciones"][est]; v = e["variantes"]["todos"]; cl = e["climatologia_pixel_secc23"]
        med = {z: v["zonas"][z]["mediana_FNU"] for z in ZN}
        rango = {z: 1 + sum(med[o] > med[z] for o in ZN) for z in ZN}
        for z in ZN:
            zz = v["zonas"][z]; tab = T[z][(r, est)]; js = (zz["mediana_FNU"], zz["ic95"][0], zz["ic95"][1])
            d = [abs(a - b) for a, b in zip(js, tab)]
            comp[r].append({"zona": z, "estacion": est, "json_mediana_ic_lo_ic_hi": list(js), "tabla1_mediana_ic_lo_ic_hi": list(tab),
                            "diferencia_maxima_FNU": round(max(d), 4), "coincide_a_2_decimales": bool(max(d) <= 0.0051)})
            filas.append({"resolution_m": r, "season": "dry" if est == "seca" else "wet", "zone": NOMBRE[z], "zone_code": z, "zone_rank_by_median": rango[z],
                          "median_FNU": zz["mediana_FNU"], "ci95_low_FNU": zz["ic95"][0], "ci95_high_FNU": zz["ic95"][1], "n_scenes": zz["n_escenas"],
                          "n_pixels_climatology": zz["n_px_climatologia"], "median_pixel_climatology_FNU": cl[z]["todos"],
                          "order_holds": "" if v["orden"] is None else bool(v["orden"]["cumple"]),
                          "margin_arms_minus_middle_FNU": "" if v["orden"] is None else v["orden"]["margen_brazos_menos_medio"],
                          "margin_middle_minus_sea_FNU": "" if v["orden"] is None else v["orden"]["margen_medio_menos_mar"]})
    os.makedirs(PUBLICO, exist_ok=True)
    with open(os.path.join(PUBLICO, "fig_zonas_mediana.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(filas[0])); w.writeheader(); w.writerows(filas)
    for r, d in ((20, "resultados"), (10, "resultados_10m")):
        res = {"resolucion_m": r, "fuente": f"{d}/gradiente_{r}m.json, estaciones.<est>.variantes.todos.zonas.<zona> y climatologia_pixel_secc23",
               "tabla1": TEX, "tolerancia_FNU": 0.0051, "n_celdas": len(comp[r]), "n_coinciden": sum(c["coincide_a_2_decimales"] for c in comp[r]),
               "diferencia_maxima_FNU": max(c["diferencia_maxima_FNU"] for c in comp[r]), "celdas": comp[r]}
        json.dump(res, open(os.path.join(d, f"e7_zonas_mediana_{r}m.json"), "w"), indent=1, ensure_ascii=False)
        print(r, res["n_coinciden"], "de", res["n_celdas"], "coinciden; dif max", res["diferencia_maxima_FNU"], flush=True)
        for c in comp[r]:
            if not c["coincide_a_2_decimales"]:
                print("  NO coincide:", c, flush=True)
    print("filas CSV:", len(filas))


if __name__ == "__main__":
    main()
