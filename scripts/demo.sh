#!/usr/bin/env bash
# Corrida de demostración: 8 tareas, 4 en paralelo, 400 fotos, guardando las
# imágenes de bordes. Muestra en qué nodo corrió cada índice y arma el mosaico.
#
# Uso: scripts/demo.sh [estrategia]   (lpt por defecto)
set -euo pipefail

RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
DATOS="${DATOS:-$RAIZ/datos}"
CORRIDA="demo-$(date +%H%M%S)"
EVID="$RAIZ/resultados/demo"
mkdir -p "$EVID"

echo "Lanzando $CORRIDA (8 tareas, 4 en paralelo, 400 fotos)..."
CONSERVAR=1 "$RAIZ/scripts/correr-job.sh" "$CORRIDA" "${1:-lpt}" 4 8 400 1 -1 | tee "$EVID/linea.csv"

kubectl get pods -l corrida="$CORRIDA" -o wide \
  -L batch.kubernetes.io/job-completion-index | tee "$EVID/pods.txt"
cp "$DATOS/salida/$CORRIDA/mosaico.png" "$EVID/mosaico.png"
cp "$DATOS/salida/$CORRIDA/summary.json" "$EVID/summary.json"
echo "Mosaico: $EVID/mosaico.png"
kubectl delete job "bordes-$CORRIDA" --wait=false
