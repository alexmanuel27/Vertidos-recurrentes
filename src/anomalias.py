"""Anomalia temporal, espacial y climatologica; mascara de buques (protocolo 8, 8.1, 9).

Se exige la CONJUNCION de temporal y espacial: es el control especifico contra el residuo
de correccion atmosferica y la carga de aerosoles, que levantan la bahia entera y por
tanto se cancelan en la anomalia espacial.
"""
import numpy as np
from scipy import ndimage

Z_T_MIN = 3.5
Z_S_MIN = 3.0
Z_C_MIN = 3.5
DILATACION_BUQUE_PX = 2
ANCHO_BANDA_M = 20.0
TOL_F_TIERRA = 0.10


def z_temporal(escena, mediana, mad):
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(mad > 0, (escena - mediana) / mad, np.nan)


def z_espacial(escena, agua_valida):
    v = escena[agua_valida & np.isfinite(escena)]
    if v.size < 30:
        return np.full(escena.shape, np.nan)
    med = np.median(v)
    mad = np.median(np.abs(v - med)) * 1.4826
    if not np.isfinite(mad) or mad <= 0:
        return np.full(escena.shape, np.nan)
    return (escena - med) / mad


def mascara_buques(residuo_swir, umbral, agua, dilatacion=DILATACION_BUQUE_PX):
    """Sobre agua, rho_SWIR ~ 0. Se aplica al RESIDUO tras restar la adyacencia
    ajustada: un umbral absoluto de mar abierto enmascararia la franja costera."""
    bruta = agua & np.isfinite(residuo_swir) & (residuo_swir > umbral)
    if dilatacion > 0:
        bruta = ndimage.binary_dilation(bruta, iterations=int(dilatacion))
    return bruta & agua


def detectar(escena, clim_est, agua_valida, rho_swir=None, umbral_swir=None,
             z_t_min=Z_T_MIN, z_s_min=Z_S_MIN):
    """Pixeles anomalos de una escena. Devuelve (mascara, zt, zs)."""
    zt = z_temporal(escena, clim_est["mediana"], clim_est["mad"])
    zs = z_espacial(escena, agua_valida)
    m = (agua_valida & clim_est["evaluable"]
         & np.isfinite(zt) & np.isfinite(zs)
         & (zt >= z_t_min) & (zs >= z_s_min))       # solo excesos positivos
    if rho_swir is not None and umbral_swir is not None and np.isfinite(umbral_swir):
        m = m & ~mascara_buques(rho_swir, umbral_swir, agua_valida)
    return m, zt, zs


# --------------------------------------------------------------------------------
# Tercera familia: fuente PERMANENTE (protocolo 8.1).
#
# Las dos familias anteriores comparan cada pixel contra su propia historia. Una fuente
# continua esta DENTRO de esa historia: la mediana de diez anios ya la incluye, z_t sale
# ~0 y la conjuncion la descarta. El diseno temporal+espacial detecta vertidos
# intermitentes y es ciego a los permanentes, que son los que mas importan.
#
# Aqui se compara la MEDIANA CLIMATOLOGICA de cada pixel contra la de los pixeles a la
# misma distancia de costa y con fraccion de tierra parecida. La estratificacion es a la
# vez el detector y el control de adyacencia: si la elevacion fuese adyacencia, los
# pixeles de su misma banda geometrica la tendrian tambien.
# --------------------------------------------------------------------------------

def anomalia_climatologica(mediana_clim, dist, f_tierra, evaluable,
                           ancho_banda_m=ANCHO_BANDA_M, tol_f=TOL_F_TIERRA,
                           n_min_banda=30):
    """z de la mediana climatologica contra su banda de distancia. Devuelve (z_c, n)."""
    z = np.full(mediana_clim.shape, np.nan)
    n_banda = np.zeros(mediana_clim.shape, dtype=int)
    validos = evaluable & np.isfinite(mediana_clim) & np.isfinite(dist)
    if not validos.any():
        return z, n_banda
    bordes = np.arange(0, float(np.nanmax(dist[validos])) + ancho_banda_m, ancho_banda_m)
    for lo, hi in zip(bordes[:-1], bordes[1:]):
        banda = validos & (dist >= lo) & (dist < hi)
        if banda.sum() < n_min_banda:
            continue
        fs, cs = np.where(banda)
        vals, ftb = mediana_clim[banda], f_tierra[banda]
        for k in range(len(fs)):
            sim = np.abs(ftb - ftb[k]) <= tol_f
            if sim.sum() < n_min_banda:
                sim = np.ones_like(ftb, dtype=bool)
            ref = vals[sim]
            med = np.median(ref)
            mad = np.median(np.abs(ref - med)) * 1.4826
            if mad > 0:
                z[fs[k], cs[k]] = (vals[k] - med) / mad
                n_banda[fs[k], cs[k]] = int(sim.sum())
    return z, n_banda


def detectar_permanentes(z_c, evaluable, z_c_min=Z_C_MIN):
    return evaluable & np.isfinite(z_c) & (z_c >= z_c_min)
