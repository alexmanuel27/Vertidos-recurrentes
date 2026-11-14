"""Anomalias, persistencia, ranking de sitios y pruebas de falsacion.

Protocolo secciones 8-12, con las reglas del registro (seccion 14) del 13/10/2026. Usa la
climatologia CONGELADA (resultados/climatologia.npz) y exactamente las mismas escenas y la
misma validez por pixel que la calcularon (src/escenas.py).

    python scripts/06_deteccion.py
    VERTIDOS_PIXEL_M=10 python scripts/06_deteccion.py --v2 --productos datos/productos_10m --resultados resultados_10m

Con --v2 (protocolo secc. 20.2): desempate en la supresion de no-maximos, familia
climatologica con bandas de la bahia y del mar por separado, y analisis secundario con
persistencia >= 0,05 y >= 3 anios (sitios_secundario.csv), que no entra en el veredicto.

Escribe resultados/deteccion.json (resumen y veredicto de los criterios de la seccion 12)
y resultados/sitios.csv (un sitio por fila, con sus pruebas). El veredicto puede ser
'no concluyente': un criterio que no puede abstenerse no es un criterio.
"""
import os, sys, csv, json, argparse, warnings
import numpy as np
from scipy import stats

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "src"))
import escenas, climatologia, anomalias, persistencia, adyacencia, mascara

PX = escenas.PIXEL_M
RADIO_SITIO_PX = int(round(80 / PX))   # 80 m: incertidumbre de localizacion del pico (secc. 10)
COSTA_M = 400                 # superficie costera del criterio 12.4 (registro 13/10)


def cargar_clim(ruta):
    d = np.load(ruta)
    clim = {e: {c: d[f"{e}_{c}"] for c in ("mediana", "mad", "n_obs", "evaluable")}
            for e in ("seca", "lluviosa")}
    return d, clim


def anomalias_por_escena(productos, resultados):
    """Anomalias de cada escena aceptada, con la climatologia congelada. Lo reutiliza
    07_exploratorio.py: lo exploratorio parte exactamente de las mismas detecciones."""
    d, clim = cargar_clim(os.path.join(resultados, "climatologia.npz"))
    agua, bahia, dist = d["agua"], d["bahia"], d["distancia_costa_m"]
    ft500 = d["f_tierra_500m"]
    aceptados = set(str(p) for p in d["productos_l1c"])

    # --- las mismas escenas aceptadas de la climatologia ---
    rutas = {}
    for r in escenas.listar(productos):
        with np.load(r) as z:
            l1c = str(z["producto_l1c"])
        if l1c in aceptados:
            rutas[l1c] = r
    assert len(rutas) == len(aceptados), (len(rutas), len(aceptados))

    det, evs, zts, fechas, aots = [], [], [], [], []
    lat = lon = None
    for l1c in sorted(rutas, key=lambda s: s.split("_")[2]):
        e = escenas.cargar(rutas[l1c])
        if lat is None:
            with np.load(rutas[l1c]) as z:
                lat, lon = z["lat"], z["lon"]
        v, _ = escenas.validez(e, agua, dist)
        ok, _ = escenas.escena_aceptada(v, agua & bahia, e["aot"])
        assert ok, f"{l1c} ya no pasa el control de calidad: la cadena no es reproducible"
        ce = clim[climatologia.estacion_de(e["fecha"])]
        t = e["turbidez_dogliotti"]
        zt = anomalias.z_temporal(t, ce["mediana"], ce["mad"]).astype(np.float32)
        zs = anomalias.z_espacial(t, v & bahia)            # estadisticos de la bahia
        ev = v & ce["evaluable"]
        m = ev & np.isfinite(zt) & np.isfinite(zs) & (zt >= anomalias.Z_T_MIN) \
            & (zs >= anomalias.Z_S_MIN)                     # solo excesos positivos
        det.append(m); evs.append(ev); zts.append(zt)
        fechas.append(e["fecha"]); aots.append(e["aot"])
    return d, clim, det, evs, zts, fechas, aots, lat, lon


SECUNDARIO = (0.05, 3)        # secc. 20.2: persistencia minima y anios minimos


