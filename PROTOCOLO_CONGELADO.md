# Protocolo congelado — detección de puntos de vertido recurrentes en la Bahía de La Habana

**Versión 1.0 — 15 de septiembre de 2026** · Versión 2.0 (segunda fase, sección 20) — 17 de octubre de 2026

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
estrecho, con tres ensenadas interiores (Marimelena al este, Guasabacoa al sur y Atarés al
suroeste; nomenclatura corregida el 21/10/2026, sección 14).

**Tile Sentinel-2:** `T17QLF` (UTM zona 17N, banda MGRS Q). La bahía completa, incluido
el canal de entrada y una franja de mar abierto frente a la bocana, cae dentro de este
único tile. No se mosaica nada. Los siete puntos de control usados para comprobarlo
(bocana, centro, dos en Marimelena, uno en la cabecera de Guasabacoa y las dos esquinas
del bbox) caen todos en `17QLF`,
holgadamente en el interior del cuadrado de 100 km, no en su borde.

**Bahía (EPSG:32617, UTM 17N / WGS84)** — era la ventana de trabajo de la versión 1.0; desde
el 13/10/2026 es la zona sobre la que se calculan el criterio de escena (sección 6) y las
estadísticas «de la bahía» del día (z_s, sección 8):

| | mínimo | máximo | extensión |
|---|---|---|---|
| Este (m) | 361 139 | 365 896 | 4,76 km |
| Norte (m) | 2 556 342 | 2 561 392 | 5,05 km |

A 20 m son 238 × 253 píxeles; a 10 m, 476 × 505.

