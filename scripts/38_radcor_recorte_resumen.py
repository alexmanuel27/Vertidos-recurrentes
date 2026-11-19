"""Bloque C con ventana ampliada (secc. 14, fila 2026-11-19): recorta los productos RAdCor a la
rejilla de la climatologia y compara d_RAdCor con d_DSF en las 10 escenas.

Paso 1 (recorte):   python scripts/38_radcor_recorte_resumen.py recorte
Paso 2 (contraste): python scripts/30_contraste_escenas.py --productos datos/productos_radcor_ampliada_20m_recorte \\
                      --aceptadas resultados/radcor_aceptadas_20m.txt --etiqueta radcor_ampliada
Paso 3 (resumen):   python scripts/38_radcor_recorte_resumen.py resumen
Regla de C: d_RAdCor>0 en >=8/10 escenas y mediana de d_RAdCor/d_DSF >=0,5.
"""
import os, sys, csv, glob, json
import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import importlib.util
spec = importlib.util.spec_from_file_location("grad", os.path.join(AQUI, "24_gradiente.py"))
grad = importlib.util.module_from_spec(spec); spec.loader.exec_module(grad)
ORIG, DEST = "datos/productos_radcor_ampliada_20m", "datos/productos_radcor_ampliada_20m_recorte"


def recorte():
    cl = np.load("resultados/climatologia.npz"); x, y = cl["x"], cl["y"]
    os.makedirs(DEST, exist_ok=True); agua = cl["agua"].astype(bool); bahia = cl["bahia"].astype(bool)
    for f in sorted(glob.glob(os.path.join(ORIG, "*.npz"))):
        d = np.load(f, allow_pickle=True)
        ix = np.searchsorted(d["x"], x); iy = np.array([int(np.where(d["y"] == v)[0][0]) for v in y])
        assert np.array_equal(d["x"][ix], x), "x no coincide con la rejilla de la climatologia"
        ny, nx = len(d["y"]), len(d["x"]); out = {}
        for k in d.files:
            a = d[k]
            out[k] = a[np.ix_(iy, ix)] if a.shape == (ny, nx) else (x if k == "x" else y if k == "y" else a)
        np.savez_compressed(os.path.join(DEST, os.path.basename(f)), **out)
        t = out["turbidez_dogliotti"].astype(float)
        print(os.path.basename(f)[:26], "ventana", (ny, nx), "-> recorte", t.shape, "finito en agua bahia %.3f" % np.isfinite(t)[agua & bahia].mean())


def leer(f):
    return {r["fecha"]: r for r in csv.DictReader(open(f))}


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def resumen():
    dsf = leer("resultados/contraste_escenas_20m_2016_2025.csv"); rad = leer("resultados/contraste_escenas_20m_radcor_ampliada.csv")
    filas = []
    for fe, r in sorted(rad.items()):
        dd, dr = num(dsf[fe]["d_focos"]), num(r["d_focos"])
        filas.append({"fecha": fe, "n_focos_validos_dsf": int(num(dsf[fe]["focos_n_validos"])), "n_focos_validos_radcor": int(num(r["focos_n_validos"])),
                      "d_dsf": dd, "d_radcor": dr, "cociente": dr / dd if np.isfinite(dr) and np.isfinite(dd) and dd != 0 else float("nan")})
    dr = np.array([f["d_radcor"] for f in filas]); q = np.array([f["cociente"] for f in filas])
    n_pos = int(np.nansum(dr > 0)); n_ok = int(np.isfinite(dr).sum())
    med_q = float(np.nanmedian(q)) if np.isfinite(q).any() else float("nan")
    cumple = bool(n_pos >= 8 and np.isfinite(med_q) and med_q >= 0.5)
    orden = {}
    for nom, tab in (("dsf", [dsf[f["fecha"]] for f in filas]), ("radcor", [rad[f["fecha"]] for f in filas])):
        orden[nom] = {}
        for var in ("todos", "a100m"):
            med = {n: float(np.nanmedian([num(t[f"{n}_{var}"]) for t in tab])) for n in grad.ZN}
            orden[nom][var] = {"medianas_zona": {k: round(v, 3) for k, v in med.items()}, "orden": grad.orden(med)}
    out = {"escenas": filas, "n_d_radcor_evaluable": n_ok, "n_d_radcor_mayor_0": n_pos, "mediana_cociente": med_q,
           "regla": "d_RAdCor>0 en >=8/10 y mediana(d_RAdCor/d_DSF)>=0,5", "cumple": cumple, "orden_zonas_10_escenas": orden,
           "ventana_ampliada_limit_SONE": [23.050, -82.450, 23.260, -82.230]}
    json.dump(out, open("resultados/radcor_resultado_ampliada_20m.json", "w"), indent=1, ensure_ascii=False)
    print(json.dumps(out, indent=1, ensure_ascii=False)[:5000])


if __name__ == "__main__":
    {"recorte": recorte, "resumen": resumen}[sys.argv[1]]()
