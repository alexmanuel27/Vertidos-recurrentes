"""Bloque A (peticion 2): prueba CONFIRMATORIA con las escenas de 2026. Reglas: fila de 2026-11-18
de la secc. 14 (commit c4d1ea7). No se cambia ningun umbral aqui.

Entradas (de 30_contraste_escenas.py --etiqueta 2026 y 2016_2025): contraste_escenas_<res>m_<et>.csv y
contraste_placebo_<res>m_<et>.npz. Salida: <resultados>/prueba_A_<res>m.json.

    python scripts/37_prueba_A.py --resultados resultados
    VERTIDOS_PIXEL_M=10 python scripts/37_prueba_A.py --resultados resultados_10m
"""
import os, sys, csv, json, argparse
import numpy as np
from scipy.stats import binomtest

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "src")); sys.path.insert(0, AQUI)
import importlib.util
spec = importlib.util.spec_from_file_location("grad", os.path.join(AQUI, "24_gradiente.py"))
grad = importlib.util.module_from_spec(spec); spec.loader.exec_module(grad)

N_MIN_A1, N_MIN_SECAS, N_MIN_ESTACION_A3 = 8, 5, 5


def leer(res, et, base):
    with open(os.path.join(base, f"contraste_escenas_{res}m_{et}.csv")) as fh:
        filas = list(csv.DictReader(fh))
    for f in filas:
        for k, v in f.items():
            if k not in ("fecha", "hora_utc", "estacion", "l1c"):
                f[k] = float(v) if v not in ("", "nan") else float("nan")
    z = np.load(os.path.join(base, f"contraste_placebo_{res}m_{et}.npz"), allow_pickle=True)
    return filas, {k: z[k] for k in z.files}


def a1(filas, plac, nom, sel):
    """Contraste de focos en las escenas elegidas por `sel` (indices). nom = focos | grupos13."""
    d = np.array([filas[i][f"d_{nom}"] for i in sel]); ok = np.isfinite(d)
    n = int(ok.sum())
    if n < N_MIN_A1:
        return {"veredicto": "insuficiente", "n_escenas_usables": n, "minimo": N_MIN_A1}
    P = plac[f"placebo_{nom}"][np.array(sel)][ok]                     # escenas x 500
    pm = np.nanmedian(P, axis=0); p95 = float(np.nanpercentile(pm, 95))
    pos = int((d[ok] > 0).sum()); p = float(binomtest(pos, n, 0.5, alternative="greater").pvalue)
    med = float(np.median(d[ok]))
    c1, c2, c3 = pos > n / 2, p < 0.05, med > p95
    return {"n_escenas_usables": n, "n_d_mayor_0": pos, "p_signo_una_cola": round(p, 5), "d_mediana": round(med, 3),
            "p95_mediana_placebo": round(p95, 3), "mediana_placebo_mediana": round(float(np.median(pm)), 3),
            "cumple_mitad": bool(c1), "cumple_signo": bool(c2), "cumple_placebo": bool(c3), "veredicto": "cumple" if (c1 and c2 and c3) else "no cumple"}


def zonas_escena(filas, sel, var):
    return {n: float(np.nanmedian([filas[i][f"{n}_{var}"] for i in sel])) if sel else float("nan") for n in grad.ZN}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--resultados", default="resultados"); a = ap.parse_args()
    res = int(os.environ.get("VERTIDOS_PIXEL_M", "20"))
    out = {"resolucion_m": res, "reglas": "secc. 14, fila 2026-11-18 (commit c4d1ea7)"}
    for et in ("2026", "2016_2025"):
        filas, plac = leer(res, et, a.resultados)
        noms = ["focos"] + (["grupos13"] if "placebo_grupos13" in plac else [])
        r = {"n_escenas": len(filas)}
        idx = {"todas": list(range(len(filas))), "seca": [i for i, f in enumerate(filas) if f["estacion"] == "seca"],
               "lluviosa": [i for i, f in enumerate(filas) if f["estacion"] == "lluviosa"]}
        r["A1"] = {nom: {k: a1(filas, plac, nom, v) for k, v in idx.items()} for nom in noms}
        sec = idx["seca"]
        if len(sec) < N_MIN_SECAS:
            r["A2"] = {"veredicto": "insuficiente", "n_secas": len(sec), "minimo": N_MIN_SECAS}
        else:
            r["A2"] = {"n_secas": len(sec), "variantes": {}}
            for var in ("todos", "a100m"):
                o = grad.orden(zonas_escena(filas, sec, var)); r["A2"]["variantes"][var] = o
            r["A2"]["cumple_variantes"] = sum(bool(v and v["cumple"]) for v in r["A2"]["variantes"].values())
        r["A3"] = {}
        for est in ("seca", "lluviosa"):
            s = idx[est]
            if len(s) < N_MIN_ESTACION_A3:
                r["A3"][est] = {"veredicto": "insuficiente", "n_escenas": len(s), "minimo": N_MIN_ESTACION_A3}; continue
            r["A3"][est] = {"n_escenas": len(s)}
            for var in ("todos", "a100m"):
                m = zonas_escena(filas, s, var)
                r["A3"][est][var] = {"max_marimelena_centro_menos_mar": round(max(m["marimelena"], m["bahia_centro_y_canal"]) - m["mar"], 3),
                                     "centro_menos_mar": round(m["bahia_centro_y_canal"] - m["mar"], 3)}
        out[et] = r
    json.dump(out, open(os.path.join(a.resultados, f"prueba_A_{res}m.json"), "w"), indent=1, ensure_ascii=False)
    print(json.dumps(out, indent=1, ensure_ascii=False)[:6000])


if __name__ == "__main__":
    main()
