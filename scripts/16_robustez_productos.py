"""Comprobacion de robustez entre productos (protocolo secc. 4): la cadena de deteccion se
repite con la turbidez de Nechad y con el SPM de Nechad, cada uno con su propia climatologia
sobre las MISMAS escenas aceptadas y la MISMA validez por pixel que la de Dogliotti.

    python scripts/16_robustez_productos.py

Regla de la secc. 4: una deteccion que aparece en un producto y desaparece en los otros dos
es sospechosa y se anota. Para los candidatos preregistrados (resultados/sitios.csv),
«aparece» = hay un sitio recurrente (umbrales principales) a <= 80 m. Para los focos
exploratorios (S3-S5 de resultados/campo/campo.json) se informan su frecuencia E1 y el z_c
maximo con bandas de la bahia (E3) a <= 80 m, en cada producto. Autocomprobacion: con
Dogliotti la climatologia y los sitios tienen que salir iguales a los congelados.
Escribe resultados/robustez_productos.json.
"""
import os, sys, csv, json, warnings, importlib.util
import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "src"))
import escenas, climatologia, anomalias, persistencia, geo

spec = importlib.util.spec_from_file_location("deteccion", os.path.join(AQUI, "06_deteccion.py"))
deteccion = importlib.util.module_from_spec(spec); spec.loader.exec_module(deteccion)

PRODUCTOS = ("turbidez_dogliotti", "turbidez_nechad", "spm")
PX = geo.PIXEL_M
RADIO_M = 80.0
N_EV_MIN = 20


def main():
    d, clim_cong = deteccion.cargar_clim("resultados/climatologia.npz")
    agua, bahia, dist, ft = d["agua"], d["bahia"], d["distancia_costa_m"], d["f_tierra_500m"]
    aceptados = set(str(p) for p in d["productos_l1c"])
    rutas = {}
    for r in escenas.listar("datos/productos"):
        with np.load(r) as z:
            if str(z["producto_l1c"]) in aceptados:
                rutas[str(z["producto_l1c"])] = r
    assert len(rutas) == len(aceptados)
    orden = sorted(rutas, key=lambda s: s.split("_")[2])
    n, forma = len(orden), agua.shape
    cubo = {p: np.full((n,) + forma, np.nan, np.float32) for p in PRODUCTOS}
    val = np.zeros((n,) + forma, bool)
    fechas = []
    for i, l1c in enumerate(orden):
        e = escenas.cargar(rutas[l1c], claves=("swir", "swir2", "verde", "nir") + PRODUCTOS)
        v, _ = escenas.validez(e, agua, dist)
        val[i] = v; fechas.append(e["fecha"])
        for p in PRODUCTOS:
            cubo[p][i] = np.where(v & np.isfinite(e[p]), e[p], np.nan)

    with np.load(sorted(rutas.values())[0]) as z:
        lat, lon = z["lat"], z["lon"]
    fs, cs = np.indices(forma)
    sitios_csv = [r for r in csv.DictReader(open("resultados/sitios.csv"))]
    focos = [s for s in json.load(open("resultados/campo/campo.json"))["sitios"] if s["codigo"] in ("S3", "S4", "S5")]
    pos = lambda E, N: (int(np.argmin(np.abs(d["y"] - N))), int(np.argmin(np.abs(d["x"] - E))))
    res = {"escenas": n, "productos": {}}
    for p in PRODUCTOS:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            clim = climatologia.climatologia(cubo[p], fechas, agua)
        if p == "turbidez_dogliotti":     # autocomprobacion contra la climatologia congelada
            for est in clim:
                assert np.allclose(clim[est]["mediana"], clim_cong[est]["mediana"], equal_nan=True, atol=1e-5)
                assert np.array_equal(clim[est]["evaluable"], clim_cong[est]["evaluable"])
        det, evs, zts = [], [], []
        for i, f in enumerate(fechas):
            ce = clim[climatologia.estacion_de(f)]
            t = cubo[p][i]
            with np.errstate(invalid="ignore"):
                zt = anomalias.z_temporal(t, ce["mediana"], ce["mad"]).astype(np.float32)
                zs = anomalias.z_espacial(t, val[i] & bahia)
                ev = val[i] & ce["evaluable"]
                m = ev & np.isfinite(zt) & np.isfinite(zs) & (zt >= anomalias.Z_T_MIN) & (zs >= anomalias.Z_S_MIN)
            det.append(m); evs.append(ev); zts.append(zt)
        sitios, pers, k = persistencia.agregar_sitios(det, fechas, evs, PX, zts, devolver_mapa=True)
        rec = persistencia.ranking(sitios)
        persistencia.a_coordenadas(rec, d["x"], d["y"], lat, lon)
        if p == "turbidez_dogliotti":
            assert [(round(s["este_utm"]), round(s["norte_utm"])) for s in rec] == \
                   [(round(float(r["este_utm"])), round(float(r["norte_utm"]))) for r in sitios_csv], "no reproduce sitios.csv"
        n_det, n_ev = np.sum(det, axis=0), np.sum(evs, axis=0)
        with np.errstate(invalid="ignore", divide="ignore"):
            freq = np.where(n_ev >= N_EV_MIN, n_det / n_ev, np.nan)
        zc_b = {}
        for est, ce in clim.items():
            ev_b = ce["evaluable"] & agua & bahia
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                zc_b[est], _ = anomalias.anomalia_climatologica(ce["mediana"], dist, ft, ev_b)
        out = {"recurrentes_margen_0": [{"este_utm": s["este_utm"], "norte_utm": s["norte_utm"],
                                         "persistencia": round(s["persistencia"], 4), "n_anios": s["n_anios"]} for s in rec],
               "candidatos": [], "focos": []}
        for r in sitios_csv:
            E, N = float(r["este_utm"]), float(r["norte_utm"])
            f0, c0 = pos(E, N)
            cerca = any(np.hypot(s["este_utm"] - E, s["norte_utm"] - N) <= RADIO_M for s in rec)
            out["candidatos"].append({"rango": int(r["rango"]), "este_utm": E, "norte_utm": N,
                                      "recurrente_a_80m": cerca,
                                      "persistencia_celda": round(float(pers[int(f0 // k), int(c0 // k)]), 4)})
        for s in focos:
            f0, c0 = s["f"], s["c"]
            disco = np.hypot(fs - f0, cs - c0) * PX <= RADIO_M
            out["focos"].append({"sitio": s["codigo"], "nombre": s["nombre"],
                                 "frecuencia_E1": None if not np.isfinite(freq[f0, c0]) else round(float(freq[f0, c0]), 4),
                                 **{f"z_c_max_80m_{est}": (None if not np.isfinite(zc_b[est][disco]).any()
                                                          else round(float(np.nanmax(zc_b[est][disco])), 2)) for est in zc_b}})
        res["productos"][p] = out
        print(p, "recurrentes:", len(rec), "| candidatos a 80 m:", [c["recurrente_a_80m"] for c in out["candidatos"]], flush=True)
    for j, c in enumerate(res["productos"]["turbidez_dogliotti"]["candidatos"]):
        otros = [res["productos"][p]["candidatos"][j]["recurrente_a_80m"] for p in PRODUCTOS[1:]]
        c["sospechoso_secc4"] = bool(c["recurrente_a_80m"] and not any(otros))
    json.dump(res, open("resultados/robustez_productos.json", "w"), indent=1, ensure_ascii=False)
    print(json.dumps({p: {"candidatos": v["candidatos"], "focos": v["focos"]} for p, v in res["productos"].items()},
                     indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
