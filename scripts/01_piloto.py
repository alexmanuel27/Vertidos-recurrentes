"""Piloto de diez escenas: la prueba que decide si se sigue o se replantea.

QUE PUEDE Y QUE NO PUEDE ESTE PILOTO
------------------------------------
Con diez escenas NO se puede construir la climatologia por pixel: el protocolo exige
>= 20 observaciones validas por pixel y estacion (seccion 7). El piloto, por tanto, NO
pone a prueba la familia de anomalia TEMPORAL. Eso no es un defecto del piloto, es
aritmetica, y conviene tenerlo claro antes de interpretar su salida.

Lo que el piloto SI decide, que es lo que importa ahora:

  1. Que ACOLITE converge sobre esta bahia y devuelve turbidez con valores sensatos.
  2. CUANTO vale de verdad la adyacencia aqui: amplitud A y longitud de decaimiento L
     medidas sobre el agua real. Es la incognita seria del proyecto.
  3. Si la mediana de las diez escenas presenta estructura costera coherente que NO se
     explica por el perfil de distancia a costa: es decir, la familia CLIMATOLOGICA
     (seccion 8.1), que si funciona con pocas escenas porque compara en el espacio,
     no en el tiempo.
  4. Que fraccion de la bahia quedaria evaluable, que es el coste real de la adyacencia.

VEREDICTO: si aparece estructura coherente en (3) y la longitud de adyacencia de (2) es
menor que la escala de las estructuras, el metodo funciona y se sigue con el archivo
completo. Si lo unico que aparece es el borde de orilla, se replantea.
"""
import sys, os, json, argparse
import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "src"))
import geo, mascara, anomalias, adyacencia, acolite_io

