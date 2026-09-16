"""Piloto: la prueba que decide si se sigue con el archivo completo o se replantea.

Lee datos/productos/*.npz (no necesita netCDF4 ni red) y se adapta a la rejilla real
que haya escrito ACOLITE, sin suponerla.

QUE PUEDE Y QUE NO PUEDE ESTE PILOTO
------------------------------------
Con diez escenas NO se puede construir la climatologia por pixel: el protocolo exige
>= 20 observaciones validas por pixel y estacion (seccion 7). El piloto, por tanto, NO
pone a prueba la familia de anomalia TEMPORAL. Es aritmetica, no un defecto.

Lo que el piloto SI decide:
  1. Que ACOLITE converge sobre esta bahia y da turbidez con valores sensatos.
  2. CUANTO vale la adyacencia aqui: amplitud A y longitud de decaimiento L medidas
     sobre el agua real. Es la incognita seria del proyecto.
  3. Si hay estructura costera coherente que NO se explica por la distancia a costa,
     via la familia CLIMATOLOGICA (seccion 8.1), que funciona con pocas escenas porque
     compara en el espacio y no en el tiempo.
  4. Que fraccion de la bahia quedaria evaluable: el coste real de la adyacencia.
"""
import os, sys, json, glob, argparse
from datetime import datetime
import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "src"))
import mascara, anomalias, adyacencia, persistencia

# Bits de l2_flags de ACOLITE: 0 no-agua SWIR, 1 cirros, 2 TOA alto, 3 rhow negativa,
# 4 fuera de escena, 5 pixel mixto, 6 sombra DEM.
# Se aplican cirros + TOA alto + negativa + fuera de escena. NO se aplican el 0 ni el 5:
# son la orilla y el agua muy turbia, es decir el objeto de estudio (protocolo secc. 6).
BITS_QC = (1 << 1) | (1 << 2) | (1 << 3) | (1 << 4)

N_MIN_PILOTO = 4        # relajado SOLO para el piloto; el protocolo exige 20. Se declara.
PIXEL_M = 20.0

# Contaminacion atmosferica por pixel, medida en B12 (~2200 nm). A esa longitud de onda
# el agua absorbe tanto que rho_w ~ 0 por turbia que este; una reflectancia apreciable
# solo puede venir de la atmosfera (bruma, nube fina) o de una superficie emergida.
# Umbral fisico, no ajustado a los datos.
UMBRAL_SWIR2 = 0.010

# Rango fisicamente admisible de la turbidez de Dogliotti. Fuera de el, el algoritmo ha
# salido de su dominio de validez (rho supera la constante C y la formula cambia de signo).
TURB_MIN, TURB_MAX = 0.0, 1000.0

FRAC_MIN_ESCENA = 0.40  # fraccion minima de agua valida para usar la escena en el piloto


