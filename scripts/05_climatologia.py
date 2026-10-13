"""Mascara de agua, geometria costera y CLIMATOLOGIA del archivo completo.

Protocolo secciones 5, 6, 7 y 9, con las reglas del registro (seccion 14) del 13/10/2026.
Este script NO calcula ninguna anomalia: la climatologia se calcula y se commitea antes
(regla central del preregistro).

SE EJECUTA EN TU macOS, entorno 'acolite' (numpy + scipy):

    python scripts/05_climatologia.py

Escribe en resultados/: climatologia.npz (se versiona), climatologia.json (resumen y
sha256 del .npz) y escenas_qc.csv (que escena entra, por que, y su ajuste de adyacencia).
El archivo no cabe en 8 GB de RAM: las pilas van a disco (datos/tmp_clim) y las medianas
se calculan por bloques de filas.
"""
import os, sys, csv, json, hashlib, argparse, warnings
import numpy as np
from scipy import ndimage

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "src"))
import escenas, mascara, climatologia

RADIOS_M = (100, 250, 500, 1000)
FILAS_BLOQUE = 16


def mediana_por_bloques(pila):
    med = np.empty(pila.shape[1:], np.float32)
    for r0 in range(0, pila.shape[1], FILAS_BLOQUE):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)   # columnas todo-NaN (tierra)
            med[r0:r0 + FILAS_BLOQUE] = np.nanmedian(pila[:, r0:r0 + FILAS_BLOQUE], axis=0)
    return med


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--productos", default="datos/productos")
    ap.add_argument("--salida", default="resultados")
    ap.add_argument("--tmp", default="datos/tmp_clim")
    a = ap.parse_args()
    os.makedirs(a.tmp, exist_ok=True)

    rutas = escenas.listar(a.productos)
    n = len(rutas)
    e0 = escenas.cargar(rutas[0], ("verde",))
    x, y = e0["x"], e0["y"]
    forma = e0["verde"].shape
    print(f"[1] {n} fechas (un producto por fecha) | rejilla {forma}", flush=True)

    # --- seccion 5: mascara de agua por NDWI mediano ---
    pila = np.lib.format.open_memmap(os.path.join(a.tmp, "ndwi.npy"), "w+",
                                     np.float32, (n,) + forma)
    for i, r in enumerate(rutas):
        pila[i] = escenas.ndwi_sin_nubes(escenas.cargar(r, ("verde", "nir")))
    ndwi_med = mediana_por_bloques(pila)
    del pila
    semillas = [escenas.indice(x, y, *escenas.SEMILLA_BAHIA),
                escenas.indice(x, y, *escenas.SEMILLA_MAR)]
    agua = mascara.agua_desde_mediana(ndwi_med, 0.0, semillas)
    for nombre, (f, c) in zip(("bahia", "mar"), semillas):
        if not agua[f, c]:
            sys.exit(f"La semilla '{nombre}' ({f},{c}) no cae en agua: NDWI mediano "
                     f"{ndwi_med[f, c]:.3f}. No se ajusta a mano: revisar antes de seguir.")
    bahia = escenas.mascara_bahia(x, y)
    agua_bahia = agua & bahia
    dist = mascara.distancia_a_costa(agua, escenas.PIXEL_M)
    f_tierra = {r: mascara.fraccion_tierra(agua, r, escenas.PIXEL_M).astype(np.float32)
                for r in RADIOS_M}
    normal = mascara.normal_a_costa(agua).astype(np.float32)
    km2 = escenas.PIXEL_M ** 2 / 1e6
    print(f"[2] agua {agua.sum()*km2:.2f} km2 ({agua.sum()} px), de ella bahia "
          f"{agua_bahia.sum()*km2:.2f} km2 | distancia maxima a costa {dist.max():.0f} m",
          flush=True)

    # --- secciones 6 y 9: validez por pixel, buques y criterio de escena ---
    pila = np.lib.format.open_memmap(os.path.join(a.tmp, "turb.npy"), "w+",
                                     np.float32, (n,) + forma)
    filas, aceptadas, fechas = [], [], []
    for i, r in enumerate(rutas):
        e = escenas.cargar(r)
        v, info = escenas.validez(e, agua, dist)
        ok, frac = escenas.escena_aceptada(v, agua_bahia, e["aot"])
        t = e["turbidez_dogliotti"]
        fuera = int((v & ((t < 0) | (t > 1000))).sum())
        est = climatologia.estacion_de(e["fecha"])
        filas.append({"fecha": e["fecha"].isoformat(), "producto_l1c": e["l1c"],
                      "estacion": est, "frac_valida_bahia": round(frac, 4),
                      "aceptada": int(ok), "aot_550": round(e["aot"], 4),
                      "adyacencia_A": round(info["A"], 5), "adyacencia_L_m": round(info["L"], 1),
                      "adyacencia_r2": round(info["r2"], 3), "buque_px": info["buque_px"],
                      "validos_fuera_0_1000_FNU": fuera})
        if ok:
            pila[len(aceptadas)] = np.where(v, t, np.nan)
            aceptadas.append(i)
            fechas.append(e["fecha"])
        if (i + 1) % 50 == 0:
            print(f"    {i+1}/{n} escenas revisadas, {len(aceptadas)} aceptadas", flush=True)
    k = len(aceptadas)
    print(f"[3] escenas aceptadas: {k} de {n} ({k/n:.0%})", flush=True)

    # --- seccion 7: climatologia por pixel y estacion (codigo de src/climatologia.py) ---
    clim = {est: {"mediana": np.full(forma, np.nan, np.float32),
                  "mad": np.full(forma, np.nan, np.float32),
                  "n_obs": np.zeros(forma, np.int16),
                  "evaluable": np.zeros(forma, bool), "n_escenas": 0}
            for est in ("seca", "lluviosa")}
    for r0 in range(0, forma[0], FILAS_BLOQUE):
        sl = slice(r0, r0 + FILAS_BLOQUE)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            parte = climatologia.climatologia(np.asarray(pila[:k, sl]), fechas, agua[sl])
        for est, d in parte.items():
            for c in ("mediana", "mad", "n_obs", "evaluable"):
                clim[est][c][sl] = d[c]
            clim[est]["n_escenas"] = d["n_escenas"]
    del pila

    # --- salida ---
    os.makedirs(a.salida, exist_ok=True)
    npz = os.path.join(a.salida, "climatologia.npz")
    datos = {"x": x, "y": y, "agua": agua, "bahia": bahia, "ndwi_mediana": ndwi_med,
             "distancia_costa_m": dist.astype(np.float32), "normal_costa_rad": normal,
             "fechas": np.array([f.isoformat() for f in fechas]),
             "productos_l1c": np.array([filas[i]["producto_l1c"] for i in aceptadas])}
    for r, f in f_tierra.items():
        datos[f"f_tierra_{r}m"] = f
    for est, d in clim.items():
        for c in ("mediana", "mad", "n_obs", "evaluable"):
            datos[f"{est}_{c}"] = d[c]
    np.savez_compressed(npz, **datos)
    with open(os.path.join(a.salida, "escenas_qc.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(filas[0]))
        w.writeheader()
        w.writerows(filas)

    fits = [f for f in filas if f["aceptada"] and np.isfinite(f["adyacencia_r2"])
            and f["adyacencia_r2"] > 0.85]
    pct = lambda v: [round(float(np.percentile(v, q)), 4) for q in (10, 50, 90)] if v else None
    resumen = {
        "fechas": n, "aceptadas": k,
        "aceptadas_por_estacion": {e: d["n_escenas"] for e, d in clim.items()},
        "agua_km2": round(float(agua.sum() * km2), 3),
        "agua_bahia_km2": round(float(agua_bahia.sum() * km2), 3),
        "distancia_max_costa_m": round(float(dist.max()), 1),
        "semillas_px": {"bahia": semillas[0], "mar": semillas[1]},
        "evaluable": {e: {"agua": round(float(d["evaluable"].sum() / agua.sum()), 4),
                          "bahia": round(float(d["evaluable"][agua_bahia].mean()), 4)}
                      for e, d in clim.items()},
        "adyacencia_r2_mayor_085": {"n": len(fits),
                                    "A_p10_p50_p90": pct([f["adyacencia_A"] for f in fits]),
                                    "L_m_p10_p50_p90": pct([f["adyacencia_L_m"] for f in fits])},
        "validos_fuera_0_1000_FNU": int(sum(f["validos_fuera_0_1000_FNU"]
                                            for f in filas if f["aceptada"])),
        "sha256_climatologia_npz": hashlib.sha256(open(npz, "rb").read()).hexdigest(),
    }
    json.dump(resumen, open(os.path.join(a.salida, "climatologia.json"), "w"), indent=1)
    print(json.dumps(resumen, indent=1))


if __name__ == "__main__":
    main()
