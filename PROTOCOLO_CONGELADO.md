# Protocolo congelado — detección de puntos de vertido recurrentes en la Bahía de La Habana

**Versión 1.0 — 15 de septiembre de 2026**

Este documento fija el método **antes de haber procesado ninguna escena y antes de haber
mirado ninguna anomalía**. Ese es su único propósito. Todo umbral, margen y criterio de
decisión que aparece aquí está elegido a ciegas, a partir de argumentos físicos o de
convenciones ya publicadas, nunca a partir del resultado.

En el momento de redactar esta versión el estado de los datos es: **cero escenas
descargadas, cero escenas procesadas**. El repositorio no contiene ningún producto.
El commit que introduce este archivo es la marca temporal que lo acredita.

Cualquier cambio posterior se registra en la sección 14 con fecha, motivo y —
obligatoriamente — si se hizo antes o después de haber visto anomalías. Un cambio
posterior no invalida el trabajo; ocultarlo sí.

---

## 1. Zona de estudio y footprint

La Bahía de La Habana es una bahía de bolsa unida al mar abierto por un canal de entrada
estrecho, con tres ensenadas interiores (Marimelena al noreste, Guasabacoa al este,
Atarés al sur).

**Tile Sentinel-2:** `T17QLF` (UTM zona 17N, banda MGRS Q). La bahía completa, incluido
el canal de entrada y una franja de mar abierto frente a la bocana, cae dentro de este
único tile. No se mosaica nada. Los siete puntos de control usados para comprobarlo
(bocana, centro, las tres ensenadas y las dos esquinas del bbox) caen todos en `17QLF`,
holgadamente en el interior del cuadrado de 100 km, no en su borde.

**Ventana de trabajo (EPSG:32617, UTM 17N / WGS84):**

| | mínimo | máximo | extensión |
|---|---|---|---|
| Este (m) | 361 139 | 365 896 | 4,76 km |
| Norte (m) | 2 556 342 | 2 561 392 | 5,05 km |

A 20 m son 238 × 253 píxeles; a 10 m, 476 × 505. La ventana incluye deliberadamente una
franja de mar abierto al norte de la bocana, que se usa como referencia de agua limpia
(sección 11).

**Resolución de trabajo: 20 m.** Es la resolución nativa de las bandas SWIR (B11, B12),
necesarias tanto para la corrección atmosférica como para el diagnóstico de adyacencia y
el enmascarado de buques, y es la rejilla común a la que ACOLITE entrega sus productos
cuando se piden esas bandas. Un producto a 10 m se conserva para la delineación final de
los sitios candidatos, no para la detección.

---

## 2. Datos de entrada

- Sentinel-2 MSI, niveles L1C, misiones S2A y S2B (y S2C cuando corresponda al periodo).
- Periodo: **1 de enero de 2016 a 31 de diciembre de 2025** (diez años completos).
- Fuente: Copernicus Data Space Ecosystem.
- **Solo la órbita relativa R097.** El tile T17QLF lo adquieren dos órbitas, R054 y R097,
  a partes casi iguales (668 y 664 productos). En R054 la bahía cae fuera de la franja
  útil: ACOLITE aborta las seis escenas R054 del piloto con *«crop is 100% blackfill»*,
  frente a las cuatro R097 que se procesan sin incidencia. La exclusión es un hecho
  geométrico verificado, no una selección: se documenta aquí y el filtro está en
  `scripts/00_descarga_cdse.py`.
- Quedan por tanto **664 productos**. Con la fracción de escenas utilizables esperada
  (30–40 %) son del orden de **200 escenas en diez años, ~100 por estación**, holgadamente
  por encima del mínimo de 20 observaciones por píxel y estación de la sección 7. El
  reparto por año es desigual —19 en 2016 y 31 en 2017, porque S2B entró en servicio a
  mitad de 2017, frente a 70–88 de 2018 en adelante—, lo que se tiene en cuenta al exigir
  detecciones en 5 años distintos (sección 10).
- Dentro de esa órbita se descargan **todos** los productos del periodo. El descarte por
  nubosidad se hace con el criterio de la sección 6, calculado sobre la bahía, **no** con
  el campo de nubosidad del metadato, que se refiere al tile entero de 110 km y no dice
  nada útil sobre 5 km² de agua.

