# Examen: detección de bordes en un clúster real (Ruta A, laptops)

Es el mismo proyecto y el mismo dataset (Oxford-IIIT Pet, 7,390 fotos), pero
ahora sobre **3 laptops físicas** con k3s en lugar de kind en una sola máquina.
El código de `app/` no cambia. Lo que cambia:

| | Proyecto (kind) | Examen (k3s) |
|---|---|---|
| Nodos | 3 contenedores Docker en 1 laptop | 3 laptops: 1 líder y 2 workers |
| Imagen | `bordes:1.0` cargada con `kind load` | `ghcr.io/diegozerm/bordes:1.0` (amd64 + arm64) |
| Datos | `hostPath` (carpeta montada por kind) | PV/PVC **NFS ReadWriteMany** desde el líder |
| Reparto | lo que decida el scheduler | `topologySpreadConstraints` por nodo |

## Máquinas

| Rol | Nodo | Integrante | CPU | Hilos | RAM | Sistema |
|---|---|---|---|---|---:|---|
| Líder (control-plane + NFS + worker) | `lider-diego` | Diego | AMD Ryzen 5 3550H | 8 | 22 GB | Arch Linux (Omarchy) |
| Worker | `worker-irving` | Irving | AMD Ryzen 7 7435HS | 16 | 15 GB | Ubuntu 24.04 |
| Worker | `worker-cesar` | César | Intel Core i5-8365U | 8 | 30 GB | Linux |

Axel no aporta nodo porque su laptop usa WSL 2 con red NAT, que no puede
unirse como worker. Su parte es la comparación kind contra clúster.

## Red

Usamos un hotspot propio, porque la red de la universidad aísla los equipos
entre sí.

```
                  Hotspot del equipo  (RED = <completar, ej. 192.168.137.0/24>)
        ┌───────────────────────┬───────────────────────┬───────────────────────┐
        │                       │                       │                       │
 lider-diego <IP_LIDER>    worker-irving <IP>     worker-cesar <IP>      laptop de Axel
 k3s server :6443          k3s agent               k3s agent              (solo kubectl
 NFS /srv/datos :2049      monta NFS               monta NFS               y análisis)
 flannel VXLAN :8472/udp   :10250 kubelet          :10250 kubelet
```

Puertos abiertos entre nodos: 6443/TCP (API), 10250/TCP (kubelet), 8472/UDP
(VXLAN de flannel) y 2049/TCP (NFSv4).

## Pasos para reproducir

```bash
# --- Líder ---
sudo examen/instalar-lider.sh lider-diego <RED>     # imprime IP_LIDER y TOKEN
export KUBECONFIG=~/.kube/config-k3s
DATOS=/srv/datos scripts/descargar-datos.sh pets     # el dataset va directo al NFS
gh auth refresh -s write:packages
examen/publicar-imagen.sh DiegoZerm                  # y en GitHub: paquete en Public

# --- Cada worker ---
sudo examen/unir-worker.sh worker-irving <IP_LIDER> <TOKEN>
sudo examen/unir-worker.sh worker-cesar  <IP_LIDER> <TOKEN>
# Si una laptop tiene dos redes activas (Wi-Fi y cable), fijar la del hotspot:
#   sudo K3S_EXTRA="--node-ip <IP> --flannel-iface <interfaz>" examen/unir-worker.sh ...
#   (en el líder, además IP_LIDER=<IP> para que imprima la IP correcta)

# --- Líder: volumen, demo, experimentos ---
kubectl get nodes -o wide                            # 3 nodos en Ready
IP_LIDER=<IP_LIDER> envsubst < examen/k8s/pv-pvc.yaml.tpl | kubectl apply -f -
kubectl get pv,pvc                                   # el PVC queda Bound

export PLANTILLA=examen/k8s/job-cluster.yaml.tpl IMAGEN=ghcr.io/diegozerm/bordes:1.0 DATOS=/srv/datos
scripts/demo.sh                                      # 8 tareas, 4 en paralelo, 400 fotos y mosaico

examen/barrido-cluster.sh DiegoZerm "1 2 4 8 16 24"  # block y lpt, 3 repeticiones

# Arranque en frío contra caliente (en el worker: sudo k3s crictl rmi ghcr.io/diegozerm/bordes:1.0)
examen/arranque.sh DiegoZerm worker-irving frio
examen/arranque.sh DiegoZerm worker-irving caliente

# --- Análisis ---
python3 scripts/analyze.py examen/resultados/tiempos-cluster.csv examen/resultados \
  --titulo "k3s en 3 laptops (Oxford-IIIT Pet, 16 tareas)"
python3 examen/comparar.py
```

## Defensa: drenar un nodo a mitad del Job

Conviene usar pocas tareas largas, por ejemplo 4 tareas de unos 40 s. Así, al
drenar, sí hay pods a la mitad de su trabajo. Con 16 tareas de unos 8 s,
muchas terminan antes de que el drenado las alcance.

```bash
export PLANTILLA=examen/k8s/job-cluster.yaml.tpl IMAGEN=ghcr.io/diegozerm/bordes:1.0 DATOS=/srv/datos
CONSERVAR=1 scripts/correr-job.sh drenado block 4 4 &     # 4 tareas, 4 en paralelo
kubectl get pods -l corrida=drenado -o wide -w             # en otra terminal: índice → nodo
kubectl drain worker-cesar --ignore-daemonsets --delete-emptydir-data
kubectl get job bordes-drenado -o jsonpath='{.status.completedIndexes} failed=[{.status.failedIndexes}]'
kubectl get events --field-selector involvedObject.name=bordes-drenado   # "Created pod" repetido
kubectl uncordon worker-cesar
```

Esto ya se probó en 3 VMs Ubuntu 24.04 con k3s v1.37 y el mismo NFS:

- Los índices 0 y 3 corrían en `worker-cesar` y fueron expulsados.
- El Job creó `bordes-drenado2-0-2tkgg` en `worker-irving` y
  `bordes-drenado2-3-w4nf5` en `lider-diego`.
- Terminó 4/4 con `failedIndexes` vacío.

Qué pasa: `drain` expulsa los pods de ese nodo. Llevan la condición
`DisruptionTarget`, y por la regla `podFailurePolicy: Ignore` esa expulsión
**no cuenta** contra `backoffLimitPerIndex`. El controlador del Job vuelve a
crear los índices que no habían terminado en los nodos que quedan. Los índices
que ya habían terminado no se repiten, porque su `part-XXXX.csv` ya está en el
NFS.

**Si se apaga la laptop** en lugar de drenarla:

1. A los ~40 s el nodo pasa a `NotReady`.
2. 30 s después (`tolerationSeconds: 30` en el Job) sus pods se marcan para
   expulsión.
3. Como el kubelet ya no responde, los pods se quedan en `Terminating` y el Job
   no puede reponerlos.

Para destrabarlo hay que avisarle a Kubernetes que el nodo está apagado:

```bash
kubectl taint node worker-cesar node.kubernetes.io/out-of-service=nodeshutdown:NoExecute
# ...el Job repone los índices y termina...
kubectl taint node worker-cesar node.kubernetes.io/out-of-service-   # al volver a encenderla
```

## Resultados

Ver `examen/resultados/`: `tiempos-cluster.csv`, `tabla.md`, `comparacion.png`,
`comparacion.md`, `arranque.csv` y la carpeta `evidencias/` con las salidas de
terminal. El reporte de análisis está en `examen/reporte/`.
