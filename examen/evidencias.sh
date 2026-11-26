#!/usr/bin/env bash
# Guarda en examen/resultados/evidencias/ cada salida de terminal que pide el
# examen, con la fecha y el comando que la produjo. Se corre en el líder.
#
# Uso:
#   examen/evidencias.sh nodos              # nodos Ready, IPs, versión, CPU y RAM asignables
#   examen/evidencias.sh volumen            # PV/PVC Bound y export NFS del líder
#   examen/evidencias.sh demo               # 8 tareas, 4 en paralelo, 400 fotos: pods por nodo y mosaico
#   examen/evidencias.sh drenado <nodo>     # drena <nodo> a mitad de un Job de 4 tareas largas
#   examen/evidencias.sh reparto            # pods por nodo en cada corrida del barrido
#   examen/evidencias.sh arranque           # tabla de arranque en frío y en caliente
#   examen/evidencias.sh todo               # nodos + volumen + demo
#
# Variables (por defecto, las del clúster del examen):
#   PLANTILLA=examen/k8s/job-cluster.yaml.tpl  IMAGEN=ghcr.io/diegozerm/bordes:1.0
#   DATOS=/srv/datos  EVID=examen/resultados/evidencias
# Para ensayar en kind: PLANTILLA=k8s/job.yaml.tpl IMAGEN=bordes:1.0 DATOS=datos
set -euo pipefail

RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
export PLANTILLA="${PLANTILLA:-$RAIZ/examen/k8s/job-cluster.yaml.tpl}"
export IMAGEN="${IMAGEN:-ghcr.io/diegozerm/bordes:1.0}"
export DATOS="${DATOS:-/srv/datos}"
EVID="${EVID:-$RAIZ/examen/resultados/evidencias}"
mkdir -p "$EVID"

# Corre un comando, lo muestra en pantalla y lo agrega al archivo con su encabezado
cmd() {
  local archivo="$1"; shift
  {
    echo "\$ $*"
    eval "$@" 2>&1 || true
    echo
  } | tee -a "$archivo"
}

encabezado() {
  printf '# %s\n# %s en %s\n\n' "$2" "$(date '+%F %T %Z')" "$(hostname)" > "$1"
}

nodos() {
  local f="$EVID/01-nodos.txt"
  encabezado "$f" "Parte 1: nodos del clúster"
  cmd "$f" kubectl get nodes -o wide
  cmd "$f" "kubectl get nodes -o custom-columns=NODO:.metadata.name,CPU:.status.allocatable.cpu,MEMORIA:.status.allocatable.memory,ARQ:.status.nodeInfo.architecture,SO:.status.nodeInfo.osImage"
  cmd "$f" kubectl version
  echo "Guardado: $f"
}

volumen() {
  local f="$EVID/02-volumen.txt"
  encabezado "$f" "Parte 1: volumen compartido NFS"
  cmd "$f" kubectl get pv,pvc -o wide
  cmd "$f" kubectl describe pvc datos
  cmd "$f" "cat /etc/exports 2>/dev/null; exportfs -v 2>/dev/null || sudo -n exportfs -v 2>/dev/null"
  cmd "$f" "ls $DATOS $DATOS/salida | head -40"
  echo "Guardado: $f"
}

demo() {
  local d="$EVID/03-demo" corrida="ev-demo-$(date +%H%M%S)"
  mkdir -p "$d"
  encabezado "$d/demo.txt" "Parte 2: corrida de demostración (8 tareas, 4 en paralelo, 400 fotos)"
  echo "Lanzando $corrida..."
  CONSERVAR=1 "$RAIZ/scripts/correr-job.sh" "$corrida" lpt 4 8 400 1 -1 | tee "$d/linea.csv"
  cmd "$d/demo.txt" kubectl get pods -l corrida="$corrida" -o wide -L batch.kubernetes.io/job-completion-index
  cmd "$d/demo.txt" "kubectl get pods -l corrida=$corrida -o jsonpath='{range .items[*]}{.spec.nodeName}{\"\\n\"}{end}' | sort | uniq -c"
  cmd "$d/demo.txt" kubectl describe job "bordes-$corrida"
  cp "$DATOS/salida/$corrida/mosaico.png" "$DATOS/salida/$corrida/summary.json" "$d/"
  kubectl delete job "bordes-$corrida" --wait=false >/dev/null
  echo "Guardado: $d (mosaico.png, demo.txt, summary.json)"
}