---

## 3. Corrección atmosférica — FIJADA

**ACOLITE, dark spectrum fitting (DSF).** Se fija aquí y no se cambia.

Motivo: en un cuerpo de agua pequeño rodeado de tierra, DSF estima la contribución
atmosférica a partir de los píxeles más oscuros del propio recorte y por bandas,
lo que tolera mejor la contaminación por adyacencia que un esquema de tabla fija como
Sen2Cor.

Configuración fijada:
- DSF con estimación **por escena** (no por baldosa), dado que la ventana es de 5 km y
  una estimación por baldosa sobre tan poca superficie es inestable.
- Corrección de sun glint activada.
- Sin corrección de adyacencia interna: el tratamiento de la adyacencia es explícito y
  se hace aguas abajo (sección 11), donde puede medirse y auditarse.
- Resolución de salida **20 m** (`s2_target_res`). El valor por defecto de ACOLITE para
  Sentinel-2 es 10 m.
- **Las banderas de ACOLITE se calculan pero no se aplican** a los productos de agua
  (`l2w_mask_water_parameters=False`). Su máscara por defecto anula el píxel cuando
  ρ(1600 nm) supera 0,0215, lo que eliminaría el agua muy turbia — es decir, el objeto de
  estudio. Las banderas se conservan en `l2_flags` y el enmascarado se aplica aguas abajo,
  donde es auditable (secciones 6 y 9).
- Datos auxiliares (ozono, vapor de agua, presión): ACOLITE no encuentra credenciales de
  EARTHDATA y usa sus valores por defecto (uoz 0,30; uwv 1,50; 1013,25 hPa) en **todas**
  las escenas. Se deja así a propósito: un tratamiento uniforme a lo largo de diez años es
  preferible a tener unas escenas con auxiliares reales y otras con valores por defecto,
  que introduciría un salto artificial en la serie. DSF estima el aerosol por su cuenta, y
  es el término dominante.

**No se procesa ninguna escena hasta que ACOLITE esté instalado.** No se sustituye por
productos L2A (Sen2Cor) ni por una reimplementación propia de DSF, tampoco "solo para el
piloto". Decisión tomada el 15/09/2026.

---

## 4. Productos

**Turbidez y sólidos suspendidos. No clorofila.** En aguas caso-2 dominadas por material
en suspensión, Sentinel-2 mide turbidez con fundamento y clorofila no; y una pluma de
descarga aparece antes en turbidez que en cualquier otra variable.

Se consumen los productos que **ACOLITE calcula directamente**, sin reimplementarlos:
- turbidez (formulación de Dogliotti, de conmutación rojo/NIR),
- turbidez (formulación de Nechad),
- SPM (formulación de Nechad).

La turbidez de Dogliotti es el **producto primario** para la detección. Las otras dos se
conservan como comprobación de robustez: una detección que aparece en un producto y
desaparece en los otros dos es sospechosa y se anota como tal.

Los coeficientes de esos algoritmos son los que trae ACOLITE en sus propias tablas para
las bandas de Sentinel-2. No se transcriben aquí a mano ni se ajustan.

Se conservan además las reflectancias de superficie de todas las bandas, que hacen falta
para el enmascarado de buques y para el diagnóstico de adyacencia.

---

## 5. Máscara de agua y geometría costera

La máscara de agua se deriva **del propio archivo Sentinel-2**, no de una línea de costa
externa:

1. Se calcula NDWI = (B3 − B8) / (B3 + B8) en cada escena válida.
2. Se toma la **mediana temporal** de NDWI sobre todo el archivo.
3. Agua = mediana de NDWI > 0. El umbral 0 es la convención estándar para NDWI, no un
   valor ajustado.
4. Se retiene la componente conexa que contiene el centro de la bahía, más la que
   contiene la referencia de mar abierto.

Ventajas: una máscara estable en el tiempo (no fluctúa escena a escena y por tanto no
introduce varianza espuria en la climatología), y una línea de costa definida en la misma
rejilla y proyección que los datos, sin errores de registro.

