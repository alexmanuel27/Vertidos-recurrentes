"""ACOLITE con RAdCor (peticion 2, bloque C) sobre los L1C de datos/crudo_radcor.

Mismos ajustes que src/acolite_io.AJUSTES (misma ventana, misma resolucion, mismos
productos L2W); lo UNICO que cambia es atmospheric_correction_method=radcor. No se toca
ningun parametro radcor_* (defectos de ACOLITE). Si falla una escena, se anota el motivo
literal y NO se reintenta con otros ajustes.

    VERTIDOS_PIXEL_M=20 ~/miniforge3/envs/acolite/bin/python scripts/34_radcor_correr.py
"""
import os, sys, glob, json, shutil, argparse, time

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "src"))
import acolite_io, exportar


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--crudo", default="datos/crudo_radcor")
    ap.add_argument("--trabajo", default="datos/trabajo_radcor")
    ap.add_argument("--productos", default="datos/productos_radcor_20m")
    ap.add_argument("--logs", default="datos/acolite_logs_radcor_20m")
    ap.add_argument("--acolite-src", default="externo/acolite")
    ap.add_argument("--registro", default="resultados/radcor_registro_20m.json")
    a = ap.parse_args()
    sys.path.insert(0, a.acolite_src)
    import acolite as ac
    os.makedirs(a.productos, exist_ok=True)
    zips = sorted(glob.glob(os.path.join(a.crudo, "*.zip")))
    limite = acolite_io.limite_bahia()
    ajustes0 = dict(acolite_io.AJUSTES)
    ajustes0["atmospheric_correction_method"] = "radcor"
    print(f"{len(zips)} productos | ajustes:", ajustes0, flush=True)
    registro = []
    for i, z in enumerate(zips, 1):
        nombre = os.path.basename(z)[:-4]
        trabajo = os.path.join(a.trabajo, nombre)
        shutil.rmtree(trabajo, ignore_errors=True)
        os.makedirs(trabajo)
        r = {"producto": nombre}
        t0 = time.time()
        so, se = sys.stdout, sys.stderr
        try:
            aj = dict(ajustes0)
            aj.update({"inputfile": z, "output": trabajo, "limit": list(limite),
                       "runid": nombre})
            ac.acolite.acolite_run(settings=aj)
            l2w = sorted(glob.glob(os.path.join(trabajo, "*L2W*.nc")))
            if len(l2w) != 1:
                r.update(estado="fallo", etapa="acolite", motivo=f"{len(l2w)} L2W")
            else:
                m = exportar.exportar(l2w[0], a.productos)
                r.update(estado="ok" if m["ok"] else "fallo",
                         **({"npz": m["npz"], "fecha": m["fecha"], "aot_550": m["aot_550"]}
                            if m["ok"] else {"etapa": "exportar", "motivo": m["motivo"]}))
        except (Exception, SystemExit) as e:
            r.update(estado="fallo", etapa="acolite", motivo=f"{type(e).__name__}: {e}"[:400])
        finally:
            sys.stdout, sys.stderr = so, se
        r["t_s"] = round(time.time() - t0)
        dlog = os.path.join(a.logs, nombre)
        os.makedirs(dlog, exist_ok=True)
        for f in glob.glob(os.path.join(trabajo, "*.txt")):
            shutil.copy2(f, dlog)
        shutil.rmtree(trabajo, ignore_errors=True)
        print(f"[{i}/{len(zips)}] {nombre[:46]} {r['estado']} {r.get('motivo','')[:120]}",
              flush=True)
        registro.append(r)
        json.dump(registro, open(a.registro, "w"), indent=1)


if __name__ == "__main__":
    main()
