"""Gradiente de turbidez por zona y estacion con TODAS las escenas aceptadas (EXPLORATORIO).

    python scripts/24_gradiente.py                                       # 20 m
    VERTIDOS_PIXEL_M=10 python scripts/24_gradiente.py --productos datos/productos_10m \
        --resultados resultados_10m

Definido en la fila del 17/11/2026 de la secc. 14 (peticion del chat del articulo), antes de calcularlo.
Estadistico: mediana entre escenas de la mediana por escena de la turbidez de Dogliotti en cada zona del
modelo (con y sin los pixeles a < 100 m de costa); IC 95 % por bootstrap de ESCENAS (2000 remuestreos,
semilla fija). Detalle de implementacion fijado antes de correr: una zona en una escena cuenta solo con
>= N_MIN_PX pixeles validos. Tambien: mediana de la climatologia por pixel (como la secc. 23) y dejar un anio
fuera cada vez. Escribe gradiente_<res>m.json y gradiente_escenas_<res>m.csv.
"""
import os, sys, json, argparse, csv
import numpy as np
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "src"))
import climatologia, escenas, geo

ZN = ("atares", "guasabacoa", "marimelena", "bahia_centro_y_canal", "mar")
N_MIN_PX, N_BOOT, SEMILLA = 50, 2000, 20261117


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


def orden(med):
    """True si min(Atares, Guasabacoa) > max(Marimelena, centro) > mar; devuelve (cumple, margen_brazos, margen_mar)."""
    if any(med.get(k) is None or not np.isfinite(med[k]) for k in ZN):
        return None
    br = min(med["atares"], med["guasabacoa"]); mid = max(med["marimelena"], med["bahia_centro_y_canal"])
    return {"cumple": bool(br > mid > med["mar"]), "margen_brazos_menos_medio": round(float(br - mid), 3),
            "margen_medio_menos_mar": round(float(mid - med["mar"]), 3)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--productos", default="datos/productos"); ap.add_argument("--resultados", default="resultados")
    a = ap.parse_args()
    cl = np.load(os.path.join(a.resultados, "climatologia.npz"))
    agua, bahia, dist = cl["agua"].astype(bool), cl["bahia"].astype(bool), cl["distancia_costa_m"]
    z = zonas(cl); lejos = dist >= 100
    acept = set(str(p) for p in cl["productos_l1c"])
    filas = []
    for r in escenas.listar(a.productos):
        e = escenas.cargar(r)
        if e["l1c"] not in acept:
            continue
        v, _ = escenas.validez(e, agua, dist)
        t = np.where(v, e["turbidez_dogliotti"], np.nan)
        f = {"fecha": e["fecha"].date().isoformat(), "anio": e["fecha"].year, "estacion": climatologia.estacion_de(e["fecha"])}
        for n in ZN:
            for var, m in (("todos", z == n), ("a100m", (z == n) & lejos)):
                x = t[m & np.isfinite(t)]
                f[f"{n}_{var}_n"] = int(x.size); f[f"{n}_{var}"] = float(np.median(x)) if x.size >= N_MIN_PX else float("nan")
        filas.append(f); print(f["fecha"], f["estacion"], flush=True)
    with open(os.path.join(a.resultados, f"gradiente_escenas_{int(geo.PIXEL_M)}m.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(filas[0].keys())); w.writeheader(); w.writerows(filas)
    rng = np.random.default_rng(SEMILLA)
    res = {"resolucion_m": geo.PIXEL_M, "n_escenas": len(filas), "n_min_px_por_zona_y_escena": N_MIN_PX, "n_bootstrap": N_BOOT,
           "estaciones": {}}
    for est in ("seca", "lluviosa"):
        fe = [f for f in filas if f["estacion"] == est]
        d = {"n_escenas": len(fe), "anios": sorted({f["anio"] for f in fe}), "variantes": {}, "dejar_un_anio": {}, "climatologia_pixel_secc23": {}}
        ev = cl[est + "_evaluable"].astype(bool); mc = cl[est + "_mediana"]
        for n in ZN:
            ok = ev & np.isfinite(mc) & (z == n)
            d["climatologia_pixel_secc23"][n] = {"todos": round(float(np.median(mc[ok])), 2),
                                                 "a100m": round(float(np.median(mc[ok & lejos])), 2), "n_px": int(ok.sum())}
        for var in ("todos", "a100m"):
            zz = {}
            for n in ZN:
                x = np.array([f[f"{n}_{var}"] for f in fe]); x = x[np.isfinite(x)]
                lo, hi = np.percentile(np.median(x[rng.integers(0, x.size, (N_BOOT, x.size))], axis=1), [2.5, 97.5])
                zz[n] = {"mediana_FNU": round(float(np.median(x)), 3), "ic95": [round(float(lo), 3), round(float(hi), 3)],
                         "n_escenas": int(x.size), "n_px_climatologia": d["climatologia_pixel_secc23"][n]["n_px"]}
            d["variantes"][var] = {"zonas": zz, "orden": orden({n: zz[n]["mediana_FNU"] for n in ZN})}
            ult = {}
            for y in d["anios"]:
                med = {}
                for n in ZN:
                    x = np.array([f[f"{n}_{var}"] for f in fe if f["anio"] != y]); x = x[np.isfinite(x)]
                    med[n] = float(np.median(x)) if x.size else None
                ult[str(y)] = orden(med)
            d["dejar_un_anio"][var] = ult
            d["variantes"][var]["anios_en_que_se_mantiene_el_orden"] = f"{sum(1 for o in ult.values() if o and o['cumple'])}/{len(ult)}"
        res["estaciones"][est] = d
        print(est, json.dumps({k: d["variantes"][k] for k in d["variantes"]}, ensure_ascii=False), flush=True)
    json.dump(res, open(os.path.join(a.resultados, f"gradiente_{int(geo.PIXEL_M)}m.json"), "w"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
