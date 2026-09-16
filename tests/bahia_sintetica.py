"""Bahia sintetica para validar la cadena de deteccion antes de tener datos reales.

Se plantan a proposito los cuatro elementos que el metodo debe distinguir:
  1. fuente INTERMITENTE en la orilla   -> debe salir en el ranking
  2. fuente PERMANENTE en la orilla     -> ciega para temporal+espacial; la debe coger
                                           la familia climatologica (protocolo 8.1)
  3. ARTEFACTO DE ADYACENCIA que decae con la distancia y varia entre escenas
                                         -> NO debe generar sitios recurrentes
  4. BUQUES transitorios y uno ATRACADO fijo -> el atracado es el falso positivo duro
"""
import numpy as np
from datetime import date, timedelta
from scipy import ndimage

FORMA = (252, 238)
PIXEL_M = 20.0
L_ADYACENCIA_M = 120.0


def geometria(forma=FORMA):
    f, c = np.indices(forma)
    agua = np.zeros(forma, bool)
    agua |= ((f - 150) / 70.0) ** 2 + ((c - 112) / 52.0) ** 2 <= 1.0   # bolsa principal
    agua |= ((f - 118) / 26.0) ** 2 + ((c - 172) / 20.0) ** 2 <= 1.0   # ensenada NE
    agua |= ((f - 178) / 22.0) ** 2 + ((c - 170) / 18.0) ** 2 <= 1.0   # ensenada E
    agua |= ((f - 212) / 24.0) ** 2 + ((c - 106) / 20.0) ** 2 <= 1.0   # ensenada S
    agua |= (f >= 28) & (f <= 92) & (c >= 96) & (c <= 110)             # canal estrecho
    agua |= f < 30                                                     # mar abierto
    agua = ndimage.binary_closing(agua, np.ones((3, 3)))
    etiq, _ = ndimage.label(agua)
    return etiq == etiq[150, 112]


def campos(agua, pixel_m=PIXEL_M):
    dist = ndimage.distance_transform_edt(agua) * pixel_m
    r = int(round(500.0 / pixel_m))
    y, x = np.ogrid[-r:r + 1, -r:r + 1]
    disco = ((x * x + y * y) <= r * r).astype(float)
    f_tierra = ndimage.convolve((~agua).astype(float), disco, mode="nearest") / disco.sum()
    return dist, f_tierra


def elegir_orilla(agua, dist, fila, col, d_lo=20.0, d_hi=70.0):
    cand = agua & (dist >= d_lo) & (dist <= d_hi)
    fs, cs = np.where(cand)
    k = np.argmin((fs - fila) ** 2 + (cs - col) ** 2)
    return int(fs[k]), int(cs[k])


def pluma(forma, origen, amplitud, escala_px=4.0, acimut=0.0, alarg=3.0):
    """Pluma anisotropa con fuente puntual, alargada a lo largo de un eje."""
    f, c = np.indices(forma)
    df, dc = f - origen[0], c - origen[1]
    u = df * np.cos(acimut) + dc * np.sin(acimut)
    v = -df * np.sin(acimut) + dc * np.cos(acimut)
    return amplitud * np.exp(-np.sqrt((u / alarg) ** 2 + v ** 2) / escala_px)


def generar(n_escenas=220, semilla=7):
    rng = np.random.default_rng(semilla)
    agua = geometria()
    dist, f_tierra = campos(agua)
    fuente_int = elegir_orilla(agua, dist, 205, 100)
    fuente_per = elegir_orilla(agua, dist, 176, 186)
    atracadero = elegir_orilla(agua, dist, 120, 156)

    base = ndimage.gaussian_filter(
        np.where(np.indices(FORMA)[0] < 30, 2.0, 8.0).astype(np.float32), 6.0)
    decae = np.exp(-dist / L_ADYACENCIA_M)

    fechas, turb, swir = [], [], []
    d0, k = date(2016, 1, 1), 0
    while len(fechas) < n_escenas:
        f = d0 + timedelta(days=5 * k); k += 1
        if f.year > 2025:
            break
        if rng.random() > 0.32:                     # nubosidad tropical
            continue
        A = float(rng.lognormal(np.log(6.0), 0.40))  # carga de aerosoles del dia
        t = base + A * decae + rng.normal(0, 1.2, FORMA).astype(np.float32)
        s = 0.002 + A * 0.0015 * decae + rng.normal(0, 0.0008, FORMA)
        if rng.random() < 0.35:
            t = t + pluma(FORMA, fuente_int, 25.0, 4.0, rng.uniform(0, np.pi), 3.0)
        t = t + pluma(FORMA, fuente_per, 9.0, 5.0, 0.6, 2.5)
        if rng.random() < 0.60:
            ff, cc = atracadero
            t[ff-1:ff+2, cc-1:cc+2] += 35.0; s[ff-1:ff+2, cc-1:cc+2] += 0.085
        for _ in range(rng.integers(3, 9)):
            fs, cs = np.where(agua & (dist > 120))
            j = rng.integers(len(fs)); ff, cc = fs[j], cs[j]
            t[ff:ff+2, cc:cc+2] += 40.0; s[ff:ff+2, cc:cc+2] += 0.090
        t[~agua] = np.nan; s[~agua] = np.nan
        fechas.append(f); turb.append(t.astype(np.float32)); swir.append(s.astype(np.float32))

    return {"agua": agua, "dist": dist, "f_tierra": f_tierra, "fechas": fechas,
            "turbidez": np.stack(turb), "swir": np.stack(swir),
            "fuente_intermitente": fuente_int, "fuente_permanente": fuente_per,
            "atracadero": atracadero}
