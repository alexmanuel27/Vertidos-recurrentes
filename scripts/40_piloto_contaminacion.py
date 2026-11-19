"""Solo lectura: reconstruye por escena del piloto (13 L2W en datos/productos) la fraccion de agua con
rho(2,2 um) > 0,010 y la fraccion valida, con la MISMA logica que scripts/figura_piloto.py. No cambia umbrales."""
import glob, json, sys
import numpy as np
sys.path.insert(0, "src")
import mascara

piloto = set(open("resultados/piloto_productos.txt").read().split())
fs = sorted(glob.glob("datos/productos/*.npz"))
ds = [d for d in (np.load(f) for f in fs) if str(d["producto_l1c"]) in piloto]
assert len(ds) == len(piloto) == 13, (len(ds), len(piloto))
ndwi = np.stack([mascara.ndwi(d["verde"], d["nir"]) for d in ds])
agua, _ = mascara.mascara_agua(ndwi)
res = []
for d in ds:
    b = d["banderas"].astype(np.int64)
    contam = agua & np.isfinite(d["swir2"]) & (d["swir2"] > 0.010)
    v = agua & np.isfinite(d["turbidez_dogliotti"]) & ((b & 30) == 0) & ~contam
    v &= (d["turbidez_dogliotti"] >= 0) & (d["turbidez_dogliotti"] <= 1000)
    res.append({"fecha": str(d["fecha"])[:10], "producto_l1c": str(d["producto_l1c"]),
                "pct_agua_swir_sobre_0_010": round(100 * float(contam.sum() / agua.sum()), 1),
                "pct_agua_valida": round(100 * float(v.sum() / agua.sum()), 1),
                "aceptada_frac_ge_0_40": bool(v.sum() / agua.sum() >= 0.40)})
ac = [r for r in res if r["aceptada_frac_ge_0_40"]]
rj = [r for r in res if not r["aceptada_frac_ge_0_40"]]
out = {"fuente": "datos/productos/*.npz (13 productos de resultados/piloto_productos.txt), campos swir2, banderas, turbidez_dogliotti; logica de scripts/figura_piloto.py",
       "escenas": res, "n_aceptadas": len(ac), "n_rechazadas": len(rj),
       "rechazadas_pct_swir_sobre_umbral": sorted(r["pct_agua_swir_sobre_0_010"] for r in rj),
       "aceptadas_pct_swir_sobre_umbral": sorted(r["pct_agua_swir_sobre_0_010"] for r in ac)}
json.dump(out, open("resultados/piloto_contaminacion.json", "w"), indent=1, ensure_ascii=False)
print(json.dumps(out, indent=1, ensure_ascii=False))
