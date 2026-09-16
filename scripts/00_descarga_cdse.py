"""Descarga del archivo Sentinel-2 L1C del tile T17QLF desde Copernicus Data Space.

NO VERIFICADO CONTRA EL SERVICIO: se escribio sin acceso de red, a partir de la API OData
de CDSE. Los tres endpoints estan como constantes arriba para poder corregirlos de un
vistazo si el servicio ha cambiado. Correr antes: scripts/99_comprobar_entorno.py

Credenciales por variables de entorno CDSE_USUARIO y CDSE_CLAVE (registro gratuito).
"""
import os, sys, json, time, argparse
from pathlib import Path
import requests

TOKEN_URL = ("https://identity.dataspace.copernicus.eu/auth/realms/CDSE/"
             "protocol/openid-connect/token")
ODATA = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
DESCARGA = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products({id})/$value"

TILE = "T17QLF"
NIVEL = "MSIL1C"          # protocolo seccion 2: L1C, la correccion la hace ACOLITE
DESDE, HASTA = "2016-01-01", "2025-12-31"


def token():
    u, c = os.environ.get("CDSE_USUARIO"), os.environ.get("CDSE_CLAVE")
    if not u or not c:
        sys.exit("Faltan CDSE_USUARIO / CDSE_CLAVE en el entorno.")
    datos = {"grant_type": "password", "username": u, "password": c,
             "client_id": "cdse-public"}
    totp = os.environ.get("CDSE_TOTP")      # codigo de 6 digitos si tienes 2FA activo
    if totp:
        datos["totp"] = totp
    r = requests.post(TOKEN_URL, data=datos, timeout=60)
    if r.status_code >= 400:
        # Keycloak explica el motivo en el cuerpo; sin esto el 400 no dice nada.
        try:
            j = r.json()
            sys.exit(f"CDSE rechazo las credenciales ({r.status_code}): "
                     f"{j.get('error')} - {j.get('error_description')}")
        except ValueError:
            sys.exit(f"CDSE devolvio {r.status_code}: {r.text[:300]}")
    return r.json()["access_token"]


def catalogo(desde=DESDE, hasta=HASTA, tile=TILE, nivel=NIVEL):
    """Lista todos los productos del tile en el periodo, paginando."""
    filtro = (f"Collection/Name eq 'SENTINEL-2' and contains(Name,'{nivel}') "
              f"and contains(Name,'{tile}') "
              f"and ContentDate/Start gt {desde}T00:00:00.000Z "
              f"and ContentDate/Start lt {hasta}T23:59:59.999Z")
    productos, salto = [], 0
    while True:
        r = requests.get(ODATA, params={"$filter": filtro, "$top": 1000,
                                        "$skip": salto, "$orderby": "ContentDate/Start"},
                         timeout=120)
        r.raise_for_status()
        lote = r.json().get("value", [])
        productos.extend(lote)
        if len(lote) < 1000:
            break
        salto += 1000
    return productos


def descargar(pid, nombre, destino, tk, reintentos=3):
    salida = Path(destino) / f"{nombre}.zip"
    if salida.exists() and salida.stat().st_size > 1_000_000:
        return salida, "ya estaba"
    for intento in range(reintentos):
        try:
            with requests.get(DESCARGA.format(id=pid),
                              headers={"Authorization": f"Bearer {tk}"},
                              stream=True, timeout=1800, allow_redirects=True) as r:
                r.raise_for_status()
                tmp = salida.with_suffix(".parcial")
                with open(tmp, "wb") as f:
                    for trozo in r.iter_content(chunk_size=1 << 20):
                        f.write(trozo)
                tmp.rename(salida)
            return salida, "descargado"
        except Exception as e:
            if intento == reintentos - 1:
                return None, f"fallo: {e}"
            time.sleep(20 * (intento + 1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--destino", default="datos/crudo")
    ap.add_argument("--solo-catalogo", action="store_true")
    ap.add_argument("--n", type=int, default=0,
                    help="descargar solo N productos repartidos por el periodo (piloto)")
    a = ap.parse_args()
    Path(a.destino).mkdir(parents=True, exist_ok=True)

    prods = catalogo()
    print(f"{len(prods)} productos {NIVEL} de {TILE} entre {DESDE} y {HASTA}")
    Path(a.destino, "catalogo.json").write_text(json.dumps(prods, indent=1))
    if a.solo_catalogo:
        return

    if a.n:   # reparto uniforme por el periodo, no los N primeros
        paso = max(1, len(prods) // a.n)
        prods = prods[::paso][:a.n]
        print(f"piloto: {len(prods)} productos repartidos por los diez años")

    tk, tk_t = token(), time.time()
    for i, p in enumerate(prods, 1):
        # El token caduca a los 30 min y una sola descarga puede tardar varios:
        # se renueva por TIEMPO, no cada N productos.
        if time.time() - tk_t > 1200:
            tk, tk_t = token(), time.time()
            print("    (token renovado)")
        t0 = time.time()
        ruta, estado = descargar(p["Id"], p["Name"], a.destino, tk)
        mb = ruta.stat().st_size / 1e6 if ruta else 0
        seg = time.time() - t0
        print(f"[{i}/{len(prods)}] {p['Name'][:44]} ... {estado}"
              + (f"  {mb:.0f} MB en {seg:.0f} s" if ruta and estado == "descargado" else ""))


if __name__ == "__main__":
    main()
