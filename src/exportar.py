"""Un L2W de ACOLITE -> un .npz. Lo usan 02_exportar_npz.py y 04_archivo_por_tandas.py.

Necesita netCDF4 (entorno 'acolite' o 'bahia' en macOS). Lo que sale de aqui ya solo
necesita numpy.

Ademas de los productos, el .npz guarda los ATRIBUTOS GLOBALES del L2W. Desde el bucle por
tandas el crudo se borra en cuanto se exporta, asi que lo que no quede en el .npz no se
recupera sin volver a bajar 700 MB por escena. En particular:

  aot_550           espesor optico de aerosoles a 550 nm que estimo DSF para la escena.
                    ACOLITE lo escribe como atributo global 'ac_aot_550' (COMPROBADO
                    sobre S2B_MSI_2019_03_05_16_16_56_T17QLF_L2W.nc, valor 0,281).
                    Lo necesita el test de covariable atmosferica (protocolo 11.3c).
  ac_model          modelo de aerosol elegido por DSF.
  producto_l1c      nombre del L1C de entrada (atributo 'inputfile'), para la trazabilidad.
  atributos_acolite todos los atributos globales, en JSON, por si mas adelante hace falta
                    alguno que hoy no se ha previsto (geometria, version de ACOLITE...).
"""
import json
import os

import numpy as np

import acolite_io

CLAVES = ("turbidez_dogliotti", "turbidez_nechad", "spm", "swir", "swir2",
          "verde", "nir", "banderas")
IMPRESCINDIBLES = {"turbidez_dogliotti", "swir", "swir2"}


def _a_json(v):
    if isinstance(v, np.ndarray):
        return v.tolist()
    if isinstance(v, np.generic):
        return v.item()
    return v


def atributos(nc):
    from netCDF4 import Dataset
    with Dataset(nc) as ds:
        return {k: _a_json(ds.getncattr(k)) for k in ds.ncattrs()}


def producto_de(npz):
    """Nombre del L1C del que sale un .npz ('' si es de antes de guardarlo)."""
    with np.load(npz, allow_pickle=False) as d:
        return str(d["producto_l1c"]) if "producto_l1c" in d.files else ""


def exportar(nc, carpeta_salida):
    """Exporta un L2W. Devuelve la entrada de manifiesto; 'ok' dice si salio bien.

    La escritura es atomica (fichero temporal y os.replace): si el proceso se corta a
    mitad, no queda un .npz a medias que la reanudacion tomaria por bueno.
    """
    nombre = os.path.basename(nc)
    disponibles = acolite_io.variables(nc)
    mapa = acolite_io.mapear(disponibles)
    claves = [c for c in CLAVES if c in mapa]
    if not IMPRESCINDIBLES <= set(claves):
        return {"escena": nombre, "ok": False,
                "motivo": f"faltan {sorted(IMPRESCINDIBLES - set(claves))}",
                "variables": disponibles}

    d = acolite_io.leer(nc, tuple(claves))
    fecha = acolite_io.fecha_de(nc)
    attrs = atributos(nc)

    extra = {}
    from netCDF4 import Dataset
    with Dataset(nc) as ds:   # coordenadas de la rejilla real, para no suponer su tamano
        for c in ("x", "y", "lat", "lon"):
            if c in ds.variables:
                extra[c] = np.array(ds.variables[c][:], dtype=np.float64)

    aot = attrs.get("ac_aot_550")
    aot = float(aot) if aot is not None else float("nan")
    l1c = os.path.basename(str(attrs.get("inputfile", "")))
    if l1c.endswith(".zip"):
        l1c = l1c[:-4]

    os.makedirs(carpeta_salida, exist_ok=True)
    destino = os.path.join(carpeta_salida, nombre.replace(".nc", ".npz"))
    # Hay fechas con DOS o TRES productos L1C del mismo paso (el tile partido entre
    # datastrips: 26 de las 637 fechas R097). ACOLITE puede dar el mismo nombre de salida a
    # los dos trozos; sin esto el segundo pisaria al primero en silencio. Si el nombre ya
    # lo ocupa OTRO L1C, se anade el sello de procesado del L1C.
    if os.path.exists(destino) and l1c and producto_de(destino) not in ("", l1c):
        destino = destino[:-4] + "__" + l1c.split("_")[-1].replace(".SAFE", "") + ".npz"
    # El temporal NO acaba en .npz: los lectores hacen glob("*.npz") y no deben verlo.
    tmp = destino + ".parcial"
    with open(tmp, "wb") as fh:
        np.savez_compressed(fh, fecha=np.array(fecha.isoformat()),
                            aot_550=np.array(aot, dtype=np.float64),
                            ac_model=np.array(str(attrs.get("ac_model", ""))),
                            producto_l1c=np.array(l1c),
                            atributos_acolite=np.array(json.dumps(attrs, default=str)),
                            **{c: d[c].astype(np.float32) for c in claves}, **extra)
    os.replace(tmp, destino)
    return {"escena": nombre, "ok": True, "fecha": fecha.isoformat(),
            "forma": list(d[claves[0]].shape), "mapa": d["_mapa"],
            "aot_550": aot, "producto_l1c": l1c, "npz": os.path.basename(destino)}
