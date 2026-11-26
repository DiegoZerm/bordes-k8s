#!/usr/bin/env bash
# Lanza UNA corrida del Job indexado, espera a que termine, une los resultados
# y escribe en stdout una línea CSV con el tiempo de pared del Job.
#
# Uso: scripts/correr-job.sh <corrida> <estrategia> <p> [tareas] [limite] [guardar] [fallar]
#   corrida     nombre único (minúsculas, números y guiones)
#   estrategia  block | cyclic | lpt
#   p           parallelism
#   tareas      completions (16)
#   limite      cuántas fotos (0 = todas)
#   guardar     1 guarda imágenes de bordes y arma el mosaico (0)
#   fallar      índice que falla en su primer intento (-1)
#
# Variables opcionales: IMAGEN (bordes:1.0), CONSERVAR=1 para no borrar el Job,
# DATOS (carpeta local que ven los pods como /data; por defecto datos/ del repo).
#
# Salida (stdout): corrida,estrategia,p,tareas,fotos,errores,T_s,inicio,fin,I,t_max_s,t_prom_s,nodos
set -euo pipefail

RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
DATOS="${DATOS:-$RAIZ/datos}"
source "$DATOS/dataset.env"

export CORRIDA="$1" ESTRATEGIA="$2" P="$3"
export TAREAS="${4:-16}" LIMITE="${5:-0}" GUARDAR="${6:-0}" FALLAR="${7:--1}"
export IMAGEN="${IMAGEN:-bordes:1.0}" CARPETA
PLANTILLA="${PLANTILLA:-$RAIZ/k8s/job.yaml.tpl}"
JOB="bordes-$CORRIDA"
SALIDA="$DATOS/salida/$CORRIDA"

# Corrida limpia: sin Job anterior con el mismo nombre ni salidas viejas
kubectl delete job "$JOB" --ignore-not-found --wait=true >/dev/null
rm -rf "$SALIDA"

envsubst < "$PLANTILLA" | kubectl apply -f - >/dev/null

# Esperar a Complete o Failed (kubectl wait solo espera una condición)
while true; do
  estado=$(kubectl get job "$JOB" -o jsonpath='{range .status.conditions[?(@.status=="True")]}{.type} {end}')
  case "$estado" in
    *Complete*) break ;;
    *Failed*) echo "El Job $JOB falló" >&2; kubectl describe job "$JOB" >&2; exit 1 ;;
  esac
  sleep 1
done

# Tiempo de pared del Job según Kubernetes: completionTime - startTime
inicio=$(kubectl get job "$JOB" -o jsonpath='{.status.startTime}')
fin=$(kubectl get job "$JOB" -o jsonpath='{.status.completionTime}')
T=$(( $(date -d "$fin" +%s) - $(date -d "$inicio" +%s) ))

# Unir partes (el mosaico solo se arma si se guardaron los bordes)
python3 "$RAIZ/app/merge.py" "$SALIDA" "$DATOS/entrada/$CARPETA" --tareas "$TAREAS" >&2

linea=$(python3 - "$SALIDA/summary.json" << 'PY'
import json, sys
s = json.load(open(sys.argv[1]))
nodos = ";".join(f"{k}:{v}" for k, v in sorted(s["tareas_por_nodo"].items()))
print(",".join(str(x) for x in (s["fotos"], s["errores"])), end="|")
print(",".join(str(x) for x in (s["desbalance_I"], s["t_max_s"], s["t_promedio_s"], nodos)))
PY
)
echo "$CORRIDA,$ESTRATEGIA,$P,$TAREAS,${linea%%|*},$T,$inicio,$fin,${linea#*|}"

[ "${CONSERVAR:-0}" = "1" ] || kubectl delete job "$JOB" --wait=false >/dev/null
