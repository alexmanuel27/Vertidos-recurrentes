# Instalación — qué hace falta antes de procesar

Ninguna de estas piezas está instalada todavía, ni en el contenedor de la sesión ni en
el Mac. El proyecto **no procesa nada hasta que ACOLITE esté funcionando** (protocolo,
sección 3).

## Bloqueo actual

El proxy de la sesión deja pasar `github.com` por git y **nada más**. Devuelven 403:
Copernicus Data Space, los espejos de Sentinel-2 de AWS / Google / Planetary Computer, y
**PyPI**. Sin PyPI no hay netCDF4, pyproj ni GDAL, que son dependencias de ACOLITE.

Para desbloquearlo hay que añadir a los dominios permitidos de la cuenta, como mínimo:

```
dataspace.copernicus.eu
catalogue.dataspace.copernicus.eu
identity.dataspace.copernicus.eu
download.dataspace.copernicus.eu
pypi.org
files.pythonhosted.org
```

## Entorno

Recomendado miniforge/mamba, porque GDAL y netCDF4 desde pip en macOS ARM dan problemas:

```bash
mamba create -n bahia python=3.11 numpy scipy matplotlib netCDF4 gdal pyproj \
      scikit-image scikit-learn pandas requests pyhdf
mamba activate bahia
```

## ACOLITE

```bash
git clone https://github.com/acolite/acolite.git
cd acolite && python -c "import acolite; print(acolite.__version__)"
```

ACOLITE necesita además sus ficheros auxiliares (LUTs), que se descarga solo la primera
vez que corre — hace falta red hacia el RBINS.

## Comprobación

```bash
python scripts/99_comprobar_entorno.py
```

Debe decir OK en las cuatro filas antes de tocar nada más.