A partir de la máscara se calculan y se guardan, de una vez y para siempre:
- **d**, distancia euclídea de cada píxel de agua a la costa, en metros;
- **f_tierra(r)**, fracción de tierra dentro de un disco de radio r centrado en el píxel,
  para r = 100, 250, 500 y 1000 m;
- el acimut de la normal a la costa más cercana.

Estos tres campos son la base del tratamiento de adyacencia.

---

## 6. Control de calidad de escena

Una escena entra en el análisis si y solo si:
- al menos el **60 %** de los píxeles de agua de la ventana son válidos (sin nube, sin
  sombra de nube, sin saturación, con recuperación atmosférica convergida);
- ACOLITE converge en la estimación DSF.

Píxel válido individual: no marcado por las banderas de ACOLITE y con reflectancia de
superficie no negativa en la banda roja.

Expectativa previa, no criterio: con la nubosidad tropical se espera que sirva un 30–40 %
del archivo, del orden de 150–250 escenas en diez años. Si la cifra real se aparta mucho
de eso, se reporta, no se reajusta el umbral.

---

## 7. Climatología por píxel

Para cada píxel de agua y cada estación por separado:

- **Estaciones:** seca = noviembre a abril; lluviosa = mayo a octubre. Es la división
  climática convencional para Cuba occidental, fijada aquí sin mirar los datos.
- **Centro:** mediana de la turbidez en ese píxel y esa estación a lo largo de los diez
  años.
- **Dispersión:** MAD (desviación absoluta mediana), escalada por **1,4826** para que sea
  comparable a una desviación típica bajo normalidad.
- **Mínimo de observaciones:** un píxel se evalúa en una estación solo si tiene
  **≥ 20 observaciones válidas** en esa estación. Por debajo de eso el píxel queda
  marcado como *no evaluado* y no puede generar detecciones. No se rellena ni se
  interpola.
- Si el MAD escalado de un píxel es cero (serie degenerada), el píxel queda *no evaluado*.

**Esta línea base se calcula y se congela sobre el archivo completo antes de calcular
ninguna anomalía.** Es la regla de higiene central del trabajo: el umbral no puede haberse
elegido viendo el resultado porque la base contra la que se compara existe antes de que
exista ninguna comparación.

---

## 8. Definición de anomalía

Dos familias, y se exige la **conjunción de ambas**.

**Anomalía temporal** — el píxel muy por encima de su propia historia:

    z_t = (T − mediana_estacional) / (1,4826 · MAD_estacional)

Detección temporal si **z_t ≥ 3,5**.

**Anomalía espacial** — el píxel muy por encima de la bahía ese mismo día:

    z_s = (T − mediana_bahía_del_día) / (1,4826 · MAD_bahía_del_día)

calculadas mediana y MAD sobre todos los píxeles de agua válidos de la bahía en esa
escena. Detección espacial si **z_s ≥ 3,0**.

**Un píxel se marca como anómalo solo si cumple las dos condiciones a la vez.**

La conjunción no es un filtro de plausibilidad: es el control específico contra el
artefacto dominante. Un residuo de corrección atmosférica o un episodio de carga de
aerosoles levanta la bahía entera y por tanto se cancela en z_s. Una pluma real es local
y sobrevive a las dos. Los valores 3,5 y 3,0 son convenciones de detección robusta
(equivalentes gaussianos), no valores ajustados; el 3,0 en la espacial es más laxo porque
la distribución espacial diaria tiene menos grados de libertad efectivos que una serie de
diez años.

**Solo se consideran excesos positivos.** Una turbidez anómalamente baja no es un vertido.

### 8.1 Tercera familia: fuente PERMANENTE

Las dos familias anteriores comparan cada píxel **contra su propia historia**. Una fuente
que descarga de forma continua está dentro de esa historia: la mediana de diez años ya
incluye la descarga, z_t sale ≈ 0 y la conjunción la descarta. Es decir, el diseño
temporal + espacial detecta vertidos **intermitentes** y es **ciego a los permanentes**,
que son precisamente los que más importan a una autoridad ambiental.

Se añade por tanto una tercera familia, independiente de las dos anteriores:

    z_c = (mediana_clim(píxel) − mediana_clim(banda)) / (1,4826 · MAD_clim(banda))

