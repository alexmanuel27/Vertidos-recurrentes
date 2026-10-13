"""Analisis EXPLORATORIOS, declarados en el registro (seccion 14, 13/10/2026) despues de
ver la deteccion preregistrada (seccion 18). No cambian aquel veredicto.

    python scripts/07_exploratorio.py

E1 frecuencia de deteccion por pixel; E2 sensibilidad del numero de sitios a persistencia
minima, anios minimos y margen; E3 familia climatologica con bandas solo de la bahia;
E4 sitios con desempate en la supresion de no-maximos.
Escribe resultados/exploratorio.json y resultados/exploratorio.png.
"""
import os, sys, json, argparse, warnings, importlib.util
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "src"))
import persistencia, anomalias, adyacencia, mascara

spec = importlib.util.spec_from_file_location("deteccion", os.path.join(AQUI, "06_deteccion.py"))
deteccion = importlib.util.module_from_spec(spec); spec.loader.exec_module(deteccion)

PX = 20.0
PMIN = (0.05, 0.075, 0.10)
AMIN = (3, 4, 5)
N_EV_MIN = 20


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--productos", default="datos/productos")
    ap.add_argument("--resultados", default="resultados")
    a = ap.parse_args()
    d, clim, det, evs, zts, fechas, aots, lat, lon = deteccion.anomalias_por_escena(
        a.productos, a.resultados)
    agua, bahia, dist, ft = d["agua"], d["bahia"], d["distancia_costa_m"], d["f_tierra_500m"]
    en_bahia = lambda s: bool(bahia[min(int(s["fila_px"]), bahia.shape[0] - 1),
                                    min(int(s["col_px"]), bahia.shape[1] - 1)])

    # --- E1: frecuencia de deteccion por pixel ---
    n_det = np.sum(det, axis=0)
    n_ev = np.sum(evs, axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        freq = np.where(n_ev >= N_EV_MIN, n_det / n_ev, np.nan)
    pct = lambda m: [round(float(np.nanpercentile(freq[m], q)), 4) for q in (50, 90, 99)]
    e1 = {"bahia_p50_p90_p99": pct(agua & bahia), "fuera_p50_p90_p99": pct(agua & ~bahia),
          "pixeles_freq_ge_0.10": {"bahia": int(np.nansum(freq[agua & bahia] >= 0.10)),
                                   "fuera": int(np.nansum(freq[agua & ~bahia] >= 0.10))}}
    print("[E1]", e1, flush=True)

    # --- E2 y E4: sitios con desempate, por margen y umbrales ---
    tabla, sitios0 = {}, None
    for mg in adyacencia.MARGENES_M:
        elig = mascara.erosionar_desde_costa(agua, mg, PX)
        s = persistencia.agregar_sitios([x & elig for x in det], fechas,
                                        [x & elig for x in evs], PX, zts, desempate=True)
        if mg == 0:
            sitios0 = s
        for p in PMIN:
            for an in AMIN:
                sel = [x for x in s if np.isfinite(x["persistencia"])
                       and x["persistencia"] >= p and x["n_anios"] >= an]
                tabla[f"margen {mg} m | pers >= {p} | anios >= {an}"] = {
                    "total": len(sel), "bahia": sum(en_bahia(x) for x in sel)}
    print("[E2] margen 0, criterio preregistrado (0,10 y 5 anios):",
          tabla["margen 0 m | pers >= 0.1 | anios >= 5"], flush=True)
    laxos = [x for x in sitios0 if np.isfinite(x["persistencia"])
             and x["persistencia"] >= PMIN[0] and x["n_anios"] >= AMIN[0]]
    persistencia.a_coordenadas(laxos, d["x"], d["y"], lat, lon)
    for x in laxos:
        x["en_bahia"] = en_bahia(x)
        x["d_costa_m"] = float(dist[int(x["fila_px"]), int(x["col_px"])])

    # --- E3: familia climatologica con bandas solo de la bahia ---
    e3, zc_mapa = {}, None
    for est, ce in clim.items():
        ev_b = ce["evaluable"] & agua & bahia
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            zc, _ = anomalias.anomalia_climatologica(ce["mediana"], dist, ft, ev_b)
        if est == "seca":
            zc_mapa = zc
        gr = persistencia.grupos(anomalias.detectar_permanentes(zc, ev_b))
        lista = []
        for g in gr:
            pf, pc = persistencia.pico_de_grupo(g, zc)
            lista.append({"fila_px": pf + 0.5, "col_px": pc + 0.5, "tam_px": g["tam"],
                          "z_c_max": round(float(zc[pf, pc]), 2),
                          "d_costa_m": round(float(dist[pf, pc]), 1)})
        persistencia.a_coordenadas(lista, d["x"], d["y"], lat, lon)
        e3[est] = sorted(lista, key=lambda g: -g["z_c_max"])
        print(f"[E3] {est}: {len(lista)} grupos en la bahia", flush=True)

    # --- figura (exploratoria, en espanol; no es figura del articulo) ---
    filas = np.where(bahia.any(axis=1))[0]; cols = np.where(bahia.any(axis=0))[0]
    zf = slice(max(filas[0] - 15, 0), filas[-1] + 15)
    zcl = slice(max(cols[0] - 15, 0), cols[-1] + 15)
    fig, ax = plt.subplots(1, 2, figsize=(11, 5.6))
    tierra = np.where(agua, np.nan, 1.0)
    for eje, mapa, tit, vmax in ((ax[0], freq, "E1  frecuencia de deteccion por pixel", 0.15),
                                 (ax[1], zc_mapa, "E3  z_c con bandas solo de la bahia (seca)", 5)):
        eje.imshow(tierra[zf, zcl], cmap="Greys", vmin=0, vmax=3, interpolation="nearest")
        im = eje.imshow(mapa[zf, zcl], cmap="viridis", vmin=0, vmax=vmax,
                        interpolation="nearest")
        fig.colorbar(im, ax=eje, shrink=0.8)
        eje.set_title(tit, fontsize=10); eje.set_xticks([]); eje.set_yticks([])
    alto, ancho = tierra[zf, zcl].shape
    for x in laxos:          # solo los que caen dentro del recorte de la bahia
        fx, cx = x["fila_px"] - zf.start, x["col_px"] - zcl.start
        if 0 <= fx < alto and 0 <= cx < ancho:
            ax[0].plot(cx, fx, "o", mfc="none", mec="#eb6834", ms=10, mew=1.5)
    ax[0].set_xlim(-0.5, ancho - 0.5); ax[0].set_ylim(alto - 0.5, -0.5)
    fig.suptitle("EXPLORATORIO (registro 13/10/2026). Circulos: sitios con persistencia "
                 ">= 0,05 y >= 3 anios, margen 0", fontsize=9)
    fig.tight_layout()
    fig.savefig(os.path.join(a.resultados, "exploratorio.png"), dpi=150)

    res = {"advertencia": "EXPLORATORIO: no cambia el veredicto preregistrado (secc. 18)",
           "E1_frecuencia_deteccion": e1, "E2_sensibilidad": tabla,
           "E4_sitios_laxos_margen0": [{k: x.get(k) for k in
               ("lat", "lon", "este_utm", "norte_utm", "en_bahia", "d_costa_m",
                "persistencia", "n_detecciones", "n_ocasiones", "n_anios", "anios")}
               for x in laxos],
           "E3_permanentes_bahia": e3}
    json.dump(res, open(os.path.join(a.resultados, "exploratorio.json"), "w"), indent=1,
              default=lambda o: o.item() if hasattr(o, "item") else str(o))


if __name__ == "__main__":
    main()
