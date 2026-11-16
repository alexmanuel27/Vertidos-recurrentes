"""Inventario EXPLORATORIO de senales, con su prueba de robustez (definido el 16/11/2026, despues de
ver los resultados a 20 y 10 m). No cambia ningun veredicto preregistrado.

    python scripts/20_inventario.py

La prueba de robustez comun es repetir con la otra resolucion: 20 m (113 escenas) y 10 m (85
escenas) usan escenas aceptadas distintas y una correccion atmosferica distinta (el AOT de DSF
cambia con la resolucion, secc. 14). Una senal es robusta si sale en las dos.
  1. Focos S1-S5: distancia del sitio de 20 m a la senal de 10 m mas cercana, por familia
     (recurrente preregistrado, recurrente secundario, permanente z_c). Reaparece si <= 80 m.
  2. Gradiente por zona: mediana de la turbidez climatologica (Dogliotti, FNU) por zona y estacion,
     con todos los pixeles de agua y solo con los que estan a >= 100 m de costa (para quitar la
     adyacencia). Zonas con la definicion del modelo SCHISM (secc. 14, 21/10/2026).
  3. Respuesta de la costa a la lluvia: rho mediana de los controles (secc. 21 y lluvia_10m.json).
  4. Escala de adyacencia: L ajustada (mediana) en metros y en pixeles.
Escribe resultados_10m/inventario.json.
"""
import csv, json, math
import numpy as np
from pyproj import Transformer

A_UTM = Transformer.from_crs(4326, 32617, always_xy=True)
R20, R10 = "resultados/", "resultados_10m/"


def zonas(clim):
    E, N = np.meshgrid(clim["x"], clim["y"])
    bahia = clim["bahia"].astype(bool)
    sur = (N < 2558800) & (E < 363300)
    z = np.full(E.shape, "", dtype=object)
    z[~bahia & clim["agua"].astype(bool)] = "mar"
    z[bahia] = "bahia_centro_y_canal"
    z[bahia & (E > 363600)] = "marimelena"
    z[bahia & sur & (E < 362350 - 0.25 * (2558800 - N))] = "atares"
    z[bahia & sur & ~(E < 362350 - 0.25 * (2558800 - N))] = "guasabacoa"
    return z


def gradiente(ruta):
    c = np.load(ruta + "climatologia.npz")
    z = zonas(c); lejos = c["distancia_costa_m"] >= 100
    out = {}
    for est in ("seca", "lluviosa"):
        m = c[est + "_mediana"]; ok = c[est + "_evaluable"].astype(bool) & np.isfinite(m)
        out[est] = {n: {"todos": round(float(np.median(m[ok & (z == n)])), 2),
                        "a_100m_o_mas": (round(float(np.median(m[ok & lejos & (z == n)])), 2)
                                         if (ok & lejos & (z == n)).sum() else None),
                        "n_px": int((ok & (z == n)).sum())}
                    for n in ("atares", "guasabacoa", "marimelena", "bahia_centro_y_canal", "mar")}
    return out


def focos():
    sitios = json.load(open(R20 + "campo/campo.json"))["sitios"]
    det = json.load(open(R10 + "deteccion.json"))
    fam = {"recurrente_preregistrado": [(float(r["este_utm"]), float(r["norte_utm"])) for r in csv.DictReader(open(R10 + "sitios.csv"))],
           "recurrente_secundario": [A_UTM.transform(float(r["lon"]), float(r["lat"])) for r in csv.DictReader(open(R10 + "sitios_secundario.csv"))],
           "permanente_zc": [(g["este_utm"], g["norte_utm"]) for e in ("seca", "lluviosa") for g in det["permanentes"][e]]}
    out = {}
    for s in sitios:
        x, y = A_UTM.transform(s["lon"], s["lat"])
        d = {f: (round(min(math.hypot(x - a, y - b) for a, b in v)) if v else None) for f, v in fam.items()}
        out[s["codigo"]] = {"nombre": s["nombre"], "dist_m": d,
                            "reaparece_80m": [f for f, v in d.items() if v is not None and v <= 80]}
    return out


def main():
    ll = {r: json.load(open(f"{p}lluvia_{r}m.json")) for r, p in ((20, R20), (10, R10))}
    cj = {r: json.load(open(p + "climatologia.json")) for r, p in ((20, R20), (10, R10))}
    inv = {"advertencia": "EXPLORATORIO, definido despues de ver los resultados",
           "focos_20m_a_10m": focos(),
           "gradiente_FNU": {"20m": gradiente(R20), "10m": gradiente(R10)},
           "lluvia_rho_controles_mediana": {r: {s["sitio"]: s["rho_controles_mediana"] for s in ll[r]["sitios"]} for r in ll},
           "lluvia_sitios_ligados": {r: [s["sitio"] for s in ll[r]["sitios"] if s["ligado_a_lluvia"]] for r in ll},
           "adyacencia_L_mediana": {r: {"m": cj[r]["adyacencia_r2_mayor_085"]["L_m_p10_p50_p90"][1],
                                        "px": round(cj[r]["adyacencia_r2_mayor_085"]["L_m_p10_p50_p90"][1] / r, 2)} for r in cj},
           "escenas_aceptadas": {r: cj[r]["aceptadas"] for r in cj}}
    json.dump(inv, open(R10 + "inventario.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(inv, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
