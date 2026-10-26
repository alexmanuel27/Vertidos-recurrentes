"""Registro de la verificacion de campo (protocolo 20.5) a partir del zip que manda la persona
de campo: transcripcion literal de las fichas y posicion/hora de cada foto (EXIF).

    python scripts/12_registro_campo.py "datos/trabajo de campo/Bahia.zip"

Escribe resultados/campo/registro_visitas.csv y resultados/campo/fotos_visitas.csv. No codifica
nada ni usa la clave: solo copia lo que hay. Las fotos no se versionan (datos/ esta ignorado).
"""
import sys, io, csv, math, zipfile, glob
import numpy as np
import openpyxl
from PIL import Image

CAMPOS = {"Punto": "punto", "Fecha": "fecha", "Hora de llegada": "hora", "Visita nº": "visita_n_ficha",
          "Acceso": "acceso", "Si no accesible, ¿por qué?": "motivo_no_accesible",
          "¿Llovió en los 2 días anteriores?": "lluvia_48h",
          "1. ¿Hay algo que vierta agua a la bahía a menos de unos 150 m?": "estructura_150m",
          "Si sí: tipo de salida": "tipo_salida", "¿Está saliendo agua ahora?": "flujo_activo",
          "¿A cuántos metros del punto?": "distancia_m", "2. El agua: color": "color",
          "Mancha o pluma": "mancha", "Espuma": "espuma", "Película o aceite": "pelicula",
          "Basura flotando": "basura", "Nada de esto": "nada", "Olor": "olor",
          "3. Fotos de la nº": "foto_desde", "Fotos hasta la nº": "foto_hasta", "Notas": "notas"}


def grados(v, ref):
    d = float(v[0]) + float(v[1]) / 60 + float(v[2]) / 3600
    return -d if ref in ("S", "W") else d


def main(ruta_zip):
    z = zipfile.ZipFile(ruta_zip)
    pts = {r["punto"]: (float(r["lat"]), float(r["lon"])) for r in csv.DictReader(open("resultados/campo/puntos.csv"))}
    agua = np.load("resultados/climatologia.npz")["agua"]
    with np.load(sorted(glob.glob("datos/productos/*.npz"))[0]) as g:
        lat, lon = g["lat"], g["lon"]
    punto_de = lambda n: "P" + n.split("Punto")[1].split("/")[0].strip()
    fotos = []
    for i in sorted(z.infolist(), key=lambda i: i.filename):
        if not i.filename.lower().endswith((".jpg", ".jpeg")):
            continue
        ex = Image.open(io.BytesIO(z.read(i))).getexif()
        gps, sub = ex.get_ifd(0x8825), ex.get_ifd(0x8769)
        p = punto_de(i.filename); la0, lo0 = pts[p]
        fila = {"punto": p, "foto": i.filename.rsplit("/", 1)[1], "hora_exif": sub.get(36867) or ex.get(306) or "",
                "lat": "", "lon": "", "dist_al_punto_m": "", "posicion_en": ""}
        if gps and 2 in gps:
            la, lo = grados(gps[2], gps[1]), grados(gps[4], gps[3])
            # equirectangular local: error < 1 % a estas distancias
            d = math.hypot((lo - lo0) * 111320 * math.cos(math.radians(la0)), (la - la0) * 110574)
            k = np.unravel_index(np.argmin((lat - la) ** 2 + ((lon - lo) * math.cos(math.radians(la))) ** 2), lat.shape)
            fila.update(lat=round(la, 5), lon=round(lo, 5), dist_al_punto_m=round(d),
                        posicion_en="agua" if agua[k] else "tierra")
        fotos.append(fila)
    with open("resultados/campo/fotos_visitas.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(fotos[0])); w.writeheader(); w.writerows(fotos)

    fichas = []
    for i in sorted(z.infolist(), key=lambda i: i.filename):
        if not i.filename.endswith(".xlsx"):
            continue
        r = {}
        for a, b in openpyxl.load_workbook(io.BytesIO(z.read(i)), data_only=True).worksheets[0].iter_rows(
                min_col=1, max_col=2, values_only=True):
            if a in CAMPOS:
                v = "" if b is None else str(b).strip()
                r[CAMPOS[a]] = {"☒": "sí", "☐": "no"}.get(v, v)
        mias = [f for f in fotos if f["punto"] == r["punto"]]
        r.update(fotos_recibidas=len(mias), fotos_con_gps=sum(f["lat"] != "" for f in mias),
                 fuente=i.filename)
        fichas.append(r)
    with open("resultados/campo/registro_visitas.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(CAMPOS.values()) + ["fotos_recibidas", "fotos_con_gps", "fuente"])
        w.writeheader(); w.writerows(fichas)
    for f in fichas:
        print(f["punto"], f["fotos_recibidas"], "fotos,", f["fotos_con_gps"], "con GPS")


if __name__ == "__main__":
    main(sys.argv[1])
