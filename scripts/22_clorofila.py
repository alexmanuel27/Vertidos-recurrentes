"""Clorofila frente a sedimento: NDCI y turbidez en las escenas piloto con L2R a 20 m (EXPLORATORIO).

    python scripts/22_clorofila.py

Definido en la fila del 17/11/2026 de la secc. 14, antes de calcularlo. NDCI = (rho704 - rho665)
/ (rho704 + rho665) sobre los L2R piloto de datos/acolite y los .npz de datos/productos_ndci (resultados/ndci_productos_20m.txt),
aceptados en resultados/escenas_qc.csv.
Zonas del modelo (secc. 14, 21/10/2026). Escribe resultados/clorofila_ndci.json.
"""
import os, sys, csv, glob, json, re
import numpy as np
from netCDF4 import Dataset
from scipy import stats
from pyproj import Transformer
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "src"))
import escenas

cl = np.load("resultados/climatologia.npz")
agua, bahia, dist = cl["agua"].astype(bool), cl["bahia"].astype(bool), cl["distancia_costa_m"]
x, y = cl["x"], cl["y"]; E, N = np.meshgrid(x, y)
sur = (N < 2558800) & (E < 363300); lim = E < 362350 - 0.25 * (2558800 - N)
ZONAS = {"atares": bahia & sur & lim, "guasabacoa": bahia & sur & ~lim, "marimelena": bahia & (E > 363600)}
ZONAS["centro_y_canal"] = bahia & ~ZONAS["atares"] & ~ZONAS["guasabacoa"] & ~ZONAS["marimelena"]
ZONAS["mar"] = agua & ~bahia
acept = {r["producto_l1c"] for r in csv.DictReader(open("resultados/escenas_qc.csv")) if r["aceptada"] == "1"}
T = Transformer.from_crs(4326, 32617, always_xy=True)
sitios = json.load(open("resultados/campo/campo.json"))["sitios"]
res = {"escenas": [], "zonas": {z: {"ndci": [], "turb": []} for z in ZONAS}, "spearman_bahia": [], "spearman_bahia_100m": [], "sitios": {}}
sit_ndci = {s["codigo"]: [] for s in sitios}; sit_ref = {s["codigo"]: [] for s in sitios}
def fuentes():
    """(npz con turbidez y banderas, rho665, rho704): los L2R del piloto y los .npz nuevos con 'rojo' y 'borde'."""
    for l2r in sorted(glob.glob("datos/acolite/*_L2R.nc")):
        npz = f"datos/productos/{os.path.basename(l2r).replace('_L2R.nc', '')}_L2W.npz"
        if os.path.exists(npz):
            with Dataset(l2r) as ds:
                yield npz, np.ma.filled(ds["rhos_665"][:], np.nan).astype(float), np.ma.filled(ds["rhos_704"][:], np.nan).astype(float)
    for npz in sorted(glob.glob("datos/productos_ndci/*.npz")):
        with np.load(npz) as d:
            if "rojo" in d.files and "borde" in d.files:
                yield npz, d["rojo"].astype(float), d["borde"].astype(float)


for npz, r665, r704 in fuentes():
    e = escenas.cargar(npz)
    if e["l1c"] not in acept:
        continue
    v, _ = escenas.validez(e, agua, dist)
    ok = v & np.isfinite(r665) & np.isfinite(r704) & (r665 > 0) & (r704 > 0)
    ndci = np.where(ok, (r704 - r665) / (r704 + r665), np.nan); t = e["turbidez_dogliotti"]
    res["escenas"].append(e["fecha"].date().isoformat())
    for z, m in ZONAS.items():
        s = ok & m
        if s.sum() > 50:
            res["zonas"][z]["ndci"].append(float(np.median(ndci[s]))); res["zonas"][z]["turb"].append(float(np.median(t[s])))
    for nombre, m in (("spearman_bahia", ok & bahia), ("spearman_bahia_100m", ok & bahia & (dist >= 100))):
        if m.sum() > 100:
            res[nombre].append(float(stats.spearmanr(ndci[m], t[m])[0]))
    for s in sitios:
        sx, sy = T.transform(s["lon"], s["lat"]); cerca = np.hypot(E - sx, N - sy) <= 80
        a = ok & cerca
        if a.sum() < 3:
            continue
        # referencia: mismos pixeles de su zona y banda de distancia a costa (+-20 m), a mas de 200 m del sitio
        d0 = float(np.median(dist[a])); zona = bahia if s["en_bahia"] else ~bahia
        ref = ok & zona & (np.abs(dist - d0) <= 20) & (np.hypot(E - sx, N - sy) > 200)
        if ref.sum() > 30:
            sit_ndci[s["codigo"]].append(float(np.median(ndci[a]))); sit_ref[s["codigo"]].append(float(np.median(ndci[ref])))
out = {"n_escenas": len(res["escenas"]), "fechas": res["escenas"],
       "zonas_mediana_de_escenas": {z: {"ndci": round(float(np.median(d["ndci"])), 3) if d["ndci"] else None,
                                       "turbidez_FNU": round(float(np.median(d["turb"])), 2) if d["turb"] else None, "n_escenas": len(d["ndci"])}
                                    for z, d in res["zonas"].items()},
       "spearman_ndci_turbidez_bahia_mediana": round(float(np.median(res["spearman_bahia"])), 3) if res["spearman_bahia"] else None,
       "spearman_ndci_turbidez_bahia_a_100m_mediana": round(float(np.median(res["spearman_bahia_100m"])), 3) if res["spearman_bahia_100m"] else None,
       "sitios_ndci_mediana_frente_referencia": {k: {"sitio": round(float(np.median(v)), 3), "referencia": round(float(np.median(sit_ref[k])), 3), "n_escenas": len(v)}
                                                 for k, v in sit_ndci.items() if v}}
json.dump(out, open("resultados/clorofila_ndci.json", "w"), indent=1, ensure_ascii=False); print(json.dumps(out, indent=1, ensure_ascii=False))
