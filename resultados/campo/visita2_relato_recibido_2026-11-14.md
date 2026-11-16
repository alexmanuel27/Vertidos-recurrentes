# Visita 2: relato de la persona de campo, transcripción literal

Recibido el 14/11/2026 por mensaje de texto, sin fotos ni fichas. **No está codificado** y no se ha abierto
`clave.csv` ni `reservas.csv` para escribirlo. Las respuestas llegaron numeradas, sin las preguntas a las que
contestan; abajo están tal cual, y las notas del registro van aparte y marcadas.

## Respuestas (literal)

1- P09 y P10 están muy cercas el uno del otro, concretamente a menos de 200 metros.
Los visité por separado, la referencia es la "Playa del Chivo", no hay carretera o calle de asfalto para llegar a esa zona directamente, son senderos hechos por los pescadores. Nota: en la zona la señal de internet era muy pobre.

2- Habían algunos puntos que aparecían en el mar como tal, todas las fotos se hicieron desde tierra:
- En los puntos P05, P09 y P10 desde la misma costa
- P02, P04, P05, P08, P06 desde el muelle ya que en esta zona no hay costa
Traté de acercarme lo más posible en todos los casos.
- En el caso del tubo es el que sale en las fotos, el cual según lo que ví en las coordenadas de Google maps estaba a aproximadamente 50 metros del punto.
- Lo ví desde la misma costa, aparece en las imágenes, es un tubo que al parecer era de drenaje

3- El color del agua se veía desde el punto anterior el P02, además de que intenté acceder a unos 550 metros desde el origen del punto, pero había una cerca, desde ahí ví parcialmente el color del agua y era igual al punto anterior, ahí mismo mirando hacia la dirección donde estaba el punto vi la basura flotando a lo lejos pegada a los muros de contención.
- Necesitas la ubicación?

4- Fue el jueves 12/11/2026, se reportaron lluvias intensas en la tarde en toda la Habana por la entrada de un frente frío. Las lluvias fueron largas y periodicas, desde la tarde hasta la madrugada e incluso el amanecer de 13/11/2026

5- No, fue la primera, seguramente me equivoqué

## Notas del registro (no son del observador)

- **Distancia P09–P10:** con `puntos.csv` son unos **410 m** (no < 200 m). Se registra la cifra del observador como
  suya y la calculada como comprobación; las fotos con GPS dirán dónde estuvo de verdad.
- **P05 aparece en las dos listas** del punto 2 (desde la costa y desde el muelle). Sin resolver.
- **Sin asignar a un punto:** el «tubo a ~50 m» y el «tubo de drenaje visto desde la costa» (punto 2), y el
  «color del agua» con «basura pegada a los muros» a ~550 m (punto 3). El texto no dice a qué punto se refiere cada
  uno; no se asigna por deducción.
- **Fecha de la visita (corregido el 14/11):** una primera versión de esta nota daba por hecho que la visita fue el
  12/11. El EXIF de las fotos de P02, P04, P09 y P10 dice **13/11/2026, entre las 14:56 y las 15:52** (hora de la
  cámara). El «jueves 12/11» del punto 4 parece ser el día de la lluvia, no el de la visita. Las fotos son de la tarde
  siguiente a la noche de lluvia; falta saber cuánto llovió (ver abajo). Las fotos están en
  `datos/trabajo de campo/bahia/Punto N/`; P03 y P08 solo tienen ficha, sin fotos.
- **Lluvia (referencia, no es el criterio del protocolo):** ERA5 todavía no tiene datos de esos días (consulta del
  14/11/2026 a Open-Meteo, todo nulo). El modelo de previsión/análisis de Open-Meteo para 23,133 N 82,333 O da
  4,5 mm el 12/11 y 2,0 mm el 13/11 (UTC), lejos de los 20 mm del criterio de la visita posterior a lluvia (secc.
  20.5). Eso no desmiente una lluvia local intensa, y un solo punto de rejilla puede subestimarla. **Pendiente:**
  repetir con ERA5 en unos días.
- **Punto 5:** no se sabe a qué pregunta responde. La visita 1 fue el 23/10/2026 (P05, P06, P08); esta, el
  12/11/2026, es la segunda salida. Pendiente de aclarar con la persona de campo.
- Pendiente: fotos originales (con metadatos), fichas, y la ubicación de la basura flotante junto a los muros.

## Preguntas a las que responden (añadido el 15/11/2026)

Las respuestas siguen la numeración del mensaje que Alex envió el 14/11 (redactado en el chat de Cowork):

1. P09 y P10: notas idénticas y fotos con la misma posición GPS. ¿Visitados por separado? ¿Desde dónde y qué se vio en cada uno?
2. Las fotos salen a 200–600 m de los puntos según el GPS. ¿Desde dónde se hicieron y a qué distancia estaba el punto? En P10 la ficha dice un tubo a 50 m: ¿cómo se vio?
3. P03: ficha «no accesible», sin fotos, pero con color marrón, basura y olor a pescado. ¿Desde dónde y a qué distancia?
4. Lluvia del 13/11 marcada «mucho»: ¿cuándo llovió y cuánto, más o menos?
5. P06: la ficha dice «visita nº 2». ¿Era la primera visita a ese punto?

Con eso, notas del registro resueltas (no se toca el texto literal ni las notas de arriba):

- **Tubo a ~50 m** (respuesta 2): es el de **P10**; según el observador sale en las fotos de P10.
- **Color y basura a ~550 m, tras una cerca** (respuesta 3): son de **P03**. El color se vio desde P02; la basura, a lo lejos, junto a los muros de contención. P03 no se vio desde menos de 150 m.
- **Respuesta 5:** P06 fue su **visita 1** (23/10/2026); la ficha dice 2 por error del observador. `registro_visitas.csv` copia la ficha tal cual (2).
- **Fechas:** la salida del 13/11 es la segunda (P02, P03, P04, P09, P10, cada punto en su visita 1); la primera fue el 23/10 (P05, P06, P08). Corrige la línea «esta, el 12/11/2026» de arriba.
- **GPS de P09 y P10:** 45 de sus 52 fotos llevan la misma posición (23,1536 N, 82,3501 O), tomadas en momentos distintos; con la mala señal que cuenta el observador, es probable una posición en caché. No sirven para situar al observador.
- **Pendiente:** a qué se refiere P05 en las dos listas de la respuesta 2, y P08 «desde el muelle» aunque no tiene fotos; ubicación (pin) de la cerca de P03.
