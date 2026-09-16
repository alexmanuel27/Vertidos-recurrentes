"""Climatologia por pixel: mediana y MAD escalada, por estacion (protocolo secc. 7).

Se calcula y se congela sobre el archivo completo ANTES de calcular ninguna anomalia.
"""
import numpy as np

ESCALA_MAD = 1.4826
N_MIN_OBS = 20
MESES_SECA = (11, 12, 1, 2, 3, 4)


def estacion_de(fecha):
    return "seca" if fecha.month in MESES_SECA else "lluviosa"


def mediana_mad(cubo, escala=ESCALA_MAD):
    med = np.nanmedian(cubo, axis=0)
    mad = np.nanmedian(np.abs(cubo - med), axis=0) * escala
    return med, mad


def climatologia(cubo, fechas, agua):
    """{estacion: dict(mediana, mad, n_obs, evaluable)}."""
    salida = {}
    for est in ("seca", "lluviosa"):
        sel = np.array([estacion_de(f) == est for f in fechas])
        sub = cubo[sel]
        if sub.size == 0:
            continue
        med, mad = mediana_mad(sub)
        n_obs = np.sum(np.isfinite(sub), axis=0)
        evaluable = agua & (n_obs >= N_MIN_OBS) & np.isfinite(mad) & (mad > 0)
        salida[est] = {"mediana": med, "mad": mad, "n_obs": n_obs,
                       "evaluable": evaluable, "n_escenas": int(sel.sum())}
    return salida


def resumen(clim, agua):
    """Fraccion de superficie de agua evaluable. El complemento es el coste real
    del problema de adyacencia y va en el articulo."""
    tot = int(agua.sum())
    return {est: {"evaluable_px": int(d["evaluable"].sum()),
                  "fraccion": round(float(d["evaluable"].sum() / tot), 4) if tot else 0.0,
                  "n_escenas": d["n_escenas"]}
            for est, d in clim.items()}
