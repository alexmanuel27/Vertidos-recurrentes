"""Descarga del archivo Sentinel-2 L1C del tile T17QLF desde Copernicus Data Space.

NO VERIFICADO CONTRA EL SERVICIO: se escribio sin acceso de red, a partir de la API OData
de CDSE. Los tres endpoints estan como constantes arriba para poder corregirlos de un
vistazo si el servicio ha cambiado. Correr antes: scripts/99_comprobar_entorno.py

Credenciales por variables de entorno CDSE_USUARIO y CDSE_CLAVE (registro gratuito).
"""
import os, sys, json, time, argparse
from pathlib import Path
import requests
from urllib.parse import urlparse

TOKEN_URL = ("https://identity.dataspace.copernicus.eu/auth/realms/CDSE/"
             "protocol/openid-connect/token")
ODATA = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
DESCARGA = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products({id})/$value"
DOMINIO = "dataspace.copernicus.eu"

class SesionCDSE(requests.Session):
    """requests borra la cabecera Authorization al redirigir a OTRO host, por seguridad.

    CDSE redirige catalogue.dataspace... -> download.dataspace..., asi que el Bearer se
    perdia por el camino y el servidor respondia 401 aunque el token fuese valido.
    Aqui se conserva solo dentro del propio dominio de Copernicus.
    """

    def rebuild_auth(self, prepared_request, response):
        destino = urlparse(prepared_request.url).hostname or ""
        if destino == DOMINIO or destino.endswith("." + DOMINIO):
            return
        return super().rebuild_auth(prepared_request, response)


TILE = "T17QLF"
NIVEL = "MSIL1C"          # protocolo seccion 2: L1C, la correccion la hace ACOLITE
DESDE, HASTA = "2016-01-01", "2025-12-31"
ORBITA = "R097"   # la R054 cubre el tile pero NO la bahia: 100% blackfill


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


def descargar(pid, nombre, destino, tk, reintentos=3, limite_s=1200):
    salida = Path(destino) / f"{nombre}.zip"
    if salida.exists() and salida.stat().st_size > 1_000_000:
        return salida, "ya estaba"
    for intento in range(reintentos):
        try:
            ses = SesionCDSE()
            ses.headers["Authorization"] = f"Bearer {tk}"
            # timeout=(conexion, lectura): un socket muerto falla en 2 min, no en 30.
            with ses.get(DESCARGA.format(id=pid), stream=True, timeout=(30, 120),
                         allow_redirects=True) as r:
                r.raise_for_status()
                tmp = salida.with_suffix(".parcial")
                t0 = time.time()
                with open(tmp, "wb") as f:
                    for trozo in r.iter_content(chunk_size=1 << 20):
                        f.write(trozo)
                        # Una conexion que gotea unos bytes cada poco no dispara el
                        # timeout de lectura y puede tener el bucle horas (visto: 297 MB
                        # en 16116 s). Se corta y se reintenta desde cero.
                        if time.time() - t0 > limite_s:
                            raise TimeoutError(f"mas de {limite_s} s bajando; se reintenta")
                tmp.rename(salida)
            return salida, "descargado"
        except Exception as e:
            if intento == reintentos - 1:
                return None, f"fallo: {e}"
            time.sleep(20 * (intento + 1))


def probar(prods, tk):
    """Pide solo los primeros bytes de un producto: confirma la autorizacion en segundos
    en vez de esperar a que fallen descargas de 700 MB."""
    p = prods[0]
    ses = SesionCDSE()
    ses.headers["Authorization"] = f"Bearer {tk}"
    with ses.get(DESCARGA.format(id=p["Id"]), stream=True, timeout=120,
                 allow_redirects=True) as r:
        print(f"  producto : {p['Name'][:52]}")
        print(f"  host final: {urlparse(r.url).hostname}")
        print(f"  HTTP      : {r.status_code}")
        if r.status_code >= 400:
            print(f"  cuerpo    : {r.text[:200]}")
            return False
        trozo = next(r.iter_content(chunk_size=1 << 20), b"")
        print(f"  recibidos : {len(trozo)/1e6:.1f} MB de prueba")
        print(f"  tamano    : {int(r.headers.get('Content-Length', 0))/1e6:.0f} MB")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--destino", default="datos/crudo")
    ap.add_argument("--solo-catalogo", action="store_true")
    ap.add_argument("--orbita", default=ORBITA,
                    help="orbita relativa a conservar; 'todas' para no filtrar")
    ap.add_argument("--probar", action="store_true",
                    help="comprobar la autorizacion sin descargar nada entero")
    ap.add_argument("--n", type=int, default=0,
                    help="descargar solo N productos repartidos por el periodo (piloto)")
    a = ap.parse_args()
    Path(a.destino).mkdir(parents=True, exist_ok=True)

    prods = catalogo()
    print(f"{len(prods)} productos {NIVEL} de {TILE} entre {DESDE} y {HASTA}")
    if a.orbita and a.orbita.lower() != "todas":
        antes = len(prods)
        prods = [p for p in prods if f"_{a.orbita}_" in p["Name"]]
        print(f"filtrado a orbita {a.orbita}: {len(prods)} de {antes} "
              f"(la otra orbita ve el tile pero no la bahia)")
    Path(a.destino, "catalogo.json").write_text(json.dumps(prods, indent=1))
    if a.solo_catalogo:
        return

    if a.probar:
        print("\n--- prueba de autorizacion ---")
        ok = probar(prods, token())
        print("\nAUTORIZACION OK: lanza --n 10" if ok else "\nSIGUE FALLANDO: pasame lo de arriba")
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
