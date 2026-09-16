"""Mascara de agua derivada del propio archivo, y geometria costera (protocolo secc. 5)."""
import numpy as np
from scipy import ndimage


def ndwi(b3, b8):
    den = b3 + b8
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(np.abs(den) > 1e-12, (b3 - b8) / den, np.nan)


def mascara_agua(cubo_ndwi, umbral=0.0, semillas=None):
    """Agua = mediana temporal de NDWI > umbral (0 = convencion estandar)."""
    med = np.nanmedian(cubo_ndwi, axis=0)
    agua = np.isfinite(med) & (med > umbral)
    if semillas:
        etiq, _ = ndimage.label(agua)
        conservar = {etiq[f, c] for f, c in semillas if etiq[f, c] > 0}
        agua = np.isin(etiq, list(conservar)) if conservar else np.zeros_like(agua)
    return agua, med


def distancia_a_costa(agua, pixel_m):
    return ndimage.distance_transform_edt(agua) * pixel_m


def fraccion_tierra(agua, radio_m, pixel_m):
    r = max(1, int(round(radio_m / pixel_m)))
    y, x = np.ogrid[-r:r + 1, -r:r + 1]
    disco = ((x * x + y * y) <= r * r).astype(float)
    suma = ndimage.convolve((~agua).astype(float), disco, mode="nearest")
    return suma / disco.sum()


def normal_a_costa(agua):
    _, (iy, ix) = ndimage.distance_transform_edt(agua, return_indices=True)
    fy, fx = np.indices(agua.shape)
    return np.arctan2(ix - fx, iy - fy)


def erosionar_desde_costa(agua, margen_m, pixel_m):
    if margen_m <= 0:
        return agua.copy()
    return distancia_a_costa(agua, pixel_m) > margen_m
