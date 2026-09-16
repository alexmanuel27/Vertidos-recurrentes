# Puntos de vertido recurrentes en la Bahía de La Habana desde series Sentinel-2

Convertir diez años de archivo Sentinel-2 en un mapa de puntos de descarga recurrentes,
ordenados por persistencia. Punto 8 del plan de doctorado.

**Estado: cero escenas procesadas.** El método está congelado y validado sobre datos
sintéticos; falta el acceso a los datos y a ACOLITE.

## Por dónde empezar

1. `PROTOCOLO_CONGELADO.md` — el método, fijado antes de mirar ningún dato. Léelo primero.
2. `INSTALACION.md` — qué falta instalar y qué dominios hay que desbloquear.
3. `resultados/validacion_sintetica.png` — la cadena, probada contra una verdad conocida.

## Lo que ya está resuelto

**Footprint.** La bahía entera cae en un solo tile, **T17QLF** (UTM 17N). Ventana de
trabajo E 361139–365896, N 2556342–2561392: 4,76 × 5,05 km, 238 × 253 px a 20 m. Sin
mosaicos. El algoritmo MGRS de `src/geo.py` está verificado contra cuatro coordenadas
publicadas.

**El método, congelado y con registro de cambios fechado.** Tres familias de anomalía
(temporal, espacial, climatológica), tratamiento explícito de la adyacencia con controles
que pueden falsar el resultado, y criterios de fracaso escritos por adelantado.

**La cadena, validada.** `tests/test_cadena.py` planta en una bahía sintética una fuente
intermitente, una permanente, un artefacto de adyacencia y buques, y comprueba que el
método recupera las fuentes y rechaza los artefactos. Las cinco comprobaciones pasan.

## Lo que falta

- **Red.** El proxy bloquea Copernicus y PyPI (ver `INSTALACION.md`).
- **ACOLITE.** Decisión tomada: no se procesa nada sin él. Ni L2A de Sen2Cor, ni una
  reimplementación propia de DSF.
- **Batimetría** para el prisma mareal (`src/prisma_mareal.py`). Todas sus entradas están
  marcadas POR CONFIRMAR.

## Estructura

```
PROTOCOLO_CONGELADO.md   el preregistro del método
INSTALACION.md           dependencias y bloqueos de red
src/geo.py               UTM/MGRS, ventana de trabajo (verificado)
src/acolite_io.py        lanzar ACOLITE y leer sus productos (nombres verificados
                         contra el código fuente de ACOLITE, no supuestos)
src/mascara.py           máscara de agua por NDWI mediano, distancia a costa
src/climatologia.py      mediana y MAD por píxel y estación
src/anomalias.py         las tres familias de anomalía y la máscara de buques
src/adyacencia.py        ajuste del decaimiento y controles de falsación
src/persistencia.py      agrupación por pico y ranking por persistencia
src/prisma_mareal.py     tiempo de renovación (entradas por confirmar)
scripts/00_descarga_cdse.py   descarga del archivo (sin verificar contra el servicio)
scripts/01_piloto.py          el piloto de diez escenas y su veredicto
scripts/99_comprobar_entorno.py
tests/                   bahía sintética y validación extremo a extremo
articulo/                plantilla sn-jnl del grupo
```

## Nota sobre la plantilla

`articulo/` lleva la clase **sn-jnl**, que es la de Springer Nature y la que usan los
otros artículos del grupo. Conviene saber que **ninguna de las tres revistas de destino
la usa**: *Remote Sensing* es MDPI y *Ecological Indicators* y *Marine Pollution Bulletin*
son Elsevier (`elsarticle`). Sirve perfectamente para redactar, pero habrá que reformatear
antes de enviar, o empezar directamente en la plantilla de la revista elegida.