donde la *banda* son los píxeles a la **misma distancia de costa** (anillos de 20 m) y con
**fracción de tierra parecida** (tolerancia 0,10 en `f_tierra(500 m)`). Detección si
**z_c ≥ 3,5**, con grupo mínimo de 4 píxeles.

La estratificación por distancia y fracción de tierra es a la vez el detector y el control
de adyacencia: si la elevación fuese adyacencia, los píxeles de su misma banda geométrica
la tendrían también y z_c se anularía. Un candidato permanente se reporta **por separado**
de los intermitentes, porque su evidencia es de naturaleza distinta y su verificación en
tierra también.

---

## 9. Máscara de buques

Los buques y sus estelas son brillantes y transitorios. El filtro de persistencia elimina
los que se mueven, pero **no elimina los atracaderos**: un muelle con barco presente en
una fracción alta de las escenas produce una anomalía recurrente en una posición fija,
justo en la orilla, indistinguible por persistencia de un emisario. Es un falso positivo
de primer orden en un puerto en activo y se trata explícitamente.

1. **Test SWIR:** sobre agua, la reflectancia en B11 y B12 es esencialmente nula. Un
   píxel de agua con reflectancia de superficie elevada en SWIR es una superficie emergida
   o una embarcación, no agua turbia. Esos píxeles se enmascaran antes de todo lo demás.
2. **Dilatación:** la máscara de buques se dilata 2 píxeles (40 m) para capturar estela y
   contaminación de píxeles mixtos.
3. **Anotación de atracaderos:** todo sitio candidato cuya posición coincida con
   infraestructura portuaria (muelles, dársenas) se marca como *candidato de atracadero*
   y se reporta por separado del resto. No se elimina en silencio: se reporta y se
   traslada a la campaña de verificación en tierra, que es quien puede distinguirlo.

El test SWIR se aplica sobre el **residuo** de ρ_SWIR una vez restado el perfil de
adyacencia ajustado en esa escena (sección 11.2), nunca sobre la reflectancia bruta: cerca
de la orilla la adyacencia eleva la SWIR del agua legítima, y un umbral absoluto sacado de
mar abierto enmascararía justo la franja costera que interesa. El umbral sobre el residuo
es mediana + 6 · MAD escalada, calculado sobre el agua de cada escena; es robusto porque
los píxeles de buque son pocos y no arrastran la mediana.

---

## 10. Persistencia y ranking

- Los píxeles anómalos de una escena se agrupan en componentes conexas (conectividad 8).
- **Tamaño mínimo de grupo: 4 píxeles a 20 m (1600 m²).** Descarta ruido de píxel único y
  embarcaciones pequeñas.
- Cada grupo se localiza por el **píxel de z_t máxima**, no por su centroide. Una pluma
  advectada por marea y viento cambia de orientación entre escenas y su centro de masa
  baila, repartiendo las detecciones de un mismo emisario entre celdas vecinas hasta que
  ninguna alcanza el umbral; el máximo se queda quieto y es, además, donde está la fuente.
- Los picos de todas las escenas se agregan sobre una rejilla de sitios de 40 m, con
  fusión de celdas dentro de un radio de 2 celdas (80 m, la incertidumbre de localización
  del pico) y supresión de no-máximos, de modo que un emisario es un sitio y no un cúmulo
  de celdas vecinas.
- **Cada escena aporta como mucho una detección por sitio**, para que la persistencia sea
  una fracción de ocasiones y no un conteo inflado por el tamaño de la pluma.
- Para cada sitio: **persistencia = número de escenas con detección / número de escenas
  válidas en las que ese sitio era evaluable.** Es una fracción, no un conteo bruto, para
  que un sitio con menos observaciones válidas no quede penalizado.

Un sitio se declara **fuente recurrente** si:
- persistencia ≥ **0,10**, y
- presenta detecciones en **≥ 5 años distintos** de los diez.

El segundo criterio es el que separa un vertido de un episodio: algo que persiste media
década es estructural. El ranking que se entrega a la autoridad ambiental se ordena por
persistencia, e informa siempre el número de observaciones válidas en las que se basa.

---

## 11. Tratamiento de la adyacencia — el riesgo serio

