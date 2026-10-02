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
cd "${0:A:h}/.."
for i in {1..30}; do
  echo "=== vigilante: intento $i, $(date '+%Y-%m-%d %H:%M') ===" >> tandas.log
  python scripts/04_archivo_por_tandas.py --tanda 20 >> tandas.log 2>&1
  codigo=$?
  if [ $codigo -eq 0 ] && sed -n "/=== vigilante: intento $i,/,\$p" tandas.log | grep -q "| pendientes 0 |"; then
    echo "=== vigilante: ARCHIVO COMPLETO ===" >> tandas.log
    exit 0
  fi
  echo "=== vigilante: la pasada $i acabo con codigo $codigo; relanzo en ${ESPERA:-300} s ===" >> tandas.log
  sleep ${ESPERA:-300}
done
echo "=== vigilante: 30 intentos sin terminar; mira el log ===" >> tandas.log