**Ventana de procesado (ampliada el 16/09/2026, sección 14):** 23,10–23,21 N,
82,40–82,28 W; en UTM 17N, E 356 620–369 040 y N 2 555 160–2 567 440 (12,4 × 12,3 km),
614 × 621 píxeles a 20 m. Contiene la bahía y 6,7 km de mar abierto, que son la
referencia de agua limpia y el campo lejano para medir la adyacencia (sección 11). Es la
rejilla de todas las escenas exportadas; la máscara de agua, la distancia a costa y la
climatología se calculan sobre ella entera.

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
- al menos el **60 %** de los píxeles de agua **de la bahía** (sección 1) son válidos (sin nube, sin
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
desde costa de **0, 20, 40, 60, 100, 200 y 400 m**. El rango se amplió el 16/09/2026: el
piloto midió longitudes de decaimiento de hasta 386 m, así que un barrido que se detenía
en 100 m no habría llegado a cubrir el artefacto que pretende acotar. La persistencia de cada sitio en función del
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
| 2026-09-16 | Ventana ampliada de 5,5 × 5,1 km a 12,2 × 12,3 km | La ventana ceñida a la bahía no dejaba dentro mar abierto (el control negativo de la sección 11.3e) y limitaba la distancia a costa a 588 m, sin campo lejano: el ajuste de ρ_SWIR(d) medía la caída de píxel mixto de la orilla (L ≈ 17–21 m) y no la adyacencia atmosférica, que es de cientos de metros | No — ninguna anomalía calculada |
| 2026-09-16 | Control de calidad por píxel con B12 (~2200 nm), umbral 0,010 | 8 de 13 escenas del piloto tenían ρ_SWIR mediana de 0,05–0,11 sobre agua, es decir corrección atmosférica no convergida, y daban turbidez de 350–490 FNU. B12 separa agua turbia de atmósfera sucia porque a 2200 nm el agua absorbe por completo y ρ_w ≈ 0 sea cual sea la carga de sedimento; la bruma, gris, sí eleva la señal. El umbral es físico, no ajustado a los datos | No — ninguna anomalía calculada |
| 2026-09-16 | El veredicto del piloto puede declararse NO CONCLUYENTE | La primera versión dictaminó «seguir» sobre turbideces de −1614 FNU, físicamente imposibles, porque su criterio no comprobaba el rango. Un criterio de decisión que no puede abstenerse no es un criterio | No — ninguna anomalía calculada |
| 2026-09-16 | Barrido de márgenes ampliado de 0–100 m a 0–400 m | El piloto midió L de hasta 386 m; un barrido hasta 100 m no cubre el artefacto | No — ninguna anomalía calculada |
| 2026-09-16 | El veredicto exige ≥20 observaciones por píxel antes de pronunciarse sobre estructuras | Con 4 observaciones z_c es ruido, y el síntoma es que el 64 % de las estructuras caían a más de 500 m de la costa | No — ninguna anomalía calculada |
| 2026-09-27 | Hallazgo, sin cambio de método todavía: en 26 fechas el catálogo R097 trae 2 o 3 productos L1C del mismo paso (tile partido entre datastrips), de modo que los 664 productos son **637 adquisiciones**. El bucle por tandas (`scripts/04_archivo_por_tandas.py`) procesa y exporta **todos**, cada uno a su `.npz`, que guarda el nombre del L1C de origen (`producto_l1c`). La regla para combinar los trozos de una misma fecha se fijará y se registrará aquí **antes de calcular la climatología** | El crudo se borra al exportar: descartar un trozo dentro del bucle sería perder datos sin haberlo decidido. Comprobado en 2016-01-15: el trozo de 34 MB da «100 % blackfill» y la bahía cae en el de 728 MB | No — ninguna anomalía calculada |
| 2026-10-13 | Fechas con varios productos L1C: se usa **un solo producto por fecha**, el que tenga más píxeles dentro de su huella dentro de la ventana (bit 4 de `l2_flags`, «fuera de escena», sin activar); a igualdad, el de procesado más reciente. Criterio solo geométrico: no mira nubes, calidad ni turbidez. Resuelve el hallazgo del 27/09: de las 26 fechas partidas, solo 7 tienen dos escenas exportadas | Cada trozo lleva su propia corrección DSF (su propio AOT). Un mosaico juntaría dos radiometrías en la misma escena: una costura que la anomalía espacial del día (z_s) podría tomar por estructura, y dos AOT para el test de covariable (11.3c). Contar los dos trozos duplicaría una misma observación. La pérdida es parte de la ventana en 7 de 637 fechas | No — ninguna anomalía calculada. Se sabía: el archivo tiene 644 escenas de 637 fechas, y qué 7 fechas tienen dos escenas. No se miró el contenido de esas escenas |
| 2026-10-13 | El umbral de escena (sección 6) **sigue siendo el 60 %**, pero se cuenta sobre el agua **de la bahía** (la ventana de la versión 1.0, sección 1), no sobre toda la ventana de procesado. La misma zona es la «bahía» sobre la que se calculan mediana y MAD del día para z_s (sección 8). Se descarta el 40 % usado en el piloto | El 60 % se escribió cuando la ventana era la bahía. Con la ventana ampliada (16/09), la mayor parte del agua es mar abierto y el criterio mediría sobre todo el mar: rechazaría días con la bahía despejada y aceptaría días con la bahía cubierta. Así se mantiene el número preregistrado y se recupera la zona para la que se escribió, que es además la «bahía» de z_s (sección 8). El 40 % salió del piloto, después de ver datos | No — ninguna anomalía calculada. Se sabía: en el piloto pasaron 5 de 13 escenas con el 40 % sobre la ventana ampliada. **No** se calculó cuántas escenas del archivo pasan con cada opción antes de decidir |
| 2026-10-13 | Detalles de implementación de la máscara, el control de calidad y la climatología, que el texto no fijaba, decididos **antes de calcularla** (`src/escenas.py`, `scripts/05_climatologia.py`): (a) el NDWI de la máscara (secc. 5) usa en cada escena los píxeles sin bits 1, 2 ni 4 de `l2_flags` (cirros, TOA alto, fuera de escena): «escena válida» se aplica por píxel porque la validez de escena (secc. 6) necesita la propia máscara; (b) semillas de las componentes conexas: el punto «centro» de `geo.PUNTOS_CONTROL` (23,133 N, 82,333 O) y mar abierto en 23,200 N, 82,333 O; si alguna no cae en agua el cálculo se detiene, no se ajusta a mano; (c) píxel válido (secc. 6): agua, turbidez finita, bits 1–4 sin activar (el 3, ρ negativa en 400–900 nm, cubre la condición de rojo no negativo), ρ(2200) ≤ 0,010 y fuera de la máscara de buques; (d) la máscara de buques es la de la secc. 9 tal como quedó el 15/09 (residuo del perfil de adyacencia ajustado hasta 600 m, umbral mediana + 6·MAD por escena, dilatación 2 px), y se aplica antes de la climatología; la secc. 13 aún lo da por pendiente, pero lo fija la 9; (e) «DSF convergido» = AOT de la escena finito; (f) no se filtra la turbidez por rango, porque el protocolo no lo prevé: se informa cuántos píxeles válidos quedan fuera de 0–1000 FNU; (g) estación por el mes de la fecha de adquisición (UTC) | Sin estas concreciones la climatología no es reproducible, y fijarlas después de verla sería elegirlas mirando el resultado | No — ninguna anomalía ni climatología calculada. Para comprobar el formato de los datos se miró en 26 escenas (una de cada 25) la frecuencia de cada bit de `l2_flags` y de ρ(2200) > 0,010: muchas escenas tienen bruma en casi toda la ventana, como ya vio el piloto. No cambió ninguna regla |
| 2026-10-13 | Controles y pruebas de falsación, fijados **antes de calcular anomalías**: (a) emparejamiento (11.3b, pendiente en la secc. 13): misma distancia a costa ±20 m, `f_tierra(500 m)` ±0,05, a más de 200 m del candidato y de cualquier otro candidato; se usan **todos** los píxeles que cumplan (el código tomaba 5 al azar); la persistencia de un control es la de su celda de 40 m; (b) un candidato se distingue de sus controles si p = (1 + controles con persistencia ≥ la suya) / (1 + nº de controles) < 0,05; sin controles = no distinguible; el criterio 12.1 se cumple (método fracasado) si se distinguen **menos de la mitad** de los candidatos; (c) barrido de márgenes 0, 20, 40, 60, 100, 200 y 400 m (el código se quedaba en 100); un candidato sobrevive al margen m si a ese margen hay un sitio recurrente a menos de 80 m + m de él (80 m es la incertidumbre de localización del pico, secc. 10); (d) covariable de aerosoles (11.3c): correlación de Pearson entre el máximo de z_t a menos de 80 m del sitio y el AOT, sobre las escenas aceptadas; se marca el sitio si r > 0 con p < 0,05; el criterio 12.3 se cumple si se marca más de la mitad de los candidatos; (e) criterio 12.4: superficie costera = agua de la ventana a ≤ 400 m de costa; no evaluada = no evaluable en la climatología de la estación; se cumple si pasa del 50 % en cualquiera de las dos; (f) z_s usa la mediana y la MAD de los píxeles válidos **de la bahía**, y la detección se evalúa en toda el agua de la ventana: lo que salga en mar abierto es el control negativo de 11.3e; (g) candidato = sitio recurrente con margen 0 | La secc. 12 da los criterios de fracaso pero no cómo se decide cada uno; sin fijarlo antes, «indistinguible» o «se explica por» se podrían interpretar después de ver los sitios. Los umbrales son convenciones (p < 0,05, mayoría simple) o salen del propio protocolo (20 m de anillo, 80 m de localización, 400 m de margen máximo) | No — ninguna anomalía calculada. La climatología (secc. 17) sí estaba calculada |
| 2026-10-13 | **Análisis exploratorios**, declarados todos antes de ejecutar ninguno (`scripts/07_exploratorio.py`): E1, mapa de la frecuencia de detección por píxel (detecciones / ocasiones evaluables), sin agrupar ni umbral de persistencia; E2, tabla del número de sitios recurrentes con persistencia mínima 0,05 / 0,075 / 0,10, años mínimos 3 / 4 / 5 y los siete márgenes, dentro y fuera de la bahía; E3, familia climatológica (8.1) recalculada con bandas formadas solo por agua de la bahía; E4, supresión de no-máximos con desempate (gana la celda con más detecciones), solo para lo exploratorio: la función conserva por defecto el comportamiento preregistrado | Entender por qué el método no pasa el criterio 12.2 y si hay señal dentro de la bahía que el diseño no capta. E3 corrige la mezcla de bahía y mar abierto en las bandas de distancia; E4, el duplicado de sitio. **Nada de esto cambia el veredicto de la sección 18**, y en el artículo se presenta como exploratorio | **Sí** — después de ver la detección (secc. 18) |
| 2026-10-17 | **Versión 2.0 (sección 20)**: repetición a 10 m de las 186 fechas con ≥ 40 % de la bahía válida a 20 m, mismos umbrales con conversión píxel→metros, desempate y z_c con bandas de la bahía en el análisis principal, umbrales laxos de E2 como secundario preregistrado; test de lluvia (ERA5, P72, Spearman frente a controles); verificación de campo a ciegas con 5 sitios y 5 controles; mapa de turbidez crónica | Responder si el fracaso a 20 m es de resolución o de atmósfera, y verificar los sitios con datos independientes del satélite, en un solo artículo | **Sí** — después de ver las secciones 18 y 19. Ninguna anomalía a 10 m, ningún dato de lluvia ni de campo. Para fijar el 40 % se contó cuántas fechas pasan cada umbral a 20 m (113 / 153 / 186 / 231 con 60 / 50 / 40 / 30 %), y para la turbidez se contó la fracción de agua válida de la bahía sobre 16,4 FNU a 20 m |
| 2026-10-17 | **Puntos de campo calculados** (20.5), con `scripts/08_controles_campo.py` y `scripts/09_fuentes_osm.py`; salida en `resultados/campo/` (`clave.csv`, `puntos.csv` para la persona de campo, `reservas.csv`, `campo.json`, `fuentes_osm.csv`, `osm_overpass.json`). Detalles que 20.5 no fijaba: (a) cada sitio se sitúa en el píxel de agua más cercano a su coordenada (a 1–21 m); (b) la mediana de E1 se toma sobre los píxeles de su zona con frecuencia definida (≥ 20 ocasiones): 0,010 en la bahía, 0 fuera; (c) los grupos E3 de las dos estaciones se excluyen con su extensión completa (243 px), no solo su pico; (d) un control no puede repetir el píxel de otro; (e) sorteo en el orden S1–S5 y después barajado de los diez puntos, todo con la semilla 20261013; (f) la revisión OSM consulta `waterway` = river/stream/canal/drain/ditch/outfall y `man_made` = outfall/pipeline en 23,09–23,22 N, 82,41–82,26 O (instantánea 2026-10-17T18:14:50Z) y mide la distancia a la geometría completa de cada elemento. Resultado OSM: solo S5 tiene una fuente conocida a ≤ 150 m (río Luyanó, 118 m); S3 queda a 329 m del Martín Pérez; ningún control tiene fuente a ≤ 150 m. Falta la cartografía publicada. Advertencia: los tres controles de la bahía caen en su mitad norte, porque la frecuencia E1 alta está en la sur; la persona de campo podría intuir los roles por la geografía, y las coordenadas de los sitios ya son públicas en 20.5. El ciego depende de no darle ni el repositorio ni este documento. El criterio principal (hay estructura o no) es objetivo Corregido el mismo día, antes de entregar nada: `puntos.csv` daba 5 decimales y los sitios, escritos con 4, salían con un cero final que los delataba; ahora todos van con 4 (~11 m). Hoja de campo imprimible y GPX con `scripts/10_hoja_campo.py`, que solo lee `puntos.csv` | Fijar la clave antes de la primera visita, como exige 20.5 | **Sí** — usa E1 y E3 tal como dice 20.5. Ningún dato de campo, ni de lluvia, ni a 10 m. Ninguna regla cambió al ver los puntos |
| 2026-10-21 | **Corrección de nomenclatura de las ensenadas**, sin cambio de método: brazo suroeste = Atarés, brazo sur = Guasabacoa (en su cabecera desemboca el Martín Pérez), brazo este = Marimelena. Es la nomenclatura del modelo hidrodinámico (repo `Modelo-hidrodin-mico`), comprobada allí sobre la carta H.O. 307 de 1879, que sitúa el castillo de Atarés junto al brazo suroeste. Su definición en UTM 17N: al sur de N 2 558 800 y al oeste de E 363 300, Atarés si E < 362 350 − 0,25·(2 558 800 − N) y Guasabacoa en el resto; Marimelena, E > 363 600. Cambian: secc. 1 (texto de las ensenadas y de los puntos de control), secc. 19 (E1), `src/geo.py` (claves de `PUNTOS_CONTROL`: «guasabacoa» → «marimelena_sur», «atares» → «guasabacoa»; las coordenadas no cambian y el código solo usa la clave «centro»), `CONTEXTO_COWORK.md` y los nombres de `focos.csv` en `scripts/11_entrega_modelo.py`, que ahora comprueba cada nombre con la definición del modelo. Las filas anteriores de este registro no se tocan. No cambia ningún dato, umbral, máscara ni resultado | La versión 1.0 llamaba Atarés al brazo sur y Guasabacoa al brazo este | No aplica: solo nombres. Comprobado al regenerar la entrega al modelo: solo cambian `focos.csv` y el README |
| 2026-10-26 | **Ficha de campo ampliada** para las visitas que faltan (20.5), sin tocar el criterio de positivo ni la evaluación: (a) «Dónde estoy», la posición del observador copiada del GPS del móvil, más una captura de Google Maps con el punto azul; (b) «Basura que tapa el agua de frente», estimación visual del agua hasta ~50 m de la orilla en cuatro clases: ninguna, poca (< 1 de cada 10 partes), bastante (1–5 de 10) y mucha (> 5 de 10). Se generan también fichas .xlsx por punto con la estructura que ya usaba la persona de campo (`resultados/campo/fichas_excel/`) | (a) En la visita 1 las fotos llegaron primero sin metadatos y, ya originales, el GPS de P05 resultó inutilizable (posiciones a 1,2–2,8 km del punto que saltan 2 km en 26 s, 6 de 17 en el agua). (b) En P05 y P06 hay grandes acumulaciones de basura flotante, que puede subir la reflectancia y leerse como turbidez: se registra como posible factor de confusión, para describirlo, no para decidir | **Sí** — después de ver la visita 1 (P05, P06 y P08). No cambia qué cuenta como positivo ni cómo se evalúa |
| 2026-11-13 | **Código de la fase 2 (20.3)**. La resolución se elige con la variable de entorno `VERTIDOS_PIXEL_M` (20 por defecto, 10 para la fase 2), y de ella salen `s2_target_res` y los parámetros fijados en píxeles, con la conversión de la tabla de 20.2: dilatación de buques, tamaño mínimo de grupo, distancia control–candidato y radio de 80 m. `scripts/06_deteccion.py --v2` activa el desempate, la familia climatológica con bandas de la bahía y del mar por separado y el análisis secundario (persistencia ≥ 0,05 y ≥ 3 años, en `sitios_secundario.csv`, fuera del veredicto). Las 186 fechas están en `resultados/fase2_productos_10m.txt`. La exportación guarda además ρ(665) (`rojo`), y `scripts/13_comprobar_rojo.py` hace la comprobación del rojo sobre las primeras escenas. Comprobado: a 20 m, `deteccion.json`, `sitios.csv`, `exploratorio.json` y `exploratorio.png` salen idénticos byte a byte, y también los ficheros de la entrega al modelo salvo `anomalias.nc`, que lleva la fecha en su historial. `tests/test_resolucion.py` comprueba los parámetros a 10 y 20 m y que las detecciones sintéticas duplicadas a 10 m dan los mismos sitios | Preparar la cadena a 10 m sin tocar la de 20 m | No a 10 m: ningún dato a 10 m. Sí a 20 m (secc. 18 y 19) |
| 2026-11-13 | **Detalles del test de lluvia (20.4)**, fijados en el código antes de ejecutarlo (`scripts/14_lluvia.py`). (a) ERA5 horario bajado de la API de archivo de Open-Meteo (`models=era5`), porque la de Copernicus pide credenciales; con `cell_selection=nearest` da la celda de 23,25 N 82,25 O, la que contiene el centro de la bahía. (b) Cada valor horario es la suma de la hora anterior; P72 es la suma de las 72 horas que terminan en la última hora entera antes de la adquisición. (c) Sitios: los cinco de campo, en el píxel de agua más cercano. (d) Controles: `adyacencia.controles_emparejados`, que excluye 200 m alrededor de los cinco sitios | Hacer reproducible el test | **Sí**, a 20 m: después de ver las secc. 18 y 19. El dato de lluvia es nuevo |
| 2026-11-13 | **Diagnósticos de sitio pendientes** (`scripts/15_diagnosticos_sitios.py`), definidos antes de calcularlos y solo descriptivos. Anisotropía (11.3d): razón de extensión paralela/perpendicular a la costa de los grupos de detección a ≤ 80 m del sitio (mediana sobre escenas), y Spearman entre z_t y `f_tierra(500 m)` sobre esos píxeles; se marca «escala con f_tierra» si ρ > 0 y p < 0,05. Atracaderos (secc. 9): OpenStreetMap `man_made=pier/quay/breakwater`, `waterway=dock` y `seamark:type=berth/mooring` a ≤ 80 m; `landuse=port` aparte. Fuentes publicadas (20.5): `resultados/campo/fuentes_publicadas.md` | Cerrar los pendientes de la secc. 18 | **Sí**, después de ver las secc. 18 y 19 |
| 2026-11-13 | **Prueba a 10 m con dos escenas y comprobación del rojo (paso 4 de 20.7)**, con los dos L1C del piloto que seguían en disco y están en la lista de 186 (2020-01-19 y 2020-11-29), por el bucle normal (`VERTIDOS_PIXEL_M=10`, salida en `datos/productos_10m`). (a) Rojo: el 0,04 % y el 0,01 % del agua válida de la bahía tienen ρ(665) ≥ 0,05, por debajo del 1 %, así que **se queda el «blended»**, como fija 20.2. (b) La rejilla real a 10 m es de **1241 × 1229** píxeles (bordes E 356 620–369 030 y N 2 555 160–2 567 450), no 1242 × 1228 como dice 20.2: ACOLITE alinea el recorte a su propia rejilla. No cambia nada, porque todo se calcula sobre las `x`, `y` de cada escena. (c) Hallazgo, sin cambio de método: el AOT de DSF cambia con la resolución (2020-11-29: 0,0045 a 20 m y 0,028 a 10 m), porque los píxeles más oscuros no son los mismos. La repetición a 10 m cambia también la corrección atmosférica, no solo el tamaño del píxel, y así se dirá. (d) ACOLITE tarda unos 4 min por producto a 10 m y cada `.npz` ocupa 31 MB (unos 5,8 GB para las 186 fechas) | Comprobar la cadena a 10 m de extremo a extremo antes del bucle | No a 10 m: no se calculó ninguna anomalía |
| 2026-11-13 | **Comprobación de robustez entre productos (secc. 4)**, que no se había hecho (`scripts/16_robustez_productos.py`, salida en `resultados/robustez_productos.json`). Para la turbidez y el SPM de Nechad se calcula una climatología propia sobre las mismas 113 escenas y la misma validez por píxel, y se repite la detección. Un candidato preregistrado «aparece» en un producto si en ese producto hay un sitio recurrente a ≤ 80 m. De los focos exploratorios se informan la frecuencia E1 y el z_c (bandas de la bahía) a ≤ 80 m. Autocomprobación superada: con Dogliotti salen la climatología y los sitios congelados. Figuras del artículo en inglés con `scripts/17_figuras_articulo.py` | Cumplir la secc. 4, que el manuscrito prometía | **Sí**, después de ver las secc. 18 y 19 |
| 2026-11-15 | **Registro de la salida de campo del 13/11 (20.5)**. (a) Se visitaron P02, P03, P04, P09 y P10 con la ficha anterior: la ampliación del 26/10 no llegó a usarse, así que no hay «Dónde estoy» ni «basura que tapa el agua» en ninguna ficha. (b) `scripts/12_registro_campo.py` rellena ahora el número de punto con cero (las carpetas nuevas se llaman «Punto 2»); se registra desde un zip de `datos/trabajo de campo/bahia`, que reúne los dos envíos. Las filas de P05, P06 y P08 salen idénticas a las anteriores. (c) Aclaraciones del observador, literales y con sus preguntas, en `resultados/campo/visita2_relato_recibido_2026-11-14.md`: P09 y P10 se visitaron por separado; 45 de sus 52 fotos llevan la misma posición GPS (mala señal), que no sirve para situar al observador; P03 solo se vio desde unos 550 m, tras una cerca, y no se evaluó a ≤ 150 m; P06 fue su visita 1, aunque la ficha dice 2. (d) P01 y P07 no se han visitado por la distancia (Alex, 14/11). (e) Lluvia del 12–13/11: el observador la describe intensa y larga; cuatro modelos de Open-Meteo dan 6–11 mm entre las 12:00 del 12/11 y las 15:00 del 13/11 (hora local). Si la salida cuenta como visita tras ≥ 20 mm se decide con ERA5 cuando esté disponible. Queda por decidir, con la regla de 20.5 y sin mirar resultados, qué se hace con P01, P03 y P07 (no visitado, o sustitución por reserva si es un control). Al preparar este registro se vieron por error las tres primeras líneas de `reservas.csv` (cabecera y dos reservas); no se abrió `clave.csv` | Registrar la visita y lo que falta antes de evaluar | No: no se evaluó nada ni se cruzaron fichas con la clave |
| 2026-11-15 | **Cierre de la verificación de campo sin más visitas (20.5)**, aprobado por Alex el 15/11 antes de cruzar fichas con la clave. (a) **Una sola visita por punto.** P-infraestructura se evalúa con ella («basta observarla una vez»); P-actividad pasa a ser solo descriptivo, porque no hay tres visitas. No se hace la visita tras lluvia. (b) **Evaluable:** un punto con ficha cuya pregunta 1 diga «sí» o «no». «No se puede ver» o sin visita = excluido y se dice. Se toma la respuesta del observador tal cual, también en P08 (tubos vistos de lejos) y P06 (visto a 100–150 m). (c) **Sin sustituciones:** P01 y P07 quedan como no visitados y P03 como no evaluable; `reservas.csv` no se usa. (d) Fisher exacto unilateral sobre P-infraestructura, sitios frente a controles, p < 0,05, como en 20.5, con `scripts/18_evaluar_campo.py`. (e) **Verificación con imagen, exploratoria y adicional (no sustituye al campo):** para los diez puntos, recorte de 400 × 400 m en UTM 17N centrado en el punto, 800 × 800 píxeles, de Esri World Imagery (consultado el 15/11/2026; fecha, sensor y resolución de cada recorte con el servicio `identify`), con un círculo de 150 m. Los recortes se etiquetan A–J con una permutación de semilla 20261115 y los codifica un subagente que solo ve las imágenes, sin coordenadas, repositorio ni clave, con la pregunta: «¿Hay dentro del círculo una estructura que vierta al agua: tubo, colector, alcantarilla, canal o desembocadura de cauce? sí / no / no se puede ver». Se informa el mismo Fisher y la concordancia con el campo en los puntos evaluables. Imagen: WorldView-3 de 27/01/2024 a 0,31 m en la zona probada | Cerrar el artículo sin volver al campo | **En parte.** Se fija antes de abrir `clave.csv`, pero las fichas ya se habían leído y las coordenadas de los sitios son públicas en 20.5, así que el resultado podía deducirse; la regla no se eligió por él: sigue la letra de 20.5 (no visitados y no evaluables fuera, sin otra condición). La imagen es nueva y exploratoria |
| 2026-11-17 | **Dos pruebas exploratorias de robustez de los focos de turbidez crónica**, definidas antes de calcularlas (`scripts/21_replicacion.py`, `scripts/22_clorofila.py`). **(1) Replicación en mitades independientes.** Con las escenas aceptadas de cada resolución (113 a 20 m, 85 a 10 m) se parten por año de adquisición: A = 2016–2020, B = 2021–2025. En cada mitad y estación se calcula la climatología (mediana y MAD) y la z_c como en `--v2` (bandas de la bahía y del mar por separado); un píxel es «caliente» si z_c ≥ 3,5. Como cada mitad tiene unas 20 escenas por estación, se pide n_obs ≥ 10 y no 20 (desviación fijada aquí, antes de ver nada). Para cada dirección (A→B y B→A) se informa la **tasa de replicación**: fracción de los grupos calientes de una mitad (conectados, como en 8.1) que tienen algún píxel caliente de la otra a ≤ 80 m, frente a la **cobertura base**: fracción de los píxeles de agua evaluables en las dos mitades, de la bahía y a ≤ 250 m de la costa, que quedan a ≤ 80 m de un píxel caliente de la otra mitad. Se informa también ρ de Spearman entre las z_c de las dos mitades. Regla de lectura: los focos «se replican» si, en las dos direcciones, la tasa es ≥ 3 veces la cobertura base y ≥ 0,30. Además, z_c máxima a ≤ 80 m de S1–S5 en cada mitad. **(2) Clorofila frente a sedimento.** Con las escenas piloto de las que se conserva el L2R a 20 m (13) y que están aceptadas en `resultados/escenas_qc.csv`, se calcula NDCI = (ρ704 − ρ665) / (ρ704 + ρ665) en los píxeles de agua válidos. Se informa: mediana de NDCI y de turbidez por zona del modelo (secc. 14, 21/10/2026); ρ de Spearman píxel a píxel entre NDCI y turbidez en la bahía, en total y a ≥ 100 m de costa; y NDCI en S1–S5 (mediana a ≤ 80 m) frente a los píxeles de su misma zona y banda de distancia a costa. Un NDCI alto donde la turbidez es alta (ρ > 0,5 y gradiente de zonas igual) indica que la señal de turbidez puede ser clorofila; si no, apunta a material no algal. Solo descriptivo; el NDCI no se calibra con clorofila medida | Responder a las dudas de la investigación bibliográfica del 16/11 (replicación independiente y confusión con clorofila) | **Sí**, después de ver las secc. 21–23: se definen con los resultados a la vista, y se dice así en el artículo |
| 2026-11-17 | **Exportación de `rhos_704` (`borde`)** en `src/acolite_io.py` y `src/exportar.py`, para la prueba de NDCI (fila anterior): el .npz guarda ahora también esa banda. Los productos ya exportados no la tienen. Subconjunto de la prueba: 30 escenas aceptadas a 20 m (`resultados/ndci_productos_20m.txt`), elegidas a intervalos regulares por fecha y sin mirar su contenido, sin las del piloto. Comprobado con un L2W piloto: sale `borde` junto a `rojo` y `tests/test_resolucion.py` pasa | Responder a la duda de clorofila | No: ninguna anomalía se recalcula |
| 2026-11-17 | **Prueba exploratoria 3: ¿los focos coinciden con agua somera?** (`scripts/23_batimetria.py`), definida antes de calcularla. Profundidad: la malla del modelo SCHISM (`Modelo-hidrodin-mico/datos/malla/hgrid.gr3`, UTM 17N), interpolada linealmente a la rejilla de Sentinel-2 en los píxeles de la bahía que caen dentro de la malla; viene de las cartas de 1879–1889, así que es una pista y no la profundidad actual (dragados, relleno). Focos: píxeles con z_c ≥ 3,5 de la climatología completa de cada estación (bandas de la bahía, como `--v2`), a 20 y 10 m. Para cada píxel caliente se toma su rango percentil de profundidad entre los píxeles de referencia de la bahía a la misma distancia a costa (± 20 m) y a más de 80 m de cualquier píxel caliente; 0,5 es «sin relación», < 0,5 es «más somero que su referencia». Se informa la mediana de ese rango, la fracción de píxeles calientes a menos de 2 m (profundidad óptica en agua turbia, donde el fondo puede subir la reflectancia) frente a la de la referencia, y lo mismo en S1–S5 (mediana a ≤ 80 m). Regla de lectura: los focos «no se explican por el fondo somero» si la mediana del rango es ≥ 0,35 y la fracción a < 2 m no supera el doble de la de la referencia | Responder a la alternativa de fondo somero (investigación del 16/11) | **Sí**, después de ver las secc. 21–24 |
| 2026-11-17 | **Cálculos pedidos por el chat del artículo** (`docs/PETICION_CHAT_TECNICO.md` del repo del artículo), todos EXPLORATORIOS y definidos después de ver las secc. 21–26, antes de calcularlos. **(1) `scripts/24_gradiente.py`**: para cada escena aceptada (20 m: 113; 10 m: 85) se toma la mediana de la turbidez de Dogliotti en cada zona del modelo (definición de la secc. 14, 21/10; con y sin los píxeles a < 100 m de costa) y por estación (seca/lluviosa); el estadístico es la mediana entre escenas de esas medianas, con IC 95 % por bootstrap de ESCENAS (2000 remuestreos, semilla fija), N de escenas y de píxeles. Se compara con la mediana de la climatología por píxel de la secc. 23. Dejar un año fuera cada vez; se informa si se mantiene el orden min(Atarés, Guasabacoa) > max(Marimelena, centro y canal) > mar. **(2) `scripts/25_umbrales.py`**: umbrales z_c ≥ 2,5; 3,0; 3,5 (el fijado); 4,0; 5,0 a 20 y 10 m, climatología completa por estación (grupos calientes como la secc. 24) y mitades A/B como en `21_replicacion.py` (misma regla: ≥ 3× la base y ≥ 0,30 en ambos sentidos); por umbral: número de grupos, distancia de S1–S5 al píxel caliente más cercano, tasa de replicación A↔B, rango percentil de profundidad y fracción < 2 m (misma definición de la secc. 25) y, para cada sitio, la probabilidad al azar de quedar a ≤ 80 m de un píxel caliente (fracción de píxeles de su zona y banda de distancia a costa ± 20 m que lo cumplen). **(3) RAdCor**: solo `grep` del clon de ACOLITE (sin ejecutar). **(4) Turbidez in situ**: búsqueda bibliográfica con referencias comprobadas. **(5) `scripts/26_figuras.py`**: panel a (climatología 10 m por estación), b (perfil brazo→mar con bootstrap de escenas), c (focos con replicación y profundidad de la carta de 1887), con los CSV en `productos_publicos/` | Responder a lo que necesita el artículo reformulado (turbidez crónica) | **Sí**, después de ver las secc. 21–26; no se cambia ningún umbral fijado |
| 2026-11-18 | **Segunda ronda de cálculos pedidos por el chat del artículo** (`docs/PETICION_CHAT_TECNICO.md`, ítems 6–9), todos EXPLORATORIOS, definidos antes de calcularlos, sin cambiar ningún umbral. **(9) `scripts/27_aclaraciones.py`**: reconciliar los 13 grupos de la fig. c con la tabla 27.2 (todos los grupos de la rejilla frente a los de la caja y de la bahía, con y sin el tamaño mínimo `MIN_PX_GRUPO`), límites exactos de las cinco zonas del gradiente y exportación de la rejilla de profundidad de la carta de 1887 (20 y 10 m; decidido el 18/11, tras definirla, que va a `datos/no_publicar_carta1887/` y no al depósito). **(6) `scripts/28_fondo.py`, ¿se ve el fondo en los focos?** Reflectancias de superficie (ρ_s) de ACOLITE en verde (B3), rojo (B4) y NIR (B8) —y borde (B5, ~704 nm) en el subconjunto de 30 escenas a 20 m de la secc. 26— tomadas como mediana por píxel de las escenas aceptadas de cada estación y válidas (como en la climatología). 10 m: las 85 escenas aceptadas (las que tengan `rojo`); focos = z_c ≥ 3,5 por estación (secc. 23). Profundidad = carta de 1887 (secc. 25), sin cambios. Referencia = píxeles de la bahía a la misma distancia a costa (± 20 m), a > 80 m de cualquier píxel caliente y con profundidad ± 0,25 m de la del píxel caliente (≥ 30 píxeles; si no, se omite el píxel y se cuenta). **(a) Relación ρ_rojo–profundidad** (Spearman) entre 0,5 y 3 m, por separado para los píxeles calientes y para todos los no calientes de la bahía, y también tras restar a cada ρ_rojo la mediana de su banda de distancia a costa (± 20 m); IC 95 % por bootstrap de bloques de 100 m (2000 remuestreos, semilla fija). Si el fondo se viera, ρ_rojo bajaría al aumentar la profundidad (ρ < 0). **(b) Forma espectral**: razón verde/rojo y NIR/rojo (y borde/rojo a 20 m) de cada píxel caliente frente a la mediana de su referencia emparejada (diferencia de log-razones), mediana sobre los píxeles calientes con profundidad 0,5–2 m y 2–3 m, con IC por bootstrap de bloques. Expectativa fijada antes de ver nada: el fondo claro y somero sube verde más que rojo (razón verde/rojo mayor que la de agua turbia de la misma profundidad); el sedimento en suspensión sube el rojo más que el verde (razón menor). Regla de lectura: la prueba **solo informa** sobre el fondo si la referencia muestra ρ ≤ −0,2 con IC que excluye 0 entre 0,5 y 3 m (si no, o el fondo no se ve en este rango o el error de la carta, σ 0,9 m, lo borra, y se dice que no se puede concluir). Si informa, «el fondo explica los focos» solo si los calientes tienen también ρ ≤ −0,2 y razón verde/rojo ≥ la de la referencia. Precisiones fijadas antes de calcular: mediana por píxel solo con n_obs ≥ 10 (10 m, 85 escenas) o ≥ 5 (subconjunto de 30 escenas a 20 m); solo píxeles con las bandas > 0; focos y referencia dentro de la ventana de la bahía; el criterio de «referencia informativa» se evalúa en las dos variantes (en bruto y tras restar la banda de distancia) y se exige en ambas. Limitaciones que se declaran: los píxeles calientes se eligen por ρ_rojo alto (la turbidez de Dogliotti es una función de ρ_rojo), así que un exceso de ρ_rojo sobre la referencia **no** es resultado (es de construcción) y no se usa como prueba; carta de 1887, no la profundidad actual; sin medida in situ de la reflectancia del fondo. **Añadido el 18/11 tras ver la primera ejecución del ítem 6** (y declarado en la secc. 28.2): variante cruzada, con los focos elegidos en una mitad (A o B) y las reflectancias medidas en la otra, n_obs ≥ 8 por mitad y estación, para quitar el sesgo de selección de las razones espectrales | Responder a lo que necesita el artículo (¿fondo somero o turbidez cronica?) | **Sí**, después de ver las secc. 21–27; no se cambia ningún umbral fijado |
| 2026-11-18 | **Petición del chat del artículo, 2.ª ronda (`docs/PETICION_CHAT_TECNICO_2.md` del repo del artículo, sha256 `fe576fe6fe54db5c…`): sus reglas, copiadas tal cual y antes de calcular nada.** Reglas generales: ▪ **Antes de calcular nada**, añade una fila en la secc. 14 de `PROTOCOLO_CONGELADO.md` con lo de abajo copiado tal cual (umbrales, criterios de éxito y mínimos). No cambies ningún umbral después. ▪ **Bloque A: no descargues ni proceses ninguna escena de 2026 hasta que Alex haya hecho commit de esa fila.** Es la prueba de que las reglas se fijaron antes de ver los datos. Pídeselo y espera. ▪ Scripts nuevos desde el 29 (`29_…py`, `30_…py`…), salidas JSON en `resultados/` (20 m) y `resultados_10m/` (10 m). No toques las salidas existentes. Resultados en una secc. 29 nueva. ▪ Todo se informa, salga bien o mal. Si algo no se puede hacer (falta de datos, error de ACOLITE, modelo de marea no descargable), dilo y para ese ítem; no lo sustituyas por otra cosa sin avisar. ▪ Sin commits tuyos: los hace Alex. ▪ Al final, una tabla resumen (ítem, n, cifra, ruta del JSON, campo) para el chat del artículo. Definiciones comunes (las ya usadas, sin recalcular): ▪ **Focos** de cada estación: los píxeles calientes de la bahía (z_c ≥ 3,5, archivo 2016–2025) de la secc. 24; a 10 m, además y por separado, los 13 grupos de la secc. 28. ▪ **Referencia** de un píxel de foco: píxeles de la bahía a su misma distancia de costa (±20 m) y a > 80 m de cualquier píxel caliente (como en `23_batimetria.py`). ▪ **Contraste por escena d**: para cada píxel de foco válido, turbidez de Dogliotti menos la mediana de sus referencias válidas en esa escena; d = mediana sobre los píxeles de foco. Escena utilizable si tiene ≥ 20 píxeles de foco válidos. ▪ **Placebo**: 500 conjuntos en los que cada píxel de foco se sustituye por un píxel al azar de la bahía no caliente (> 80 m de cualquier caliente) de su misma banda de distancia (±20 m); mismo d. Semilla fija. ▪ Zonas y `orden()`: las de `24_gradiente.py`. **A. Prueba fuera de muestra con 2026 (CONFIRMATORIA)** Datos: todas las adquisiciones L1C T17QLF, órbita R097, desde el 01/01/2026 hasta la fecha del commit de la fila (fecha de corte; lo posterior no se usa). Misma cadena: ACOLITE commit d61c8de con la misma configuración, salida a 20 y 10 m, control de calidad de la secc. 6 sin cambios, estaciones de la secc. 7 (seca nov–abr, lluviosa may–oct). Los focos, referencias y zonas son los de 2016–2025: no se recalculan con 2026. ▪ **A1 focos (principal).** Por resolución, con todas las escenas 2026 aceptadas (focos de la estación de cada escena): proporción de escenas con d > 0 y prueba de signo unilateral. **Éxito** si d > 0 en más de la mitad de las escenas con p < 0,05 **y** la mediana de d supera el percentil 95 de la misma mediana en los 500 placebos. Menos de 8 escenas utilizables → «insuficiente», no fracaso. Informa también por estación y, como referencia (no prueba), el mismo d en las escenas 2016–2025. ▪ **A2 jerarquía seca.** Escenas secas 2026: `orden()` sobre la mediana de las medianas por escena, variantes `todos` y `a100m`, 20 y 10 m. **Éxito** si `cumple` en ≥ 3 de las 4 combinaciones. Menos de 5 escenas secas por resolución → «insuficiente». ▪ **A3 bahía > mar.** En cada estación con ≥ 5 escenas: max(Marimelena, centro) − mar > 0 en las 4 combinaciones. Informa también centro − mar por separado. **B. Profundidad frente a distancia a costa (exploratorio, archivo 2016–2025)** Profundidad: la de `23_batimetria.py` (malla SCHISM, cartas 1879–1889). ▪ **B1.** Píxeles de la bahía por banda de distancia (0–40, 40–80, 80–160, 160–320 m) × clase de profundidad (< 2, 2–5, > 5 m) × estación × resolución: n de píxeles, mediana de la mediana climatológica y mediana de z_c, con IC 95 % por bootstrap de bloques espaciales de 200 × 200 m (2000 remuestreos). ▪ **B2.** Regresión por rangos: z_c ~ rango(profundidad) + rango(distancia) + fracción de tierra a 500 m, por estación y resolución; coeficientes estandarizados con IC 95 % por el mismo bootstrap de bloques; Spearman entre profundidad y distancia. ▪ **B3.** Píxeles a < 60 m de costa con profundidad de carta > 5 m frente a los de < 2 m a la misma distancia: n, zona y distribución de z_c. Nota: la carta es anterior a dragados y rellenos; marca los píxeles en muelles o zonas dragadas si hay información, y si no, dilo. ▪ **B4.** Pregunta: ¿hay en `Modelo-hidrodin-mico` u otro sitio una batimetría posterior a 1889 (además de GEBCO)? Ruta o «no». **C. Adyacencia con RAdCor (exploratorio)** Subconjunto fijado ahora: las 10 escenas secas aceptadas a 20 m con mayor fracción de píxeles válidos de la bahía (empates por fecha), y las mismas fechas a 10 m si están aceptadas. ACOLITE (mismo commit) con RAdCor y el resto de la configuración idéntica; turbidez de Dogliotti. ▪ Por escena: d con DSF y con RAdCor; medianas por zona y `orden()`. ▪ **Regla fijada:** el contraste de los focos «sobrevive» si d_RAdCor > 0 en ≥ 8 de 10 escenas y la mediana de d_RAdCor/d_DSF ≥ 0,5. Si RAdCor no corre o no converge, informa por qué; no lo ajustes. **D. Marea y viento a la hora de paso (exploratorio)** ▪ **D1.** Para cada escena aceptada (113 a 20 m, 85 a 10 m): hora de adquisición del metadato; nivel de marea y fase (subiendo/bajando) en la boca de la bahía con un modelo global de marea descargable sin registro (p. ej. GOT4.10c con pyTMD; documenta modelo y versión; si ninguno se puede descargar, para y dilo); viento ERA5 horario a 10 m en el punto de rejilla más cercano: velocidad a la hora de paso y media de las 24 h previas (ya tenéis acceso a ERA5 por la precipitación). ▪ **D2.** Estratos: marea alta/baja (por encima/debajo de la mediana de las escenas), subiendo/bajando, viento a la hora de paso y en 24 h por encima/debajo de su mediana. En cada estrato: `orden()` seco (2 variantes × 2 resoluciones), mediana de d con IC bootstrap por escenas, y bahía − mar. Spearman de d por escena frente a nivel de marea y frente a viento. ▪ **Regla fijada:** «no depende de marea ni viento» si en todo estrato con ≥ 8 escenas se mantiene `orden()` seco y la mediana de d > 0. Prioridad si no da tiempo a todo: A, B, D, C. **Precisiones operativas del chat técnico, fijadas aquí antes de calcular; no cambian ningún umbral ni criterio de éxito:** (1) La fecha de corte del bloque A es la del commit de esta fila; no se descarga ni procesa ninguna escena de 2026 hasta que Alex confirme ese commit. (2) Semilla de todos los bootstraps y placebos: 20261118. (3) «Escena 2026 aceptada»: criterio de la secc. 6 aplicado con el mismo código que a las 113 (20 m) y 85 (10 m) escenas del archivo. (4) A1: el d de cada escena usa los focos y la referencia de su estación y de su resolución (z_c ≥ 3,5 del archivo 2016–2025, sin recalcular); a 10 m se informa además, por separado, el d de la unión de píxeles de los 13 grupos de la secc. 28 (y el subconjunto de los 8 con el primer píxel en la ventana de la bahía, solo como información). (5) A1, comparación con placebos: cada uno de los 500 conjuntos da un d por escena y su mediana entre escenas; el percentil 95 se toma sobre esas 500 medianas. Prueba de signo: binomial unilateral P(X ≥ k | n, 0,5), sin contar las escenas con d = 0. (6) A2 y A3: medianas por zona y por escena como en `24_gradiente.py` (N_MIN_PX 50 por zona y escena); variante `a100m` = sin los píxeles a < 100 m de costa. (7) B: «mediana climatológica» = mediana por píxel y estación de la secc. 7; z_c = la de `zc_estacion` de `23_batimetria.py`; solo píxeles de la bahía con profundidad de la malla; bloques de 200 × 200 m de la rejilla UTM, y un píxel sin estadístico en una celda no cuenta. B2: regresión de mínimos cuadrados sobre los rangos (percentiles 0–1) de cada variable, coeficientes estandarizados. (8) C: «fracción de píxeles válidos de la bahía» = píxeles de agua de la ventana de la bahía válidos según `escenas.validez` entre los de agua de la ventana; empate: gana la fecha más antigua; el subconjunto se fija con `resultados/escenas_qc.csv` y se escribe en el JSON antes de lanzar ACOLITE. (9) D1: modelo de marea = GOT4.10c si se puede descargar sin registro; si no, EOT20 (libre, SEANOE, doi 10.17882/79489; ya lo usa el repo del modelo) y se dice cuál; si ninguno se puede, se para y se dice. Punto de la boca: E 361000, N 2560900 (UTM 17N). Viento: ERA5 horario 10 m de la entrega de forzamiento del repo del modelo si cubre 2016–2025 (solo lectura); si no, se para y se dice. Hora de paso = la del metadato de la escena (UTC). (10) Todo lo no listado en la petición se informa tal como salga; ningún ítem se sustituye por otro sin avisar. | Atacar con datos las tres pegas previsibles de un revisor: todo es exploratorio (A), profundidad, distancia a costa y adyacencia confundidas (B, C) y una sola hora de paso (D) | **A: NO**, confirmatoria: reglas fijadas antes de procesar ninguna escena de 2026 y ninguna se cambia después. **B, C y D: sí**, exploratorios, después de ver las secc. 21–28 |
| 2026-11-19 | **Bloque C de la petición 2, repetición con ventana ampliada (CAMBIO DE MÉTODO, decidido por Alex tras ver el resultado de la secc. 29.3: «ampliala»), definida antes de calcularla.** Motivo, ya visto: con la ventana congelada (23,100–23,210 N; −82,400 a −82,280 E; 614×621 px a 20 m) RAdCor deja NaN todo píxel a menos de `radcor_kernel_radius` = 5 km del borde y ningún foco queda válido. **Qué cambia:** SOLO la ventana de ACOLITE al correr RAdCor sobre los mismos 10 L1C secos de `resultados/radcor_subconjunto_20m.json`: `limit` = (S 23,050; O −82,450; N 23,260; E −82,230), es decir 0,050° más por cada lado (≈5,1–5,5 km, 255–277 px > 250 px del núcleo). **Qué NO cambia:** el resto de ajustes (`acolite_io.AJUSTES` salvo `atmospheric_correction_method=radcor`; ningún `radcor_*`, `radcor_edge_extend` queda en su defecto False), la resolución (20 m), las 10 escenas, los focos, la climatología, el agua, las zonas y la regla de C: d_RAdCor>0 en ≥8/10 escenas y mediana de d_RAdCor/d_DSF ≥0,5, con d por escena calculada como en `scripts/30_contraste_escenas.py`. **Cálculo:** cada producto RAdCor ampliado se recorta a la rejilla de `resultados/climatologia.npz` por coordenadas (x, y) exactas, de modo que la máscara de agua, la distancia a costa y los focos son idénticos; d_DSF son las ya calculadas (`contraste_escenas_20m_2016_2025.csv`), con ajustes DSF sin cambios. **Honestidad:** el cambio se decide después de ver el fallo, es EXPLORATORIO y lo único que se compara es RAdCor frente a DSF en las mismas 10 escenas; la AOT de RAdCor se estima ahora sobre otra ventana, así que no es idéntica a la del primer intento. Si vuelve a fallar o los píxeles de recorte no coinciden, se informa y no se ajusta nada más. |

## 16. Lo que midió el piloto (16/09/2026, 13 escenas)

Primera medida de las cantidades de las que depende el método. **No es un resultado sobre
vertidos**: es la caracterización del instrumento.

| Cantidad | Valor medido |
|---|---|
| Agua en la ventana | 76,9 km²; distancia máxima a costa 6747 m |
| Escenas utilizables | 5 de 13 (38 %), dentro del 30–40 % esperado |
| Turbidez, bahía interior | mediana 3,01 FNU (p25 2,23; p75 3,92; p95 5,64) |
| Turbidez, mar abierto | mediana 1,40 FNU (p25 1,22; p75 1,69; p95 2,28) |
| Contraste bahía/mar | **2,1×** |
| Adyacencia: amplitud A | 0,0031–0,0046 en ρ(1610 nm) |
| Adyacencia: longitud L | 55, 94 y 386 m en los tres ajustes con r² > 0,85 |

Extrapolando el 38 % a los 664 productos de R097: **~250 escenas utilizables, ~125 por
estación**, holgadamente por encima del mínimo de 20 observaciones por píxel.

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

## 17. Climatología del archivo completo (13/10/2026)

Calculada con `scripts/05_climatologia.py` y commiteada **antes de calcular ninguna
anomalía**. Ficheros: `resultados/climatologia.npz` (sha256 en `climatologia.json`) y
`resultados/escenas_qc.csv` (qué escena entra y por qué).

| Cantidad | Valor |
|---|---|
| Fechas de paso (un producto por fecha) | 637 |
| Escenas aceptadas (≥ 60 % del agua de la bahía válida) | **113 (18 %)**: seca 71, lluviosa 42 |
| Años con escenas aceptadas | 2017–2025; **ninguna de 2016** |
| Agua | 76,8 km² en la ventana, 4,5 km² en la bahía; distancia máxima a costa 7,06 km |
| Píxeles evaluables (≥ 20 obs. y MAD > 0) | seca: 99 % del agua, 91 % de la bahía; lluviosa: 98 % y 90 % |
| Adyacencia (89 ajustes con r² > 0,85) | A = 0,0031 / 0,0055 / 0,0161; L = 18 / 45 / 96 m (p10 / p50 / p90) |
| Turbidez mediana climatológica | bahía 2,1 FNU (seca) y 2,6 (lluviosa); mar a más de 2 km 1,3 y 1,8 |
| Píxeles válidos fuera de 0–1000 FNU | 29 en todo el archivo |

La fracción de escenas aceptadas (18 %) queda **por debajo** de lo esperado en la sección 6
(30–40 %) y del piloto (38 %, con el 40 % sobre la ventana ampliada). Como dice la sección 6,
se reporta y **no se reajusta el umbral**. Consecuencias: el criterio de 5 años distintos
(sección 10) se evalúa sobre 9 años con datos, no 10; y la estación lluviosa, con 42
escenas, queda más justa frente al mínimo de 20 observaciones por píxel.

## 18. Resultado de la detección (13/10/2026)

Primera ejecución de `scripts/06_deteccion.py` sobre la climatología congelada (secc. 17),
con las reglas fijadas en la sección 14 antes de calcular ninguna anomalía. Ficheros:
`resultados/deteccion.json` y `resultados/sitios.csv`. Se transcribe tal cual salió.

| Cantidad | Valor |
|---|---|
| Escenas | 113 |
| Celdas con alguna detección | 1833 |
| Sitios recurrentes (persistencia ≥ 0,10 y ≥ 5 años), margen 0 | **3**, los tres **fuera de la bahía** |
| Sitios recurrentes por margen (0/20/40/60/100/200/400 m) | 3 / 2 / **0** / 0 / 0 / 0 / 0 |
| Candidatos distinguibles de sus controles (p < 0,05) | 3 de 3 |
| Candidatos marcados por aerosoles | 0 de 3 |
| Superficie costera (≤ 400 m) no evaluada | 7,4 % (seca), 10,9 % (lluviosa) |

**Veredicto, según la sección 12: MÉTODO FRACASADO por el criterio 2** (ningún candidato
sobrevive al margen de 40 m). Los criterios 1, 3 y 4 no se cumplen.

Los tres candidatos: uno en la costa al este de la bahía (23,173 N, 82,282 O; persistencia
0,126; 5 años) y dos a 40 m uno del otro junto a la bocana (23,156 N, 82,350 O; 0,123;
6–7 años), a 60 m de costa. Estos dos son el mismo punto: la supresión de no-máximos de la
sección 10 deja pasar dos celdas vecinas cuando empatan en persistencia. Es un fallo del
código que no se corrige aquí; si se corrige, irá al registro como cambio hecho después de
ver anomalías.

Familia climatológica (8.1), que se reporta aparte y no tiene criterio de fracaso: 43 grupos
en la estación seca (5 en la bahía) y 17 en la lluviosa (2 en la bahía). El mayor (1980 px,
z_c 10,7, dentro de la bahía) es la bahía entera más turbia que el mar abierto a la misma
distancia de costa: con la ventana ampliada, las bandas de distancia mezclan bahía y mar, y
esta familia deja de aislar fuentes puntuales. Queda anotado como limitación, no como
detección.

Pendiente, sin efecto en el veredicto: anisotropía (11.3d) y anotación de atracaderos
(secc. 9).

## 19. Resultados EXPLORATORIOS (13/10/2026)

Declarados en la sección 14 antes de ejecutarlos y **después** de ver la sección 18, cuyo
veredicto no cambian. Ficheros: `resultados/exploratorio.json` y `resultados/exploratorio.png`.

- **E1, frecuencia de detección por píxel.** Mayor en la bahía que fuera: mediana 0,010
  frente a 0,000, y percentil 90 de 0,035 frente a 0,013. Dentro de la bahía se concentra en
  la cabecera del brazo sur (Guasabacoa), en torno a su punto de control (23,118 N, 82,338 O),
  y en el brazo suroeste (Atarés; ≈ 23,120 N, 82,351–82,356 O).
- **E2, sensibilidad.** Con el criterio preregistrado (persistencia ≥ 0,10 y ≥ 5 años) hay 2
  sitios con margen 0 (los de la secc. 18, ya sin duplicado) y 0 en la bahía. Si se relaja,
  aparecen sitios dentro de la bahía que sí aguantan el margen: con ≥ 0,05 y ≥ 3 años, 14 de 27
  con margen 0 y **13 de 20 con margen 40 m** están en la bahía (9 con 100 m); con ≥ 0,075 y
  ≥ 3 años, 2 en la bahía con margen 0 y 3 con 40–100 m. Con ≥ 0,10 no queda ninguno a partir
  de 40 m.
- **E3, familia climatológica con bandas solo de la bahía.** 7 grupos en la estación seca y
  6 en la lluviosa. Dos coinciden con las zonas de E1: la cabecera del brazo sur (z_c hasta
  7,1 en seca y 5,0 en lluviosa) y el brazo suroeste (hasta 6,2 en las dos). El más intenso
  está en otro sitio, una franja en la orilla oeste donde arranca el brazo sur (23,122 N,
  82,345 O; z_c 11,9 en seca y 9,3 en lluviosa, a 40–45 m de costa), que E1 apenas marca. La
  boca del canal (≈ 23,156 N, 82,350 O) sale en las dos estaciones.
- **E4, desempate.** Elimina el duplicado de la secc. 18: los candidatos preregistrados son 2
  sitios distintos, no 3.

**Lectura.** Dos detectores que miden cosas distintas coinciden en dos rincones de la bahía
(cabecera del brazo sur y brazo suroeste): E1 compara cada píxel con su propia historia y E3 compara medianas entre píxeles con
la misma geometría. Esto es una **hipótesis para verificar en campo**, no un resultado. Los
umbrales relajados se eligieron después de ver datos. A los sitios laxos no se les han pasado
los controles emparejados. Y los fondos de los brazos son estrechos, con mucha tierra
alrededor, que es justo donde la adyacencia pesa más.

## 20. Versión 2.0 — segunda fase, para un solo artículo (redactada el 13/10/2026, aprobada el 17/10/2026)

**Estado al aprobarla: no se ha procesado nada a 10 m, no se han descargado datos de lluvia
y no se ha calculado ningún punto de control de campo.** Entra en vigor con el commit que la
introduce; desde ese momento, todo lo que sigue vale como preregistro y
cualquier cambio va a la sección 14.

### 20.1 Qué se sabe al escribirla y qué no cambia

Se escribe **después** de ver la detección a 20 m (secc. 18) y los exploratorios (secc. 19).
Por eso no es un preregistro limpio frente a las adquisiciones: a 10 m se reprocesan las
**mismas** escenas. Lo que sí es ciego es el producto a 10 m, que no existe todavía, la lluvia
y el campo.

Nada de las secciones 1–19 cambia. El veredicto a 20 m (MÉTODO FRACASADO, criterio 12.2) es
definitivo y se publica como tal. La climatología y la detección a 20 m se quedan en
`resultados/` sin tocar; la fase 2 escribe en `datos/productos_10m/` y `resultados_10m/`.

**Pregunta del artículo:** ¿puede Sentinel-2 localizar los puntos de vertido de una bahía
tropical pequeña, y qué lo limita? Entran cinco piezas: el resultado preregistrado a 20 m,
la repetición a 10 m (20.2), el test de lluvia (20.4), la verificación de campo (20.5) y el
mapa de turbidez crónica (20.6). Nada más.

### 20.2 Repetición a 10 m

**Hipótesis, escritas antes del resultado.** El fracaso a 20 m (ningún sitio aguanta el
margen de 40 m) tiene dos explicaciones posibles:

- **H-píxel:** el píxel mixto de la orilla, de unos 20 m, se come la señal. Si es esto, a
  10 m debe aparecer **algún sitio recurrente que sobreviva al margen de 40 m**.
- **H-atmósfera:** la adyacencia atmosférica, medida con L mediana de 45 m (p90 96 m, secc. 17),
  no depende de la resolución. Si es esto, a 10 m el criterio 12.2 vuelve a cumplirse.

Las dos salidas son resultado del artículo. Las adquisiciones son las mismas, así que esto
prueba la **resolución**, no si los sitios existen. Eso lo prueba el campo (20.5).

**Escenas.** Se reprocesan solo las fechas que a 20 m tuvieron **al menos el 40 %** del agua
de la bahía válida: 186 de 637, frente a las 113 que pasaron el 60 %. El margen de 20 puntos
cubre las escenas que a 10 m podrían cruzar el umbral. Las otras 451 fechas cuentan como
rechazadas. En cada fecha se usa el mismo producto L1C que a 20 m: la regla del 13/10 es
geométrica y no depende de la resolución. El criterio de escena (secc. 6) se aplica de nuevo
a 10 m, sin heredar la decisión de 20 m.

**Corrección atmosférica.** Los AJUSTES de la sección 3, cambiando solo `s2_target_res` de 20 a
10. ACOLITE remuestrea a 10 m las bandas de 20 m (B5–B7, B8A, B11, B12). El control de calidad
(ρ(2200) ≤ 0,010) y la máscara de buques siguen leyendo SWIR, que conserva su resolución
efectiva de 20 m. Se declara así y no se corrige.

**Turbidez.** Dogliotti 2015 «blended» de ACOLITE usa solo el rojo (B4, 665 nm, nativa a
10 m) mientras ρ_rojo < 0,05, equivalente a T < 16,4 FNU. Por encima mezcla el NIR (B8A, 20 m).
Comprobado sobre el archivo a 20 m, en las 113 escenas aceptadas: el 0,20 % de las
observaciones válidas de la bahía supera 16,4 FNU, y solo 4 escenas superan el 1 %. Dentro de
la bahía, el producto es en la práctica de 10 m nativo. **Comprobación a 10 m:** en las dos
primeras escenas procesadas se lee `rhos_665` del L2W antes de borrarlo y se cuenta la
fracción de agua válida de la bahía con ρ_rojo ≥ 0,05. Si en alguna pasa del 1 %, la
detección a 10 m usa `tur_dogliotti2015_red`, que da lo mismo por debajo del umbral. Se
decide aquí y no se vuelve a decidir.

**Umbrales.** Los mismos: z_t ≥ 3,5, z_s ≥ 3,0, z_c ≥ 3,5, n ≥ 20 observaciones, persistencia
≥ 0,10, ≥ 5 años, rejilla de sitio de 40 m, fusión de 80 m, márgenes 0–400 m, tolerancias de
los controles (±20 m, ±0,05) y criterios de la sección 12 con sus reglas de decisión
(secc. 14, 13/10). **Regla de conversión:** lo que el protocolo fija en metros se queda en
metros, y lo que el código fija en píxeles se pasa a los mismos metros:

| Parámetro | 20 m | 10 m |
|---|---|---|
| Dilatación de la máscara de buques | 2 px | 4 px (40 m) |
| Tamaño mínimo de grupo | 4 px | 16 px (1600 m²) |
| Distancia mínima control–candidato | 10 px | 20 px (200 m) |
| Radio del test de aerosoles y de lluvia | 4 px | 8 px (80 m) |
| Rejilla de sitio | 2 × 2 px | 4 × 4 px (40 m) |

Ventana igual (secc. 1): 1242 × 1228 píxeles. Bahía: 476 × 505.

**Dos correcciones que entran en el análisis principal**, ambas vistas en la fase 1 y
declaradas antes de tener datos a 10 m:

- **(a) Desempate** en la supresión de no-máximos (E4, `desempate=True`). Corrige el sitio
  duplicado de la sección 18.
- **(b) La familia climatológica (8.1) usa bandas de distancia formadas solo por agua de la
  bahía** (E3). La versión de la sección 8.1 mezclaba bahía y mar abierto (secc. 18). El mar
  abierto se evalúa con sus propias bandas, por separado.

**Análisis secundario, preregistrado aquí:** los umbrales laxos de E2 (persistencia ≥ 0,05 y
≥ 3 años), **con** controles emparejados, test de aerosoles y barrido de márgenes. Se
informa siempre, pero el veredicto 10 m lo dan solo los umbrales principales. También se
repite el mapa E1.

**Salida a 10 m.** La versión que corresponda de este texto:

- «Criterios 12.1–12.4 no cumplidos: H-píxel compatible.»
- «Criterio 12.2 cumplido otra vez: la resolución no era el límite.»

### 20.3 Código

`s2_target_res` y los parámetros en píxeles pasan a depender de la resolución. A 20 m los
valores por defecto quedan igual, y se comprueba que la cadena a 20 m reproduce
`resultados/deteccion.json` byte a byte. `tests/test_cadena.py` tiene que pasar a las dos
resoluciones. Nada de esto se hace antes del commit de esta sección.

### 20.4 Test de lluvia (mecanismo)

Un vertido de escorrentía o de alcantarillado unitario debería encenderse más después de
llover. La adyacencia no tiene por qué.

- **Dato.** Precipitación total horaria de ERA5 en la celda que contiene el centro de la
  bahía (23,133 N, 82,333 O). Se anotan versión y fecha de descarga.
- **Variable.** P72, la precipitación acumulada en las 72 h que acaban en la hora de
  adquisición de cada escena aceptada.
- **Estadístico por sitio.** El máximo de z_t a menos de 80 m, igual que en el test de
  aerosoles.
- **Prueba.** Para cada sitio, Spearman ρ entre P72 y ese estadístico sobre las escenas
  aceptadas. La misma ρ se calcula en **todos** sus controles emparejados. Se calcula
  p = (1 + controles con ρ ≥ la del sitio) / (1 + nº de controles), con
  `adyacencia.p_controles`. Un sitio queda «ligado a la lluvia» si ρ > 0 y p < 0,05.
- **Sitios.** Los candidatos a 10 m (principales y secundarios) y los cinco sitios de campo
  (20.5), a 10 m y también a 20 m.
- **Abstención.** Si menos de 10 escenas aceptadas tienen P72 ≥ 1 mm, el test se declara
  **no evaluable** y no se reinterpreta.
- **Confusión.** Se informa también la Spearman entre P72 y AOT.

No es un criterio de falsación. Es evidencia de mecanismo y se presenta así.

### 20.5 Verificación de campo, a ciegas

**Sitios predichos, fijados ahora:**

| Sitio | Lat (N) | Lon (O) | Origen |
|---|---|---|---|
| S1, costa al este de la bahía | 23,1730 | 82,2821 | preregistrado (secc. 18) |
| S2, bocana | 23,1562 | 82,3499 | preregistrado (secc. 18); también E3 |
| S3, cabecera del brazo sur | 23,1135 | 82,3401 | E1 + E3 (pico en seca) |
| S4, brazo suroeste | 23,1220 | 82,3560 | E1 + E3 (las dos estaciones) |
| S5, orilla oeste al arrancar el brazo sur | 23,1217 | 82,3455 | E3 (pico de z_c 11,9) |

**Controles: uno por sitio, cinco en total.** Se calculan con la rejilla y la climatología a
20 m, con semilla fija 20261013. Cada control:

- empareja a su sitio en distancia a costa (±20 m) y `f_tierra(500 m)` (±0,05);
- está en la misma zona (bahía o fuera);
- queda a más de 200 m de los cinco sitios y de cualquier grupo E3;
- es negativo predicho: frecuencia E1 ≤ la mediana de su zona.

Si un punto, sitio o control, no es accesible ni desde tierra ni desde el agua, Alex lo
decide sobre el mapa **antes** de la visita, mirando solo la accesibilidad. Un control
inaccesible se sustituye por el siguiente sorteado; un sitio inaccesible se informa como no
visitado. La clave sitio/control se commitea antes de la primera visita. A la persona de campo
se le dan los diez puntos barajados y numerados P01–P10, sin decirle cuáles son cuáles.

**Antes de la visita, revisión de fuentes conocidas.** Sobre OpenStreetMap, con la fecha de
la instantánea anotada, se buscan cauces que desembocan (`waterway` = river, stream, canal,
drain) y `man_made` = outfall o pipeline. También cartografía publicada, con su DOI
comprobado. Cada uno de los diez puntos se clasifica como «fuente conocida a ≤ 150 m» o no.
Así se puede decir después si el método encuentra solo lo ya conocido.

**Qué cuenta como positivo**, dentro de 150 m del punto (80 m de localización, más la
distancia a costa, más el GPS):

- **P-infraestructura (criterio principal).** Una estructura que vierte al agua: tubo,
  colector, alcantarilla, canal o desembocadura de cauce. Basta observarla una vez.
- **P-actividad (secundario).** En alguna visita hay flujo entrando al agua, o una pluma,
  cambio de color, espuma o película visible.

**Evaluación.** Fisher exacto unilateral sobre P-infraestructura: sitios frente a controles.
El campo **apoya** el método si p < 0,05. Con 5 frente a 5 eso exige, por ejemplo, 4 de 5
frente a 0 de 5, o 5 de 5 frente a 1 de 5. Se informa igual P-actividad. Los puntos no
visitados se excluyen y se dicen.

**Visitas.** Al menos tres:

- una en estación lluviosa (mayo–octubre);
- una en seca (noviembre–abril);
- una en las 48 h siguientes a un día con ≥ 20 mm de lluvia en La Habana.

Lo ideal es hacerlas cerca del paso del satélite: 16:17 UTC, es decir hacia las 11:15 hora
local en invierno y las 12:15 en verano. En cada punto:

- coordenadas GPS y hora;
- fotos de la orilla y del agua, con posición;
- ¿hay estructura de vertido? ¿de qué tipo? ¿está activa?;
- color del agua, espuma, olor, película;
- lluvia de las 48 h previas;
- notas de acceso.

Si una visita a 10 m dejara sitios nuevos, se añadirían en otra visita con sus propios
controles, sorteados igual, y se marcarían como añadidos después.

### 20.6 Mapa de turbidez crónica (producto)

Con la climatología a 10 m, para cada estación:

- la mediana estacional de turbidez;
- la máscara de evaluable;
- el z_c con bandas de la bahía.

Va al artículo como figura, y al repositorio como `resultados_10m/climatologia.npz` con su
sha256. Es descriptivo y no lleva criterio de éxito.

### 20.7 Orden

1. Commit de esta sección.
2. Puntos de control de campo y revisión de fuentes, con su commit.
3. Código a 10 m y tests.
4. Prueba con dos escenas y comprobación del rojo.
5. Bucle sobre las 186 fechas.
6. Climatología a 10 m y su commit.
7. Detección, lluvia y mapa.
8. El campo va en paralelo, desde el paso 2.

## 21. Resultados a 20 m del 13/11/2026: lluvia, anisotropía, atracaderos y fuentes publicadas

Descriptivos: no cambian el veredicto de la secc. 18. Ficheros: `resultados/lluvia_20m.json`,
`resultados/lluvia_p72_20m.csv` y `resultados/diagnosticos_sitios.json`.

**Lluvia (20.4).** El test es evaluable: 69 de las 113 escenas tienen P72 ≥ 1 mm (mediana 1,5 mm,
p90 13,4 mm, máximo 30,7 mm). La lluvia se correlaciona con el AOT (Spearman 0,28): después de
llover la atmósfera cambia. Sitios y controles comparten ese efecto, y por eso se comparan entre sí.

| Sitio | ρ (P72, z_t máx.) | Controles: n y mediana de ρ | p frente a controles | Ligado a la lluvia |
|---|---|---|---|---|
| S1, costa al este | 0,31 | 627; 0,20 | 0,22 | no |
| S2, bocana | 0,30 | 1846; 0,24 | 0,29 | no |
| S3, cabecera del brazo sur (Guasabacoa) | 0,07 | 306; 0,21 | 0,89 | no |
| S4, brazo suroeste (Atarés) | 0,36 | 376; 0,18 | **0,027** | **sí** |
| S5, orilla oeste del brazo sur (Guasabacoa) | −0,05 | 410; 0,18 | 0,87 | no |

Toda la costa se enciende algo más después de llover (ρ de los controles ≈ 0,2). Solo S4 lo hace
más que sus controles. Con cinco pruebas, uno de cinco con p < 0,05 puede salir por azar
(se esperan 0,25 falsos positivos).

**Anisotropía (11.3d) y atracaderos (secc. 9).**

| Sitio | Escenas con grupo | Razón paralela/perpendicular (mediana) | ρ(z_t, f_tierra) | Escala con f_tierra | Atracadero (OSM a ≤ 80 m) |
|---|---|---|---|---|---|
| S1 | 13 | 1,61 | 0,53 | **sí** | no |
| S2 | 17 | 0,74 | −0,27 | no | no |
| S3 | 16 | 1,28 | 0,34 | **sí** | no |
| S4 | 10 | 1,07 | −0,16 | no | **sí** (dos muelles a 30 y 52 m) |
| S5 | 6 | 1,22 | −0,40 | no | no |

En S1 y S3 la amplitud crece donde hay más tierra alrededor, que es la firma de la adyacencia. S4
es candidato de atracadero, igual que en las fotos de campo de P06 (muelles y tuberías a 72–123 m).

**Fuentes publicadas.** Dos fuentes, sin coordenadas ni DOI (`resultados/campo/fuentes_publicadas.md`).
Ríos Luyanó y Martín Pérez a Guasabacoa (S3, S5), drenes directos a Atarés (S4) y Arroyo
Tadeo a Marimelena.

**Robustez entre productos (secc. 4).** El candidato de la costa al este (S1) solo es recurrente
con Dogliotti: con la turbidez y el SPM de Nechad su celda baja a una persistencia de 0,012.
**Es sospechoso** según la regla de la secc. 4, y además su amplitud crece con la fracción de
tierra (arriba). El de la bocana (S2) es recurrente con los tres productos. En los focos
exploratorios de la bahía los tres productos dan la misma frecuencia E1 y z_c con diferencias
de 0,3 como mucho. Pero eso prueba poco: dentro de la bahía Dogliotti usa solo el rojo, y los
dos productos de Nechad salen de esa misma banda. La comprobación solo discrimina donde
Dogliotti pasa al infrarrojo cercano.

## 22. Verificación de campo y con imagen (15/11/2026)

Regla de la fila del 15/11/2026 en la secc. 14. Ficheros: `resultados/campo/evaluacion_campo.json`
(`scripts/18_evaluar_campo.py`), `resultados/campo/imagen_codificacion.csv` e `imagen_etiquetas.csv`
(`scripts/19_imagen_ciega.py`). Visitas: 23/10/2026 (P05, P06, P08) y 13/11/2026 (P02, P03, P04, P09, P10).

| Punto | Rol | Par | Campo: estructura a ≤ 150 m | Imagen (a ciegas) |
|---|---|---|---|---|
| P07 | sitio | S1 | no visitado | sí (laguna costera abierta al mar, la respuesta menos segura) |
| P09 | sitio | S2 | no | no |
| P05 | sitio | S3 | no | no |
| P06 | sitio | S4 | sí (tubo y río) | no |
| P08 | sitio | S5 | sí (tubo) | sí (río o canal con pluma) |
| P01 | control | S1 | no visitado | no |
| P10 | control | S2 | sí (tubo) | no |
| P04 | control | S3 | sí (tubo) | sí (canal estrecho) |
| P03 | control | S4 | no se puede ver | no |
| P02 | control | S5 | sí (tubo) | no |

**Campo (P-infraestructura, criterio principal).** Sitios 2 de 4, controles 3 de 3; Fisher
unilateral p = 1,0. **El campo no apoya el método.** Las tres estructuras de los controles son tubos
vistos desde tierra: en esta bahía urbana, a 150 m casi siempre hay alguna salida, así que el
criterio discrimina poco. Con 4 frente a 3 solo 4/4 frente a 0/3 habría dado p < 0,05.

**P-actividad (descriptivo).** Flujo saliendo solo en P06 (S4: tubos y desembocadura del Luyanó),
que también tiene mancha y espuma. Película o aceite en P05, P06 y P08 (los tres sitios del sur) y en
ningún control. Agua gris o negra en P05, P06 y P08; marrón o turbia en P02, P03 y P04; normal en P09 y
P10. **Fecha y rol están confundidos:** tres de los cuatro sitios visitados se vieron el 23/10 y todos
los controles el 13/11, tras el frente frío, así que estas diferencias no se pueden atribuir al rol.

**Imagen (exploratorio).** WorldView-3 del 27/01/2024, 0,31 m, la misma en los diez puntos. Sitios 2
de 5, controles 1 de 5; Fisher unilateral p = 0,50. Concordancia con el campo 4 de 7: la imagen no ve
tres de los cinco tubos que vio el observador (P02, P06, P10), que desde arriba pueden quedar bajo muelles o
ser demasiado pequeños. En esta prueba la imagen solo detectó salidas grandes (cauces, canales).

**Lectura.** Ni el campo ni la imagen separan los sitios de los controles. Coincide con el fracaso
preregistrado (secc. 18): a 20 m el método no localiza puntos de vertido. La repetición a 10 m (20.2)
sigue en marcha y no cambia esta sección.

## 23. Resultados a 10 m (16/11/2026) e inventario exploratorio

Bucle completo: 186 de 186 fechas (cinco fallos de descarga recuperados por el vigilante). Ficheros en
`resultados_10m/`. La climatología se calculó antes de la detección; su sha256 está en
`climatologia.json` (`f8374f00…5c95`), pero el commit previo que pide 20.7 no se hizo (lo hace Alex).

**Climatología.** 85 escenas aceptadas de 186 (seca 44, lluviosa 41), frente a 113 a 20 m; 75 fechas
son comunes. Adyacencia (ajustes con r² > 0,85): L mediana 28 m a 10 m frente a 45 m a 20 m.

**Detección preregistrada (`--v2`).** Un candidato recurrente (costa al este, junto a S1), que solo
sobrevive al margen de 0 m: **el método fracasa también a 10 m por 12.2.** El análisis secundario
(persistencia ≥ 0,05 y ≥ 3 años, fuera del veredicto) da 14 candidatos, 12 a 40 m.

**Lluvia a 10 m (20.4).** Ningún sitio ligado a la lluvia (S4 tenía p = 0,027 a 20 m y aquí 0,64). La
costa entera responde a la lluvia en las dos resoluciones (ρ mediana de los controles 0,14–0,24).

**Inventario exploratorio** (`scripts/20_inventario.py`, `resultados_10m/inventario.json`; definido
después de ver los resultados). Robustez = repetir a la otra resolución, que cambia la corrección
atmosférica (el AOT de DSF) y parte de las escenas, no los datos L1C.

| Señal | 20 m | 10 m | ¿Robusta? |
|---|---|---|---|
| Focos S1–S5 como **anomalía permanente (z_c)** | definidos así S3–S5 | los cinco a 12–57 m de un grupo permanente; los cinco controles de campo, a ≥ 423 m. Al azar, un píxel de agua a ≤ 60 m de costa queda a ≤ 80 m de un grupo el 4,3 % de las veces | **Sí**, como turbidez crónica, no como vertido intermitente |
| Gradiente (FNU, mediana; seca / lluviosa) | Atarés 2,48 / 2,64; Guasabacoa 2,39 / 2,72; Marimelena 2,00 / 2,59; centro y canal 1,99 / 2,49; mar 1,26 / 1,81 | 2,52 / 2,90; 2,41 / 3,10; 2,01 / 2,88; 2,00 / 2,73; 1,11 / 1,94 | **Sí**: brazos del sur > Marimelena ≈ centro > mar, en las dos estaciones y sin los 100 m de costa |
| Lluvia en toda la costa | ρ controles 0,18–0,24 | 0,14–0,24 | **Sí** |
| S4 ligado a la lluvia | p = 0,027 | p = 0,64 | No |
| Escala de adyacencia | 2,3 píxeles | 2,8 píxeles | Escala con el píxel: apunta a píxeles mezcla más que a la atmósfera (interpretación por confirmar) |

Límite: S3–S5 se eligieron a 20 m por ser permanentes, y 75 de las 85 fechas son las mismas; la
reaparición a 10 m demuestra que la señal no depende de la resolución ni de la corrección
atmosférica, no que venga de datos independientes.

## 24. Pruebas de robustez de los focos de turbidez crónica (17/11/2026)

Exploratorias, definidas en la fila del 17/11/2026 de la secc. 14 (después de ver las secc. 21–23).
Ficheros: `resultados/replicacion_20m.json`, `resultados_10m/replicacion_10m.json`
(`scripts/21_replicacion.py`) y `resultados/clorofila_ndci.json` (`scripts/22_clorofila.py`).

**1. Replicación en mitades independientes (A = 2016–2020, B = 2021–2025).** Escenas aceptadas:
51 y 62 a 20 m; 38 y 47 a 10 m. Tasa de replicación (grupos calientes de una mitad con algún píxel
caliente de la otra a ≤ 80 m) frente a la cobertura base (píxeles de la bahía a ≤ 250 m de costa
que quedan a ≤ 80 m de un píxel caliente de la otra mitad):

| Resolución | Estación | A→B | B→A | Cobertura base | ρ(z_c) bahía |
|---|---|---|---|---|---|
| 20 m | seca | 0,92 (33/36) | 0,88 (30/34) | 0,13 | 0,77 |
| 20 m | lluviosa | 0,71 (10/14) | 0,54 (7/13) | 0,17 / 0,09 | 0,20 |
| 10 m | seca | 0,89 (8/9) | 1,00 (18/18) | 0,17 | 0,65 |
| 10 m | lluviosa | 0,73 (8/11) | 1,00 (3/3) | 0,18 / 0,19 | 0,33 |

La regla fijada (tasa ≥ 3 veces la base y ≥ 0,30 en las dos direcciones) **se cumple en las cuatro
combinaciones**; en lluviosa a 10 m B→A son solo 3 grupos. Los cinco sitios S1–S5 tienen z_c ≥ 3,5
a ≤ 80 m en las dos mitades en la estación seca, a 20 y a 10 m. En lluviosa S3 no llega a 3,5 a 20 m
(2,5 y 2,9) y a 10 m solo en B (4,2); S1 en lluviosa pasa de 10,7 a 66,4 a 20 m, un valor extremo que
indica una zona pequeña y variable. La replicación en el tiempo no descarta que el patrón sea fijo
por una causa distinta de un vertido (fondo somero, adyacencia de una orilla permanente): la
climatología describe dónde, no por qué.

**2. Clorofila frente a sedimento: no concluyente.** De los 13 L2R piloto solo 2 están aceptados en
`escenas_qc.csv` (2020-01-19 y 2020-11-29). Con ellos: NDCI mediano más alto en Atarés (0,12) que en
Guasabacoa (−0,08), Marimelena (−0,02) y el mar (−0,05), con turbidez parecida en las tres ensenadas
(1,7–1,9 FNU); ρ píxel a píxel entre NDCI y turbidez en la bahía 0,07 (0,11 a ≥ 100 m de costa). Con dos
escenas no se puede afirmar nada. `rhos_704` no se exportaba (secc. 14, 17/11): el exportador lo guarda ya
como `borde`. Para la prueba hacen falta 30 escenas aceptadas más a 20 m
(`resultados/ndci_productos_20m.txt`), a procesar con las credenciales de Copernicus de Alex en
`datos/productos_ndci`.

## 25. Prueba 3 exploratoria: focos frente a profundidad de la carta (17/11/2026)

Definida en la secc. 14 antes de calcularla (`scripts/23_batimetria.py`; `resultados/batimetria_20m.json`,
`resultados_10m/batimetria_10m.json`). Profundidad de la malla SCHISM (cartas de 1879–1889) en los píxeles de la
bahía que caen dentro de la malla (20 m: 12 237 de 60 214; 10 m: 49 036 de 240 380). Rango percentil de cada píxel
caliente (z_c ≥ 3,5) entre píxeles de la bahía a su misma distancia de costa (± 20 m) y a > 80 m de otro caliente.

| Resolución | Estación | Calientes con profundidad | Rango percentil mediano | Prof. mediana calientes / referencia (m) | Fracción < 2 m: calientes / referencia |
|---|---|---|---|---|---|
| 20 m | seca | 221 | 0,19 | 1,72 / 6,10 | 0,57 / 0,15 |
| 20 m | lluviosa | 163 | 0,13 | 1,48 / 6,19 | 0,72 / 0,12 |
| 20 m | ambas | 90 | 0,19 | 1,54 / 6,03 | 0,77 / 0,16 |
| 10 m | seca | 676 | 0,14 | 1,39 / 6,28 | 0,68 / 0,13 |
| 10 m | lluviosa | 544 | 0,12 | 1,59 / 6,13 | 0,64 / 0,12 |
| 10 m | ambas | 235 | 0,14 | 1,42 / 6,17 | 0,83 / 0,14 |

Profundidad mediana a ≤ 80 m de los sitios: S2 2,1 m, S3 0,5 m, S4 1,7 m, S5 1,4 m (S1 fuera de la malla).

**Lectura.** La regla (rango ≥ 0,35 y fracción < 2 m no mayor que el doble de la de referencia) NO se cumple en
ningún caso: los focos de turbidez crónica están en agua somera de la carta, 4–6 veces más de lo esperado a igual
distancia de costa. No se puede decir que los focos sean descargas: son coherentes con fondo somero visible o
resuspendido, con sedimentación junto a las desembocaduras (que también sería señal de aporte) o con ambas cosas.
Limitaciones: cartas de hace siglo y medio (dragados y relleno posteriores), solo cubre la parte interior de la
bahía, y cercanía a costa y profundidad no son independientes. Para la pregunta del artículo: la turbidez crónica
se concentra en los brazos someros del sur; la causa (aporte, resuspensión o fondo) no queda separada con estos datos.

**Nota del 17/11 (tras comparar con el repo del modelo).** La malla `hgrid.gr3` coincide con la superficie de la carta de
1887 (`batimetria_1887.nc`: diferencia mediana 0,0 m en 3623 nodos de la bahía; con la de 1879, 0,6 m), sin dragado. La
carta tiene un error de campo declarado de σ = 0,9 m (L = 150 m) y un datum incierto de 0 a +0,5 m, que son del orden de
la profundidad de los focos (1,4–1,7 m); aun así el contraste con la referencia (≈ 6 m) es mucho mayor que ese error.

## 26. Prueba 2 exploratoria: NDCI frente a turbidez (17/11/2026, 30 escenas a 20 m)

Definida en la secc. 14 el 17/11 (`scripts/22_clorofila.py`). Resultados en `resultados/clorofila_ndci.json` y
`datos/clorofila_30.log`. Escenas: 30 nuevas con `rhos_704` (banda «borde») más 2 del piloto, 32 en total.
NDCI = (ρ704 − ρ665) / (ρ704 + ρ665).

| Zona (mediana de escenas) | NDCI | Turbidez (FNU) |
|---|---|---|
| Atarés | −0,017 | 2,44 |
| Guasabacoa | −0,015 | 2,42 |
| Marimelena | −0,002 | 2,37 |
| Centro y canal | −0,026 | 2,11 |
| Mar | −0,146 | 1,34 |

Correlación de Spearman NDCI–turbidez en la bahía: −0,086 (mediana de escenas); −0,107 a ≥ 100 m de costa.

Sitios frente a su referencia (NDCI mediano; escenas con dato entre paréntesis):

| Sitio | Sitio | Referencia |
|---|---|---|
| S1 | 0,225 (18) | −0,081 |
| S2 | 0,119 (29) | −0,108 |
| S3 | 0,084 (27) | −0,006 |
| S4 | −0,019 (29) | −0,010 |
| S5 | 0,041 (32) | −0,006 |

**Lectura.** En la bahía el NDCI no sube con la turbidez (correlación ligeramente negativa), así que los focos de
turbidez crónica no son un gradiente general de clorofila. En cuatro de los cinco sitios el NDCI mediano es mayor que
en su referencia (S1 y S2 con más diferencia); en S4 no. Eso deja abierto que algunos focos tengan además clorofila
elevada, o materia orgánica que el NDCI no separa, pero con valores cercanos a cero, sin validación con clorofila
medida y sin corrección de adyacencia, no se puede separar del ruido atmosférico. Veredicto: prueba inconclusa para
separar clorofila de sedimento. Lo que sí queda: la turbidez crónica de la bahía no sigue a la clorofila.


## 27. Cálculos pedidos por el chat del artículo (17/11/2026)

Respuesta a `docs/PETICION_CHAT_TECNICO.md` (repo del artículo). Todo EXPLORATORIO y definido después de ver las
secc. 21–26 (fila del 17/11 de la secc. 14). Scripts `24_gradiente.py`, `25_umbrales.py`, `26_figuras.py`; registros
en `datos/gradiente_*.log`, `datos/umbrales_*.log`, `datos/figuras_10m.log`. No se cambió ningún umbral fijado. Las
tablas están generadas desde los JSON, sin redondeo a mano.

### 27.1 Gradiente por zona y estación con todas las escenas aceptadas

**20 m** (113 escenas; mediana entre escenas de la mediana por escena de cada zona, IC 95 % por bootstrap de escenas, 2000 remuestreos; zona-escena con ≥ 50 píxeles válidos). Fuente: `resultados/gradiente_20m.json`.

| Estación (escenas) | Variante | Atarés | Guasabacoa | Marimelena | Centro y canal | Mar | Orden brazos > centro > mar (margen brazos−centro; centro−mar, FNU) | Orden al dejar un año fuera |
|---|---|---|---|---|---|---|---|---|
| seca (71) | todos los píxeles | 2,45 [2,25–2,72] | 2,35 [2,08–2,62] | 2,05 [1,74–2,27] | 2,05 [1,84–2,17] | 1,32 [1,19–1,42] | sí (0,305; 0,734) | 9/9 años |
| seca (71) | ≥ 100 m de costa | 2,48 [2,31–2,72] | 2,38 [2,09–2,71] | 2,04 [1,73–2,25] | 2,11 [1,89–2,27] | 1,32 [1,19–1,41] | sí (0,268; 0,791) | 9/9 años |
| seca | mediana de la climatología por píxel (secc. 23) | 2,48 | 2,39 | 2,00 | 1,99 | 1,26 | — | — |
| lluviosa (42) | todos los píxeles | 2,56 [2,31–2,75] | 2,84 [2,60–2,98] | 2,55 [2,22–2,87] | 2,36 [2,15–2,85] | 2,17 [1,72–2,62] | sí (0,009; 0,386) | 5/9 años |
| lluviosa (42) | ≥ 100 m de costa | 2,66 [2,53–2,84] | 2,85 [2,64–2,99] | 2,66 [2,17–3,01] | 2,48 [2,23–2,90] | 2,16 [1,71–2,59] | sí (0,005; 0,495) | 5/9 años |
| lluviosa | mediana de la climatología por píxel (secc. 23) | 2,64 | 2,72 | 2,59 | 2,49 | 1,81 | — | — |

**10 m** (85 escenas; mediana entre escenas de la mediana por escena de cada zona, IC 95 % por bootstrap de escenas, 2000 remuestreos; zona-escena con ≥ 50 píxeles válidos). Fuente: `resultados_10m/gradiente_10m.json`.

| Estación (escenas) | Variante | Atarés | Guasabacoa | Marimelena | Centro y canal | Mar | Orden brazos > centro > mar (margen brazos−centro; centro−mar, FNU) | Orden al dejar un año fuera |
|---|---|---|---|---|---|---|---|---|
| seca (44) | todos los píxeles | 2,54 [2,33–2,87] | 2,40 [2,10–2,71] | 2,06 [1,82–2,29] | 2,03 [1,82–2,27] | 1,18 [1,00–1,43] | sí (0,342; 0,882) | 9/9 años |
| seca (44) | ≥ 100 m de costa | 2,63 [2,40–3,01] | 2,39 [2,22–2,80] | 2,05 [1,77–2,27] | 2,19 [1,90–2,32] | 1,18 [1,01–1,41] | sí (0,199; 1,009) | 9/9 años |
| seca | mediana de la climatología por píxel (secc. 23) | 2,52 | 2,41 | 2,01 | 2,00 | 1,11 | — | — |
| lluviosa (41) | todos los píxeles | 2,69 [2,53–3,48] | 3,09 [2,78–3,81] | 2,93 [2,41–3,16] | 2,44 [2,32–3,12] | 2,31 [1,97–2,65] | no (-0,233; 0,618) | 0/9 años |
| lluviosa (41) | ≥ 100 m de costa | 2,78 [2,60–3,76] | 3,18 [2,85–3,67] | 2,76 [2,41–3,24] | 2,53 [2,41–3,14] | 2,30 [1,96–2,63] | sí (0,021; 0,464) | 3/9 años |
| lluviosa | mediana de la climatología por píxel (secc. 23) | 2,90 | 3,10 | 2,88 | 2,73 | 1,94 | — | — |


**Aclaración.** La tabla del gradiente de la secc. 23 usa todas las escenas aceptadas (mediana de la climatología
por píxel: 113 escenas a 20 m, 85 a 10 m). Las cifras 2,44 / 2,42 / 2,37 / 2,11 / 1,34 FNU de la secc. 26 son medianas
entre 32 escenas de la prueba de clorofila y no deben citarse como gradiente. La afirmación «igual en las dos
estaciones» que se dio en el chat era incorrecta y se retira.

**Lectura.** En la estación seca el orden min(Atarés, Guasabacoa) > max(Marimelena, centro y canal) > mar se cumple a
20 y 10 m y al dejar fuera cada año (9/9); el margen brazos − centro es 0,20–0,34 FNU. El IC de Atarés a 20 m
([2,25–2,72]) no se solapa con el del centro ([1,84–2,17]), pero el de Guasabacoa ([2,08–2,62]) sí se solapa algo.
En la estación lluviosa el margen brazos − centro es casi nulo (0,009 FNU a 20 m; −0,233 a 10 m con todos los píxeles)
y el orden solo se mantiene en 5/9 años a 20 m y 0/9 (3/9 a ≥ 100 m) a 10 m: Guasabacoa es la mayor y Marimelena
iguala o supera a Atarés. Es decir, la jerarquía «brazos del sur > Marimelena ≈ centro > mar» es de la estación seca;
en la lluviosa solo se sostiene que la bahía es más turbia que el mar (centro − mar de 0,39 a 0,62 FNU).

### 27.2 Sensibilidad de los focos al umbral de z_c

**20 m** (mitades A/B: 51 y 62 escenas). Fuente: `resultados/umbrales_20m.json`.

| z_c ≥ | Estación | Grupos (en bahía) | S1–S5 a ≤ 80 m: observados / esperados por azar (p) | Controles pareados a ≤ 80 m: obs. / esp. | Rango percentil de profundidad (mediano) | Fracción < 2 m: focos / referencia | Replicación A→B (base) | B→A (base) | Regla (≥ 3× base y ≥ 0,30) |
|---|---|---|---|---|---|---|---|---|---|
| 2,5 | seca | 99 (8) | 5/5 / 1,47 (p = 0,0016) | 1/5 / 1,33 | 0,229 | 0,394 / 0,143 | 0,852 (0,217) | 0,855 (0,213) | se cumple |
| 2,5 | lluviosa | 82 (12) | 5/5 / 1,60 (p = 0,0030) | 0/5 / 1,49 | 0,107 | 0,619 / 0,113 | 0,843 (0,341) | 0,762 (0,255) | NO se cumple |
| 3,0 | seca | 67 (9) | 5/5 / 1,20 (p = 0,0005) | 0/5 / 1,10 | 0,198 | 0,486 / 0,151 | 0,837 (0,178) | 0,907 (0,162) | se cumple |
| 3,0 | lluviosa | 37 (10) | 5/5 / 1,36 (p = 0,0013) | 0/5 / 1,26 | 0,120 | 0,680 / 0,116 | 0,769 (0,233) | 0,552 (0,135) | se cumple |
| 3,5 | seca | 46 (7) | 5/5 / 1,06 (p = 0,0002) | 0/5 / 0,91 | 0,191 | 0,570 / 0,151 | 0,917 (0,132) | 0,882 (0,129) | se cumple |
| 3,5 | lluviosa | 14 (6) | 5/5 / 1,14 (p = 0,0004) | 0/5 / 1,00 | 0,133 | 0,724 / 0,124 | 0,714 (0,171) | 0,538 (0,089) | se cumple |
| 4,0 | seca | 34 (5) | 5/5 / 0,91 (p = 0,0001) | 0/5 / 0,77 | 0,189 | 0,652 / 0,152 | 0,895 (0,105) | 0,905 (0,100) | se cumple |
| 4,0 | lluviosa | 10 (4) | 5/5 / 0,92 (p = 0,0001) | 0/5 / 0,74 | 0,155 | 0,804 / 0,141 | 0,875 (0,141) | 0,500 (0,053) | se cumple |
| 5,0 | seca | 16 (4) | 5/5 / 0,71 (p = 0,0000) | 0/5 / 0,61 | 0,190 | 0,765 / 0,156 | 1,000 (0,075) | 1,000 (0,055) | se cumple |
| 5,0 | lluviosa | 4 (2) | 4/5 / 0,70 (p = 0,0004) | 0/5 / 0,47 | 0,184 | 0,846 / 0,160 | 0,600 (0,082) | 0,400 (0,020) | se cumple |

**10 m** (mitades A/B: 38 y 47 escenas). Fuente: `resultados_10m/umbrales_10m.json`.

| z_c ≥ | Estación | Grupos (en bahía) | S1–S5 a ≤ 80 m: observados / esperados por azar (p) | Controles pareados a ≤ 80 m: obs. / esp. | Rango percentil de profundidad (mediano) | Fracción < 2 m: focos / referencia | Replicación A→B (base) | B→A (base) | Regla (≥ 3× base y ≥ 0,30) |
|---|---|---|---|---|---|---|---|---|---|
| 2,5 | seca | 82 (8) | 5/5 / 1,55 (p = 0,0025) | 1/5 / 1,63 | 0,188 | 0,445 / 0,127 | 0,864 (0,273) | 0,988 (0,282) | se cumple |
| 2,5 | lluviosa | 43 (13) | 5/5 / 1,83 (p = 0,0064) | 1/5 / 1,91 | 0,080 | 0,569 / 0,093 | 0,943 (0,402) | 0,950 (0,400) | NO se cumple |
| 3,0 | seca | 52 (5) | 5/5 / 1,22 (p = 0,0007) | 1/5 / 1,30 | 0,145 | 0,580 / 0,131 | 0,917 (0,218) | 0,956 (0,236) | se cumple |
| 3,0 | lluviosa | 20 (12) | 5/5 / 1,39 (p = 0,0015) | 1/5 / 1,42 | 0,090 | 0,614 / 0,099 | 0,875 (0,277) | 0,875 (0,305) | NO se cumple |
| 3,5 | seca | 22 (5) | 5/5 / 1,06 (p = 0,0003) | 1/5 / 1,08 | 0,139 | 0,682 / 0,131 | 0,889 (0,168) | 1,000 (0,170) | se cumple |
| 3,5 | lluviosa | 8 (5) | 5/5 / 1,12 (p = 0,0005) | 1/5 / 1,14 | 0,115 | 0,642 / 0,117 | 0,727 (0,182) | 1,000 (0,188) | se cumple |
| 4,0 | seca | 14 (6) | 5/5 / 0,90 (p = 0,0001) | 1/5 / 0,91 | 0,144 | 0,716 / 0,131 | 1,000 (0,122) | 0,900 (0,137) | se cumple |
| 4,0 | lluviosa | 2 (1) | 5/5 / 0,87 (p = 0,0001) | 1/5 / 0,88 | 0,130 | 0,724 / 0,130 | 0,750 (0,147) | 0,667 (0,120) | se cumple |
| 5,0 | seca | 5 (2) | 5/5 / 0,63 (p = 0,0000) | 1/5 / 0,62 | 0,168 | 0,791 / 0,142 | 0,667 (0,080) | 0,800 (0,078) | se cumple |
| 5,0 | lluviosa | 2 (1) | 4/5 / 0,52 (p = 0,0003) | 1/5 / 0,49 | 0,177 | 0,792 / 0,150 | 1,000 (0,082) | 1,000 (0,063) | se cumple |


**Lectura.** (i) Profundidad: el rango percentil mediano es 0,08–0,23 y la fracción < 2 m es 0,39–0,85 frente a
0,09–0,16 en la referencia, a todos los umbrales y en las dos resoluciones: la conclusión de agua somera no depende
del 3,5. (ii) S1–S5 quedan a ≤ 80 m de un píxel caliente en todos los umbrales salvo S3 (lluviosa, z_c ≥ 5,0, 20 m:
995 m) y S2 (lluviosa, z_c ≥ 5,0, 10 m: 81 m), con 0,5–1,8 sitios esperados por azar. Cautela: S1–S5 salieron de la
detección preregistrada con las mismas escenas, así que no es una prueba independiente; los controles pareados quedan
lejos (0–1 de 5, como se espera por azar). (iii) Replicación: la regla (≥ 3× la base y ≥ 0,30) se cumple en todos los
umbrales salvo la estación lluviosa a z_c ≥ 2,5 (20 y 10 m) y a ≥ 3,0 (10 m); allí la cobertura base es 0,26–0,40,
3× la base ronda o supera 0,8–1,2 y la regla es casi imposible de cumplir con tasas de replicación de 0,76–0,95: es un
límite de la regla con umbrales bajos, no una caída de la replicación. (iv) Número de grupos: a 20 m en seca baja de
99 (z_c ≥ 2,5) a 16 (≥ 5,0), de 8 a 4 en la bahía; a umbrales altos quedan 1–6 grupos en la bahía. Conclusión: «los
focos están en los brazos someros del sur» no depende del umbral entre 2,5 y 5,0.

### 27.3 ¿Permite el ACOLITE instalado (clon d61c8de, 9/9/2026) la corrección de adyacencia RAdCor?

**Sí, sin ejecutarla.** (1) `config/defaults.txt:383–405`: bloque `radcor_*` (`radcor_kernel_radius=5.0`,
`radcor_max_vza=15`, `radcor_aot_estimate=tsdsf`, …). (2) `acolite/acolite/acolite_run.py:216–217`:
`atmospheric_correction_method == 'radcor'` → `ac.adjacency.radcor.radcor(l1r)`. (3)
`acolite/adjacency/radcor/radcor.py:453–457`: `S2A_MSI`, `S2B_MSI`, `S2C_MSI` con resolución 10 por defecto o la de
`s2_target_res` (10, 20 o 60 m). (4) Los ajustes PSF/SAF de S2 están en `data/Shared/RAdCor/psf/fit/` (117 ficheros cuyo
nombre contiene S2 o MSI). **Ojo:** el parámetro `adjacency_correction=True` solo activa GLAD
(`acolite_run.py:225–226`, `adjacency_correction_method == 'glad'`, solo con DSF); RAdCor no se añade al DSF, lo
sustituye (`atmospheric_correction_method=radcor`). Usarlo cambiaría el método congelado: requeriría una fila nueva en
la secc. 14 y reprocesar las 113 / 85 escenas. No se ha ejecutado.

### 27.4 Turbidez in situ publicada para la bahía de La Habana

**No he encontrado ninguna.** Búsquedas (17/11/2026): OpenAlex mediante la herramienta de referencias, 7 consultas de búsqueda
(«Havana Bay turbidity suspended solids water quality», «bahía de La Habana calidad del agua transparencia sólidos
suspendidos», «Secchi disk Havana Bay Cuba», «bahía de La Habana», «Havana Bay Cuba pollution sediments water
chlorophyll», «Martínez Varona clorofila bahía de La Habana», «Cuban bays remote sensing turbidity Sentinel-2 Landsat
suspended particulate matter Cuba») más la comprobación de un registro, y 3 búsquedas web (turbidez / sólidos suspendidos / Secchi /
REDCAM / CIMAB). Hallazgos: (a) Valle-Pombrol, Ávila-Alonso, Muñoz-Caravaca, Cárdenas-Ortiz y Castro-Rodríguez (2017),
*Variación espacio-temporal del coeficiente de atenuación de la luz en la bahía de Cienfuegos, Cuba*, Revista de
Investigaciones Marinas 37(1): 40–51, sin DOI (https://iris.polito.it/handle/11583/2869974, acceso 17/11/2026): Secchi,
sólidos suspendidos y clorofila en 16 estaciones, 2009–2014, **solo Cienfuegos**, no La Habana; sirve como comparador
regional. (b) Vega, Capetillo Piñar, Lopeztegui Castillo y Martínez-Daranas (2013), *Variación espacio-temporal de la
turbidez y calidad en cuerpos de agua marina de uso pesquero, región norcentral de Cuba, 2008–2010*
(http://hdl.handle.net/1834/12675; título y autores comprobados en OpenAlex): **no pude abrir el registro** (la página de
AquaDocs devolvió una página vacía), así que no sé si incluye La Habana ni qué variables ni cuántas muestras; Alex
puede descargarlo y comprobarlo. (c) Candidata no leída para el argumento de agua somera: Castro, Pereira, Dias y Lopes
(2026), *Assessing the Reliability of Sentinel-2 for Turbidity Estimation in a Shallow Coastal Lagoon*, Remote Sensing
18(13): 2176, doi:10.3390/rs18132176 (solo vi el título). Los estudios in situ ya conocidos de la bahía (secc. 21 y la
revisión del 16/11) son por estación y de clorofila, bacterias o sedimentos; no se ha confirmado que den turbidez,
Secchi o sólidos suspendidos. Consecuencia: el artículo no puede decir nada sobre valores absolutos de turbidez.

### 27.5 Figuras (10 m, caja del área de estudio)

Archivos en `productos_publicos/figuras/` (PDF con las capas ráster incrustadas y el resto en vectores; paleta viridis y
Okabe-Ito, seguras para daltonismo; inglés; sin fronteras administrativas; la nota de límites para el pie está en
`NOTA_pies_de_figura.txt`): **a** `fig_a_climatologia_10m.pdf` y `.csv.gz` (mediana por píxel, seca y lluviosa, escala
común 2–98 percentil); **b** `fig_b_perfil_brazos.pdf` y `.csv` (perfil por el eje de cada brazo: camino más corto por el
agua desde la entrada del canal (361 000 E, 2 560 900 N) hasta el píxel más lejano de la zona, corredor de ± 150 m, bins
de 250 m, mediana entre escenas con banda de IC 95 % por bootstrap de escenas); **c** `fig_c_focos_10m.pdf` y `.csv`
(grupos con z_c ≥ 3,5, color = nº de mitades A/B en que replican, forma = profundidad de la carta de 1887 a ≤ 80 m,
isóbata de 2 m, S1–S5 y los puntos de control P01–P04 y P10). Cifras de la figura b:

| Brazo | Estación | Bin (m) | Mediana (FNU) | IC 95 % | Escenas |
|---|---|---|---|---|---|
| atares | seca | 125 | 1,26 | [1,12–1,46] | 42 |
| atares | seca | 1125 | 1,51 | [1,22–1,64] | 40 |
| atares | seca | 2125 | 2,37 | [2,09–2,55] | 44 |
| atares | seca | 3125 | 2,60 | [2,32–2,99] | 44 |
| atares | seca | 4375 | 4,60 | [3,87–5,35] | 39 |
| atares | lluviosa | 125 | 2,77 | [2,52–3,12] | 36 |
| atares | lluviosa | 1125 | 2,59 | [1,93–3,02] | 37 |
| atares | lluviosa | 2125 | 2,98 | [2,42–3,51] | 39 |
| atares | lluviosa | 3125 | 2,73 | [2,60–3,26] | 40 |
| atares | lluviosa | 4375 | 4,16 | [3,10–5,47] | 39 |
| guasabacoa | seca | 125 | 1,26 | [1,12–1,46] | 42 |
| guasabacoa | seca | 1125 | 1,51 | [1,22–1,64] | 40 |
| guasabacoa | seca | 2125 | 2,37 | [2,09–2,56] | 44 |
| guasabacoa | seca | 3125 | 2,61 | [2,44–2,95] | 44 |
| guasabacoa | seca | 5125 | 2,66 | [2,44–3,23] | 39 |
| guasabacoa | lluviosa | 125 | 2,77 | [2,52–3,12] | 36 |
| guasabacoa | lluviosa | 1125 | 2,59 | [1,93–3,02] | 37 |
| guasabacoa | lluviosa | 2125 | 2,98 | [2,42–3,51] | 39 |
| guasabacoa | lluviosa | 3125 | 3,02 | [2,75–3,84] | 39 |
| guasabacoa | lluviosa | 5125 | 3,94 | [2,70–5,09] | 31 |

Grupos de la figura c (10 m, caja del área de estudio): 13 ; en la bahía: 8 ; replican en 2 de 2 mitades: 12 ; en 1: 1 ; en 0: 0
En la bahía: 8 grupos; profundidad mediana a ≤ 80 m (m): [0.46, 0.61, 1.54, 1.55, 2.14, 2.16, 2.61, 3.35]

**Lectura.** Los dos corredores comparten los primeros ~3 km (canal y bahía central), por eso las curvas coinciden
hasta ahí; el contraste entre brazos está solo en los últimos 1,5–2 km. En seca la mediana sube de 1,26 FNU a 125 m de
la entrada hasta 2,60 FNU a 3,1 km, y llega a 4,60 [3,87–5,35] en el último bin de Atarés (4,4 km) y a 2,66 [2,44–3,23]
en el de Guasabacoa (5,1 km). En lluviosa la serie es más ruidosa (2,77 en el primer bin; 4,16 en Atarés y 3,94 en
Guasabacoa al final, con IC amplios). Figura c: 13 grupos en la caja, 8 en la bahía; 12 replican en 2 de 2 mitades y 1
en una; los 8 de la bahía tienen una profundidad mediana de la carta de 0,46–3,35 m (4 por debajo de 2 m, 6 por debajo
de 2,2 m), frente a ≈ 6 m de la referencia. Los otros 5 están fuera de la bahía, junto a la boca del canal.


## 28. Aclaraciones y pruebas pedidas por el chat del artículo, ítems 6–9 (18/11/2026)

Definidas en la secc. 14 el 18/11, antes de calcularlas (todo EXPLORATORIO; no se cambia ningún umbral). Scripts:
`scripts/27_aclaraciones.py` (ítem 9) y `scripts/28_fondo.py` (ítem 6). Salidas: `resultados_10m/aclaraciones_10m.json`,
`resultados/aclaraciones_20m.json`, `datos/aclaraciones_10m.log`, `datos/aclaraciones_20m.log`,
`resultados_10m/fondo_10m.json`, `resultados/fondo_20m.json`, `datos/fondo_10m.log`, `datos/fondo_20m.log`.

### 28.1 Ítem 9. Aclaraciones sobre la secc. 27

**(a) Los 13 grupos de la fig. c frente a los 22 y 8 de la tabla 27.2** (z_c ≥ 3,5, 10 m). Son contadores distintos de la
misma lista de grupos (conectividad 8, tamaño mínimo `MIN_PX_GRUPO` = 1600 m² = 16 px a 10 m, heredado de
`persistencia.grupos`; la fig. c no añade ningún filtro de tamaño):

| Contador | seca | lluviosa |
|---|---|---|
| Componentes conexas sin tamaño mínimo (solo para ver el efecto del filtro) | 957 | 1100 |
| Grupos con el tamaño mínimo, en **toda la rejilla** (mar abierto incluido): columna «grupos» de la tabla 27.2 | 22 | 8 |
| … de ellos con el centroide dentro de la caja de la figura (E 360000–365000, N 2555900–2561900): **fig. c** | 7 | 6 |
| … de ellos con el primer píxel en la ventana de la bahía (columna `in_bay` del CSV de la fig. c) | 4 | 4 |
| … de ellos con algún píxel en la ventana de la bahía | 5 | 5 |
| Grupos de `grupos(hot & bahia)`, es decir, recalculados tras recortar a la ventana: columna «grupos_bahia» de la tabla 27.2 | 5 | 5 |

Por tanto 13 = 7 + 6 son los 30 grupos de la rejilla (22 + 8) menos los 17 que quedan fuera de la caja (15 + 2, todos en
mar abierto: N > 2 561 900, E < 360 000 o E > 365 000). De los 13, 8 (4 + 4) tienen su primer píxel en la ventana de
la bahía; los otros 5 (seca 15, 16, 17; lluviosa 2, 3) están en el canal exterior junto a la boca, fuera de la ventana
(E < 361139 o N > 2561392). La diferencia entre 8 (fig. c) y 5 + 5 = 10 (tabla 27.2) viene de que `grupos_bahia`
recorta primero y cuenta después: los grupos seca 15 (28 px dentro) y lluviosa 2 (17 px dentro) cruzan el borde norte de la
ventana y, ya recortados, superan los 16 px; en la fig. c se asignan por su primer píxel y quedan «fuera». Lista completa
de los 30 grupos (id, tamaño, E, N, banderas) en `datos/aclaraciones_10m.log`.

**(b) Límites exactos de las cinco zonas** (UTM 17N, EPSG:32617; `zonas()` de `scripts/24_gradiente.py`; la ventana de la
bahía es el rectángulo E 361139–365896, N 2556342–2561392 de `src/geo.py`, que `escenas.mascara_bahia` aplica **sin
recortar al agua**; después se usa solo el agua):

| Zona | Definición (en este orden de asignación) | Píxeles de agua (10 m) | Área | Caja del agua (E; N) |
|---|---|---|---|---|
| mar | fuera de la ventana y agua (incluye el canal exterior; ventana ampliada de la climatología E 356630–369030, N 2555170–2567430 a 20 m) | 723 363 | 72,34 km² | 356625–369025; 2557325–2567445 |
| marimelena | en la ventana y E > 363 600 | 5 521 | 0,552 km² | 363605–364345; 2558525–2560025 |
| atares | en la ventana, N < 2 558 800, E < 363 300 y E < 362 350 − 0,25·(2 558 800 − N) | 6 539 | 0,654 km² | 361145–362345; 2557375–2558795 |
| guasabacoa | en la ventana, N < 2 558 800, E < 363 300 y E ≥ 362 350 − 0,25·(2 558 800 − N) | 13 024 | 1,302 km² | 362105–363155; 2556615–2558795 |
| bahia_centro_y_canal | el resto de la ventana (N ≥ 2 558 800 con E ≤ 363 600, y la franja 363 300 ≤ E ≤ 363 600 al sur de 2 558 800) | 20 088 | 2,009 km² | 361145–363595; 2558575–2561385 |

Suma de las cuatro zonas de la bahía: 45 172 px = **4,517 km²** a 10 m (11 287 px a 20 m = 4,515 km²). La recta que separa
Atarés de Guasabacoa va de (E 362 350, N 2 558 800) [lat 23,1323, lon −82,3444] a (E 361 735,5, N 2 556 342) [lat 23,11005,
lon −82,35018]; el corte sur de los brazos es E = 363 300 [lat 23,13238, lon −82,33512 en N 2 558 800]. Coordenadas
geográficas de los vértices en `resultados_10m/aclaraciones_10m.json`. Las zonas son rectángulos y una recta, no polígonos
dibujados sobre la costa: sus límites no siguen ninguna isobata ni accidente.

**(c) Fig. b: la banda gris.** Sí: cada curva lleva su IC 95 % como banda semitransparente (alfa 0,25; naranja Atarés, azul
Guasabacoa); donde las dos bandas se solapan los colores se mezclan y se ve gris; donde solo hay una, queda naranja o azul.
No es una magnitud aparte. Precisión que no estaba en la sec. 27: en el tramo común (hasta ~2,6 km) las **medianas son
idénticas** (mismos píxeles; `fig_b_perfil_brazos.csv`), pero cada brazo remuestrea por separado, así que los IC no coinciden
del todo, solo casi. Los IC de los dos brazos no se solapan en cuatro bines: lluviosa 3 625 y 3 875 m (Guasabacoa mayor) y
seca 4 125 y 4 375 m (Atarés mayor); en los demás se solapan. Ruta: `productos_publicos/figuras/fig_b_perfil_brazos.pdf/.csv`.

**(d) Rejilla de profundidad de la carta de 1887: NO va al depósito (decisión de Alex, 18/11).** La rejilla se generó (GeoTIFF
float32 a 20 m, 238 × 253, y a 10 m, 476 × 505; nodata −9999; 12 237 y 49 036 píxeles con dato; 0,3–17,3 m) pero se guarda en
`datos/no_publicar_carta1887/` (carpeta ignorada por git, fuera de `productos_publicos/`), junto con su README y
`SHA256SUMS_profundidad`; `scripts/27_aclaraciones.py` escribe ahí. Motivo: la superficie es derivada y sus condicionantes son
los de la procedencia del repo del modelo (`Modelo-hidrodin-mico`, commit `72095a8`, `docs/procedencia_datos.md`; `batimetria_1887.nc`,
md5 `b2872f94fe9486a20a39e6d8c565f86c`): las posiciones de los 1514 sondeos dependen de la georreferenciación de la carta de 1889 de
Harvard, cuyo FGDC dice «For educational, non-commercial use only»; la costa viene de OSM (ODbL); GEBCO es de dominio público con
cita; la carta de 1898 figura como «No known copyright restrictions». La decisión de licencia de esa superficie sigue pendiente en el
repo del modelo. Si algún texto o tabla del depósito usa la profundidad de la carta, debe citar ese repo y ese commit y no
redistribuir la rejilla. Los ficheros que siguen en `productos_publicos/figuras/` y derivan de ella se tratan en la secc. 28.5.

### 28.2 Ítem 6. ¿Se ve el fondo en los focos?

Escenas: 10 m, 85 aceptadas (44 seca, 41 lluviosa; todas con `rojo`), mediana por píxel con n_obs ≥ 10; 20 m, las 30 escenas de
la secc. 26 (19 seca, 11 lluviosa), n_obs ≥ 5, con la banda del borde. Focos z_c ≥ 3,5 dentro de la ventana de la bahía;
profundidad 0,5–3 m de la carta de 1887; referencia emparejada por distancia a costa (± 20 m), > 80 m de cualquier foco y
profundidad ± 0,25 m. IC 95 % por bootstrap de bloques de 100 m (pocos bloques en los focos: los IC son aproximados).

**10 m, medianas de todas las escenas de cada estación** (definición de la secc. 14; la primera ejecución, `datos/fondo_10m_primera_pasada.log`, dio lo mismo salvo ≤ 0,01 en los IC de lluviosa, por el remuestreo):

| Estación | ρ(rojo, prof.) focos [IC] | ρ(rojo, prof.) referencia [IC] | Referencia informativa |
|---|---|---|---|
| seca (417 focos, 6 739 ref.) | −0,21 [−0,59; 0,10] | −0,00 [−0,15; 0,15] | no |
| lluviosa (381 focos, 5 765 ref.) | −0,04 [−0,32; 0,26] | −0,03 [−0,18; 0,11] | no |

Regla prefijada: la prueba solo informa sobre el fondo si la referencia da ρ ≤ −0,2 con IC que excluye 0 (en bruto y tras
restar la banda de distancia). **No se cumple en ningún caso**, a 10 ni a 20 m (referencia: ρ entre −0,12 y +0,10, IC siempre
incluye 0). Es decir, con esta carta y estas reflectancias no se detecta relación rojo–profundidad en el agua somera de la bahía:
o el fondo no se ve en 0,5–3 m, o el error de la carta (σ 0,9 m, mayor que la mitad del rango) la borra. **La prueba no puede
afirmar ni descartar que se vea el fondo.**

**Forma espectral de los focos frente a su referencia emparejada** (razón focos/referencia; < 1 = el foco tiene menor
razón). Profundidad 0,5–2 m; entre paréntesis el IC 95 % de la diferencia de log-razones:

| Caso | verde/rojo | NIR/rojo | borde/rojo | rojo (exceso) |
|---|---|---|---|---|
| 10 m seca, todas las escenas (n = 277) | 0,76 (−0,42; −0,24) | 0,79 (−0,33; −0,17) | — | 2,18 |
| 10 m lluviosa, todas las escenas (n = 296) | 0,81 (−0,26; −0,16) | 0,83 (−0,24; −0,11) | — | 1,72 |
| 20 m seca (n = 85) | 0,72 (−0,44; −0,27) | 0,83 (−0,28; −0,13) | 0,97 (−0,08; 0,08) | 2,41 |
| 20 m lluviosa (n = 97) | 0,83 (−0,25; −0,15) | 0,81 (−0,27; −0,12) | 0,88 (−0,17; −0,08) | 1,76 |

El exceso de ρ_rojo **no es un resultado**: los focos se eligen por ρ_rojo alto (declarado en la secc. 14). Y la razón verde/rojo
y NIR/rojo también están sesgadas a la baja por la misma selección (el rojo está en el denominador), de modo que esa comparación no basta.

**Variante cruzada (añadida el 18/11 DESPUÉS de ver la primera ejecución, para quitar ese sesgo):** focos elegidos en una mitad
(A = 2016–2020, B = 2021–2025; `resultados_10m/zc_mitades.npz`) y reflectancias medidas en las escenas de la otra, con n_obs ≥ 8
por mitad y estación (`NMIN_MITAD` en el script; se fijó al añadirla). Solo a 10 m (a 20 m no hay mitades calculadas). Profundidad
0,5–2 m:

| Focos de → espectros de | verde/rojo | NIR/rojo | rojo (exceso, razón) | ρ(rojo, prof.) focos [IC 95 %] | ρ referencia |
|---|---|---|---|---|---|
| seca, A → B (n = 189) | 0,80 | 0,83 | 2,01 | −0,04 [−0,39; 0,26] | −0,02 |
| seca, B → A (n = 203) | 0,70 | 0,84 | 2,36 | −0,36 [−0,58; 0,04] | 0,03 |
| lluviosa, A → B (n = 301) | 0,89 | 0,85 | 1,44 | −0,46 [−0,65; −0,11] | −0,12 |
| lluviosa, B → A (n = 114) | 0,77 | 0,89 | 1,74 | −0,20 [−0,53; 0,43] | 0,06 |

(La columna de ρ usa 0,5–3 m. Todos los IC de verde/rojo y de NIR/rojo en 0,5–2 m excluyen 0; los de 2–3 m, no siempre; cifras
completas en `resultados_10m/fondo_10m.json`.)

**Lectura.** (i) Con los focos y los espectros tomados de datos independientes, el exceso de rojo sobre la referencia a igual
distancia de costa y profundidad **se mantiene** (razón 1,4–2,4, IC que excluye 1 en los cuatro casos): los focos no se
explican por «estar a esa profundidad», dentro de la precisión de la carta. (ii) La razón verde/rojo de los focos es menor que la
de la referencia (0,70–0,89 a 0,5–2 m; también en datos independientes). Un fondo claro y somero subiría el verde más que el rojo,
es decir, **lo contrario** de lo observado; sí encaja con agua con sedimento en suspensión. A 20 m la razón borde/rojo es ≈ 1
en seca y 0,88 en lluviosa (el NDCI ya salió no concluyente, secc. 26). (iii) Los focos muestran una tendencia negativa de
ρ_rojo con la profundidad (−0,04 a −0,46; solo un IC excluye 0 a 10 m; a 20 m, seca da −0,34 [−0,58; −0,14] pero lluviosa +0,11 [−0,14; 0,37]), mientras que la
referencia está en torno a 0. Eso es compatible con el fondo asomando en los focos, pero igual de compatible con que haya más
resuspensión donde hay menos agua; la prueba no separa las dos cosas. **Conclusión para el artículo:** no se puede demostrar
que el fondo no contribuye, pero el único indicio espectral que habría delatado un fondo brillante (razón verde/rojo mayor) va en
sentido contrario, y el exceso de rojo se replica con profundidad emparejada. Debe decirse como «no hay indicio espectral de
fondo, la prueba tiene poca potencia con una carta de 1887», no como «descartado». Límites: carta de 1887 con σ 0,9 m (el
emparejamiento por ± 0,25 m es nominal); profundidad actual desconocida; sin reflectancia de fondo medida; sin tipo de fondo
(arena, fango, vegetación) ni material en suspensión medido; no se ha aplicado ninguna corrección de adyacencia más que la ya
descrita en las secc. 6–11.

### 28.3 Ítem 7. Informe JICA y área de la bahía

- La ficha `https://openjicareport.jica.go.jp/619/619/619_606.html` (consultada el 18/11/2026) es un listado de la serie
  «Cuba – Pollution / Environmental engineering», no un solo informe. El informe final es de **marzo de 2004**: «The
  development study on the improvement of sewerage and drainage system for the Havana Bay in the Republic of Cuba: final report»,
  JICA y Nihon Suido Consultants Co., Ltd.; Vol. 1 Executive summary
  (`https://openjicareport.jica.go.jp/619/619/619_606_11767191.html`, PDF `https://openjicareport.jica.go.jp/pdf/11767191_03.pdf`),
  Vol. 2 Main report (`.../619_606_11767209.html`), y versión en español, Vols. 4 y 5. En la misma ficha hay también un informe
  previo («キューバ国 ハバナ湾汚染源対策調査事前調査報告書及び予備調査報告書», 国際協力事業団, 2002.4); si el artículo cita «el informe JICA», el
  año es 2004 (final) salvo que se cite el de 2002.
- Cifra publicada (Vol. 1, resumen y p. S-1, §1.1.1; leída el 18/11/2026): «Havana Bay has an area of 5.0 km2, an average water
  depth of 9 meters, and a capacity of 47 million m3» y, en p. S-6 (§1.3.1), «The average and maximum water depth of the bay is 9
  and 17 meters respectively». El texto llega a través de una lectura automática del PDF; las dos frases se obtuvieron literales
  y coinciden. 5,0 km² × 9 m = 45 millones de m³, no 47: el informe da ambas cifras y no se concilian. No es un área de ventana ni de
  máscara de agua; el informe no dice cómo se midió.
- Comparación: nuestra máscara de agua (ventana de la bahía, 20 y 10 m) = **4,52 km²** (≈ 90 % de 5,0 km²); la malla del modelo
  (cartas + OSM), 4,91 km² (repo del modelo, `docs/articulo/cifras.md`; ≈ 98 %). **No se pudo confirmar de dónde sale el «~5,2 km²»
  del borrador del modelo**; no aparece en JICA. Por qué faltan ~0,5 km² frente a JICA no está comprobado: hipótesis (no
  comprobadas) son píxeles de borde mezclados con tierra, muelles y astilleros que la máscara de agua excluye, y el recorte de la
  ventana en el canal exterior; la profundidad media de 9 m de JICA es mayor que los ≈ 6 m de la
  referencia de la malla en nuestros píxeles, pero no están medidas sobre la misma zona (la malla cubre solo la bahía interior).
- Frase prudente para el artículo: «The bay covers about 5 km² (JICA & Nihon Suido Consultants, 2004); the Sentinel-2 water mask
  used here covers 4.5 km².» Referencia: Japan International Cooperation Agency and Nihon Suido Consultants Co., Ltd. (2004). The
  development study on the improvement of sewerage and drainage system for the Havana Bay in the Republic of Cuba. Final report,
  Vol. 1 Executive summary. https://openjicareport.jica.go.jp/619/619/619_606_11767191.html (accessed 2026-11-18). No tiene DOI.

### 28.4 Ítem 8. Los productos del modelo no han cambiado desde `69728b5`

Salida de la comprobación (18/11/2026, repo `Vertidos-recurrentes`):

```
git diff --stat 69728b5 HEAD -- productos_publicos            (vacío)
shasum -a 256 -c SHA256SUMS : anomalias.nc, costa.geojson, escenas.csv, focos.csv, mascara_agua.tif,
                              persistencia_anomalias.tif, pixeles_comparacion_modelo.csv, rejilla.npz: OK (8 de 8)
rejilla.npz                        69728b5=de762c763672365b ahora=de762c763672365b IGUAL
persistencia_anomalias.tif         69728b5=df51486d0cebef10 ahora=df51486d0cebef10 IGUAL
pixeles_comparacion_modelo.csv     69728b5=ece325c48db0fb4e ahora=ece325c48db0fb4e IGUAL
README.md                          69728b5=aa95d70b60c721b3 ahora=aa95d70b60c721b3 IGUAL
repo del modelo datos/sentinel2/   rejilla.npz de762c763672365b y persistencia_anomalias.tif df51486d0cebef10: idénticos a los de aquí
```

El mapa de frecuencia a 20 m (`rejilla.npz` y `persistencia_anomalias.tif`) y `pixeles_comparacion_modelo.csv` (8908 píxeles, 145
bloques) son idénticos byte a byte a los de `69728b5`; los dos primeros también a las copias de `Modelo-hidrodin-mico/datos/sentinel2/`
(última entrega del repo del modelo: `8772c85`, que solo corrigió la nomenclatura de `focos.csv`). El CSV de píxeles no tiene copia
en el repo del modelo (la búsqueda por nombre no encontró ninguna): allí se reconstruye con `pixeles()` de
`scripts/comparacion_s2.py`, así que no se ha podido comparar ese fichero con una copia. Desde `69728b5` solo se han añadido ficheros
(`productos_publicos/figuras/`); ninguno modifica los entregados. (Las rejillas de profundidad se han sacado de `productos_publicos/`, secc. 28.1 d.)

### 28.5 Qué del depósito deriva de la carta de 1887 (18/11/2026)

Comprobación por búsqueda de «profundidad», «1887», «depth», «chart», «batimetr» y «bathym» en `productos_publicos/` (README,
CSV, notas), `README.md` y `LICENSE*`. Quedan tres elementos que dependen de la carta, todos en `productos_publicos/figuras/`:
`fig_c_focos_10m.csv` (columna `median_chart_depth_80m_m`, 13 filas), `fig_c_focos_10m.pdf` (isóbata de 2 m y forma del símbolo según
la profundidad) y `NOTA_pies_de_figura.txt` (pie de la fig. c). Ningún README ni CSV del depósito menciona la rejilla de profundidad;
el CSV no puede llevar la referencia en la propia tabla; el pie sí la llevaba sin apuntar al repo del modelo y se ha corregido
(`scripts/26_figuras.py` y el fichero): ahora cita `Modelo-hidrodin-mico`, commit `72095a8`, `docs/procedencia_datos.md`, y dice que la
rejilla no se redistribuye. `escenas.csv` salió en la búsqueda solo por una cadena de un identificador, no por la carta. Además, los
JSON de `resultados/` y `resultados_10m/` (`batimetria_*`, `umbrales_*`, `fondo_*`, `aclaraciones_*`) llevan estadísticos de profundidad
agregados; no están en `productos_publicos/`, pero quedan en el repo y habría que decidir si se publican con él.


## 29. Petición 2 del chat del artículo (18/11/2026): resultados

Reglas congeladas en la fila de 2026-11-18 de la secc. 14 (`PETICION_CHAT_TECNICO_2.md`, sha256 fe576fe6fe54db5c…). Estado a la fecha de este texto: **B, C y D calculados; A pendiente** (no se ha descargado ni procesado ninguna escena de 2026 porque falta la confirmación del commit de la secc. 14). B, C y D son exploratorios; A es confirmatorio y no existe todavía.

### 29.1 Bloque A. Prueba confirmatoria con escenas de 2026

**Estado: calculado a 20 y 10 m.** Corte: commit `c4d1ea7` (2026-11-18 14:02 +01:00, fila de la secc. 14 con las reglas). Catálogo CDSE T17QLF, órbita R097, adquisiciones del 2026-01-02 al 2026-11-13 (`datos/crudo_2026/catalogo.json`, 79 productos, 57 GB). Mismos ajustes congelados y mismo ACOLITE (d61c8de), mismas reglas de QC de la secc. 6, y mismos focos, climatología, agua y distancia a costa del archivo 2016–2025 (no se recalcula nada con 2026). Scripts: `35_bucle_2026.py` (descarga y proceso), `36_qc_2026.py`, `30_contraste_escenas.py --etiqueta 2026`, `37_prueba_A.py`. Salidas: `resultados/escenas_qc_2026.csv`, `resultados/contraste_escenas_20m_2026.csv`, `resultados/contraste_placebo_20m_2026.npz`, `resultados/prueba_A_20m.json`.

Procesado a 20 m: 79 productos, 75 con producto y 4 sin él. Los 4 fallos son segundas versiones del mismo paso (22 ene, 16 feb, 27 abr) o recorte 100 % sin datos (29 oct); la otra versión de cada fecha sí dio producto. Quedan 75 escenas únicas; **13 aceptadas** (8 secas, 5 lluviosas), 17,3 %, frente al 17,7 % del archivo (113 de 637). Aceptadas: 2026-01-04, 01-17, 02-11, 02-16, 02-21, 03-15, 03-28, 09-11, 09-14, 10-09, 10-14, 10-29, 11-03.

Resultados a 20 m (reglas de la secc. 14; no se ha cambiado ningún umbral):

- **A1 (contraste de focos).** Todas las escenas (n=13): d>0 en 13/13, p del signo 0,00012, d mediana 1,088 FNU, p95 de la mediana de los 500 placebos 0,038; **cumple**. Seca (n=8, justo el mínimo): 8/8, p=0,0039, d mediana 1,080, p95 placebo 0,045; **cumple**. Lluviosa: 5 escenas usables, **insuficiente** (mínimo 8). Referencia 2016–2025: d mediana 1,93 (todas), 2,03 (seca), 1,69 (lluviosa). La d de 2026 es aproximadamente la mitad de la del archivo en seca; no es parte de la regla, pero se declara.
- **A2 (jerarquía seca, `orden()`).** 8 escenas secas (≥5): variante «todos» **cumple** (brazos−medio +0,224; medio−mar +1,407), variante «a100m» **cumple** (+0,161; +1,485). 2 de 2 a 20 m; la regla de ≥3 de 4 necesita también los dos de 10 m.
- **A3 (bahía>mar por estación, ≥5 escenas).** Seca (n=8): max(Marimelena, centro)−mar = +1,407 (todos) y +1,485 (a100m); centro−mar igual. Lluviosa (n=5, justo el mínimo): +0,972 y +1,110. Positivo en las 4 combinaciones de esta resolución.

Límites: 13 escenas son pocas (seca 8 y lluviosa 5, justo en el mínimo de A3 y por debajo del de A1 en lluviosa); tres de las 13 son de febrero (11, 16, 21) y tres de octubre (09, 14, 29). Las escenas de 2026 no entran ni en los focos ni en la climatología, que salen del archivo 2016–2025 (diseño confirmatorio). La d de 2026 es del orden de la mitad de la del archivo; la regla no lo pide, pero se declara.

**A 10 m (calculado el 2026-11-19).** Mismo catálogo y mismo procesado a 10 m (`datos/bucle_2026_10m.log`: 75 escenas, 4 fallos iguales que a 20 m). Aceptadas a 10 m: **11** (6 secas, 5 lluviosas), las mismas que a 20 m salvo 2026-02-21 y 2026-11-03, que a 10 m no llegan al 60 % de agua válida. Salidas: `resultados_10m/escenas_qc_2026.csv`, `resultados_10m/contraste_escenas_10m_2026.csv`, `resultados_10m/contraste_placebo_10m_2026.npz`, `resultados_10m/prueba_A_10m.json`.

- **A1, focos de 10 m.** Todas (n=11): d>0 en 11/11, p del signo 0,00049, d mediana 1,046 FNU frente a 0,021 del p95 de los placebos; **cumple**. Seca (n=6) y lluviosa (n=5): **insuficiente** (mínimo 8), así que a 10 m A1 no se puede evaluar por estación. Referencia 2016–2025 a 10 m: d mediana 1,87 (todas), 2,15 (seca), 1,51 (lluviosa).
- **A1, 13 grupos de la secc. 28 (a 10 m).** Todas (n=11): d>0 en solo 6/11, p del signo 0,5, d mediana 0,56 FNU (el p95 del placebo, 0,018, sí se supera); **no cumple** porque falla el test del signo. Por estación, insuficiente. Es coherente con la referencia 2016–2025, donde los 13 grupos en seca tampoco pasan el signo (26/44, p=0,146; d mediana 0,19), mientras que en lluviosa sí (37/41). Se declara tal cual: los focos agregados confirman; los 13 grupos por separado no.
- **A2 a 10 m (6 secas, ≥5).** «todos» **cumple** (brazos−medio +0,181; medio−mar +1,208); «a100m» **cumple** (+0,133; +1,288). **Con los de 20 m, A2 cumple en 4 de 4 variantes** (regla: ≥3 de 4): **confirmada**.
- **A3 a 10 m.** Seca (n=6): max(Marimelena, centro)−mar = +1,208 («todos») y +1,288 («a100m»); lluviosa (n=5): +0,506 y +0,625; centro−mar idéntico. Positivo en las 4 combinaciones de 10 m y en las 4 de 20 m: **bahía>mar confirmada en las dos estaciones, a las dos resoluciones** (con n=5 en lluviosa, justo el mínimo).

**Veredicto de A (fijado por las reglas congeladas).** A1 con focos: cumple a 20 m (todas y seca) y a 10 m (todas); la estación lluviosa a las dos resoluciones y la seca a 10 m quedan «insuficiente». A1 con los 13 grupos a 10 m: no cumple. A2: cumple (4/4). A3: cumple (8/8 combinaciones positivas). No se ha cambiado ningún umbral ni se ha descartado ninguna escena de 2026 por otra razón que el QC de la secc. 6.

Límites declarados: pocas escenas (11–13), con la lluviosa y la seca de 10 m por debajo del mínimo de A1; la d de 2026 es del orden de la mitad de la del archivo (1,05–1,09 frente a 1,9–2,0 FNU); los 13 grupos no se confirman. Las escenas de 2026 no intervienen en los focos ni en la climatología.

### 29.2 Bloque B. Profundidad frente a distancia a la costa (exploratorio)

Scripts y salidas: `scripts/29_profundidad_distancia.py` → `resultados/prof_dist_20m.json`, `resultados_10m/prof_dist_10m.json` (logs en `datos/prof_dist_{20,10}m.log`). Bootstrap por bloques de 200×200 m, 2000 réplicas, semilla 20261118. B1 (bandas × clases de profundidad × estación × resolución) y B3 están en los JSON con IC.

B2 (regresión de rangos de z_c sobre rango de profundidad, rango de distancia y fracción de tierra a 500 m; coeficientes estandarizados):

- 20 m, seca (n=10297): profundidad −0,207 [−0,338; −0,062]; distancia −0,005 [−0,159; 0,146]; tierra −0,076 [−0,245; 0,098].
- 20 m, lluviosa (n=10126): profundidad −0,270 [−0,375; −0,155]; distancia 0,051 [−0,062; 0,168]; tierra −0,033.
- 10 m, seca (n=39890): profundidad −0,244 [−0,367; −0,117]; distancia 0,016 [−0,141; 0,189].
- 10 m, lluviosa (n=40469): profundidad −0,270 [−0,375; −0,167]; distancia 0,102 [−0,016; 0,223].

Lectura: a distancia fija, más profundidad va con menos z_c y el IC excluye 0 en las cuatro combinaciones. El coeficiente de la distancia es ≈0, pero eso es casi por construcción: z_c ya está corregido por distancia a la costa. Por eso se añadió **B2b (post hoc, no estaba en la petición; se añadió después de ver B2)**, con la mediana climatológica sin corregir como respuesta: profundidad −0,345 (seca) y −0,365 (lluviosa) a 20 m, −0,373 y −0,383 a 10 m, todos con IC que excluyen 0; distancia +0,22 a +0,38, y ninguno de los cuatro IC cruza 0 (p. ej. 20 m seca [0,065; 0,371]). La profundidad y la distancia están correlacionadas (Spearman 0,441 en seca a 20 m, IC [0,338; 0,543]), de modo que no se separan del todo.

B3 (píxeles a menos de 60 m de la costa): los de más de 5 m de profundidad están sobre todo en el canal y junto a los muelles (fracción en zona portuaria de OSM entre 0,07 y 0,49 según banda y resolución; ejemplo 10 m, 20–40 m, >5 m: 0,257) y tienen z_c mediana negativa y pocos píxeles calientes (fracción caliente de 0 a 3,1 % a 20 m y de 0 a 7,5 % a 10 m; solo las bandas de 20–60 m a 10 m dan ≤ 0,3 %; corregido el 2026-11-19, ver 29.7); los de menos de 2 m están en los brazos del sur y Marimelena, con fracción caliente de 8–10 % en la banda 40–60 m. Conclusión de B3: cerca de la costa, profundidad y tipo de orilla (muelle frente a orilla de fango) van juntos y esta prueba no los separa. La marca de muelles viene de OSM (`resultados/campo/osm_portuario.json`); no hay información de dragados más allá de eso.

B4. No se ha encontrado ninguna batimetría de la bahía posterior a 1889 en rejilla entre los datos del repo del modelo (`datos/batimetria/fuentes/`): solo GEBCO 2026 (una celda oceánica dentro de la bahía), el texto de la guía de prácticos 2018 y el resumen de JICA 2004. **No se ha buscado en la web**; no se afirma que no exista.

Límites: la profundidad de la bahía es la carta de 1887–1889 (no se publica; ver 28.5), la distancia a costa está cuantizada a 2 m, y la referencia de d no se restringe a la profundidad del mallado.

### 29.3 Bloque C. RAdCor en 10 escenas secas (exploratorio): NO EVALUABLE con los ajustes congelados

Selección fija (`resultados/radcor_subconjunto_20m.json`): las 10 escenas secas aceptadas a 20 m con mayor fracción válida de la bahía; empates por fecha más antigua. Descargadas con `scripts/33_descarga_subconjunto.py` (10/10) y procesadas con `scripts/34_radcor_correr.py`, mismos ajustes que `acolite_io.AJUSTES` salvo `atmospheric_correction_method=radcor` (confirmado en los `*_l1r_settings.txt` de `datos/acolite_logs_radcor_20m/`). ACOLITE d61c8de, LUT ACOLITE-LUT-202110-MOD1/MOD2. Las 10 corrieron sin error (`resultados/radcor_registro_20m.json`).

Resultado: **0 focos válidos en las 10 escenas** (`resultados/contraste_escenas_20m_radcor.csv`), así que d_RAdCor no se puede calcular y la regla (d_RAdCor>0 en ≥8/10 y mediana de d_RAdCor/d_DSF ≥0,5) no se puede aplicar. Motivo, en `resultados/radcor_resultado_20m.json`: RAdCor deja NaN todo píxel a menos de `radcor_kernel_radius` (5 km, valor por defecto) del borde de la ventana (`externo/acolite/acolite/adjacency/radcor/radcor.py`, líneas 1771–1772 y 281; solo si `radcor_edge_extend=False`). La ventana congelada mide 614×621 px a 20 m (~12,3 km), de modo que solo sobreviven las filas 249–364 y columnas 249–371 (116×123 px): 188 de 11287 píxeles de agua de la bahía (1,7 %). Ningún foco de la orilla entra. Los píxeles que sobreviven están en el centro de la bahía.

No se ha cambiado ni el radio del núcleo, ni `radcor_edge_extend`, ni la ventana. Cualquiera de las tres cosas es un cambio de método: haría falta una fila fechada en la secc. 14 y la decisión de Alex (ventana ampliada ≥5 km por lado sobre los mismos L1C, o `radcor_edge_extend=True`). Por tanto C queda como **no evaluable**, no como fallo ni como éxito de RAdCor.

#### 29.3b Repetición de C con la ventana ampliada (2026-11-19; cambio de método fechado en la secc. 14)

Decidida por Alex tras ver 29.3 y fechada en la secc. 14 antes de calcular. Solo cambia la ventana de ACOLITE para RAdCor: (S 23,050; O −82,450; N 23,260; E −82,230), 1173×1139 px a 20 m; mismos 10 L1C, mismos ajustes y sin tocar ningún `radcor_*`. Scripts: `34_radcor_correr.py --limite …`, `38_radcor_recorte_resumen.py` (recorte por coordenadas exactas a la rejilla de la climatología y resumen), `30_contraste_escenas.py --etiqueta radcor_ampliada`. Salidas: `resultados/radcor_registro_ampliada_20m.json`, `resultados/contraste_escenas_20m_radcor_ampliada.csv`, `resultados/radcor_resultado_ampliada_20m.json`. El primer intento (29.3) se conserva tal cual.

Resultado: las 10 escenas corrieron y el recorte tiene el 100 % del agua de la bahía con valor. **Regla de C cumplida**: d_RAdCor>0 en **9 de 10** escenas (mínimo 8) y mediana de d_RAdCor/d_DSF = **0,78** (mínimo 0,5). La excepción es 2023-04-03 (d_RAdCor −0,056 frente a d_DSF 2,20). Cocientes por escena: 1,17 (2018-03-10), 0,77 (2019-01-19), 0,70 (2021-01-03), 0,83 (2021-02-22), 0,69 (2022-03-19), 1,31 (2022-11-04), −0,03 (2023-04-03), 0,79 (2024-02-17), 0,98 (2025-02-01), 0,78 (2025-12-08). La jerarquía de zonas `orden()` sobre estas 10 escenas se cumple con las dos correcciones y en las dos variantes: DSF «todos» brazos−medio +0,166 y medio−mar +0,908; RAdCor «todos» +0,251 y +1,040; RAdCor «a100m» +0,414 y +0,833.

Límites y cautelas: exploratorio y decidido después de ver el fallo del primer intento; solo 10 escenas secas, elegidas por mayor fracción válida de la bahía (no representativas de las turbias); con RAdCor entran menos focos válidos en varias escenas (por ejemplo 106 frente a 205 el 2023-04-03 y 123 frente a 182 el 2021-01-03) y no se ha investigado la causa; la estimación de AOT de RAdCor usa una ventana distinta a la del primer intento. Lo que muestra es que, con esta corrección de adyacencia, los focos siguen saliendo en 9 de las 10 escenas; no prueba que la adyacencia sea irrelevante en las demás.

### 29.4 Bloque D. Marea y viento (exploratorio)

Scripts y salidas: `scripts/31_marea_viento.py` → `resultados/marea_viento_20m.json`, `resultados_10m/marea_viento_10m.json` y CSV por escena. Marea: EOT20 (doi 10.17882/79489; constantes de la malla de 0,125° del repo del modelo, 9 constituyentes, IDW en la boca 23,1512 N, −82,3578 E; predicción con pyTMD con argumentos nodales FES). Sensibilidad: FES2022b (registro AVISO+). Concordancia EOT20–FES2022: correlación de nivel 0,994 (20 m) y 0,995 (10 m), concordancia de fase 0,982 y 0,988; rango EOT20 −0,17 a +0,26 m. Viento: ERA5 en el punto (23,25 N, −82,25 E), instantáneo a la hora del paso (campo `fecha` del metadato, ~16:16 UTC) y media de las 24 h previas. Estratos con n≥8; bootstrap por escenas, 2000, semilla 20261118.

Resultado por regla («no depende de marea ni viento» si cada estrato con ≥8 escenas mantiene `orden()` seco y d mediana >0):

- 20 m seco (71 escenas): se cumple. Todos los estratos mantienen `orden()` y d>0 (d mediana global 2,03 FNU [1,74; 2,29], d>0 en 71/71). Spearman de d con marea y viento: ninguno significativo (viento 24 h ρ=0,19, p=0,11).
- 10 m seco (44 escenas): **no se cumple del todo**. Todos los estratos mantienen `orden()` salvo `marea_subiendo` (n=20) en la variante «todos» (margen brazos−medio −0,024 FNU; la variante a>100 m sí cumple, +0,111). d mediana global 2,145 FNU [1,757; 2,373], d>0 en 43/44 (0,977). Spearman de d con el viento de las 24 h previas: ρ=0,332, p=0,0275 (la única correlación nominalmente significativa; con muchas pruebas no se corrige).
- Estación lluviosa: la regla no la exige; en varios estratos `orden()` no se cumple (ver JSON). No se interpreta.

Límites: modelo de marea grueso (0,125°; nodos válidos más cercanos a ~15 km), fase no verificada de forma independiente (la comprobación con la API de pyTMD 3.x falló y no se resolvió; la concordancia EOT20–FES2022 solo prueba consistencia entre modelos); punto ERA5 en mar abierto; la hora de paso es la del metadato.

### 29.5 Tabla resumen para el chat del artículo

| Ítem | n | Cifra | JSON | Estado |
|---|---|---|---|---|
| A 20 m (2026) | 13 (8 s, 5 ll) | A1 focos cumple (todas y seca; lluviosa insuficiente); A2 2/2; A3 +; d mediana 1,09 FNU | `resultados/prueba_A_20m.json` | confirmatorio |
| A 10 m (2026) | 11 (6 s, 5 ll) | A1 focos cumple (todas, d 1,05); estaciones insuficientes; 13 grupos NO cumple (6/11, p=0,5); A2 2/2 (4/4 con 20 m); A3 + | `resultados_10m/prueba_A_10m.json` | confirmatorio |
| B2 prof. (rangos) | 10 126–40 469 px | −0,21 a −0,27, IC sin 0 | `prof_dist_*.json` | exploratorio |
| B2b (post hoc) | ídem | prof. −0,35 a −0,38 | ídem | exploratorio, post hoc |
| B3 | ver JSON | >5 m cerca de costa = canal/muelles | ídem | exploratorio |
| B4 | – | sin batimetría posterior a 1889 en el repo; web no buscada | – | – |
| C RAdCor, ventana congelada | 10 | 0 focos válidos | `radcor_resultado_20m.json` | no evaluable |
| C RAdCor, ventana ampliada (post hoc, fechada 19/11) | 10 | d>0 en 9/10; mediana d_RAdCor/d_DSF 0,78; `orden()` cumple | `radcor_resultado_ampliada_20m.json` | regla cumplida, exploratorio |
| D 20 m seco | 71 | regla cumplida | `marea_viento_20m.json` | exploratorio |
| D 10 m seco | 44 | falla `marea_subiendo` (variante «todos»); ρ(d, viento 24 h)=0,33 | `marea_viento_10m.json` | exploratorio |

### 29.6 Decisión de Alex sobre la profundidad de la carta en el depósito (2026-11-19)

Decisión: no se redistribuye ningún dato de profundidad derivado de la carta; se cita la carta y quien quiera reproducir la figura c la busca y repite el procedimiento (opción 1 de las dadas). Hecho: se quitó la columna `median_chart_depth_80m_m` de `productos_publicos/figuras/fig_c_focos_10m.csv` (el fichero se ha editado con la misma operación que ahora hace `scripts/26_figuras.py`, que se corrigió para que no la reintroduzca; no se ha vuelto a ejecutar `26_figuras.py` completo), y el pie de figura (`NOTA_pies_de_figura.txt` y `26_figuras.py`) cita ahora la carta H.O. n.º 307 (ed. 1898, Leventhal Map & Education Center) y la georreferencia de Harvard (ed. 1889), y apunta al repo del modelo (commit 72095a8, `docs/procedencia_datos.md`) para el procedimiento. **No se ha podido verificar hoy ninguna de las dos URL** (la de Leventhal devuelve un bloqueo anti-bot; la de Harvard, un error 4xx), de modo que figuran «tal como constan en el repo del modelo, 2 oct 2026; no reverificadas el 19 nov 2026». Tampoco se ha comprobado en una página oficial la declaración de derechos de ninguna de las dos cartas; el pie dice «check its terms of use» y no afirma que estén libres de restricciones. Sigue pendiente: (a) el PDF de la fig. c dibuja la isobata de 2 m y marca los grupos por clase de profundidad (imagen, no datos); (b) los JSON agregados de `resultados/` y `resultados_10m/` (`batimetria_*`, `fondo_*`, `umbrales_*`, `prof_dist_*`, `aclaraciones_*`) siguen en el repo con estadísticos de profundidad; (c) las dos URL deben abrirse en un navegador y confirmarse antes de enviar el artículo.


### 29.7 Comprobaciones para el chat del artículo (2026-11-19)

Solo lectura de datos y resultados ya existentes: ningún análisis recalculado, ningún umbral cambiado (no hace falta fila en la sección 14). Script `scripts/39_comprobaciones_articulo.py`; salida `resultados/comprobaciones_articulo.json`, que da la ruta y el campo de cada cifra. Lo que no se pudo comprobar se dice como tal.

| Ítem | Artículo | Comprobado | Fuente | Coincide |
|---|---|---|---|---|
| 1. Ventana | «12,2 × 12,3 km» | Caja nominal 23,100–23,210 N, 82,400–82,280 O: 12,4 (E–O) × 12,07 (N–S) km en UTM 17N. Rejilla real: 20 m, 621 × 614 px = 12,42 × 12,28 km; 10 m, 1241 × 1229 px = 12,41 × 12,29 km | `resultados/climatologia.npz` y `resultados_10m/climatologia.npz`, campos `x`, `y` | No: decir «≈ 12,4 × 12,3 km (E–O × N–S)» |
| 2. Escenas por año | 19 (2016), 31 (2017), 70–88 desde 2018, de 637 | Los 19, 31 y 70–88 son **productos del catálogo** (664), no adquisiciones: 19, 31, 70, 75, 74, 80, 75, 73, 79, 88. Fechas distintas: 17, 30, 70, 73, 69, 73, 73, 72, 73, 85. Filas de QC (637): 17, 30, 70, 73, 69, 73, 73, 72, 75, 85 | `datos/crudo/catalogo.json` (`Name`); `resultados/escenas_qc.csv` (`fecha`) | Cifras sí, denominador no: 664 productos, no 637 |
| 3. AOT | 0,0045 a 10 m frente a 0,028 a 20 m | 2020-11-29: **0,0045 a 20 m y 0,0277 a 10 m** (al revés) | `datos/productos/…2020_11_29…npz` y `datos/productos_10m/…npz`, campo `aot_550`; protocolo sec. 14, fila 2026-11-13 (c) | No: resoluciones invertidas. El log de ACOLITE a 20 m de esa escena no existe; el valor sale del `.npz` |
| 4. Coordenadas | 23,13° N, 82,33° O | Centroide del agua de la bahía (11 287 px): 23,1326 N, 82,3418 O. Centroide del polígono de la bahía, con tierra (60 214 px): 23,1330 N, 82,3330 O | `resultados/climatologia.npz`, campos `bahia`, `agua` | Latitud sí. Longitud: 82,33 corresponde al polígono con tierra; para el agua es 82,34 |
| 5. Pie de fig_b | corredores iguales los primeros 3 km, contraste solo en los últimos 1,5–2 km | Medianas idénticas hasta ≈ 2,6 km (seca y lluviosa; parte por construcción, comparten corredor). Divergen desde ≈ 3,4 km (seca) y ≈ 3,1 km (lluviosa). IC 95 % disjuntos solo en 4,1–4,4 km (seca) y 3,6–3,9 km (lluviosa) | `productos_publicos/figuras/fig_b_perfil_brazos.csv` (`median_FNU`, `ci95_*`, `bin_center_m`) | Parcial: «primeros 3 km» vale (≈ 2,6–2,9 km); «últimos 1,5–2 km» exagera; con IC separados, ≈ 0,5 km |
| 6. B3 | «0–0,3 %» de píxeles calientes, > 5 m, < 60 m de costa | 20 m: 0–3,1 %. 10 m: 0–7,5 % (0,042 seca y 0,075 lluviosa en la banda 0–20 m, con 48 y 53 px). Solo las bandas 20–60 m a 10 m dan ≤ 0,3 %. z_c mediana negativa en todas las celdas (máx. −0,06 a 10 m) | `resultados/prof_dist_20m.json`, `resultados_10m/prof_dist_10m.json`, `estaciones.*.B3` (`fraccion_caliente_z_c>=3.5`) | No: corregido en 29.2 |
| 7. Suplemento secc. 1–5 | ver abajo | ver abajo | ver abajo | ver abajo |

Suplemento (`series-Sentinel-2/manuscript/supplement.tex`).

- Coinciden con su fuente: Tabla 1 y tabla de zonas (conteos de píxeles); Tabla 2, las cuatro filas (n, verde/rojo, NIR/rojo, exceso de rojo, ρ de focos con IC y ρ de referencia, de `resultados_10m/fondo_10m.json`, `cruzada`); z_t medio 0,08 de la fuente permanente (protocolo, fila «Fuente permanente ciega para z_t»); 43 y 17 grupos de la familia climatológica (protocolo, resultados de detección); 85 escenas a 10 m, 44 secas y 41 lluviosas (`fondo_10m.json`, `escenas_usadas`); cifras de lluvia y de campo contrastadas.
- Pendientes de la primera pasada, resueltos el mismo día: (a) «a 10 m el candidato sobrevivió solo con margen cero» **coincide**: `resultados_10m/sitios.csv` da `sobrevive_0m` = True y `sobrevive_20m` … `sobrevive_400m` = False (23,1731 N, 82,2829 O; persistencia 0,1667; 6 años). El 1 de `recurrentes_por_margen_m` a 60 m es otro sitio recurrente a más de 140 m del candidato, no el candidato; mi lectura anterior del JSON era errónea. (b) «siete años» **coincide**: `resultados/sitios.csv`, rango 2 (23,1562 N, 82,3499 O; 0,1226; 7 años, a 60 m de costa); el rango 3 es la celda duplicada (6 años), de ahí el «6–7» de esta sección. (c) «85–99 % de los píxeles de agua sobre el umbral de 2,2 µm» y «0,7–43 %» **se reconstruyen** con `scripts/40_piloto_contaminacion.py` (salida `resultados/piloto_contaminacion.json`; misma lógica que `scripts/figura_piloto.py`, B12 > 0,010 sobre el agua de la ventana): de las 8 escenas rechazadas, 7 tienen 85,5–99,4 % (la octava, 2020-01-19, 0,5 % con solo 37,3 % de agua válida por las banderas, bajo el 40 %); las 5 aceptadas pierden 0,7, 0,8, 23,4, 38,4 y 42,6 %. Son cifras reconstruidas desde los productos de `datos/productos`, no leídas de una salida guardada en su día; el protocolo no las tenía escritas. (d) «75 escenas en común» **coincide**: 75 fechas (y 75 productos) aceptadas en `resultados/escenas_qc.csv` y `resultados_10m/escenas_qc.csv`; 85 a 10 m, 10 solo a 10 m y 38 solo a 20 m.
- Secc. 6 (comprobación de 12 cifras, no solo 5): Tabla de profundidad (coeficientes e IC de los cuatro bloques de B2 y B2b, ρ de profundidad–distancia), tabla de marea y viento (n, márgenes y d con IC en filas «todas», «marea subiendo», «viento 24 h alto» a 20 y 10 m), Spearman −0,06 a 0,19 con p ≥ 0,11 (20 m), 0,33 con p = 0,028 (10 m), rango de marea −0,17 a +0,26 m, concordancia con FES2022 (0,994 y 0,995; 0,982 y 0,988), mediana del cociente 0,78 y 9 de 10 escenas con d > 0, y las diez filas de la tabla de RAdCor: todas coinciden.
