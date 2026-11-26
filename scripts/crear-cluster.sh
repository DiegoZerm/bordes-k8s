#!/usr/bin/env bash
# Crea el clúster kind "bordes" (1 control-plane + 3 workers) con datos/
# montada en /data de cada nodo, construye la imagen bordes:1.0 y la carga.
#
# Uso: scripts/crear-cluster.sh            (si ya existe, solo recarga la imagen)
#      scripts/crear-cluster.sh --borrar   (borra el clúster)
set -euo pipefail

RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
CLUSTER=bordes
IMAGEN=bordes:1.0

if [ "${1:-}" = "--borrar" ]; then
  kind delete cluster --name "$CLUSTER"
  exit 0
fi

[ -f "$RAIZ/datos/dataset.env" ] || {
  echo "Primero descarga el dataset: scripts/descargar-datos.sh pets" >&2
  exit 1
}
mkdir -p "$RAIZ/datos/salida"

if ! kind get clusters 2>/dev/null | grep -qx "$CLUSTER"; then
  export DATOS_ABS="$RAIZ/datos"
  envsubst < "$RAIZ/k8s/kind-config.yaml.tpl" > "$RAIZ/k8s/kind-config.yaml"
  kind create cluster --config "$RAIZ/k8s/kind-config.yaml" --wait 120s
fi

docker build -t "$IMAGEN" "$RAIZ/app"
kind load docker-image "$IMAGEN" --name "$CLUSTER"

kubectl cluster-info --context "kind-$CLUSTER"
kubectl get nodes -o wide
