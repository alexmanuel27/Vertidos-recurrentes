"""La cadena a 10 m (protocolo secc. 20.2) equivale a la de 20 m en metros.

1. Parametros: lo fijado en pixeles se deriva de VERTIDOS_PIXEL_M y da los mismos metros.
2. Persistencia: las detecciones sinteticas a 20 m, duplicadas a 10 m, dan los mismos sitios.
"""
import os, sys, subprocess
import numpy as np
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "src")); sys.path.insert(0, AQUI)

SONDA = ("import sys; sys.path.insert(0, 'src'); sys.path.insert(0, 'scripts');"
         "import importlib.util as u, anomalias, persistencia, adyacencia, acolite_io, inspect;"
         "s = u.spec_from_file_location('d', 'scripts/06_deteccion.py'); d = u.module_from_spec(s); s.loader.exec_module(d);"
         "print(anomalias.DILATACION_BUQUE_PX, persistencia.MIN_PX_GRUPO,"
         " inspect.signature(adyacencia.controles_emparejados).parameters['dist_min_px'].default,"
         " d.RADIO_SITIO_PX, acolite_io.AJUSTES['s2_target_res'])")
for px, esperado in (("20", "2 4 10 4 20"), ("10", "4 16 20 8 10")):
    out = subprocess.run([sys.executable, "-c", SONDA], cwd=os.path.join(AQUI, ".."), text=True,
                         capture_output=True, env=dict(os.environ, VERTIDOS_PIXEL_M=px))
    assert out.stdout.split() == esperado.split(), (px, out.stdout, out.stderr[-500:])
    print(f"OK    parametros a {px} m: {out.stdout.strip()}")

import climatologia, anomalias, persistencia
from bahia_sintetica import generar, PIXEL_M
d = generar()
agua, turb, fechas = d["agua"], d["turbidez"], d["fechas"]
clim = climatologia.climatologia(turb, fechas, agua)
det, ev, zt = [], [], []
for i, f in enumerate(fechas):
    ce = clim[climatologia.estacion_de(f)]
    val = agua & np.isfinite(turb[i])
    m, z, _ = anomalias.detectar(turb[i], ce, val)
    det.append(m); ev.append(val & ce["evaluable"]); zt.append(z)
s20 = persistencia.agregar_sitios(det, fechas, ev, PIXEL_M, zt, min_px=4, desempate=True)
x2 = lambda a: np.kron(a, np.ones((2, 2), a.dtype))
s10 = persistencia.agregar_sitios([x2(m) for m in det], fechas, [x2(e) for e in ev], PIXEL_M / 2,
                                  [x2(z) for z in zt], min_px=16, desempate=True)
clave = lambda s: [(t["celda"], round(t["persistencia"], 6), t["n_anios"]) for t in s]
assert clave(s20) == clave(s10), "los sitios a 10 m no coinciden con los de 20 m"
print(f"OK    {len(s20)} sitios identicos a 20 m y duplicados a 10 m "
      f"({len(persistencia.ranking(s20))} recurrentes)")
