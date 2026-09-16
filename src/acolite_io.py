"""Lanzar ACOLITE y leer sus productos, recortados a la ventana de la bahia.

Los nombres de variable de salida de ACOLITE se DESCUBREN del NetCDF, no se codifican a
mano: asi el pipeline no se rompe si cambian entre versiones, y no se inventan nombres
que no se han podido comprobar sin red.
"""
import glob
import os
import re
import numpy as np

import geo

# Patrones con los que se reconocen los productos, por orden de preferencia.
PATRONES = {
    # Nombres VERIFICADOS contra el codigo fuente de ACOLITE (acolite_l2w.py y
    # config/parameter_labels.txt), no supuestos. El producto de Dogliotti es el
    # de 2015 con conmutacion rojo/NIR, y su salida mezclada se llama
    # TUR_Dogliotti2015 (existen ademas las variantes _red y _nir).
    "turbidez_dogliotti": [r"^TUR_Dogliotti2015$", r"^TUR_Dogliotti"],
    "turbidez_nechad":    [r"^TUR_Nechad"],
    "spm":                [r"^SPM_Nechad"],
    "swir":               [r"^rhos_(1[5-9]\d{2}|2[0-4]\d{2})$"],   # B11 ~1610, B12 ~2200
    "verde":              [r"^rhos_(5[3-6]\d{2})$"],                # B3 ~560
    "nir":                [r"^rhos_(8[0-9]\d{2})$"],                # B8 ~833 / B8A ~865
}

AJUSTES = {
    "atmospheric_correction": "dark_spectrum",
    "s2_target_res": 20,        # protocolo seccion 1. El defecto de ACOLITE es 10.
    "dsf_aot_estimate": "fixed",        # por escena, no por baldosa: 5 km es poco
    "dsf_residual_glint_correction": True,
    "l2w_mask_wave": False,
    "l2w_parameters": "tur_dogliotti2015,tur_nechad2009_*,spm_nechad2010_*,rhos_*",
    "output_geolocation": True,
}


def lanzar_acolite(entrada, salida, limite_wgs84, ruta_acolite=None):
    """Corre ACOLITE sobre un producto. limite_wgs84 = (S, O, N, E)."""
    import sys
    if ruta_acolite:
        sys.path.insert(0, ruta_acolite)
    import acolite as ac
    ajustes = dict(AJUSTES)
    ajustes.update({"inputfile": entrada, "output": salida,
                    "limit": list(limite_wgs84), "runid": os.path.basename(entrada)})
    ac.acolite.acolite_run(settings=ajustes)
    return sorted(glob.glob(os.path.join(salida, "*L2W*.nc")))


def variables(nc):
    from netCDF4 import Dataset
    with Dataset(nc) as d:
        return list(d.variables.keys())


def mapear(nombres):
    """Empareja los nombres reales del NetCDF con los productos que necesita el pipeline."""
    salida = {}
    for clave, pats in PATRONES.items():
        for p in pats:
            hit = [n for n in nombres if re.search(p, n, re.IGNORECASE)]
            if hit:
                salida[clave] = sorted(hit)[0] if clave != "swir" else sorted(hit)[-1]
                break
    return salida


def leer(nc, claves=("turbidez_dogliotti", "swir")):
    """Lee los productos pedidos ya recortados a la ventana de trabajo."""
    from netCDF4 import Dataset
    with Dataset(nc) as d:
        mapa = mapear(list(d.variables.keys()))
        faltan = [c for c in claves if c not in mapa]
        if faltan:
            raise KeyError(f"{nc}: no se encontraron {faltan}. Hay: {list(d.variables)}")
        out = {}
        for c in claves:
            v = np.array(d.variables[mapa[c]][:], dtype=np.float32)
            v = np.where(np.isfinite(v), v, np.nan)
            out[c] = v
        out["_mapa"] = mapa
    return out


def fecha_de(nombre):
    """Fecha de adquisicion a partir del nombre del producto Sentinel-2."""
    from datetime import datetime
    m = re.search(r"_(\d{8})T(\d{6})_", os.path.basename(nombre))
    if not m:
        raise ValueError(f"sin fecha en {nombre}")
    return datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S")


def limite_bahia():
    """Ventana de trabajo en (S, O, N, E) WGS84, que es lo que espera ACOLITE."""
    import math
    # inversa aproximada suficiente para un limite de recorte (ACOLITE reproyecta)
    lats = [23.1085, 23.1575]
    lons = [-82.3575, -82.3085]
    return (min(lats), min(lons), max(lats), max(lons))
