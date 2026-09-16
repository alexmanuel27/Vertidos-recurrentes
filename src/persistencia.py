"""Agrupacion espacial de anomalias y ranking por persistencia (protocolo secc. 10).

Lo que persiste una decada es un vertido; lo que aparece una vez es un barco.
"""
import numpy as np
from collections import defaultdict
from scipy import ndimage

MIN_PX_GRUPO = 4              # 4 px a 20 m = 1600 m2
REJILLA_SITIO_M = 40.0
RADIO_FUSION_CELDAS = 2       # 80 m: incertidumbre de localizacion del pico
PERSISTENCIA_MIN = 0.10
ANIOS_MIN = 5


def grupos(mascara, min_px=MIN_PX_GRUPO):
    """Componentes conexas (conectividad 8) de al menos min_px pixeles."""
    etiq, n = ndimage.label(mascara, structure=np.ones((3, 3), dtype=bool))
    if n == 0:
        return []
    tam = np.bincount(etiq.ravel())
    salida = []
    for k in range(1, n + 1):
        if tam[k] >= min_px:
            fs, cs = np.where(etiq == k)
            salida.append({"pixeles": list(zip(fs.tolist(), cs.tolist())),
                           "tam": int(tam[k]),
                           "centroide": (float(fs.mean()), float(cs.mean()))})
    return salida


def pico_de_grupo(grupo, z):
    """Pixel de maxima z dentro del grupo.

    La fuente es el MAXIMO de la pluma, no su centro de masa: una pluma advectada por
    marea y viento cambia de orientacion entre escenas y su centroide baila, repartiendo
    las detecciones de un mismo emisario entre celdas vecinas. El pico se queda quieto.
    """
    px = np.array(grupo["pixeles"])
    vals = z[px[:, 0], px[:, 1]]
    if not np.isfinite(vals).any():
        return int(px[0, 0]), int(px[0, 1])
    j = int(np.nanargmax(vals))
    return int(px[j, 0]), int(px[j, 1])


def _disco(radio):
    y, x = np.ogrid[-radio:radio + 1, -radio:radio + 1]
    return (x * x + y * y) <= radio * radio


def agregar_sitios(detecciones, fechas, evaluable_por_escena, pixel_m, z_por_escena,
                   rejilla_m=REJILLA_SITIO_M, min_px=MIN_PX_GRUPO,
                   radio_fusion=RADIO_FUSION_CELDAS):
    """Agrega los picos de todas las escenas sobre una rejilla de sitios.

    Cada escena aporta como mucho UNA deteccion por sitio, de modo que la persistencia es
    "en que fraccion de las ocasiones evaluables aparecio algo aqui", sin doble conteo por
    el tamanio de la pluma.
    """
    k = rejilla_m / pixel_m
    forma = (int(np.ceil(detecciones[0].shape[0] / k)),
             int(np.ceil(detecciones[0].shape[1] / k)))
    disco = _disco(radio_fusion)

    n_det = np.zeros(forma, dtype=int)
    anios = defaultdict(set)
    tams = defaultdict(list)

    for mask, fecha, z in zip(detecciones, fechas, z_por_escena):
        golpe = np.zeros(forma, dtype=bool)
        for g in grupos(mask, min_px):
            pf, pc = pico_de_grupo(g, z)
            cf, cc = int(pf // k), int(pc // k)
            if 0 <= cf < forma[0] and 0 <= cc < forma[1]:
                golpe[cf, cc] = True
                tams[(cf, cc)].append(g["tam"])
        if not golpe.any():
            continue
        golpe = ndimage.binary_dilation(golpe, structure=disco)
        n_det += golpe
        for cf, cc in zip(*np.where(golpe)):
            anios[(int(cf), int(cc))].add(fecha.year)

    n_ocas = np.zeros(forma, dtype=int)
    for ev in evaluable_por_escena:
        celdas = np.zeros(forma, dtype=bool)
        fs, cs = np.where(ev)
        celdas[(fs // k).astype(int), (cs // k).astype(int)] = True
        n_ocas += ndimage.binary_dilation(celdas, structure=disco)

    with np.errstate(invalid="ignore", divide="ignore"):
        pers = np.where(n_ocas > 0, n_det / np.maximum(n_ocas, 1), np.nan)

    # supresion de no-maximos: un emisario es un sitio, no un cumulo de celdas vecinas
    pico_local = (pers == ndimage.maximum_filter(np.nan_to_num(pers, nan=-1),
                                                 footprint=_disco(radio_fusion + 1)))
    sitios = []
    for cf, cc in zip(*np.where((n_det > 0) & pico_local)):
        cf, cc = int(cf), int(cc)
        a = sorted(anios[(cf, cc)])
        p = float(pers[cf, cc])
        t = tams.get((cf, cc), [])
        sitios.append({"celda": (cf, cc),
                       "fila_px": (cf + 0.5) * k, "col_px": (cc + 0.5) * k,
                       "n_detecciones": int(n_det[cf, cc]),
                       "n_ocasiones": int(n_ocas[cf, cc]),
                       "persistencia": p, "anios": a, "n_anios": len(a),
                       "tam_medio_px": float(np.mean(t)) if t else np.nan,
                       "recurrente": bool(np.isfinite(p) and p >= PERSISTENCIA_MIN
                                          and len(a) >= ANIOS_MIN)})
    sitios.sort(key=lambda s: (-(s["persistencia"] if np.isfinite(s["persistencia"]) else -1),
                               -s["n_anios"]))
    return sitios


def ranking(sitios, solo_recurrentes=True):
    return [s for s in sitios if s["recurrente"]] if solo_recurrentes else sitios


def a_coordenadas(sitios, pixel_m, geo_mod):
    """Anade este/norte UTM y lat/lon a cada sitio, para el briefing de campo."""
    for s in sitios:
        e, n = geo_mod.indice_a_utm(s["fila_px"], s["col_px"], pixel_m)
        s["este_utm"], s["norte_utm"] = round(e, 1), round(n, 1)
    return sitios
