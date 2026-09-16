"""Comprueba que el entorno esta listo. Correr ANTES de procesar."""
import importlib, shutil, sys

print("--- paquetes ---")
faltan = []
for m in ("numpy", "scipy", "matplotlib", "netCDF4", "pyproj", "skimage", "requests"):
    try:
        importlib.import_module(m); print(f"  OK    {m}")
    except ImportError:
        print(f"  FALTA {m}"); faltan.append(m)

print("--- acolite ---")
try:
    import acolite
    print(f"  OK    acolite {getattr(acolite, '__version__', '?')}")
except ImportError:
    print("  FALTA acolite  -> git clone https://github.com/acolite/acolite.git")
    faltan.append("acolite")

print("--- red ---")
try:
    import requests
    for url in ("https://identity.dataspace.copernicus.eu/auth/realms/CDSE/"
                ".well-known/openid-configuration",
                "https://catalogue.dataspace.copernicus.eu/odata/v1/Products?$top=1"):
        r = requests.get(url, timeout=20)
        print(f"  {'OK   ' if r.status_code < 400 else 'FALLO'} {url.split('/')[2]} ({r.status_code})")
except Exception as e:
    print(f"  FALLO red: {e}"); faltan.append("red")

print("\n" + ("LISTO" if not faltan else f"FALTA: {', '.join(faltan)}"))
sys.exit(0 if not faltan else 1)