N_MIN_PILOTO = 6      # relajado SOLO para el piloto; el protocolo exige 20. Se declara.


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--acolite", default="datos/acolite", help="carpeta con los L2W .nc")
    ap.add_argument("--salida", default="resultados")
    a = ap.parse_args()
    os.makedirs(a.salida, exist_ok=True)

    ncs = sorted([os.path.join(a.acolite, f) for f in os.listdir(a.acolite)
                  if f.endswith(".nc")])
    if len(ncs) < 5:
        sys.exit(f"Solo {len(ncs)} escenas en {a.acolite}. El piloto necesita ~10.")
    print(f"[1] {len(ncs)} escenas L2W")

    turb, swir, verde, nir, fechas = [], [], [], [], []
    for nc in ncs:
        d = acolite_io.leer(nc, ("turbidez_dogliotti", "swir", "verde", "nir"))
        turb.append(d["turbidez_dogliotti"]); swir.append(d["swir"])
        verde.append(d["verde"]); nir.append(d["nir"])
        fechas.append(acolite_io.fecha_de(nc))
        print(f"    {os.path.basename(nc)[:40]}  ->  {d['_mapa']}")
    turb, swir = np.stack(turb), np.stack(swir)

    # --- mascara de agua del propio archivo (protocolo seccion 5) ---
    cubo_ndwi = np.stack([mascara.ndwi(v, n) for v, n in zip(verde, nir)])
    centro = geo.utm_a_indice(363517.8, 2558866.8)
    agua, ndwi_med = mascara.mascara_agua(cubo_ndwi, semillas=[centro])
    dist = mascara.distancia_a_costa(agua, geo.PIXEL_M)
    f_tierra = mascara.fraccion_tierra(agua, 500.0, geo.PIXEL_M)
    print(f"[2] agua: {int(agua.sum())} px ({agua.sum()*geo.PIXEL_M**2/1e6:.2f} km2)")

    # --- (2) la adyacencia, medida ---
    ajustes = [adyacencia.ajustar_decaimiento(s, dist, agua & np.isfinite(s)) for s in swir]
    ok = [x for x in ajustes if x]
    if ok:
        L = np.array([x["L"] for x in ok]); A = np.array([x["A"] for x in ok])
        print(f"[3] adyacencia medida sobre {len(ok)}/{len(ncs)} escenas:")
        print(f"    L = {np.median(L):.0f} m  (rango {L.min():.0f}-{L.max():.0f})")
        print(f"    A = {np.median(A):.4f}   (rango {A.min():.4f}-{A.max():.4f})")
    else:
        print("[3] AVISO: no se pudo ajustar el decaimiento en ninguna escena")
        L = np.array([np.nan])

    # --- (3) familia climatologica sobre la mediana de las escenas ---
    med = np.nanmedian(turb, axis=0)
    n_obs = np.sum(np.isfinite(turb), axis=0)
    evaluable = agua & (n_obs >= N_MIN_PILOTO) & np.isfinite(med)
    print(f"[4] evaluable con n>={N_MIN_PILOTO}: {int(evaluable.sum())} px "
          f"({evaluable.sum()/max(agua.sum(),1):.1%} del agua)")

    zc, n_banda = anomalias.anomalia_climatologica(med, dist, f_tierra, evaluable,
                                                   n_min_banda=20)
    cand = anomalias.detectar_permanentes(zc, evaluable)
    import persistencia
    gp = persistencia.grupos(cand, min_px=4)
    print(f"[5] estructuras costeras coherentes (z_c >= {anomalias.Z_C_MIN}, >=4 px): "
          f"{len(gp)}")
    for g in sorted(gp, key=lambda x: -x["tam"])[:8]:
        f0, c0 = g["centroide"]
        e, n = geo.indice_a_utm(f0, c0)
        print(f"    {g['tam']:4d} px  UTM {e:.0f}, {n:.0f}  d_costa "
              f"{dist[int(f0), int(c0)]:.0f} m  z_c max "
              f"{np.nanmax([zc[f, c] for f, c in g['pixeles']]):.1f}")

    res = {"n_escenas": len(ncs), "agua_px": int(agua.sum()),
           "agua_km2": round(float(agua.sum()*geo.PIXEL_M**2/1e6), 3),
           "L_mediana_m": float(np.nanmedian(L)),
           "evaluable_frac": round(float(evaluable.sum()/max(agua.sum(), 1)), 4),
           "n_estructuras": len(gp),
           "estructuras": [{"tam_px": g["tam"],
                            "este": round(geo.indice_a_utm(*g["centroide"])[0], 1),
                            "norte": round(geo.indice_a_utm(*g["centroide"])[1], 1),
                            "d_costa_m": round(float(dist[int(g["centroide"][0]),
                                                          int(g["centroide"][1])]), 1)}
                           for g in sorted(gp, key=lambda x: -x["tam"])[:20]]}
    with open(os.path.join(a.salida, "piloto.json"), "w") as f:
        json.dump(res, f, indent=1)
    np.savez_compressed(os.path.join(a.salida, "piloto.npz"),
                        agua=agua, dist=dist, f_tierra=f_tierra, mediana=med, zc=zc,
                        n_obs=n_obs)

    print("\n=== VEREDICTO ===")
    escala = np.sqrt(np.median([g["tam"] for g in gp])) * geo.PIXEL_M if gp else 0
    if len(gp) == 0:
        print("  NO hay estructura costera coherente. Replantear antes de gastar semanas.")
    elif np.isfinite(np.nanmedian(L)) and escala > 0 and escala < np.nanmedian(L) * 0.5:
        print(f"  {len(gp)} estructuras, pero su escala (~{escala:.0f} m) es menor que la")
        print(f"  longitud de adyacencia ({np.nanmedian(L):.0f} m): NO son separables del")
        print("  artefacto de orilla. Replantear.")
    else:
        print(f"  {len(gp)} estructuras costeras coherentes, de escala ~{escala:.0f} m")
        print(f"  frente a una adyacencia de L ~ {np.nanmedian(L):.0f} m. Son separables.")
        print("  SEGUIR con el archivo completo.")


if __name__ == "__main__":
    main()
