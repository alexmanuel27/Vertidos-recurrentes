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
estrecho, con tres ensenadas interiores (Marimelena al noreste, Guasabacoa al este,
Atarés al sur).

**Tile Sentinel-2:** `T17QLF` (UTM zona 17N, banda MGRS Q). La bahía completa, incluido
el canal de entrada y una franja de mar abierto frente a la bocana, cae dentro de este
único tile. No se mosaica nada. Los siete puntos de control usados para comprobarlo
(bocana, centro, las tres ensenadas y las dos esquinas del bbox) caen todos en `17QLF`,
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
| 2026-10-17 | **Puntos de campo calculados** (20.5), con `scripts/08_controles_campo.py` y `scripts/09_fuentes_osm.py`; salida en `resultados/campo/` (`clave.csv`, `puntos.csv` para la persona de campo, `reservas.csv`, `campo.json`, `fuentes_osm.csv`, `osm_overpass.json`). Detalles que 20.5 no fijaba: (a) cada sitio se sitúa en el píxel de agua más cercano a su coordenada (a 1–21 m); (b) la mediana de E1 se toma sobre los píxeles de su zona con frecuencia definida (≥ 20 ocasiones): 0,010 en la bahía, 0 fuera; (c) los grupos E3 de las dos estaciones se excluyen con su extensión completa (243 px), no solo su pico; (d) un control no puede repetir el píxel de otro; (e) sorteo en el orden S1–S5 y después barajado de los diez puntos, todo con la semilla 20261013; (f) la revisión OSM consulta `waterway` = river/stream/canal/drain/ditch/outfall y `man_made` = outfall/pipeline en 23,09–23,22 N, 82,41–82,26 O (instantánea 2026-10-17T18:14:50Z) y mide la distancia a la geometría completa de cada elemento. Resultado OSM: solo S5 tiene una fuente conocida a ≤ 150 m (río Luyanó, 118 m); S3 queda a 329 m del Martín Pérez; ningún control tiene fuente a ≤ 150 m. Falta la cartografía publicada. Advertencia: los tres controles de la bahía caen en su mitad norte, porque la frecuencia E1 alta está en la sur; la persona de campo podría intuir los roles por la geografía, y las coordenadas de los sitios ya son públicas en 20.5. El ciego depende de no darle ni el repositorio ni este documento. El criterio principal (hay estructura o no) es objetivo | Fijar la clave antes de la primera visita, como exige 20.5 | **Sí** — usa E1 y E3 tal como dice 20.5. Ningún dato de campo, ni de lluvia, ni a 10 m. Ninguna regla cambió al ver los puntos |

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
  la cabecera del brazo sur, en torno al punto de control de Atarés (23,118 N, 82,338 O), y
  en el brazo suroeste (≈ 23,120 N, 82,351–82,356 O).
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
