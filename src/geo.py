"""Geometría: UTM/MGRS, ventana de trabajo y rejilla. Sin dependencias externas."""
import math

A_WGS84 = 6378137.0
F_WGS84 = 1 / 298.257223563
E2 = F_WGS84 * (2 - F_WGS84)
EP2 = E2 / (1 - E2)
K0 = 0.9996

_COLS = ("ABCDEFGH", "JKLMNPQR", "STUVWXYZ")
_ROWS = "ABCDEFGHJKLMNPQRSTUV"
_BANDS = "CDEFGHJKLMNPQRSTUVWX"


def ll2utm(lat, lon):
    """Lat/lon WGS84 -> (zona, este, norte). Verificado contra MGRS publicados."""
    zona = int(math.floor((lon + 180) / 6)) + 1
    lon0 = math.radians((zona - 1) * 6 - 180 + 3)
    lat_r, lon_r = math.radians(lat), math.radians(lon)
    N = A_WGS84 / math.sqrt(1 - E2 * math.sin(lat_r) ** 2)
    T = math.tan(lat_r) ** 2
    C = EP2 * math.cos(lat_r) ** 2
    Aa = math.cos(lat_r) * (lon_r - lon0)
    M = A_WGS84 * (
        (1 - E2 / 4 - 3 * E2**2 / 64 - 5 * E2**3 / 256) * lat_r
        - (3 * E2 / 8 + 3 * E2**2 / 32 + 45 * E2**3 / 1024) * math.sin(2 * lat_r)
        + (15 * E2**2 / 256 + 45 * E2**3 / 1024) * math.sin(4 * lat_r)
        - (35 * E2**3 / 3072) * math.sin(6 * lat_r)
    )
    este = K0 * N * (Aa + (1 - T + C) * Aa**3 / 6
                     + (5 - 18 * T + T**2 + 72 * C - 58 * EP2) * Aa**5 / 120) + 500000
    norte = K0 * (M + N * math.tan(lat_r) * (
        Aa**2 / 2 + (5 - T + 9 * C + 4 * C**2) * Aa**4 / 24
        + (61 - 58 * T + T**2 + 600 * C - 330 * EP2) * Aa**6 / 720))
    if lat < 0:
        norte += 10000000
    return zona, este, norte


def banda_latitud(lat):
    return _BANDS[int((lat + 80) // 8)]


def cuadrado_100k(zona, este, norte):
    conjunto = ((zona - 1) % 6) + 1
    col = _COLS[(conjunto - 1) % 3][int(este // 100000) - 1]
    desfase = 0 if zona % 2 == 1 else 5
    fila = _ROWS[(int(norte // 100000) + desfase) % 20]
    return col + fila


def tile_mgrs(lat, lon):
    """Identificador de tile Sentinel-2 que contiene el punto."""
    z, e, n = ll2utm(lat, lon)
    return f"{z}{banda_latitud(lat)}{cuadrado_100k(z, e, n)}"


# --- Ventana de trabajo congelada (ver PROTOCOLO_CONGELADO.md, seccion 1) ---
TILE = "T17QLF"
EPSG = 32617
ESTE_MIN, ESTE_MAX = 361139.0, 365896.0
NORTE_MIN, NORTE_MAX = 2556342.0, 2561392.0
PIXEL_M = 20.0

PUNTOS_CONTROL = {
    "bocana": (23.1500, -82.3490),
    "centro": (23.1330, -82.3330),
    "marimelena": (23.1420, -82.3180),
    "guasabacoa": (23.1250, -82.3180),
    "atares": (23.1180, -82.3380),
}


def forma_ventana(pixel_m=PIXEL_M):
    nc = int(round((ESTE_MAX - ESTE_MIN) / pixel_m))
    nf = int(round((NORTE_MAX - NORTE_MIN) / pixel_m))
    return nf, nc


def utm_a_indice(este, norte, pixel_m=PIXEL_M):
    return int((NORTE_MAX - norte) // pixel_m), int((este - ESTE_MIN) // pixel_m)


def indice_a_utm(fila, col, pixel_m=PIXEL_M):
    return ESTE_MIN + (col + 0.5) * pixel_m, NORTE_MAX - (fila + 0.5) * pixel_m
