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
    # Nombres COMPROBADOS sobre salidas reales de ACOLITE. Ojo: S2A y S2B tienen
    # centros de banda distintos (1614/1610, 560/559, 865/864), por eso van por rango.
    "turbidez_dogliotti": [r"^TUR_Dogliotti2015$", r"^TUR_Dogliotti"],
    "turbidez_nechad":    [r"^TUR_Nechad"],
    "spm":                [r"^SPM_Nechad"],
    "swir":               [r"^rhos_16\d{2}$", r"^rhos_2[12]\d{2}$"],  # B11 preferida a B12
    "verde":              [r"^rhos_5[56]\d$"],                        # B3
    "nir":                [r"^rhos_83\d$"],                           # B8
    "banderas":           [r"^l2_flags$"],
}

AJUSTES = {
    "atmospheric_correction": "dark_spectrum",
    "s2_target_res": 20,             # protocolo seccion 1. El defecto de ACOLITE es 10.
    "dsf_aot_estimate": "fixed",     # por escena: 5 km es poco para estimar por baldosa
    "dsf_residual_glint_correction": True,
    # OJO: tiene que ser una LISTA. ACOLITE hace `for par in l2w_parameters`, asi que
    # una cadena se recorre LETRA A LETRA y no calcula ningun producto.
    "l2w_parameters": ["tur_dogliotti2015", "tur_nechad2009_*",
                       "spm_nechad2010_*", "rhos_*"],
    # ACOLITE calcula sus banderas y las guarda en l2_flags, pero NO las aplica a los
    # productos: su mascara por SWIR (umbral 0.0215 a 1600 nm) borraria el agua muy
    # turbia, que es justo lo que buscamos. El enmascarado lo hacemos nosotros, de
    # forma auditable (protocolo secciones 6 y 9).
    "l2w_mask_water_parameters": False,
    "output_geolocation": True,
    "output_xy": True,
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
    """Empareja los nombres reales del NetCDF con los productos del pipeline.

    Recorre los patrones EN ORDEN y se queda con el primero que acierte, de modo que
    la preferencia (B11 antes que B12, por ejemplo) queda explicita en PATRONES.
    """
    salida = {}
    for clave, pats in PATRONES.items():
        for pat in pats:
            hit = sorted(n for n in nombres if re.search(pat, n, re.IGNORECASE))
            if hit:
                salida[clave] = hit[0]
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
