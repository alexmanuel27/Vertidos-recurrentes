"""Validacion extremo a extremo de la cadena de deteccion sobre la bahia sintetica."""
import sys, os, time
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))
import climatologia, anomalias, persistencia, adyacencia
from bahia_sintetica import generar, PIXEL_M

t0 = time.time()
d = generar()
agua, dist, f_tierra = d["agua"], d["dist"], d["f_tierra"]
turb, swir, fechas = d["turbidez"], d["swir"], d["fechas"]
fi, fp, at = d["fuente_intermitente"], d["fuente_permanente"], d["atracadero"]
print(f"[1] bahia sintetica: {len(fechas)} escenas, {int(agua.sum())} px de agua")

clim = climatologia.climatologia(turb, fechas, agua)
print("[2] climatologia congelada:", climatologia.resumen(clim, agua))

det, ev, ztm, zt_int, zt_per, nbuq = [], [], [], [], [], 0
for i, fecha in enumerate(fechas):
    ce = clim[climatologia.estacion_de(fecha)]
    val = agua & np.isfinite(turb[i])
    aj = adyacencia.ajustar_decaimiento(swir[i], dist, val)
    res = adyacencia.residuo_swir(swir[i], dist, aj)
    umb = adyacencia.umbral_robusto(res, val)
    mb = anomalias.mascara_buques(res, umb, val); nbuq += int(mb.sum())
    m, zt, zs = anomalias.detectar(turb[i], ce, val, rho_swir=res, umbral_swir=umb)
    det.append(m); ztm.append(zt); ev.append(val & ce["evaluable"] & ~mb)
    zt_int.append(zt[fi]); zt_per.append(zt[fp])

print(f"[3] {len(det)} escenas | px de buque enmascarados: {nbuq}")
print(f"    z_t medio fuente intermitente: {np.nanmean(zt_int):6.2f}")
print(f"    z_t medio fuente permanente  : {np.nanmean(zt_per):6.2f}   <- ciega por diseno")

sitios = persistencia.agregar_sitios(det, fechas, ev, PIXEL_M, ztm)
rec = persistencia.ranking(sitios)
k = persistencia.REJILLA_SITIO_M / PIXEL_M
cel = lambda p: (int(p[0] // k), int(p[1] // k))
cerca = lambda s, p, tol=2: (abs(s["celda"][0]-cel(p)[0]) <= tol and abs(s["celda"][1]-cel(p)[1]) <= tol)

print(f"[4] sitios recurrentes: {len(rec)} (de {len(sitios)} con alguna deteccion)")
for s in rec[:6]:
    etq = ("<- FUENTE INTERMITENTE" if cerca(s, fi) else "<- atracadero" if cerca(s, at)
           else "<- fuente permanente" if cerca(s, fp) else "")
    print(f"    celda {s['celda']}  persist {s['persistencia']:.2f}  anios {s['n_anios']}  "
          f"n={s['n_detecciones']}/{s['n_ocasiones']}  {etq}")

est = max(clim, key=lambda e: clim[e]["n_escenas"])
zc, _ = anomalias.anomalia_climatologica(clim[est]["mediana"], dist, f_tierra, clim[est]["evaluable"])
print(f"[5] familia climatologica (estacion {est}):")
print(f"    z_c fuente permanente  : {zc[fp]:6.2f}")
print(f"    z_c fuente intermitente: {zc[fi]:6.2f}")

ctrl = adyacencia.controles_emparejados(rec[:3], dist, f_tierra, agua, clim[est]["evaluable"])
mp = {s["celda"]: s["persistencia"] for s in sitios}
for c in ctrl:
    ps = [mp.get(cel((f, cc)), 0.0) for f, cc in c["controles"]]
    cand = next(s["persistencia"] for s in rec if s["celda"] == c["candidato"])
    print(f"[6] control de {c['candidato']}: candidato {cand:.2f} vs controles "
          f"{np.mean(ps) if ps else 0:.3f} (n={c['n']} emparejables)")

aj = adyacencia.ajustar_decaimiento(swir[0], dist, agua)
print(f"[7] adyacencia escena 0: A={aj['A']:.4f} L={aj['L']:.0f} m r2={aj['r2']:.3f} (plantada 120 m)")

falsos = [s for s in rec if not (cerca(s, fi) or cerca(s, fp) or cerca(s, at))]
pruebas = [("fuente intermitente recuperada", any(cerca(s, fi) for s in rec)),
           ("fuente permanente recuperada por familia climatologica",
            bool(np.isfinite(zc[fp]) and zc[fp] >= anomalias.Z_C_MIN)),
           ("fuente permanente ciega para z_t", abs(np.nanmean(zt_per)) < 1.0),
           ("cero sitios recurrentes falsos por adyacencia", len(falsos) == 0),
           ("longitud de adyacencia recuperada", 80 < aj["L"] < 200)]
print("\n=== VEREDICTO DEL TEST ===")
for n, ok in pruebas: print(f"  {'OK   ' if ok else 'FALLO'} {n}")
print(f"\n{'TODO CORRECTO' if all(o for _, o in pruebas) else 'REVISAR'}  ({time.time()-t0:.0f} s)")
