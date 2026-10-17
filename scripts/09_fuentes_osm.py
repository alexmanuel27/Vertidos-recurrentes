"""Revision de fuentes conocidas antes de la visita de campo (protocolo seccion 20.5).

    python scripts/09_fuentes_osm.py

Lee resultados/campo/osm_overpass.json (consulta Overpass guardada tal cual, con su fecha
de instantanea) y resultados/campo/clave.csv. Para cada punto da la distancia al elemento
OSM mas cercano (cauces waterway river/stream/canal/drain/ditch; man_made outfall/pipeline;
waterway=outfall) y lo clasifica como «fuente conocida a <= 150 m» o no.
Escribe resultados/campo/fuentes_osm.csv. Datos (c) colaboradores de OpenStreetMap, ODbL.
"""
import csv, json, math, os

RADIO_M = 150.0
CAMPO = os.path.join("resultados", "campo")


def a_metros(lat, lon, lat0):
    return lon * 111320.0 * math.cos(math.radians(lat0)), lat * 110574.0


def dist_segmento(p, a, b):
    ax, ay = a[0] - p[0], a[1] - p[1]; bx, by = b[0] - p[0], b[1] - p[1]
    dx, dy = bx - ax, by - ay
    L = dx * dx + dy * dy
    t = 0.0 if L == 0 else max(0.0, min(1.0, -(ax * dx + ay * dy) / L))
    return math.hypot(ax + t * dx, ay + t * dy)


def main():
    osm = json.load(open(os.path.join(CAMPO, "osm_overpass.json")))
    lat0 = 23.14
    elems = []
    for e in osm["elements"]:
        t = e.get("tags", {})
        tipo = t.get("waterway") or t.get("man_made") or "?"
        nombre = t.get("name", "")
        if e["type"] == "node":
            pts = [a_metros(e["lat"], e["lon"], lat0)]
        else:
            pts = [a_metros(g["lat"], g["lon"], lat0) for g in e.get("geometry", [])]
        if pts:
            elems.append((f"{e['type']}/{e['id']}", tipo, nombre, pts))
    filas = []
    for r in csv.DictReader(open(os.path.join(CAMPO, "clave.csv"))):
        p = a_metros(float(r["lat"]), float(r["lon"]), lat0)
        mejor = (math.inf, None)
        for eid, tipo, nombre, pts in elems:
            d = math.hypot(pts[0][0] - p[0], pts[0][1] - p[1]) if len(pts) == 1 else \
                min(dist_segmento(p, pts[i], pts[i + 1]) for i in range(len(pts) - 1))
            if d < mejor[0]:
                mejor = (d, (eid, tipo, nombre))
        d, (eid, tipo, nombre) = mejor
        filas.append({"punto": r["punto"], "fuente_conocida_150m": "si" if d <= RADIO_M else "no",
                      "distancia_m": round(d), "osm_id": eid, "tipo": tipo, "nombre": nombre})
    with open(os.path.join(CAMPO, "fuentes_osm.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(filas[0])); w.writeheader(); w.writerows(filas)
    print("instantanea OSM:", osm["osm3s"]["timestamp_osm_base"], "| elementos:", len(elems))
    for f in filas:
        print(f)


if __name__ == "__main__":
    main()
