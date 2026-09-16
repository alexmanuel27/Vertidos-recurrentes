# Puesta en marcha — paso a paso

## Qué problema hay exactamente

Tres máquinas distintas intervienen, y solo una tiene internet normal:

| Máquina | Qué es | Internet |
|---|---|---|
| Contenedor en la nube | donde corre Claude | proxy con lista blanca: **solo github.com** |
| VM Ubuntu en tu Mac | lo que Claude ve como "tu Mac" | el mismo proxy: **nada** |
| **Tu macOS** | tu Terminal, tu Chrome | **internet normal** |

Por eso Claude no puede descargar de Copernicus ni instalar nada con pip: no es un fallo
de tu conexión ni algo que se arregle cambiando de wifi. Lo que sí funciona es que las
tres cosas que necesitan internet las lances tú desde tu Terminal, y el resto lo haga
Claude. Las carpetas son las mismas para los dos, así que los ficheros se comparten solos.

Reparto:

- **Tú (Terminal de macOS):** instalar el entorno, descargar las escenas, correr ACOLITE,
  exportar a `.npz`. Pasos 1 a 5 de abajo.
- **Claude:** todo lo demás — climatología, anomalías, persistencia, adyacencia, figuras,
  artículo. Sin tocar la red.

---

## Paso 1 — Miniforge (una sola vez, ~5 min)

Abre Terminal en tu Mac:

```bash
cd ~/Downloads
curl -L -O "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-MacOSX-arm64.sh"
bash Miniforge3-MacOSX-arm64.sh -b -p "$HOME/miniforge3"
"$HOME/miniforge3/bin/conda" init zsh
```

Cierra la Terminal y ábrela de nuevo. Debe aparecer `(base)` al principio de la línea.

Si ya tienes conda o miniforge instalado, sáltate este paso.

## Paso 2 — ACOLITE y su entorno (~15 min)

```bash
cd "$HOME/Nube /repos/publication plan/series-Sentinel-2"
mkdir -p externo
git clone https://github.com/acolite/acolite.git externo/acolite
mamba env create -f externo/acolite/environment.yml
conda activate acolite
```

El entorno se crea desde el `environment.yml` del propio ACOLITE, no desde una lista
inventada: así las versiones de GDAL, netCDF4 y el lector de JPEG2000 son las que él
espera. Comprueba:

```bash
python -c "import sys; sys.path.insert(0,'externo/acolite'); import acolite; print('ACOLITE OK')"
```

## Paso 3 — Cuenta de Copernicus (gratis, ~3 min)

Regístrate en **https://dataspace.copernicus.eu** y luego, en la misma Terminal:

```bash
export CDSE_USUARIO="tu-correo"
export CDSE_CLAVE="tu-contraseña"
```

## Paso 4 — Descargar las escenas

**Primero solo el catálogo**, para comprobar que la API responde como espera el script
(está escrito sin haber podido probarlo contra el servicio):

```bash
python scripts/00_descarga_cdse.py --solo-catalogo
```

Debe decir cuántos productos L1C de `T17QLF` hay entre 2016 y 2025. Si da error, pásale
el mensaje a Claude y lo corrige. Si va bien, las diez del piloto:

```bash
python scripts/00_descarga_cdse.py --n 10
```

Son unos 8 GB y las reparte por los diez años, no coge las diez primeras.

## Paso 5 — ACOLITE y exportación

```bash
python scripts/03_correr_acolite.py --acolite-src externo/acolite
python scripts/02_exportar_npz.py
```

La primera vez ACOLITE se descarga solo sus tablas auxiliares (necesita internet: por eso
va aquí y no en el lado de Claude).

## Paso 6 — Dile a Claude que ya está

A partir de `datos/productos/*.npz` el análisis solo necesita numpy y scipy, así que
Claude sigue desde ahí sin red. Si algo falló, el fichero
`datos/productos/manifiesto.json` dice qué variables devolvió ACOLITE en cada escena y es
lo primero que hay que mirar.

---

## Alternativa: ampliar la lista de dominios

Si prefieres que Claude lo haga todo, habría que permitir estos dominios en los ajustes
de red de la cuenta:

```
dataspace.copernicus.eu           catalogue.dataspace.copernicus.eu
identity.dataspace.copernicus.eu  download.dataspace.copernicus.eu
pypi.org                          files.pythonhosted.org
```

Ese ajuste vive en la configuración de administrador de la organización y, en cuentas
personales, puede sencillamente no existir. Míralo si quieres, pero **no hace falta**:
los seis pasos de arriba funcionan igual y no dependen de ello.
