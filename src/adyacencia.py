"""Diagnostico de adyacencia: medicion del decaimiento y controles de falsacion.

Protocolo seccion 11. La adyacencia no se evita con un margen fijo (eso eliminaria el
objeto de estudio): se mide, y se somete a controles que pueden falsar el resultado.
"""
import numpy as np
from scipy.optimize import curve_fit

MARGENES_M = (0, 20, 40, 60, 100)


def _modelo(d, A, L, c):
    return A * np.exp(-d / L) + c


def perfil_por_anillos(valores, dist, agua, ancho_m=20.0, d_max=600.0):
    bordes = np.arange(0, d_max + ancho_m, ancho_m)
    centros, medianas, n = [], [], []
    for lo, hi in zip(bordes[:-1], bordes[1:]):
        sel = agua & (dist >= lo) & (dist < hi) & np.isfinite(valores)
        if sel.sum() >= 10:
            centros.append((lo + hi) / 2)
            medianas.append(float(np.median(valores[sel])))
            n.append(int(sel.sum()))
    return np.array(centros), np.array(medianas), np.array(n)


def ajustar_decaimiento(rho_swir, dist, agua, ancho_m=20.0, d_max=600.0):
    """Ajusta rho_SWIR(d) = A exp(-d/L) + c.

    Sobre agua limpia y tras correccion atmosferica rho_SWIR ~ 0, asi que cualquier
    elevacion que decaiga con la distancia a costa es adyacencia (mas residuo de
    correccion). Convierte la adyacencia de supuesto en cantidad medida.
    """
    d, y, n = perfil_por_anillos(rho_swir, dist, agua, ancho_m, d_max)
    if d.size < 5:
        return None
    p0 = [max(y[0] - y[-1], 1e-4), 150.0, float(y[-1])]
    try:
        popt, _ = curve_fit(_modelo, d, y, p0=p0, maxfev=20000,
                            bounds=([0, 10, -0.05], [1.0, 3000.0, 0.5]))
    except Exception:
        return None
    resid = y - _modelo(d, *popt)
    ss_tot = np.sum((y - y.mean()) ** 2)
    return {"A": float(popt[0]), "L": float(popt[1]), "c": float(popt[2]),
            "r2": float(1 - np.sum(resid ** 2) / ss_tot) if ss_tot > 0 else np.nan,
            "d": d, "y": y, "n": n}


def residuo_swir(rho_swir, dist, ajuste):
    """rho_SWIR menos el perfil de adyacencia ajustado. El test de buques va sobre esto."""
    if ajuste is None:
        return rho_swir
    return rho_swir - _modelo(dist, ajuste["A"], ajuste["L"], ajuste["c"])


def umbral_robusto(residuo, agua, k=6.0):
    """mediana + k*MAD escalada. Robusto: los pixeles de buque son pocos."""
    v = residuo[agua & np.isfinite(residuo)]
    if v.size < 50:
        return np.inf
    med = np.median(v)
    mad = np.median(np.abs(v - med)) * 1.4826
    return float(med + k * mad) if mad > 0 else np.inf


def controles_emparejados(candidatos, dist, f_tierra, agua, evaluable,
                          tol_d=20.0, tol_f=0.05, n_por_candidato=5, semilla=0):
    """Test de falsacion principal (protocolo 11.3b).

    Para cada candidato busca pixeles con la MISMA distancia a costa y la MISMA fraccion
    de tierra, pero lejos de el. Si el metodo midiese adyacencia, los controles se
    encenderian igual. El emparejamiento usa solo geometria, conocida antes de ver
    ninguna anomalia.
    """
    rng = np.random.default_rng(semilla)
    fs, cs = np.where(agua & evaluable)
    salida = []
    for cand in candidatos:
        f0, c0 = int(cand["fila_px"]), int(cand["col_px"])
        if not (0 <= f0 < agua.shape[0] and 0 <= c0 < agua.shape[1]):
            continue
        d0, ft0 = dist[f0, c0], f_tierra[f0, c0]
        ok = ((np.abs(dist[fs, cs] - d0) <= tol_d)
              & (np.abs(f_tierra[fs, cs] - ft0) <= tol_f)
              & (np.hypot(fs - f0, cs - c0) > 10))
        idx = np.where(ok)[0]
        if idx.size == 0:
            salida.append({"candidato": cand["celda"], "controles": [], "n": 0})
            continue
        eleg = rng.choice(idx, size=min(n_por_candidato, idx.size), replace=False)
        salida.append({"candidato": cand["celda"], "d": float(d0), "f_tierra": float(ft0),
                       "controles": [(int(fs[i]), int(cs[i])) for i in eleg],
                       "n": int(idx.size)})
    return salida


def correlacion_aerosol(serie_zt, serie_aot):
    """Test de covariable atmosferica (11.3c). Correlacion significativa = residuo
    atmosferico o adyacencia modulada por aerosoles, no una descarga."""
    zt, aot = np.asarray(serie_zt, float), np.asarray(serie_aot, float)
    ok = np.isfinite(zt) & np.isfinite(aot)
    if ok.sum() < 8 or np.std(zt[ok]) == 0 or np.std(aot[ok]) == 0:
        return np.nan
    return float(np.corrcoef(zt[ok], aot[ok])[0, 1])


def anisotropia(pixeles, acimut_costa):
    """Razon extension paralela / perpendicular a la costa (11.3d). La adyacencia es
    aproximadamente isotropa; una pluma con fuente puntual no."""
    if len(pixeles) < 3:
        return np.nan
    p = np.array(pixeles, float)
    cen = p.mean(axis=0)
    p = p - cen
    try:
        th = float(acimut_costa[int(round(cen[0])), int(round(cen[1]))])
    except Exception:
        th = 0.0
    perp = p[:, 0] * np.cos(th) + p[:, 1] * np.sin(th)
    para = -p[:, 0] * np.sin(th) + p[:, 1] * np.cos(th)
    sp = np.std(perp)
    return float(np.std(para) / sp) if sp > 0 else np.nan