En una bahía estrecha los píxeles cercanos a la orilla reciben fotones dispersados desde
la tierra circundante, mucho más brillante que el agua. Y la orilla es exactamente donde
están las descargas. Un margen fijo desde costa resuelve el artefacto eliminando el
objeto de estudio. Por eso aquí la adyacencia no se evita: se mide, y se somete a
controles preespecificados.

### 11.1 El argumento de fondo

La adyacencia depende de la radiancia de la tierra circundante y de la geometría, que en
una bahía fija son **esencialmente estáticas en el tiempo**. El método está construido
sobre la anomalía de cada píxel **contra su propia historia**. Por tanto el término de
adyacencia está dentro de la línea base de ese píxel: la mediana lo absorbe y el MAD
absorbe su variabilidad.

La consecuencia honesta de esto no es que la adyacencia sea inocua, es que **cuesta
sensibilidad cerca de la orilla en vez de fabricar detecciones**: al inflar el MAD de los
píxeles costeros sube el umbral efectivo justo donde más falta hace. El trabajo debe
reportar esa pérdida de sensibilidad, no esconderla.

Para que la adyacencia fabricase una fuente recurrente falsa tendría que ser a la vez
elevada y anómala respecto a su propia historia, repetidamente y en el mismo sitio. Las
vías por las que eso puede ocurrir son conocidas y se controlan una por una.

### 11.2 Medición empírica del decaimiento

Sobre agua limpia y tras corrección atmosférica, la reflectancia en SWIR debe ser ~0.
Cualquier elevación sistemática en SWIR que decaiga con la distancia a costa es
adyacencia (más residuo de corrección). Para cada escena se ajusta

    ρ_SWIR(d) = A · exp(−d / L) + c

sobre la mediana de ρ_SWIR por anillos de distancia. Se obtienen por escena una amplitud
**A** y una longitud de decaimiento **L**. Se reportan sus distribuciones sobre el
archivo. Esto convierte la adyacencia de supuesto en cantidad medida, y es la primera
figura que va a pedir un revisor.

### 11.3 Controles preespecificados

**a. Barrido de margen en vez de margen fijo.** Todo el análisis se repite con márgenes
desde costa de **0, 20, 40, 60 y 100 m**. La persistencia de cada sitio en función del
margen se reporta como resultado. Una fuente real sobrevive al aumento del margen,
desplazándose hacia fuera a lo largo del eje de la pluma; un artefacto de orilla
desaparece. La sensibilidad al margen deja de ser una elección de parámetro y pasa a ser
un dato.

**b. Controles emparejados (test de falsación principal).** Para cada sitio candidato se
seleccionan segmentos de costa **sin descarga conocida** con la misma distancia a costa y
la misma fracción de tierra `f_tierra(500 m)`, dentro de una tolerancia fijada. Si el
método estuviese midiendo adyacencia, los controles emparejados se encenderían igual que
los candidatos. Que los candidatos se enciendan y los controles no es la prueba de que la
adyacencia no es el motor del resultado. **El emparejamiento se construye a partir de la
geometría, que es conocida antes de ver ninguna anomalía.**

**c. Test de covariable atmosférica.** Para cada sitio candidato se contrasta la serie de
z_t contra el espesor óptico de aerosoles estimado por DSF en cada escena. Una correlación
significativa señala residuo atmosférico o adyacencia modulada por aerosoles, no una
descarga. Los sitios que la presenten se marcan.

**d. Test de anisotropía.** La adyacencia es aproximadamente isótropa respecto a la costa
y máxima en la perpendicular. Una pluma de descarga tiene fuente puntual y es anisótropa,
advectada por marea y viento. Para cada sitio se calcula la razón entre extensión
paralela y perpendicular a la costa, y la correlación de la amplitud de la anomalía con
`f_tierra(500 m)`. Un sitio cuya amplitud escale con la fracción de tierra es adyacencia.

**e. Referencia de mar abierto.** La franja de mar abierto al norte de la bocana, incluida
en la ventana a propósito, es agua sin descargas y con adyacencia decreciente. Sirve de
control negativo global del procesado entero.

### 11.4 Qué se reporta pase lo que pase

