"""Bloque A (peticion 2): baja y procesa las escenas de 2026 del catalogo fijado.

Catalogo: datos/crudo_2026/catalogo.json (T17QLF, R097, 2026-01-02 a 2026-11-13; corte =
commit c4d1ea7 de 2026-11-18 14:02 +01:00 con la fila de la secc. 14). Mismos ajustes
congelados (acolite_io.AJUSTES, commit de ACOLITE d61c8de). La resolucion sale de
VERTIDOS_PIXEL_M (20 por defecto, 10 para la segunda pasada).
A diferencia de 04_archivo_por_tandas.py NO borra el .zip: el 10 m reutiliza la descarga.
Credenciales solo por CDSE_USUARIO / CDSE_CLAVE.

    python scripts/35_bucle_2026.py --productos datos/productos_2026_20m
    VERTIDOS_PIXEL_M=10 python scripts/35_bucle_2026.py --productos datos/productos_2026_10m
"""
import os, sys, json, time, shutil, argparse, importlib.util

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "src"))
import acolite_io, exportar


def cargar(nombre):
    spec = importlib.util.spec_from_file_location(nombre, os.path.join(AQUI, nombre + ".py"))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalogo", default="datos/crudo_2026/catalogo.json")
    ap.add_argument("--crudo", default="datos/crudo_2026")
    ap.add_argument("--trabajo", default="datos/trabajo_2026")
    ap.add_argument("--productos", required=True)
    ap.add_argument("--logs", default=None)
    ap.add_argument("--acolite-src", default="externo/acolite")
    a = ap.parse_args()
    a.logs = a.logs or a.productos.replace("productos", "acolite_logs")
    desc, tandas = cargar("00_descarga_cdse"), cargar("04_archivo_por_tandas")
    prods = json.load(open(a.catalogo))
    assert all(p["ContentDate"]["Start"] < "2026-11-18" for p in prods), "escena posterior al corte"
    for d in (a.crudo, a.trabajo, a.productos, a.logs):
        os.makedirs(d, exist_ok=True)
    hechos = tandas.exportados(a.productos)
    limite = acolite_io.limite_bahia()
    reg = []
    tk, t_tk = desc.token(), time.time()
    for i, p in enumerate(prods, 1):
        nombre = p["Name"]
        if nombre in hechos:
            print(f"[{i}/{len(prods)}] {nombre[:46]} ya exportado", flush=True); continue
        if time.time() - t_tk > 480:
            tk, t_tk = desc.token(), time.time()
        t0 = time.time()
        ruta, estado = desc.descargar(p["Id"], nombre, a.crudo, tk)
        if ruta is None:
            print(f"[{i}/{len(prods)}] {nombre[:46]} DESCARGA FALLO: {estado}", flush=True)
            reg.append({"producto": nombre, "estado": "fallo", "etapa": "descarga", "motivo": estado}); continue
        r = tandas.procesar(str(ruta), nombre, a, limite)
        shutil.rmtree(os.path.join(a.trabajo, nombre), ignore_errors=True)
        print(f"[{i}/{len(prods)}] {nombre[:46]} {r['estado']} {r.get('motivo','')[:100]} "
              f"({time.time()-t0:.0f} s)", flush=True)
        reg.append(r)
        json.dump(reg, open(os.path.join(a.productos, "registro_2026.json"), "w"), indent=1)
    print(f"\nok {sum(r['estado']=='ok' for r in reg)} / fallo {sum(r['estado']!='ok' for r in reg)}")


if __name__ == "__main__":
    main()
