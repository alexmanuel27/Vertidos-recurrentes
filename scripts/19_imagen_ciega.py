"""Recortes de imagen de muy alta resolucion para la verificacion a ciegas (secc. 14, fila del 15/11/2026).

    python scripts/19_imagen_ciega.py

Para cada punto de clave.csv: 400 x 400 m en UTM 17N centrados en el punto, 800 x 800 px, de Esri
World Imagery, con un circulo de 150 m. Se etiquetan A-J con una permutacion de semilla 20261115.
Las imagenes van a datos/imagen_ciega/ (sin versionar); la correspondencia letra-punto y los metadatos
de la imagen (fecha, sensor, resolucion) a resultados/campo/imagen_etiquetas.csv. A quien codifica
solo se le dan las imagenes.
"""
import csv, io, json, os, string, urllib.request, urllib.parse
import numpy as np
from PIL import Image, ImageDraw
from pyproj import Transformer

SERV = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/"
MEDIO, PX, RADIO = 200, 800, 150
SALIDA = "datos/imagen_ciega/"


def leer(url):
    q = urllib.request.Request(url, headers={"User-Agent": "Vertidos-recurrentes/1.0 (investigacion)"})
    return urllib.request.urlopen(q, timeout=60).read()


def main():
    os.makedirs(SALIDA, exist_ok=True)
    pts = list(csv.DictReader(open("resultados/campo/clave.csv", encoding="utf-8")))
    letras = string.ascii_uppercase[:len(pts)]
    orden = np.random.default_rng(20261115).permutation(len(pts))
    a_utm = Transformer.from_crs(4326, 32617, always_xy=True)
    filas = []
    for letra, k in zip(letras, orden):
        p = pts[k]; lat, lon = float(p["lat"]), float(p["lon"])
        x, y = a_utm.transform(lon, lat)
        q = urllib.parse.urlencode({"bbox": f"{x-MEDIO},{y-MEDIO},{x+MEDIO},{y+MEDIO}", "bboxSR": 32617,
                                    "imageSR": 32617, "size": f"{PX},{PX}", "format": "png", "f": "image"})
        im = Image.open(io.BytesIO(leer(SERV + "export?" + q))).convert("RGB")
        r = RADIO * PX / (2 * MEDIO); c = PX / 2
        d = ImageDraw.Draw(im); d.ellipse([c - r, c - r, c + r, c + r], outline=(255, 230, 0), width=3)
        d.line([c - 8, c, c + 8, c], fill=(255, 230, 0), width=2); d.line([c, c - 8, c, c + 8], fill=(255, 230, 0), width=2)
        im.save(SALIDA + letra + ".png")
        q = urllib.parse.urlencode({"geometry": f"{lon},{lat}", "geometryType": "esriGeometryPoint", "sr": 4326,
                                    "layers": "all", "tolerance": 1, "mapExtent": f"{lon-.01},{lat-.01},{lon+.01},{lat+.01}",
                                    "imageDisplay": "800,800,96", "returnGeometry": "false", "f": "json"})
        meta = json.loads(leer(SERV + "identify?" + q))["results"][0]["attributes"]
        filas.append({"letra": letra, "punto": p["punto"], "fecha_imagen": meta.get("DATE (YYYYMMDD)", ""),
                      "sensor": meta.get("DESCRIPTION", ""), "resolucion_m": meta.get("RESOLUTION (M)", ""),
                      "version": meta.get("ReleaseName", "")})
        print(letra, filas[-1]["fecha_imagen"], filas[-1]["sensor"], filas[-1]["resolucion_m"])
    filas.sort(key=lambda f: f["letra"])
    with open("resultados/campo/imagen_etiquetas.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(filas[0])); w.writeheader(); w.writerows(filas)


if __name__ == "__main__":
    main()
