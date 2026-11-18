"""Peticion 2, bloque C: fija el subconjunto de escenas para la prueba de RAdCor (EXPLORATORIO) y lo escribe en un JSON
ANTES de lanzar ACOLITE. Regla (fila del 18/11/2026, secc. 14): las 10 escenas secas aceptadas a 20 m con mayor fraccion de
pixeles validos de la bahia (`frac_valida_bahia` de resultados/escenas_qc.csv; empates: gana la fecha mas antigua) y las mismas
fechas a 10 m si estan aceptadas a 10 m (resultados_10m/escenas_qc.csv).

    python scripts/32_radcor_subconjunto.py
"""
import os, csv, json, glob

AQUI = os.path.dirname(os.path.abspath(__file__)); RAIZ = os.path.join(AQUI, "..")


def aceptadas(ruta):
    return [r for r in csv.DictReader(open(ruta)) if r["aceptada"] == "1"]


def main():
    r20 = [r for r in aceptadas(os.path.join(RAIZ, "resultados", "escenas_qc.csv")) if r["estacion"] == "seca"]
    r20.sort(key=lambda r: (-float(r["frac_valida_bahia"]), r["fecha"]))
    sel = r20[:10]
    p10 = os.path.join(RAIZ, "resultados_10m", "escenas_qc.csv")
    a10 = {r["producto_l1c"] for r in aceptadas(p10)} if os.path.exists(p10) else set()
    crudo = {os.path.basename(p).replace(".zip", "") for p in glob.glob(os.path.join(RAIZ, "datos", "crudo", "*.zip"))}
    out = {"regla": "10 escenas secas aceptadas a 20 m con mayor frac_valida_bahia; empates: fecha mas antigua", "n_secas_aceptadas_20m": len(r20),
           "escenas": [{"fecha": r["fecha"], "producto_l1c": r["producto_l1c"], "frac_valida_bahia": float(r["frac_valida_bahia"]),
                        "aceptada_a_10m": r["producto_l1c"] in a10, "l1c_en_datos_crudo": r["producto_l1c"] in crudo} for r in sel]}
    out["siguientes_en_la_lista_solo_informacion"] = [{"fecha": r["fecha"], "frac_valida_bahia": float(r["frac_valida_bahia"])} for r in r20[10:13]]
    json.dump(out, open(os.path.join(RAIZ, "resultados", "radcor_subconjunto_20m.json"), "w"), indent=1, ensure_ascii=False)
    for e in out["escenas"]:
        print(e["fecha"], e["frac_valida_bahia"], "10m" if e["aceptada_a_10m"] else "-", "crudo" if e["l1c_en_datos_crudo"] else "FALTA", e["producto_l1c"])
    print("secas aceptadas 20 m:", len(r20), "| a 10 m:", sum(e["aceptada_a_10m"] for e in out["escenas"]), "| con L1C local:", sum(e["l1c_en_datos_crudo"] for e in out["escenas"]))


if __name__ == "__main__":
    main()
