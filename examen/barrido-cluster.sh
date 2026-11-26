#!/usr/bin/env bash
# Barrido del examen en el clúster real: estrategias block y lpt, 16 tareas,
# 3 repeticiones y p = 1, 2, 4, 8 y más, hasta los núcleos del clúster.
# Reutiliza scripts/barrido.sh y scripts/correr-job.sh con la plantilla del
# clúster (imagen de GHCR + PVC NFS + topologySpreadConstraints).
#
# Uso (en la laptop líder, con KUBECONFIG apuntando a k3s):
#   examen/barrido-cluster.sh <usuario-github> ["1 2 4 8 16 24"]
set -euo pipefail

RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
USUARIO="${1:?Falta el usuario de GitHub dueño de la imagen}"

export PLANTILLA="$RAIZ/examen/k8s/job-cluster.yaml.tpl"
export IMAGEN="ghcr.io/${USUARIO,,}/bordes:1.0"
export DATOS=/srv/datos                     # el NFS, visto localmente en el líder
export ESTRATEGIAS="block lpt"
export PARALELISMOS="${2:-1 2 4 8 16 24}"
export REPETICIONES=3
export SALIDA_CSV="$RAIZ/examen/resultados/tiempos-cluster.csv"
export PREFIJO=c

mkdir -p "$RAIZ/examen/resultados"
echo "Núcleos asignables por nodo:"
kubectl get nodes -o custom-columns=NODO:.metadata.name,CPU:.status.allocatable.cpu,MEM:.status.allocatable.memory
"$RAIZ/scripts/barrido.sh"
