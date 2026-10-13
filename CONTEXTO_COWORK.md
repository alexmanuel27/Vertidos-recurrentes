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
ACOLITE devuelve *100 % blackfill*). Catálogo: 664 productos L1C R097, 2016–2025, que son
**637 adquisiciones**: en 26 fechas el tile viene partido en 2–3 productos (registro del
protocolo, 27/09/2026). Todos se procesan; cómo combinarlos está pendiente.
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
- El token de CDSE caduca antes de lo que parecía (renovándolo a los 20 min hubo 401): el bucle lo renueva a los 8 min, pide otro ante un 401 y espera si se cae la red.

## 7. Pendiente, por orden

1. ~~Bucle por tandas~~ **HECHO y EJECUTADO** (27/09–03/10/2026). Archivo completo:
   **644 `.npz` que cubren las 637 adquisiciones R097** (S2A 301, S2B 300, S2C 36); ninguna
   fecha sin escena. 19 trozos de fechas partidas dieron «100 % blackfill» (su otro trozo
   sí está) y 1 producto S2C de baseline N9906 (2024-12-18, puesta en servicio) da 404 en
   CDSE (su fecha también tiene escena). **7 fechas tienen 2 escenas exportadas** (los dos
   trozos ven parte de la ventana): las afecta la regla 2b. Registro en
   `datos/productos/registro_tandas.jsonl`. Se lanza con `scripts/archivo_sin_parar.sh`
   (vigilante que relanza si el sistema mata el proceso). Quedan en disco, prescindibles,
   el crudo y los productos ACOLITE del piloto (`datos/crudo` 9,4 GB, `datos/acolite` 11 GB).
2. ~~Exportar el AOT~~ **HECHO 27/09/2026**: ACOLITE lo guarda como atributo global
   `ac_aot_550` (comprobado en un L2W real). `src/exportar.py` lo escribe en cada `.npz`
   como `aot_550`, junto con `producto_l1c` y todos los atributos globales en JSON
   (`atributos_acolite`). Los 13 `.npz` del piloto se reexportaron: arrays idénticos al byte.
2b. ~~Regla para fechas con varios productos~~ **FIJADA 13/10/2026** (sección 14): un
   solo producto por fecha, el que más ventana cubre (bit 4 de `l2_flags` sin activar);
   empate → procesado más reciente. **Falta implementarla** en la carga de escenas de la
   climatología: hoy un `glob("*.npz")` aún cuenta como dos escenas las 7 fechas partidas.
3. ~~Sección 1 y umbral de escena~~ **HECHO 13/10/2026**: la ventana de la v1.0 pasa a
   ser «la bahía»; el umbral sigue en **60 %, contado sobre el agua de la bahía** (no sobre
   la ventana ampliada). Registrado en la sección 14.
4. ~~Climatología~~ **HECHA y COMMITEADA 13/10/2026** (`scripts/05_climatologia.py`,
   resumen en la sección 17 del protocolo): 113 escenas aceptadas de 637 (18 %), ninguna
   de 2016. **Siguiente:** antes de calcular anomalías, fijar en la sección 14 la
   tolerancia del emparejamiento candidato/control (sección 13, aún pendiente; el código
   tiene por defecto 20 m y 0,05 en `f_tierra`). Después: anomalías, persistencia,
   barrido de márgenes (0–400 m), controles emparejados, covariable de aerosoles,
   anisotropía. Cargar escenas SIEMPRE con `src/escenas.py` (misma validez que la
   climatología).
4b. **Detección EJECUTADA 13/10/2026** (`scripts/06_deteccion.py`, sección 18 del protocolo):
   3 sitios recurrentes, todos fuera de la bahía; **ninguno sobrevive al margen de 40 m →
   MÉTODO FRACASADO según el criterio 12.2** del preregistro. Todo lo que se haga a partir
   de aquí es **exploratorio** y va al registro con «¿después de ver anomalías? Sí».
   Conocido: duplicado de sitio por empate en la supresión de no-máximos; la familia z_c
   marca la bahía entera (bandas de distancia que mezclan bahía y mar).
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
