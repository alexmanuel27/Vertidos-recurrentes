# Contexto para una sesión nueva de trabajo técnico

Léelo entero antes de tocar nada. Está escrito para una sesión que no recuerda nada de
las anteriores. Última actualización: 27/09/2026.

## 1. El proyecto

Alex Manuel Rivera Rivera (investigador; doctorado en Cuba y en Bruselas) prepara un
artículo sobre **puntos de vertido recurrentes en la Bahía de La Habana** a partir de diez
años de Sentinel-2 (2016–2025). Es el punto 8 de su plan de doctorado: algoritmos para
localizar fuentes de contaminación. **Trabaja y escribe en español.**

Idea central: una pluma de un emisario real es un exceso de turbidez localizado y
recurrente sobre la historia del propio píxel; un barco o un evento aislado no lo es. Lo
que persiste una década es un vertido. El producto final es un mapa de puntos de descarga
ordenados por persistencia, que una autoridad ambiental pueda usar.

Revista objetivo: **Marine Pollution Bulletin** (Elsevier, plantilla CAS).

## 2. Dos repos, y qué va en cada uno

| Repo | Ruta en el Mac | Remoto | Contenido |
|---|---|---|---|
| **Este** (técnico) | `/Users/alex/Nube /repos/Vertidos-recurrentes` | `github.com/alexmanuel27/Vertidos-recurrentes` | método, código, datos, resultados |
| Artículo | `/Users/alex/Nube /repos/publication plan/series-Sentinel-2` | `github.com/Publication-Plan/series-Sentinel-2` | solo el manuscrito LaTeX |

Aquí se generan las figuras y las cifras; al artículo solo se le **entregan** figuras
finales (PDF vectorial, en inglés) en `manuscript/figuras/` y los números para el texto.
No meter código en el repo del artículo ni el manuscrito aquí.

## 3. Reglas que no se negocian

1. **Higiene del preregistro.** `PROTOCOLO_CONGELADO.md` fija el método. La línea base
   (climatología) se calcula y se **commitea antes** de calcular ninguna anomalía. Ningún
   umbral se cambia después de haber visto anomalías sin registrarlo como tal.
2. **Todo cambio de método va a la sección 14 del protocolo** con fecha, motivo y la
   columna «¿después de ver anomalías?» contestada con honestidad.
3. **No reescribir la historia de git** (nada de rebase, amend de commits ya empujados,
   ni force-push). El commit `0eeeecd` del 15/09/2026 es la prueba de que el método se
   fijó antes de procesar datos; este repo heredó toda la historia justo para conservarla.
4. **Ninguna referencia bibliográfica de memoria.** Se descarga de doi.org
   (`curl -LH "Accept: application/x-bibtex" https://doi.org/<DOI>`) y se comprueba el título.
5. **Un veredicto tiene que poder abstenerse.** Si los datos no permiten concluir, se dice
   «no concluyente» y por qué. El piloto dictaminó dos veces «seguir» sobre datos no
   físicos antes de corregirse; no repetirlo.
6. Nunca escribir credenciales en ficheros del repo. Las de Copernicus van en las
   variables de entorno `CDSE_USUARIO` / `CDSE_CLAVE`.

## 4. Dónde se ejecuta cada cosa

Hay tres máquinas y conviene no confundirlas:

- **macOS real de Alex**: internet normal, git con sus credenciales, TeX Live 2026, conda
  (`~/miniforge3`) con el entorno **`acolite`** (Python 3.14; ACOLITE importa bien).
  Si la sesión tiene las herramientas de **Desktop Commander**, corren aquí.
- **VM Linux de Cowork** (`device_bash`): ve las carpetas conectadas pero **no tiene red**
  ni scipy.
- **Contenedor en la nube** (`Bash`): numpy, scipy, matplotlib; red limitada a github.

Si no hay Desktop Commander, los pasos con red (descargas, ACOLITE, push) los lanza Alex
en su Terminal: dale comandos **sin comentarios en línea** (zsh interpreta `#` y `~4`
como argumentos y aborta el bloque entero).

## 5. Estado actual

**Datos.** Tile T17QLF, **solo órbita R097** (en R054 la bahía cae fuera de la franja:
ACOLITE devuelve *100 % blackfill*). Catálogo: 664 productos L1C R097, 2016–2025.
En disco: `datos/crudo` 9,3 GB (15 productos), `datos/acolite` 10 GB, `datos/productos`
13 escenas `.npz` de 614 × 621 px a 20 m. Libres en el disco: ~94 GB.

**Ventana.** 23,10–23,21 N, 82,40–82,28 W (12,2 × 12,3 km), en `src/acolite_io.py`,
`limite_bahia()`. Incluye 6,7 km de mar abierto: hace falta como referencia limpia y
como campo lejano para medir la adyacencia.

**Lo que midió el piloto (13 escenas):**

