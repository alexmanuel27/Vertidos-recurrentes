"""Puntos de control para la verificacion de campo (protocolo seccion 20.5).

    python scripts/08_controles_campo.py

Un control por sitio predicho, sorteado con semilla fija entre los pixeles de agua que:
emparejan al sitio en distancia a costa (+-20 m) y f_tierra(500 m) (+-0,05); estan en su
misma zona (bahia o fuera); quedan a mas de 200 m de los cinco sitios y de cualquier grupo
E3 (las dos estaciones); y son negativos predichos (frecuencia E1 <= la mediana de su zona).
Escribe en resultados/campo/: clave.csv (quien es quien, NO se da a la persona de campo),
puntos.csv (los diez puntos barajados P01-P10, lo unico que se le da), reservas.csv
(siguientes sorteados por sitio, para sustituir un control inaccesible) y campo.json.
"""
import os, sys, csv, json, argparse, warnings, importlib.util
import numpy as np
from scipy import ndimage

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "src"))
import persistencia, anomalias

spec = importlib.util.spec_from_file_location("deteccion", os.path.join(AQUI, "06_deteccion.py"))
deteccion = importlib.util.module_from_spec(spec); spec.loader.exec_module(deteccion)

PX = 20.0
SEMILLA = 20261013
TOL_D, TOL_F = 20.0, 0.05
DIST_MIN_PX = 200.0 / PX
N_EV_MIN = 20
N_RESERVAS = 5
SITIOS = [  # protocolo 20.5, en este orden
    ("S1", "costa al este de la bahia", 23.1730, -82.2821),
    ("S2", "bocana", 23.1562, -82.3499),
    ("S3", "cabecera del brazo sur", 23.1135, -82.3401),
    ("S4", "brazo suroeste", 23.1220, -82.3560),
    ("S5", "orilla oeste al arrancar el brazo sur", 23.1217, -82.3455),
]


def pixel_de(lat0, lon0, lat, lon, agua):
    """Pixel de agua mas cercano a la coordenada (en grados escalados a metros)."""
    dd = np.hypot((lat - lat0) * 110.6e3, (lon - lon0) * 102.3e3)
    dd = np.where(agua, dd, np.inf)
    f, c = np.unravel_index(np.argmin(dd), dd.shape)
    return int(f), int(c), float(dd[f, c])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--productos", default="datos/productos")
    ap.add_argument("--resultados", default="resultados")
    a = ap.parse_args()
    d, clim, det, evs, zts, fechas, aots, lat, lon = deteccion.anomalias_por_escena(
        a.productos, a.resultados)
    agua, bahia, dist, ft = d["agua"], d["bahia"], d["distancia_costa_m"], d["f_tierra_500m"]

    # E1, igual que en 07_exploratorio.py
    n_det, n_ev = np.sum(det, axis=0), np.sum(evs, axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        freq = np.where(n_ev >= N_EV_MIN, n_det / n_ev, np.nan)
    med = {True: float(np.nanmedian(freq[agua & bahia])),
           False: float(np.nanmedian(freq[agua & ~bahia]))}

    # E3, igual que en 07_exploratorio.py, las dos estaciones
    e3 = np.zeros(agua.shape, bool)
    for ce in clim.values():
        ev_b = ce["evaluable"] & agua & bahia
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            zc, _ = anomalias.anomalia_climatologica(ce["mediana"], dist, ft, ev_b)
        for g in persistencia.grupos(anomalias.detectar_permanentes(zc, ev_b)):
            px = np.array(g["pixeles"]); e3[px[:, 0], px[:, 1]] = True
    lejos = ndimage.distance_transform_edt(~e3) > DIST_MIN_PX

    sitios = []
    for cod, nombre, la, lo in SITIOS:
        f, c, err = pixel_de(la, lo, lat, lon, agua)
        sitios.append({"codigo": cod, "nombre": nombre, "lat": la, "lon": lo, "f": f, "c": c,
                       "error_pixel_m": round(err, 1), "en_bahia": bool(bahia[f, c]),
                       "d_costa_m": float(dist[f, c]), "f_tierra_500m": float(ft[f, c]),
                       "freq_E1": float(freq[f, c])})
    fs, cs = np.indices(agua.shape)
    for s in sitios:
        lejos &= np.hypot(fs - s["f"], cs - s["c"]) > DIST_MIN_PX

    rng = np.random.default_rng(SEMILLA)
    elegidos, controles, reservas = set(), [], []
    for s in sitios:
        zona = bahia if s["en_bahia"] else ~bahia
        ok = (agua & zona & lejos & np.isfinite(freq) & (freq <= med[s["en_bahia"]])
              & (np.abs(dist - s["d_costa_m"]) <= TOL_D)
              & (np.abs(ft - s["f_tierra_500m"]) <= TOL_F))
        cand = [(int(f), int(c)) for f, c in zip(*np.where(ok)) if (f, c) not in elegidos]
        assert cand, f"{s['codigo']}: ningun pixel cumple las condiciones del control"
        orden = [cand[i] for i in rng.permutation(len(cand))]
        elegidos.add(orden[0])
        for k, (f, c) in enumerate(orden[:1 + N_RESERVAS]):
            fila = {"sitio": s["codigo"], "orden": k, "lat": round(float(lat[f, c]), 5),
                    "lon": round(float(lon[f, c]), 5), "d_costa_m": float(dist[f, c]),
                    "f_tierra_500m": round(float(ft[f, c]), 4),
                    "freq_E1": round(float(freq[f, c]), 4), "n_elegibles": len(cand)}
            (controles if k == 0 else reservas).append(fila)

    # barajar: el numero P01-P10 no dice si es sitio o control
    puntos = [("sitio", s["codigo"], s["lat"], s["lon"]) for s in sitios] + \
             [("control", c["sitio"], c["lat"], c["lon"]) for c in controles]
    orden = rng.permutation(len(puntos))
    out = os.path.join(a.resultados, "campo"); os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "clave.csv"), "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["punto", "rol", "sitio", "lat", "lon"])
        for i, j in enumerate(orden):
            w.writerow([f"P{i + 1:02d}", *puntos[j]])
    with open(os.path.join(out, "puntos.csv"), "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["punto", "lat", "lon"])
        for i, j in enumerate(orden):
            # 4 decimales para todos (~11 m): con 5, los ceros finales de los sitios los delatarian
            w.writerow([f"P{i + 1:02d}", f"{puntos[j][2]:.4f}", f"{puntos[j][3]:.4f}"])
    with open(os.path.join(out, "reservas.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(reservas[0])); w.writeheader(); w.writerows(reservas)
    json.dump({"semilla": SEMILLA, "tolerancias": {"d_costa_m": TOL_D, "f_tierra_500m": TOL_F},
               "dist_min_m": 200, "mediana_freq_E1": {"bahia": med[True], "fuera": med[False]},
               "pixeles_E3": int(e3.sum()), "sitios": sitios, "controles": controles},
              open(os.path.join(out, "campo.json"), "w"), indent=1, ensure_ascii=False)
    for s, c in zip(sitios, controles):
        print(s["codigo"], s["en_bahia"], s["d_costa_m"], round(s["f_tierra_500m"], 3),
              "->", c["lat"], c["lon"], c["d_costa_m"], c["f_tierra_500m"], c["n_elegibles"],
              flush=True)


if __name__ == "__main__":
    main()