La distribución de L y A por escena; los mapas de persistencia a los cinco márgenes; el
resultado del emparejamiento candidato/control; y la fracción de la superficie costera
que queda *no evaluada* por MAD inflado o por observaciones insuficientes. Ese último
número es el coste real del problema de adyacencia y va en el artículo.

---

## 12. Criterios de falsación

El método se declara fracasado, y así se escribe, si ocurre cualquiera de estas:

1. Los controles emparejados presentan persistencia estadísticamente indistinguible de la
   de los sitios candidatos.
2. Ningún sitio candidato sobrevive al margen de 40 m.
3. La persistencia de los sitios candidatos se explica por la covariable de aerosoles.
4. La fracción de superficie costera *no evaluada* supera el 50 %, en cuyo caso el método
   no tiene alcance sobre la zona que pretende vigilar.

---

## 13. Lo que este documento NO decide

Queda explícitamente pendiente, y se fijará **antes** de mirar anomalías y documentado
aquí:

- El umbral del test SWIR de buques (sección 9), que se fijará sobre la distribución de la
  referencia de mar abierto.
- La tolerancia de emparejamiento candidato/control (sección 11.3b).
- El tiempo de renovación por prisma mareal: es aritmética y depende de batimetría y rango
  mareal aún no confirmados con fuente. Entra en el trabajo como contexto interpretativo,
  **nunca** como criterio de detección, para que no pueda contaminar el análisis.

---

## 14. Registro de cambios

| Fecha | Cambio | Motivo | ¿Después de ver anomalías? |
|---|---|---|---|
| 2026-09-15 | Versión 1.0 inicial | Preregistro del método | No — cero escenas procesadas |
| 2026-09-15 | Añadida familia de anomalía climatológica (sección 8.1) | La conjunción temporal+espacial es ciega a una fuente permanente, que queda dentro de su propia línea base. Detectado al validar la cadena sobre una bahía sintética | No — cero escenas reales procesadas |
| 2026-09-15 | Test SWIR sobre residuo de adyacencia en vez de reflectancia bruta (sección 9) | Un umbral absoluto de mar abierto enmascaraba la franja costera legítima | No — cero escenas reales procesadas |
| 2026-09-15 | Localización de grupos por pico de z_t en vez de centroide, con fusión y supresión de no-máximos (sección 10) | El centroide de una pluma de orientación variable reparte las detecciones de un mismo emisario entre celdas vecinas. Verificado sobre bahía sintética: con centroide, 0 sitios recurrentes; con pico, 1 y correcto | No — cero escenas reales procesadas |

| 2026-09-16 | Solo órbita R097; salida a 20 m; banderas de ACOLITE sin aplicar | Verificado sobre las 10 escenas del piloto: R054 da 100 % blackfill; 10 m no casa con la rejilla del protocolo; la máscara SWIR de ACOLITE borraría las plumas | No — ninguna anomalía calculada todavía |

## 15. Validación previa del método

Antes de disponer de ningún dato real, la cadena completa se validó sobre una **bahía
sintética** con cuatro elementos plantados en posiciones conocidas: una fuente
intermitente (35 % de las escenas), una fuente permanente, un artefacto de adyacencia que
decae con la distancia y varía entre escenas, y buques (transitorios más uno atracado
fijo). 220 escenas sobre diez años.

Resultado (`tests/test_cadena.py`, figura en `resultados/validacion_sintetica.png`):

| Comprobación | Resultado |
|---|---|
| Fuente intermitente recuperada | **Sí** — único sitio recurrente de toda la bahía, persistencia 0,27, detecciones en los 10 años |
| Fuente permanente ciega para z_t | **Confirmado** — z_t medio 0,08 |
| Fuente permanente recuperada por la familia climatológica | **Sí** — z_c = 19,2 |
| Sitios recurrentes falsos generados por adyacencia | **Cero** |
| Longitud de decaimiento de adyacencia recuperada | 119 m ajustada frente a 120 m plantada, r² = 0,999 |
| Controles emparejados frente al candidato | 0,000 frente a 0,27, con 274 píxeles comparables |
| Buque atracado (falso positivo duro) | Enmascarado, no llega al ranking |

Esta validación **no sustituye** al piloto sobre datos reales: demuestra que la cadena
hace lo que dice cuando la verdad es conocida, no que la bahía real contenga nada.
