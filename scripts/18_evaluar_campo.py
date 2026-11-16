"""Evaluacion de la verificacion de campo (protocolo 20.5, regla de la fila del 15/11/2026 en la secc. 14).

    python scripts/18_evaluar_campo.py [--imagen resultados/campo/imagen_codificacion.csv]

Evaluable = ficha con «sí» o «no» en la pregunta 1; sin visita o «no se puede ver» = excluido.
Fisher exacto unilateral sobre P-infraestructura, sitios frente a controles. P-actividad solo
descriptivo. Con --imagen repite el Fisher con la codificacion a ciegas de la imagen (exploratorio).
Escribe resultados/campo/evaluacion_campo.json.
"""
import argparse, csv, json
from scipy.stats import fisher_exact

C = "resultados/campo/"


def fisher(filas, campo):
    ev = [f for f in filas if f[campo] in ("sí", "no")]
    tab = [[sum(f["rol"] == r and f[campo] == v for f in ev) for v in ("sí", "no")] for r in ("sitio", "control")]
    return {"tabla_si_no": {"sitios": tab[0], "controles": tab[1]}, "n_evaluables": len(ev),
            "excluidos": [f["punto"] for f in filas if f not in ev],
            "p_unilateral": float(fisher_exact(tab, alternative="greater")[1])}


def main(imagen):
    clave = {r["punto"]: r for r in csv.DictReader(open(C + "clave.csv", encoding="utf-8"))}
    reg = {r["punto"]: r for r in csv.DictReader(open(C + "registro_visitas.csv", encoding="utf-8"))}
    filas = []
    for p, k in sorted(clave.items()):
        r = reg.get(p, {})
        act = {x: r.get(x, "") for x in ("flujo_activo", "mancha", "espuma", "pelicula", "color")}
        filas.append({"punto": p, "rol": k["rol"], "sitio": k["sitio"], "visitado": p in reg,
                      "infraestructura": r.get("estructura_150m", ""), "tipo_salida": r.get("tipo_salida", "").strip(),
                      "actividad": act})
    out = {"regla": "PROTOCOLO_CONGELADO.md secc. 14, fila del 2026-11-15", "puntos": filas,
           "P_infraestructura": fisher(filas, "infraestructura")}
    if imagen:
        img = {r["punto"]: r["respuesta"] for r in csv.DictReader(open(imagen, encoding="utf-8"))}
        fi = [dict(f, imagen=img.get(f["punto"], "")) for f in filas]
        out["imagen_exploratorio"] = fisher(fi, "imagen")
        par = [f for f in fi if f["infraestructura"] in ("sí", "no") and f["imagen"] in ("sí", "no")]
        out["imagen_exploratorio"]["concordancia_con_campo"] = f"{sum(f['infraestructura'] == f['imagen'] for f in par)}/{len(par)}"
        out["puntos"] = fi
    json.dump(out, open(C + "evaluacion_campo.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for f in out["puntos"]:
        print(f["punto"], f["rol"], f["sitio"], f["infraestructura"] or "-", f.get("imagen", ""))
    print("campo:", out["P_infraestructura"])
    if imagen:
        print("imagen:", out["imagen_exploratorio"])


if __name__ == "__main__":
    a = argparse.ArgumentParser(); a.add_argument("--imagen"); main(a.parse_args().imagen)
