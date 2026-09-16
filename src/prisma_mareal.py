"""Tiempo de renovacion de la bahia por prisma mareal.

Es aritmetica, pero TODA entrada viene de una fuente que hay que confirmar. Entra en el
trabajo como CONTEXTO INTERPRETATIVO, nunca como criterio de deteccion: un foco pesa mas
si cae en un rincon que no se lava, pero el tiempo de residencia no puede intervenir en
decidir si el foco existe (protocolo seccion 13).
"""
import numpy as np

# --- Entradas. TODAS pendientes de fuente. NO son resultados. ---
AREA_KM2 = 5.2              # POR CONFIRMAR: superficie de la bahia
PROF_MEDIA_M = 9.0          # POR CONFIRMAR: necesita batimetria (carta nautica del puerto)
RANGO_MAREAL_M = 0.30       # POR CONFIRMAR: La Habana es micromareal
PERIODO_MAREA_H = 12.42     # semidiurna lunar M2
RETORNO_B = 0.5             # fraccion del agua vaciada que vuelve en el flujo siguiente


def tiempo_renovacion(area_km2=AREA_KM2, prof_m=PROF_MEDIA_M, rango_m=RANGO_MAREAL_M,
                      periodo_h=PERIODO_MAREA_H, b=RETORNO_B):
    """V = A h ; P = A rango ; T = V / (P (1-b)) ciclos x periodo."""
    A = area_km2 * 1e6
    V, P = A * prof_m, A * rango_m
    ciclos = V / (P * (1 - b)) if b < 1 else np.inf
    return {"volumen_m3": V, "prisma_m3": P, "ciclos": ciclos,
            "dias": ciclos * periodo_h / 24.0}


def sensibilidad(prof=(7, 9, 11), rango=(0.25, 0.30, 0.40), b=(0.0, 0.5)):
    return [{"prof_m": h, "rango_m": r, "b": bb,
             "dias": round(tiempo_renovacion(prof_m=h, rango_m=r, b=bb)["dias"], 1)}
            for h in prof for r in rango for bb in b]


if __name__ == "__main__":
    d = tiempo_renovacion()
    print(f"volumen {d['volumen_m3']/1e6:.1f} hm3 | prisma {d['prisma_m3']/1e6:.2f} hm3")
    print(f"ciclos de marea para renovar: {d['ciclos']:.0f}")
    print(f"tiempo de renovacion: {d['dias']:.0f} dias ({d['dias']/7:.1f} semanas)")
    dd = [f["dias"] for f in sensibilidad()]
    print(f"rango sobre la incertidumbre: {min(dd):.0f} a {max(dd):.0f} dias")
    print("\nTODAS las entradas estan POR CONFIRMAR con fuente.")
