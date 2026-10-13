"""Carga del archivo de escenas (.npz) y control de calidad por pixel y por escena.

Lo comparten la climatologia y, despues, la deteccion: las dos tienen que ver las MISMAS
escenas con la MISMA validez, o la anomalia se mediria contra una base distinta.
Reglas: PROTOCOLO_CONGELADO.md secciones 1, 5, 6 y 9 y registro de la seccion 14.
"""
import glob
import os
import re
from collections import defaultdict
from datetime import datetime

import numpy as np

import adyacencia
import anomalias
import geo

PIXEL_M = 20.0
# Bits de l2_flags: 0 no-agua SWIR, 1 cirros, 2 TOA alto, 3 rho negativa, 4 fuera de escena,
# 5 pixel mixto. Nunca 0 ni 5: son la orilla y el agua muy turbia (CONTEXTO, lecciones).
BITS_QC = (1 << 1) | (1 << 2) | (1 << 3) | (1 << 4)
BITS_NUBE = (1 << 1) | (1 << 2) | (1 << 4)      # para el NDWI de la mascara (registro 13/10)
BIT_FUERA = 1 << 4
UMBRAL_SWIR2 = 0.010                            # bruma: rho(2200 nm) sobre agua (16/09)
FRAC_MIN_ESCENA = 0.60                          # sobre el agua de la bahia (13/10)
SEMILLA_BAHIA = geo.PUNTOS_CONTROL["centro"]    # componentes conexas de la mascara
SEMILLA_MAR = (23.200, -82.333)


def banderas(d):
    b = d["banderas"]
    return np.where(np.isfinite(b), b, 0).astype(np.int64)


def _sello(l1c):
    """Sello de procesado del L1C (ultimo campo del nombre): desempate entre trozos."""
    return l1c.replace(".SAFE", "").split("_")[-1]


def elegir_por_fecha(candidatos):
    """Un producto por fecha (registro 13/10): el que mas ventana cubre; empate -> el de
    procesado mas reciente. candidatos: [(clave, n_px_en_escena, producto_l1c, ruta)]."""
    grupos = defaultdict(list)
    for c in candidatos:
        grupos[c[0]].append(c)
    return sorted(max(g, key=lambda c: (c[1], _sello(c[2])))[3] for g in grupos.values())


def listar(carpeta):
    """Rutas de los .npz a usar, una por fecha de adquisicion."""
    cand = []
    for f in sorted(glob.glob(os.path.join(carpeta, "*.npz"))):
        with np.load(f) as d:
            l1c = str(d["producto_l1c"])
            if not l1c:
                raise ValueError(f"{f} no dice de que L1C sale: reexportalo (02_exportar_npz)")
            dentro = int(((banderas(d) & BIT_FUERA) == 0).sum())
        m = re.search(r"_(\d{8})T", l1c)
        cand.append(((l1c[:3], m.group(1)), dentro, l1c, f))
    return elegir_por_fecha(cand)


def cargar(ruta, claves=("turbidez_dogliotti", "swir", "swir2", "verde", "nir")):
    with np.load(ruta) as d:
        e = {k: d[k].astype(np.float32) for k in claves}
        e["flags"] = banderas(d)
        e["fecha"] = datetime.fromisoformat(str(d["fecha"]))
        e["aot"] = float(d["aot_550"])
        e["l1c"] = str(d["producto_l1c"])
        e["x"], e["y"] = d["x"], d["y"]
    return e


def indice(x, y, lat, lon):
    """(fila, col) del pixel mas cercano a un punto lat/lon."""
    _, este, norte = geo.ll2utm(lat, lon)
    return int(np.argmin(np.abs(y - norte))), int(np.argmin(np.abs(x - este)))


def mascara_bahia(x, y):
    """La bahia de la seccion 1 (ventana de la v1.0) sobre la rejilla ampliada."""
    cx = (x >= geo.ESTE_MIN) & (x <= geo.ESTE_MAX)
    cy = (y >= geo.NORTE_MIN) & (y <= geo.NORTE_MAX)
    return cy[:, None] & cx[None, :]


def ndwi_sin_nubes(e):
    """NDWI de una escena con nubes, cirros y fuera de escena a NaN (para la mascara)."""
    import mascara
    v = mascara.ndwi(e["verde"], e["nir"])
    return np.where((e["flags"] & BITS_NUBE) == 0, v, np.nan).astype(np.float32)


def validez(e, agua, dist):
    """Pixeles validos de una escena (seccion 6) y la mascara de buques (seccion 9).

    Devuelve (validos, info) con el ajuste de adyacencia de la escena, que la seccion
    11.2 pide reportar.
    """
    v = agua & np.isfinite(e["turbidez_dogliotti"]) & ((e["flags"] & BITS_QC) == 0)
    v &= ~(np.isfinite(e["swir2"]) & (e["swir2"] > UMBRAL_SWIR2))
    aj = adyacencia.ajustar_decaimiento(e["swir"], dist, v)
    res = adyacencia.residuo_swir(e["swir"], dist, aj)
    umb = adyacencia.umbral_robusto(res, v)
    buq = anomalias.mascara_buques(res, umb, v)
    v &= ~buq
    info = {"A": aj["A"] if aj else np.nan, "L": aj["L"] if aj else np.nan,
            "r2": aj["r2"] if aj else np.nan, "buque_px": int(buq.sum())}
    return v, info


def escena_aceptada(v, agua_bahia, aot):
    """60 % del agua de la bahia valida y DSF convergido (AOT finito)."""
    frac = float(v[agua_bahia].sum() / max(agua_bahia.sum(), 1))
    return (frac >= FRAC_MIN_ESCENA and np.isfinite(aot)), frac


if __name__ == "__main__":
    # Comprobacion de la regla de fechas partidas.
    c = [(("S2A", "20160115"), 10, "S2A_x_20231027T180111.SAFE", "a"),
         (("S2A", "20160115"), 900, "S2A_x_20231013T171001.SAFE", "b"),
         (("S2B", "20200208"), 500, "S2B_x_20230412T012443.SAFE", "c"),
         (("S2B", "20200208"), 500, "S2B_x_20230701T075632.SAFE", "d"),
         (("S2A", "20220101"), 7, "S2A_x_20240101T000000.SAFE", "e")]
    assert elegir_por_fecha(c) == ["b", "d", "e"], elegir_por_fecha(c)
    print("elegir_por_fecha OK")
