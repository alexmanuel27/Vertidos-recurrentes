# Vertidos-recurrentes — parte técnica

Procesado del archivo Sentinel-2 (2016–2025) de la Bahía de La Habana para localizar
puntos de descarga recurrentes, ordenados por persistencia.

Este repo contiene **el método, el código, los datos y los resultados**. El artículo vive
aparte, en `series-Sentinel-2` (repo del *publication plan*), y solo recibe de aquí las
figuras finales y las cifras.

## Por dónde empezar

1. `PROTOCOLO_CONGELADO.md` — el método, fijado antes de calcular ninguna anomalía. Su
   registro de cambios (sección 14) acredita qué se decidió y cuándo. **La historia de git
   de este repo es parte de esa prueba: el protocolo entró en el commit `0eeeecd` del
   15/09/2026, antes de procesar ninguna escena. No reescribir la historia.**
2. `INSTALACION.md` — entorno conda de ACOLITE y cuenta de Copernicus.
3. `resultados/piloto.png` — lo que midió el piloto sobre 13 escenas reales.

## Estado (27/09/2026)

| | |
|---|---|
| Tile | T17QLF, **solo órbita R097** (R054 no ve la bahía: 100 % *blackfill*) |
| Catálogo | 664 productos L1C R097 entre 2016 y 2025 |
| Ventana | 12,2 × 12,3 km, 614 × 621 px a 20 m, incluye 6,7 km de mar abierto |
| Piloto | 13 escenas procesadas, 5 utilizables (38 %) |
| Adyacencia medida | A = 0,003–0,005 en ρ(1610 nm); L = 55, 94 y 386 m |
| Turbidez | bahía 3,01 FNU, mar abierto 1,40 FNU (2,1×) |
| Archivo completo | `scripts/04_archivo_por_tandas.py` listo y probado; falta lanzarlo con red |
| Pendiente | climatología; detección |

## Flujo

Los pasos con red se ejecutan en **macOS** (Terminal propia, entorno `acolite`); el
análisis sobre `.npz` solo necesita numpy y scipy.

```
python scripts/00_descarga_cdse.py --n 10            # descarga (filtra R097)
python scripts/03_correr_acolite.py --acolite-src externo/acolite > acolite.log 2>&1
python scripts/02_exportar_npz.py                    # L2W -> datos/productos/*.npz
python scripts/04_archivo_por_tandas.py --tanda 20   # archivo entero: bajar, ACOLITE, npz, borrar
python scripts/01_piloto.py                          # QC, adyacencia, veredicto
python scripts/figura_piloto.py                      # resultados/piloto.png
python tests/test_cadena.py                          # validación sobre bahía sintética
```

## Estructura

```
PROTOCOLO_CONGELADO.md    método preregistrado y registro de cambios
INSTALACION.md            entorno y credenciales
src/acolite_io.py         ajustes congelados de ACOLITE, ventana, lectura de productos
src/exportar.py           L2W -> .npz (productos, AOT, L1C de origen, atributos de ACOLITE)
src/mascara.py            máscara de agua por NDWI mediano, distancia a costa
src/climatologia.py       mediana y MAD por píxel y estación
src/anomalias.py          anomalía temporal, espacial y climatológica; máscara de buques
src/adyacencia.py         ajuste del decaimiento, controles emparejados
src/persistencia.py       agrupación por pico y ranking por persistencia
src/prisma_mareal.py      tiempo de renovación (entradas POR CONFIRMAR)
src/geo.py                UTM/MGRS
scripts/00..04, 97..99    descarga, ACOLITE, exportación, piloto, archivo por tandas, diagnósticos
tests/                    bahía sintética y validación extremo a extremo
resultados/               figuras y resúmenes (los .npz no se versionan)
datos/, externo/          NO versionados: crudo (~20 GB), ACOLITE clonado
```

## Lecciones que costaron caras

- ACOLITE recorre `l2w_parameters` con un `for`: **tiene que ser una lista**. Una cadena se
  recorre letra a letra y el L2W sale sin ningún producto, sin error.
- Por defecto ACOLITE saca Sentinel-2 a 10 m y **aplica su máscara SWIR a los productos**,
  lo que borraría el agua muy turbia. Aquí: 20 m y banderas calculadas pero no aplicadas.
- Las escenas con bruma no las marcan las banderas de ACOLITE. Se detectan con
  **ρ(2200 nm) > 0,010** sobre agua: a esa longitud de onda el agua absorbe por completo.
- Una ventana ceñida a la bahía (d_máx 588 m) **no permite medir la adyacencia**: el ajuste
  devuelve la caída de píxel mixto de la orilla. Hace falta campo lejano.
- `requests` borra la cabecera `Authorization` al redirigir entre hosts; CDSE redirige de
  `catalogue` a `download`. Ver `SesionCDSE` en `00_descarga_cdse.py`.
