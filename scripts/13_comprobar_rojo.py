"""Comprobacion del rojo a 10 m (protocolo secc. 20.2), sobre las primeras escenas exportadas.

    VERTIDOS_PIXEL_M=10 python scripts/13_comprobar_rojo.py datos/productos_10m [n_escenas=2]

Dogliotti 2015 «blended» usa solo el rojo (B4, nativo a 10 m) mientras rho(665) < 0,05.
Cuenta, en el agua valida de la bahia de cada escena, la fraccion con rho(665) >= 0,05.
Agua = NDWI de la propia escena > 0 (aun no hay mascara de la mediana a 10 m); valido =
bits 1-4 de l2_flags sin activar y rho(2200) <= 0,010. Regla fijada en 20.2: si en alguna
escena pasa del 1 %, la deteccion a 10 m usa tur_dogliotti2015_red.
"""
import os, sys, glob
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import escenas, mascara

carpeta = sys.argv[1]
n = int(sys.argv[2]) if len(sys.argv) > 2 else 2
peor = 0.0
for r in sorted(glob.glob(os.path.join(carpeta, "*.npz")))[:n]:
    z = np.load(r)
    assert "rojo" in z.files, f"{r} no trae rho(665): exportado antes del 13/11/2026"
    bahia = escenas.mascara_bahia(z["x"], z["y"])
    agua = mascara.ndwi(z["verde"], z["nir"]) > 0
    v = bahia & agua & ((z["banderas"].astype(np.int64) & escenas.BITS_QC) == 0) \
        & (z["swir2"] <= escenas.UMBRAL_SWIR2) & np.isfinite(z["rojo"])
    f = float((z["rojo"][v] >= 0.05).mean()) if v.any() else np.nan
    peor = max(peor, f) if np.isfinite(f) else peor
    print(f"{os.path.basename(r)}: {int(v.sum())} px validos, rho(665) >= 0,05 en {100 * f:.2f} %")
print("DECISION:", "usar tur_dogliotti2015_red" if peor > 0.01 else "se queda el blended (es rojo en la bahia)")