def cargar(carpeta):
    escenas = []
    for f in sorted(glob.glob(os.path.join(carpeta, "*.npz"))):
        d = np.load(f, allow_pickle=False)
        if "turbidez_dogliotti" not in d:
            print(f"  sin turbidez: {os.path.basename(f)}"); continue
        escenas.append({
            "nombre": os.path.basename(f),
            "fecha": datetime.fromisoformat(str(d["fecha"])),
            "turb": d["turbidez_dogliotti"].astype(np.float32),
            "swir": d["swir"].astype(np.float32) if "swir" in d else None,
            "swir2": d["swir2"].astype(np.float32) if "swir2" in d else None,
            "verde": d["verde"].astype(np.float32) if "verde" in d else None,
            "nir": d["nir"].astype(np.float32) if "nir" in d else None,
            "flags": d["banderas"] if "banderas" in d else None,
            "x": d["x"] if "x" in d else None,
            "y": d["y"] if "y" in d else None,
        })
    return escenas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--productos", default="datos/productos")
    ap.add_argument("--salida", default="resultados")
    a = ap.parse_args()
    os.makedirs(a.salida, exist_ok=True)

    esc = cargar(a.productos)
    if len(esc) < 3:
        sys.exit(f"Solo {len(esc)} escenas con turbidez en {a.productos}.")
    forma = esc[0]["turb"].shape
    if any(e["turb"].shape != forma for e in esc):
        sys.exit("Las escenas no comparten rejilla: " +
                 str({e["nombre"]: e["turb"].shape for e in esc}))
    print(f"[1] {len(esc)} escenas | rejilla {forma[0]}x{forma[1]} a {PIXEL_M:.0f} m "
          f"({forma[0]*PIXEL_M/1000:.2f} x {forma[1]*PIXEL_M/1000:.2f} km)")
    print("    fechas:", ", ".join(e["fecha"].strftime("%Y-%m-%d") for e in esc))

    # --- mascara de agua primero: todo lo demas se mide SOBRE AGUA ---
    if esc[0]["verde"] is None or esc[0]["nir"] is None:
        sys.exit("Faltan rhos verde/NIR: no se puede derivar la mascara de agua.")
    cubo_ndwi = np.stack([mascara.ndwi(e["verde"], e["nir"]) for e in esc])
    agua, ndwi_med = mascara.mascara_agua(cubo_ndwi)
    dist = mascara.distancia_a_costa(agua, PIXEL_M)
    f_tierra = mascara.fraccion_tierra(agua, 500.0, PIXEL_M)
    print(f"[2] agua: {int(agua.sum())} px = {agua.sum()*PIXEL_M**2/1e6:.2f} km2 "
          f"| distancia a costa maxima {dist.max():.0f} m")
    if dist.max() < 1500:
        print("    AVISO: sin campo lejano (<1,5 km). El perfil rho_SWIR(d) no puede")
        print("    identificar una longitud de adyacencia atmosferica con esta ventana.")

    # --- validez por pixel ---
    print(f"\n[3] control de calidad, SOBRE AGUA "
          f"(B12 > {UMBRAL_SWIR2} = contaminacion atmosferica):")
    print(f"    {'escena':12s} {'agua val':>9s} {'contam':>7s} {'fuera rango':>11s} "
          f"{'T p50':>8s} {'T p95':>8s}")
    val, usable = [], []
    for e in esc:
        t = e["turb"].astype(np.float64)
        v = agua & np.isfinite(t)
        if e["flags"] is not None:
            v &= (e["flags"].astype(np.int64) & BITS_QC) == 0
        contam = np.zeros_like(v)
        if e["swir2"] is not None:
            contam = agua & np.isfinite(e["swir2"]) & (e["swir2"] > UMBRAL_SWIR2)
            v &= ~contam
        rango = (t >= TURB_MIN) & (t <= TURB_MAX)
        fuera = v & ~rango
        v &= rango
        val.append(v)
        frac = v.sum() / max(agua.sum(), 1)
        ok = frac >= FRAC_MIN_ESCENA
        usable.append(ok)
        tv = t[v]
        p50 = np.median(tv) if tv.size else np.nan
        p95 = np.percentile(tv, 95) if tv.size else np.nan
        print(f"    {e['fecha']:%Y-%m-%d} {frac:8.1%} {contam.sum()/max(agua.sum(),1):6.1%} "
              f"{fuera.sum()/max(agua.sum(),1):10.1%} {p50:8.2f} {p95:8.2f}"
              + ("" if ok else "   DESCARTADA"))
    n_ok = sum(usable)
    print(f"    -> {n_ok} de {len(esc)} escenas utilizables "
          f"({n_ok/len(esc):.0%}; el protocolo esperaba 30-40 %)")
    esc = [e for e, u in zip(esc, usable) if u]
    val = [v for v, u in zip(val, usable) if u]
    if n_ok < 3:
        sys.exit(f"\nSolo {n_ok} escenas utilizables: el piloto no puede concluir nada.")

    # --- (2) la adyacencia, medida ---
    ajustes = []
    for e, v in zip(esc, val):
        if e["swir"] is None:
            continue
        aj = adyacencia.ajustar_decaimiento(e["swir"], dist, agua & v)
        if aj:
            aj["fecha"] = e["fecha"]
            ajustes.append(aj)
    if ajustes:
        L = np.array([x["L"] for x in ajustes]); A = np.array([x["A"] for x in ajustes])
        r2 = np.array([x["r2"] for x in ajustes])
        print(f"[3] adyacencia medida en {len(ajustes)}/{len(esc)} escenas:")
        print(f"    L = {np.median(L):6.0f} m   (rango {L.min():.0f} a {L.max():.0f})")
        print(f"    A = {np.median(A):6.4f}     (rango {A.min():.4f} a {A.max():.4f})")
        print(f"    r2 = {np.median(r2):5.3f}")
    else:
        print("[3] AVISO: no se pudo ajustar el decaimiento en ninguna escena")
        L = np.array([np.nan])

    # --- (3) familia climatologica sobre la mediana ---
    cubo = np.stack([np.where(v, e["turb"], np.nan) for e, v in zip(esc, val)])
    med = np.nanmedian(cubo, axis=0)
    n_obs = np.sum(np.isfinite(cubo), axis=0)
    evaluable = agua & (n_obs >= N_MIN_PILOTO) & np.isfinite(med)
    print(f"[4] evaluable con n>={N_MIN_PILOTO}: {int(evaluable.sum())} px "
          f"({evaluable.sum()/max(agua.sum(),1):.1%} del agua)")

    zc, _ = anomalias.anomalia_climatologica(med, dist, f_tierra, evaluable,
                                             n_min_banda=20)
    cand = anomalias.detectar_permanentes(zc, evaluable)
    gp = persistencia.grupos(cand, min_px=4)
    print(f"[5] estructuras costeras coherentes (z_c >= {anomalias.Z_C_MIN}, >=4 px): {len(gp)}")

    x, y = esc[0]["x"], esc[0]["y"]
    def utm(f, c):
        if x is None or y is None:
            return (np.nan, np.nan)
        return (float(np.interp(c, np.arange(len(x)), x)),
                float(np.interp(f, np.arange(len(y)), y)))

    filas = []
    for g in sorted(gp, key=lambda z: -z["tam"])[:12]:
        f0, c0 = g["centroide"]
        e_, n_ = utm(f0, c0)
        zmax = float(np.nanmax([zc[f, c] for f, c in g["pixeles"]]))
        d0 = float(dist[int(f0), int(c0)])
        filas.append({"tam_px": g["tam"], "este": round(e_, 1), "norte": round(n_, 1),
                      "d_costa_m": round(d0, 1), "z_c_max": round(zmax, 2)})
        print(f"    {g['tam']:4d} px  UTM {e_:9.0f} {n_:10.0f}  "
              f"d_costa {d0:5.0f} m  z_c max {zmax:6.1f}")

    res = {"n_escenas": len(esc), "rejilla": list(forma),
           "agua_px": int(agua.sum()),
           "agua_km2": round(float(agua.sum()*PIXEL_M**2/1e6), 3),
           "L_mediana_m": float(np.nanmedian(L)),
           "A_mediana": float(np.nanmedian([x["A"] for x in ajustes])) if ajustes else None,
           "evaluable_frac": round(float(evaluable.sum()/max(agua.sum(), 1)), 4),
           "n_estructuras": len(gp), "estructuras": filas,
           "fechas": [e["fecha"].isoformat() for e in esc]}
    json.dump(res, open(os.path.join(a.salida, "piloto.json"), "w"), indent=1)
    np.savez_compressed(os.path.join(a.salida, "piloto.npz"), agua=agua, dist=dist,
                        f_tierra=f_tierra, mediana=med, zc=zc, n_obs=n_obs,
                        ndwi_med=ndwi_med)

    print("\n=== VEREDICTO ===")
    Lm = float(np.nanmedian(L))
    escala = float(np.sqrt(np.median([g["tam"] for g in gp])) * PIXEL_M) if gp else 0.0
    sin_campo_lejano = dist.max() < 1500
    ajustes_buenos = [x for x in ajustes if x["r2"] > 0.8 and x["A"] < 0.9]

    n_med = float(np.median(n_obs[evaluable])) if evaluable.any() else 0
    d_est = np.array([dist[int(g["centroide"][0]), int(g["centroide"][1])] for g in gp]) \
            if gp else np.array([])
    frac_costera = float((d_est < 500).mean()) if d_est.size else 0.0

    if sin_campo_lejano:
        print("  NO CONCLUYENTE sobre adyacencia: la ventana no tiene campo lejano, asi")
        print(f"  que la L ajustada ({Lm:.0f} m) mide el pixel mixto de la orilla y no la")
        print("  adyacencia atmosferica. Ampliar la ventana y repetir.")
    elif len(ajustes_buenos) >= 3:
        LL = sorted(x["L"] for x in ajustes_buenos)
        AA = sorted(x["A"] for x in ajustes_buenos)
        print(f"  ADYACENCIA MEDIDA: L entre {LL[0]:.0f} y {LL[-1]:.0f} m "
              f"(mediana {np.median(LL):.0f} m),")
        print(f"  amplitud A entre {AA[0]:.4f} y {AA[-1]:.4f} en rho(1610 nm),")
        print(f"  sobre {len(ajustes_buenos)} ajustes con r2 > 0,8.")
    else:
        print(f"  Adyacencia NO medida con fiabilidad: solo {len(ajustes_buenos)} ajustes")
        print("  con r2 > 0,8.")

    print()
    if n_med < 20:
        print(f"  NO CONCLUYENTE sobre estructuras: la mediana climatologica se apoya en")
        print(f"  {n_med:.0f} observaciones por pixel y el protocolo exige 20 (seccion 7).")
        print(f"  Con tan pocas, z_c es ruido. Sintoma: {100*(1-frac_costera):.0f} % de las")
        print(f"  {len(gp)} estructuras caen a mas de 500 m de la costa, donde no puede")
        print("  haber un vertido costero. Esta pregunta necesita el archivo completo")
        print("  POR CONSTRUCCION: diez escenas nunca iban a responderla.")
    elif not gp:
        print("  NO hay estructura costera coherente. Replantear.")
    elif escala < Lm:
        print(f"  {len(gp)} estructuras de escala ~{escala:.0f} m frente a una adyacencia")
        print(f"  de L ~ {Lm:.0f} m: NO separables del artefacto de orilla. Replantear.")
    else:
        print(f"  {len(gp)} estructuras coherentes de escala ~{escala:.0f} m, el "
              f"{100*frac_costera:.0f} % a menos de 500 m de costa,")
        print(f"  frente a una adyacencia de L ~ {Lm:.0f} m. Son separables. SEGUIR.")
    print(f"\nresultados en {a.salida}/piloto.json y piloto.npz")


if __name__ == "__main__":
    main()