def evaluar(cand, det, evs, zts, fechas, aots, d, clim, pers, k, umbrales, desempate):
    """Margenes (11.3a), controles (11.3b), aerosoles (11.3c) y criterios de la secc. 12
    sobre una lista de candidatos. umbrales = None para los principales."""
    agua, bahia, dist, ft500 = d["agua"], d["bahia"], d["distancia_costa_m"], d["f_tierra_500m"]
    pmin, amin = umbrales or (None, None)

    # --- 11.3a: barrido de margenes ---
    for c in cand:
        c["sobrevive"] = {}
    rec_por_margen = {}
    for mg in adyacencia.MARGENES_M:
        elig = mascara.erosionar_desde_costa(agua, mg, PX)
        rec = persistencia.ranking(persistencia.agregar_sitios(
            [x & elig for x in det], fechas, [x & elig for x in evs], PX, zts,
            desempate=desempate), pmin=pmin, amin=amin)
        rec_por_margen[mg] = len(rec)
        for c in cand:
            c["sobrevive"][mg] = any(
                np.hypot(r["fila_px"] - c["fila_px"], r["col_px"] - c["col_px"]) * PX
                <= 80 + mg for r in rec)

    # --- 11.3b: controles emparejados ---
    ev_alguna = clim["seca"]["evaluable"] | clim["lluviosa"]["evaluable"]
    for c, ct in zip(cand, adyacencia.controles_emparejados(cand, dist, ft500, agua,
                                                             ev_alguna)):
        celdas = {(f // int(k), cc // int(k)) for f, cc in ct["controles"]}
        vals = [pers[cel] for cel in celdas if np.isfinite(pers[cel])]
        c["n_controles"] = len(vals)
        c["persistencia_controles_mediana"] = float(np.median(vals)) if vals else np.nan
        c["p_controles"] = adyacencia.p_controles(c["persistencia"], vals)
        c["distinguible"] = c["p_controles"] < 0.05

    # --- 11.3c: covariable de aerosoles ---
    yy, xx = np.ogrid[-RADIO_SITIO_PX:RADIO_SITIO_PX + 1, -RADIO_SITIO_PX:RADIO_SITIO_PX + 1]
    disco = (yy ** 2 + xx ** 2) <= RADIO_SITIO_PX ** 2
    for c in cand:
        f0, c0 = int(c["fila_px"]), int(c["col_px"])
        serie = []
        for zt in zts:
            ven = zt[max(f0 - RADIO_SITIO_PX, 0):f0 + RADIO_SITIO_PX + 1,
                     max(c0 - RADIO_SITIO_PX, 0):c0 + RADIO_SITIO_PX + 1]
            msk = disco[:ven.shape[0], :ven.shape[1]] & np.isfinite(ven)
            serie.append(float(ven[msk].max()) if msk.any() else np.nan)
        s, ao = np.array(serie), np.array(aots)
        ok = np.isfinite(s) & np.isfinite(ao)
        if ok.sum() >= 8 and np.std(s[ok]) > 0:
            r, p = stats.pearsonr(s[ok], ao[ok])
        else:
            r, p = np.nan, np.nan
        c["r_aerosol"], c["p_aerosol"] = float(r), float(p)
        c["marcado_aerosol"] = bool(np.isfinite(r) and r > 0 and p < 0.05)
        c["d_costa_m"] = float(dist[f0, c0])
        c["f_tierra_500m"] = float(ft500[f0, c0])
        c["en_bahia"] = bool(bahia[min(f0, bahia.shape[0] - 1), min(c0, bahia.shape[1] - 1)])

    # --- secc. 12: criterios de falsacion ---
    costa = agua & (dist <= COSTA_M)
    no_eval = {e: float(1 - ce["evaluable"][costa].mean()) for e, ce in clim.items()}
    nc = len(cand)
    crit = {
        "12.1_controles": (None if nc == 0 else
                           sum(c["distinguible"] for c in cand) < nc / 2),
        "12.2_margen_40m": nc == 0 or not any(c["sobrevive"][40] for c in cand),
        "12.3_aerosoles": (None if nc == 0 else
                           sum(c["marcado_aerosol"] for c in cand) > nc / 2),
        "12.4_costa_no_evaluada": any(v > 0.5 for v in no_eval.values()),
    }
    if nc == 0:
        veredicto = "NO CONCLUYENTE: ningun sitio recurrente con margen 0"
    elif any(v for v in crit.values()):
        veredicto = "METODO FRACASADO segun " + ", ".join(k2 for k2, v in crit.items() if v)
    else:
        veredicto = "NINGUN CRITERIO DE FRACASO SE CUMPLE"
    return rec_por_margen, no_eval, crit, veredicto


def escribir_sitios(ruta, cand):
    campos = ["rango", "lat", "lon", "este_utm", "norte_utm", "en_bahia", "d_costa_m",
              "f_tierra_500m", "persistencia", "n_detecciones", "n_ocasiones", "n_anios",
              "anios", "tam_medio_px"] + [f"sobrevive_{m}m" for m in adyacencia.MARGENES_M] + \
             ["n_controles", "persistencia_controles_mediana", "p_controles", "distinguible",
              "r_aerosol", "p_aerosol", "marcado_aerosol", "atracadero"]
    with open(ruta, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=campos, extrasaction="ignore")
        w.writeheader()
        for i, c in enumerate(cand, 1):
            fila = dict(c, rango=i, anios=" ".join(map(str, c["anios"])),
                        atracadero="sin verificar")
            for m in adyacencia.MARGENES_M:
                fila[f"sobrevive_{m}m"] = c["sobrevive"][m]
            w.writerow({k2: (round(v, 4) if isinstance(v, float) else v)
                        for k2, v in fila.items() if k2 in campos})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--productos", default="datos/productos")
    ap.add_argument("--resultados", default="resultados")
    ap.add_argument("--v2", action="store_true", help="reglas de la fase 2 (secc. 20.2)")
    a = ap.parse_args()

    d, clim, det, evs, zts, fechas, aots, lat, lon = anomalias_por_escena(a.productos,
                                                                          a.resultados)
    agua, bahia, dist = d["agua"], d["bahia"], d["distancia_costa_m"]
    ft500 = d["f_tierra_500m"]
    n = len(det)
    print(f"[1] {n} escenas | pixeles anomalos por escena: mediana "
          f"{np.median([x.sum() for x in det]):.0f}", flush=True)

    # --- secc. 10: sitios con margen 0 -> candidatos ---
    sitios, pers, k = persistencia.agregar_sitios(det, fechas, evs, PX, zts,
                                                  devolver_mapa=True, desempate=a.v2)
    cand = persistencia.ranking(sitios)
    persistencia.a_coordenadas(cand, d["x"], d["y"], lat, lon)
    print(f"[2] sitios con alguna deteccion: {len(sitios)} | recurrentes (candidatos): "
          f"{len(cand)}", flush=True)
    rec_por_margen, no_eval, crit, veredicto = evaluar(
        cand, det, evs, zts, fechas, aots, d, clim, pers, k, None, a.v2)
    print(f"[3] recurrentes por margen: {rec_por_margen}", flush=True)

    # --- 8.1: familia climatologica (fuente permanente), aparte ---
    # v2: bandas formadas solo por agua de la bahia, y el mar con las suyas (secc. 20.2b)
    permanentes = {}
    for est, ce in clim.items():
        zonas = ([("bahia", ce["evaluable"] & bahia), ("mar", ce["evaluable"] & ~bahia)]
                 if a.v2 else [(None, ce["evaluable"])])
        lista = []
        for zona, ev_z in zonas:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                zc, _ = anomalias.anomalia_climatologica(ce["mediana"], dist, ft500, ev_z)
            for g in persistencia.grupos(anomalias.detectar_permanentes(zc, ev_z)):
                pf, pc = persistencia.pico_de_grupo(g, zc)
                lista.append({"fila_px": pf + 0.5, "col_px": pc + 0.5, "tam_px": g["tam"],
                              "z_c_max": round(float(zc[pf, pc]), 2),
                              "d_costa_m": round(float(dist[pf, pc]), 1),
                              "en_bahia": bool(bahia[pf, pc])})
                if zona:
                    lista[-1]["zona_bandas"] = zona
        persistencia.a_coordenadas(lista, d["x"], d["y"], lat, lon)
        permanentes[est] = sorted(lista, key=lambda g: -g["z_c_max"])
        print(f"[4] permanentes ({est}): {len(lista)} grupos", flush=True)

    # --- salida ---
    escribir_sitios(os.path.join(a.resultados, "sitios.csv"), cand)
    nc = len(cand)
    res = {"escenas": n, "sitios_con_deteccion": len(sitios), "candidatos": nc,
           "recurrentes_por_margen_m": rec_por_margen,
           "candidatos_fuera_de_la_bahia": sum(not c["en_bahia"] for c in cand),
           "candidatos_distinguibles_de_controles": sum(c["distinguible"] for c in cand),
           "candidatos_marcados_aerosol": sum(c["marcado_aerosol"] for c in cand),
           "costa_no_evaluada": {e: round(v, 4) for e, v in no_eval.items()},
           "criterios_fracaso": crit, "veredicto": veredicto,
           "permanentes": permanentes,
           "pendiente": ["anisotropia (11.3d)", "anotacion de atracaderos (secc. 9)"]}
    if a.v2:
        # --- secc. 20.2: analisis secundario, fuera del veredicto ---
        sec = persistencia.ranking(sitios, pmin=SECUNDARIO[0], amin=SECUNDARIO[1])
        persistencia.a_coordenadas(sec, d["x"], d["y"], lat, lon)
        rpm2, _, crit2, ver2 = evaluar(sec, det, evs, zts, fechas, aots, d, clim, pers, k,
                                       SECUNDARIO, True)
        escribir_sitios(os.path.join(a.resultados, "sitios_secundario.csv"), sec)
        res["resolucion_m"] = PX
        res["secundario"] = {
            "umbrales": {"persistencia_min": SECUNDARIO[0], "anios_min": SECUNDARIO[1]},
            "candidatos": len(sec), "recurrentes_por_margen_m": rpm2,
            "candidatos_en_bahia": sum(c["en_bahia"] for c in sec),
            "distinguibles_de_controles": sum(c["distinguible"] for c in sec),
            "marcados_aerosol": sum(c["marcado_aerosol"] for c in sec),
            "criterios_fracaso": crit2, "veredicto_informativo": ver2}
        print(f"[5] secundario: {len(sec)} candidatos | por margen {rpm2}", flush=True)
    json.dump(res, open(os.path.join(a.resultados, "deteccion.json"), "w"), indent=1,
              default=lambda o: o.item() if hasattr(o, "item") else str(o))
    print(json.dumps({k2: v for k2, v in res.items() if k2 != "permanentes"}, indent=1,
                     default=str))


if __name__ == "__main__":
    main()
