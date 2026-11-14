#!/bin/zsh
# Vigilante del bucle por tandas: lo relanza si algo lo mata desde fuera.
#
# Por que: tres veces el proceso murio sin dejar rastro en el log (sin traceback, sin
# PARADA): algo del sistema lo cerro con una senal. El bucle es reanudable, asi que
# basta con volver a lanzarlo; esto lo hace solo, a los 5 min.
#
# Se lanza UNA vez, con las credenciales ya en el entorno:
#   nohup caffeinate -i zsh scripts/archivo_sin_parar.sh > /dev/null 2>&1 &
#
# Termina cuando una pasada acaba bien y ya no queda nada pendiente, o tras 30 intentos.
#
# Los argumentos se pasan al bucle tal cual, y LOG elige el log (tandas.log por defecto).
# Fase 2 a 10 m (protocolo 20.2), las 186 fechas de resultados/fase2_productos_10m.txt.
# --tanda 5 porque con ~24 GB libres una tanda de 20 pide 35 GB (1 GB/producto + 15) y para:
#   VERTIDOS_PIXEL_M=10 LOG=tandas_10m.log nohup caffeinate -i zsh scripts/archivo_sin_parar.sh \
#     --productos datos/productos_10m --crudo datos/crudo_10m --logs datos/acolite_logs_10m --tanda 5 \
#     --solo $(cat resultados/fase2_productos_10m.txt) > /dev/null 2>&1 &
cd "${0:A:h}/.."
LOG=${LOG:-tandas.log}
for i in {1..30}; do
  echo "=== vigilante: intento $i, $(date '+%Y-%m-%d %H:%M') ===" >> $LOG
  python scripts/04_archivo_por_tandas.py --tanda 20 "$@" >> $LOG 2>&1
  codigo=$?
  if [ $codigo -eq 0 ] && sed -n "/=== vigilante: intento $i,/,\$p" $LOG | grep -q "| pendientes 0 |"; then
    echo "=== vigilante: ARCHIVO COMPLETO ===" >> $LOG
    exit 0
  fi
  echo "=== vigilante: la pasada $i acabo con codigo $codigo; relanzo en ${ESPERA:-300} s ===" >> $LOG
  sleep ${ESPERA:-300}
done
echo "=== vigilante: 30 intentos sin terminar; mira el log ===" >> $LOG
