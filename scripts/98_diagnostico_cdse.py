"""Diagnostico del acceso a Copernicus: dice EXACTAMENTE por que falla el token.

    python scripts/98_diagnostico_cdse.py

Si tienes 2FA activo en la cuenta, exporta tambien el codigo de 6 digitos justo antes
de ejecutarlo (caduca en 30 s):

    export CDSE_TOTP=123456
"""
import os, sys, json
import requests

TOKEN_URL = ("https://identity.dataspace.copernicus.eu/auth/realms/CDSE/"
             "protocol/openid-connect/token")
CONFIG_URL = ("https://identity.dataspace.copernicus.eu/auth/realms/CDSE/"
              ".well-known/openid-configuration")

u = os.environ.get("CDSE_USUARIO")
c = os.environ.get("CDSE_CLAVE")
totp = os.environ.get("CDSE_TOTP")
print(f"usuario: {u!r}   clave: {'definida (' + str(len(c)) + ' caracteres)' if c else 'NO DEFINIDA'}"
      f"   totp: {'si' if totp else 'no'}")
if not u or not c:
    sys.exit("Faltan CDSE_USUARIO / CDSE_CLAVE.")

print("\n--- 1. el servicio responde? ---")
try:
    r = requests.get(CONFIG_URL, timeout=30)
    print(f"  {r.status_code}  grant types: {r.json().get('grant_types_supported')}")
except Exception as e:
    sys.exit(f"  no se pudo contactar: {e}")

print("\n--- 2. peticion de token ---")
datos = {"grant_type": "password", "username": u, "password": c, "client_id": "cdse-public"}
if totp:
    datos["totp"] = totp
r = requests.post(TOKEN_URL, data=datos, timeout=60)
print(f"  codigo HTTP: {r.status_code}")
try:
    j = r.json()
    if r.status_code < 400:
        print(f"  OK. token de {len(j.get('access_token',''))} caracteres, "
              f"caduca en {j.get('expires_in')} s")
        print("\nTODO CORRECTO: vuelve a lanzar 00_descarga_cdse.py --n 10")
        sys.exit(0)
    print(f"  error           : {j.get('error')}")
    print(f"  descripcion     : {j.get('error_description')}")
except ValueError:
    print(f"  cuerpo: {r.text[:400]}")

print("\n--- que significa ---")
desc = ""
try:
    desc = (r.json().get("error_description") or "").lower()
except Exception:
    pass
if "totp" in desc or "otp" in desc or "2fa" in desc:
    print("  Tienes 2FA activo. Exporta CDSE_TOTP con el codigo de 6 digitos y repite.")
elif "not fully set up" in desc or "account is not" in desc:
    print("  La cuenta esta sin terminar de activar: entra por web a dataspace.copernicus.eu,")
    print("  completa lo que te pida (verificar correo, aceptar terminos) y repite.")
elif "invalid user credentials" in desc or "invalid_grant" in desc:
    print("  Usuario o contrasena incorrectos para el token. Comprueba que entras por web")
    print("  con esos mismos datos. Ojo con caracteres especiales al exportar la variable:")
    print("  usa comillas simples, no dobles, si la clave lleva $ o !.")
elif "invalid client" in desc or "unauthorized_client" in desc:
    print("  El client_id 'cdse-public' ya no vale para este flujo. Avisame y lo cambio.")
else:
    print("  Motivo no reconocido. Pasame las lineas de arriba tal cual.")