drenado() {
  local nodo="${1:?Falta el nodo a drenar, ej. worker-cesar}"
  local d="$EVID/04-drenado" corrida="ev-drenado-$(date +%H%M%S)"
  mkdir -p "$d"
  local f="$d/drenado.txt"
  encabezado "$f" "Defensa: drenar $nodo a mitad del Job (4 tareas largas, 4 en paralelo)"

  # Pocas tareas largas para que el drenado alcance pods a la mitad de su trabajo
  CONSERVAR=1 "$RAIZ/scripts/correr-job.sh" "$corrida" block 4 4 > "$d/linea.csv" &
  local job_pid=$!

  echo "Esperando a que haya un pod corriendo en $nodo..."
  for _ in $(seq 1 120); do
    kubectl get pods -l corrida="$corrida" --field-selector spec.nodeName="$nodo",status.phase=Running \
      -o name 2>/dev/null | grep -q . && break
    sleep 1
  done
  sleep 5   # que ya vayan a la mitad
  cmd "$f" kubectl get pods -l corrida="$corrida" -o wide -L batch.kubernetes.io/job-completion-index
  cmd "$f" kubectl drain "$nodo" --ignore-daemonsets --delete-emptydir-data --timeout=120s
  cmd "$f" kubectl get pods -l corrida="$corrida" -o wide -L batch.kubernetes.io/job-completion-index

  wait "$job_pid"
  cmd "$f" kubectl get pods -l corrida="$corrida" -o wide -L batch.kubernetes.io/job-completion-index
  cmd "$f" "kubectl get job bordes-$corrida -o jsonpath='completedIndexes={.status.completedIndexes} failedIndexes=[{.status.failedIndexes}] succeeded={.status.succeeded}{\"\\n\"}'"
  cmd "$f" kubectl describe job "bordes-$corrida"
  cmd "$f" kubectl get events --field-selector involvedObject.name="bordes-$corrida" --sort-by=.lastTimestamp
  cmd "$f" kubectl uncordon "$nodo"
  kubectl delete job "bordes-$corrida" --wait=false >/dev/null
  echo "Guardado: $f"
}

reparto() {
  local f="$EVID/05-reparto.txt" csv="$RAIZ/examen/resultados/tiempos-cluster.csv"
  [ -f "$csv" ] || { echo "Todavía no hay $csv (corre examen/barrido-cluster.sh)" >&2; exit 1; }
  encabezado "$f" "Parte 2: pods (tareas) por nodo en cada corrida del barrido"
  {
    printf '%-18s %4s %-10s %s\n' corrida p T_s "tareas por nodo"
    python3 - "$csv" << 'PY'
import csv, sys
for r in csv.DictReader(open(sys.argv[1], encoding="utf-8")):
    print(f"{r['corrida']:<18} {r['p']:>4} {r['T_s']:<10} {r['nodos'].replace(';', '  ')}")
PY
  } | tee -a "$f"
  echo "Guardado: $f"
}

arranque() {
  local f="$EVID/06-arranque.txt" csv="$RAIZ/examen/resultados/arranque.csv"
  [ -f "$csv" ] || { echo "Todavía no hay $csv (corre examen/arranque.sh)" >&2; exit 1; }
  encabezado "$f" "Parte 3: arranque de un pod sin la imagen (frío) y con ella (caliente)"
  cmd "$f" "column -s, -t < $csv"
  echo "Guardado: $f"
}

case "${1:-}" in
  nodos | volumen | demo | reparto | arranque) "$1" ;;
  drenado) drenado "${2:-}" ;;
  todo) nodos; volumen; demo ;;
  *) sed -n '2,18p' "$0"; exit 1 ;;
esac