| | |
|---|---|
| Escenas utilizables | 5 de 13 (38 %) → ~250 en el archivo, ~125 por estación |
| Adyacencia | A = 0,0031–0,0046 en ρ(1610 nm); L = 55, 94 y 386 m (ajustes con r² > 0,85) |
| Turbidez | bahía 3,01 FNU (RIC 2,23–3,92), mar abierto 1,40 FNU (1,22–1,69), 2,1× |
| Estructuras | no concluyente: 4 observaciones por píxel frente a las 20 exigidas |

Validación sintética (`tests/test_cadena.py`): las cinco comprobaciones pasan.

## 6. Lecciones caras (no volver a caer)

- `l2w_parameters` de ACOLITE **tiene que ser una lista**. Con una cadena, ACOLITE la
  recorre letra a letra y escribe un L2W válido **sin ningún producto**, sin error.
- ACOLITE saca Sentinel-2 a **10 m por defecto** y **aplica su máscara SWIR a los
  productos**, lo que borraría el agua muy turbia. Aquí: `s2_target_res=20`,
  `l2w_mask_water_parameters=False`, banderas en `l2_flags` aplicadas por nosotros.
- Bits de `l2_flags`: 0 no-agua SWIR, 1 cirros, 2 TOA alto, 3 ρ negativa, 4 fuera de
  escena, 5 píxel mixto. Se aplican 1–4; **nunca 0 ni 5** (son la orilla y el agua turbia).
- La bruma que deja la corrección no la marca ninguna bandera. Se detecta con
  **ρ(2200 nm) > 0,010 sobre agua**, por píxel: a esa longitud de onda el agua absorbe
  por completo, turbia o no.
- Los resúmenes por escena se calculan **sobre la máscara de agua**; sobre la ventana
  entera la tierra da turbideces de millones negativos.
- ACOLITE renombra la salida a `S2A_MSI_AAAA_MM_DD_HH_MM_SS_T17QLF_L2W.nc`.
- `requests` borra la cabecera `Authorization` al redirigir de `catalogue.dataspace` a
  `download.dataspace`: por eso existe `SesionCDSE`.
- El token de CDSE caduca a los 30 min: se renueva por tiempo, no por número de productos.

## 7. Pendiente, por orden

1. **Bucle por tandas para el archivo completo** (`scripts/04_archivo_por_tandas.py`):
   bajar ~20 productos → ACOLITE → `.npz` → **borrar crudo y SAFE** → siguiente tanda.
   Reanudable (saltar lo ya exportado) y con registro de qué se procesó y qué falló. Sin
   borrar no cabe: son ~465 GB de crudo frente a 94 GB libres; los `.npz` finales ocupan
   unos 5 GB.
2. **Exportar el AOT de cada escena** al `.npz`: lo necesita el test de covariable
   atmosférica (protocolo 11.3c). Mirar en un L2R/L2W real cómo lo guarda ACOLITE
   (atributo global) antes de escribir el lector; no suponer el nombre.
3. **Actualizar la sección 1 del protocolo**: sigue describiendo la ventana antigua
   (238 × 253 px). El cambio ya está en el registro (sección 14), pero el texto no.
   Decidir si el umbral de escena es 60 % (protocolo) o 40 % (piloto) y registrarlo
   **antes** de calcular anomalías.
4. **Climatología** sobre el archivo completo → **commit** → solo entonces anomalías,
   persistencia, barrido de márgenes (0–400 m), controles emparejados, covariable de
   aerosoles, anisotropía.
5. **Figuras para el artículo en inglés**, sin título incrustado (lo lleva el pie), PDF
   vectorial, a `manuscript/figuras/` del repo del artículo. Las actuales
   (`validacion_sintetica`, `piloto`) están en español con título: rehacerlas.
6. **Fig. 1**: mapa del área de estudio (ensenadas de Marimelena, Guasabacoa y Atarés,
   canal de entrada, ventana de análisis).
7. **Tiempo de renovación** por prisma mareal (`src/prisma_mareal.py`): todas las
   entradas están POR CONFIRMAR; falta batimetría (oficial o digitalizada de la carta
   náutica del puerto). Solo contexto interpretativo, nunca criterio de detección.
8. **Briefing de la campaña de verificación** cuando haya sitios: seis puntos con
   coordenadas, y qué traer —fotos con hora, descripción (color, olor, espuma, caudal),
   muestra si se puede—. Si un sitio coincide con un emisario registrado, también es
   confirmación.
9. Antes de enviar: *release* etiquetada con DOI de Zenodo.

## 8. Convenciones de commit

Mensajes en español, primera línea corta y en imperativo, cuerpo con el porqué. Terminar
con las líneas de atribución que indique la sesión. Push al terminar cada bloque de
trabajo; si falla, dejar a Alex la línea exacta:

    cd "/Users/alex/Nube /repos/Vertidos-recurrentes" && git push -u origin main
