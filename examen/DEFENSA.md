# Preparación de la demo del proyecto y la defensa del examen

El profe puede preguntarle **a cualquiera sobre cualquier parte**, y quien no pueda
explicar su parte pierde esos puntos. Este documento tiene:

1. El reparto de la demo (5 min) y de la defensa (15 min).
2. Lo mínimo que los cuatro deben saber de memoria.
3. Preguntas con respuesta, por persona.
4. Lo que **no** debemos afirmar.

Para practicar: que otro te lea la pregunta y tú contestes **sin leer**, en menos de un
minuto. Si no puedes, abre el archivo que se indica y vuelve a intentarlo.

Los números del clúster real dicen `[clúster]`. Esos se llenan el día del examen, con
`examen/resultados/comparacion.md` y el reporte.

---

## 1. Reparto

### Demo del proyecto en kind (5 min)

| Min | Quién | Qué se muestra | Comando o archivo |
|---:|---|---|---|
| 0:00 | Diego | Problema, dataset y arquitectura en una frase | `README.md` |
| 0:45 | Irving | Demo en vivo: 8 tareas, 4 en paralelo, pods por nodo y mosaico | `scripts/demo.sh` |
| 2:00 | César | Barrido de 36 corridas y prueba de fallo del índice 3 | `resultados/tiempos.csv`, `resultados/fallo/` |
| 3:15 | Axel | Speedup, eficiencia, Amdahl y desbalance | `resultados/speedup.png`, `resultados/tabla.md` |
| 4:15 | Diego | Por qué no escala de 4 a 8 y conclusión | `resultados/descomposicion.md` |

Antes de empezar, en la laptop de Diego: `kubectl config use-context kind-bordes` y
`kubectl get nodes`. Si kind no responde: `scripts/crear-cluster.sh --borrar && scripts/crear-cluster.sh`.
**Plan B:** si la demo en vivo falla, se abre `resultados/demo/mosaico.png` y `resultados/demo/pods.txt`.

### Defensa del examen en el clúster real (15 min)

| Min | Quién | Tema | Evidencia |
|---:|---|---|---|
| 0:00 | Diego | Ruta A, las 3 laptops, la red y el líder (k3s + NFS) | `examen/README.md`, `evidencias/01-nodos.txt` |
| 2:00 | Irving | Cómo se une un worker, puertos y montaje del NFS | `examen/unir-worker.sh` |
| 3:30 | Diego | PV/PVC, imagen en GHCR y el Job con `topologySpreadConstraints` | `evidencias/02-volumen.txt`, `examen/k8s/` |
| 5:00 | Irving | Demo en vivo: pods en los 3 nodos y mosaico | `evidencias/03-demo/` |
| 6:30 | César | Barrido en el clúster y arranque en frío contra caliente | `tiempos-cluster.csv`, `evidencias/06-arranque.txt` |
| 8:30 | Axel | kind contra el clúster: T, S, E y fotos por segundo | `comparacion.png`, `comparacion.md` |
| 10:30 | Diego | Drenar un nodo en vivo y explicar qué pasó | `examen/evidencias.sh drenado worker-cesar` |
| 12:00 | Todos | Cuello de botella y conclusiones; preguntas | `examen/reporte/reporte.pdf` |

---

## 2. Lo mínimo que los cuatro deben saber

- **Qué hacemos:** detectar bordes en las **7,390 fotos** de Oxford-IIIT Pet (775 MB):
  escala de grises → desenfoque gaussiano (σ = 1.4) → Sobel → umbral. La tabla del curso
  dice 7,349 porque ese es el número de fotos con anotación; el tar trae 7,390.
- **Job indexado:** `completionMode: Indexed`, 16 tareas (`completions`) y `parallelism: p`.
  Cada pod lee su `JOB_COMPLETION_INDEX` y, con la estrategia, calcula qué fotos le tocan.
  **Los pods no se comunican entre sí:** todos ordenan la lista igual y cada uno toma su parte.
- **Estrategias:** `block` (bloques contiguos), `cyclic` (foto i → tarea i mod 16) y
  `lpt` (de mayor a menor tamaño, cada foto a la tarea con menos bytes; montículo).
- **Métricas:** S = T(1)/T(p); E = S/p; f = (1/S − 1/p)/(1 − 1/p) (Amdahl);
  I = t_max / t_promedio (1 = reparto perfecto). T(p) = `completionTime − startTime` del Job.
- **Números de kind** (Ryzen 5 3550H, 4 núcleos y 8 hilos):
  - S ≈ 3.5–3.7 con p = 4. Con p = 8 ya no mejora (block 4.12, lpt 3.48).
  - Cada foto pasa de 8.9 ms (p = 1) a 24.5 ms (p = 8): **2.75 veces más lenta**.
  - **Arrancar pods es el 51 % de T(1):** las 16 tareas suman 65.9 s de cómputo, pero T(1) = 134 s.
  - El costo por foto lo predicen los megapíxeles (r = 0.95), no los bytes (r = 0.50).
  - I simulado: block 1.185, cyclic 1.119, lpt 1.065.
- **Fallos:** `backoffLimitPerIndex: 2` cuenta los fallos **por índice**. En la prueba solo se
  repitió el índice 3, los otros 15 no.
- **Clúster del examen:** k3s en 3 laptops (16 núcleos y 32 hilos en total), NFS desde el líder,
  PV/PVC `ReadWriteMany`, imagen en `ghcr.io/diegozerm/bordes:1.0` y `topologySpreadConstraints`.
- **Uso de IA:** se usó un asistente de IA (Claude Code) para desarrollar código, experimentos
  y documentación. Cada quien subió y debe saber explicar su parte.

---

## 3. Preguntas y respuestas

### Diego: líder, NFS, PV/PVC, imagen, Job y drenado

**¿Por qué la Ruta A y no la nube?**
Porque tenemos tres laptops con Linux y así no dependemos de créditos ni de cuentas de Azure.
La de Axel no entra porque usa WSL 2, cuya red NAT no deja que otras máquinas lleguen a su kubelet.

**¿Qué hace `instalar-lider.sh`?**
Instala el servidor NFS y exporta `/srv/datos` a la red del hotspot. Abre en ufw los
puertos 6443, 10250, 8472/udp y 2049, además de las redes de pods y servicios de k3s.
Después instala k3s en modo servidor con `--node-name lider-diego` y deja el kubeconfig en
`~/.kube/config-k3s`. Al final imprime la IP y el TOKEN para los workers.

**¿Por qué NFS y no `hostPath` como en kind?**
En kind los 3 "nodos" eran contenedores en la misma laptop y montaban la misma carpeta.
Aquí cada nodo es otra máquina: un `hostPath` apuntaría al disco local de cada laptop, y
las fotos solo están en la de Diego. Con NFS todos los pods ven la misma carpeta por red.
Por eso el PV es `ReadWriteMany`: muchos pods en varios nodos leen y escriben a la vez.

**¿Qué es `all_squash, anonuid=1000`?**
Que cualquier cliente del NFS escribe como el uid 1000. El contenedor corre como uid 1000
(`USER 1000` en el Dockerfile), así que los pods pueden escribir sus `part-XXXX.csv` sin
correr como root.

**¿Por qué la imagen está en GHCR?**
En kind usábamos `kind load` para copiarla a los nodos. En un clúster real cada nodo tiene
que descargarla de un registro. Está construida para amd64 y arm64 con `docker buildx`,
así que también serviría en una Raspberry o en una Mac con ARM.

**¿Cómo llegó la imagen a cada laptop?**
Hay dos caminos y los dos los usamos. Lo normal en un clúster es que cada nodo la baje de
GHCR la primera vez, y eso es lo que medimos en el arranque en frío. Pero el hotspot es lento
y tiene datos limitados, así que antes del examen cada quien copió el archivo exportado
(`bordes-1.0-amd64.tar.zst`, 70 MB) a `/var/lib/rancher/k3s/agent/images/`. k3s importa
solo lo que hay en esa carpeta al arrancar. Es el mecanismo de k3s para instalaciones sin
internet (*air-gap*).

**¿Qué hace `topologySpreadConstraints`?**
Con `maxSkew: 1` sobre `kubernetes.io/hostname`, el scheduler intenta que ningún nodo tenga
más de un pod de diferencia con otro. Usamos `whenUnsatisfiable: ScheduleAnyway` para que,
si un nodo se cae, el Job siga en los demás en lugar de quedarse en `Pending`.

**¿Qué pasa al drenar un nodo a mitad del Job?**
`kubectl drain` expulsa los pods de ese nodo. Llevan la condición `DisruptionTarget`, y la
regla `podFailurePolicy: Ignore` hace que esa expulsión **no cuente** contra
`backoffLimitPerIndex`. El controlador del Job vuelve a crear esos índices en otros nodos.
Los índices que ya terminaron no se repiten, porque su resultado ya está en el NFS.
`failedIndexes` queda vacío.

**¿Y si la laptop se apaga en vez de drenarla?**
A los ~40 s el nodo pasa a `NotReady`. A los 30 s más (`tolerationSeconds: 30`) sus pods se
marcan para expulsión, pero se quedan en `Terminating` porque el kubelet ya no contesta.
Con el taint `node.kubernetes.io/out-of-service` Kubernetes los da por muertos y el Job los repone.

### Irving: workers, merge y demo

**¿Qué hace `unir-worker.sh`?**
Instala el cliente NFS y revisa que llegue al puerto 6443 del líder. Monta el NFS a mano y
escribe un archivo de prueba, para saber que el kubelet también podrá montarlo. Abre 10250
y 8472/udp si hay ufw y por último instala k3s en modo agente con la IP y el TOKEN del líder.

**¿Para qué sirve cada puerto?**
6443/TCP es la API de Kubernetes, donde el agente se registra. 10250/TCP es el kubelet, que
usa el líder para `logs` y `exec`. 8472/UDP es la VXLAN de flannel, por donde viaja el
tráfico entre pods de distintos nodos. 2049/TCP es NFSv4.

**¿Qué hace `merge.py`?**
Junta los `part-XXXX.csv` de las 16 tareas en `resultados.csv` y arma `summary.json`, con el
desbalance I, el tiempo de cada tarea y cuántas tareas corrió cada nodo. Si se guardaron los
bordes, arma el mosaico. Cada pod escribe su propio archivo para que no se peleen por uno solo.

**¿Cómo sabe cada pod en qué nodo corrió?**
Por la Downward API: el Job pasa `spec.nodeName` en la variable `NODE_NAME`.

**¿Qué muestra la demo?**
8 tareas con 4 en paralelo sobre 400 fotos. `kubectl get pods -o wide -L
batch.kubernetes.io/job-completion-index` muestra el índice y el nodo de cada pod. En kind
quedaron 4, 2 y 2; en el clúster `[clúster]`.

### César: barrido, fallo y arranque

**¿Cómo se hace el barrido?**
`barrido.sh` lanza cada combinación con `correr-job.sh`, espera a que el Job termine y anota
T(p) en el CSV. En kind fueron 3 estrategias × p = 1, 2, 4 y 8 × 3 repeticiones = 36. En el
clúster son block y lpt × p = 1, 2, 4, 8, 16 y 24 × 3 = 36. El orden alterna estrategias
para que un ruido pasajero no caiga siempre en la misma combinación. Si se corta, se salta
las corridas que ya están en el CSV.

**¿Por qué T(p) del Job y no un cronómetro?**
`completionTime − startTime` lo mide Kubernetes, así que incluye crear pods, el scheduling y
el arranque, que es lo que de verdad paga quien lanza el lote.

**¿Cómo se provoca el fallo?**
Con `FALLAR_INDICE=3`, el worker 3 deja una marca en el volumen y sale con código 1. En el
reintento encuentra la marca y procesa normal. Se ve el índice 3 con un pod en `Error` y otro en
`Completed`, `16 Succeeded / 1 Failed` y `failedIndexes` vacío.

**¿Qué mide `arranque.sh`?**
El tiempo desde que se crea un pod fijado a un nodo hasta que su contenedor arranca. En frío
se borra antes la imagen de ese nodo con `crictl rmi`, y entonces tiene que bajar ~70 MB de
GHCR. En caliente ya la tiene. La diferencia es el costo de la descarga y se paga **una
vez por nodo**: `[clúster]` s contra `[clúster]` s.

### Axel: análisis y comparación

**¿Cómo se calcula la fracción serial?**
Despejando Amdahl: S = 1/(f + (1−f)/p) → f = (1/S − 1/p)/(1 − 1/p). En kind, con p ≤ 4,
f queda entre 0.02 y 0.06: al menos el 94 % es paralelizable.

**¿Por qué f "sube" con p = 8 en kind?**
No es código serial nuevo. Amdahl supone que la parte paralela se acelera p veces, y con más
de 4 pods en 4 núcleos físicos eso ya no pasa. El f estimado mide la saturación del hardware.

**¿Qué compara `comparar.py`?**
Lee la tabla de kind y la del clúster, que salen del mismo `analyze.py`. Pone T, S y E en la
misma figura (punteada kind, continua clúster) y arma una tabla lado a lado con fotos por
segundo (7,390 / T).

**¿El clúster escala mejor o peor?**
`[clúster]`. Lo esperado: con p ≤ 4 van parejos, porque ninguno satura. Arriba de 4, kind se
atora y el clúster sigue subiendo mientras haya núcleos físicos libres (16 en total). Lo que
lo frena después es el arranque de pods y la lectura por NFS sobre Wi-Fi.

**¿El tamaño del archivo predice el costo?**
Regular: r = 0.50 contra bytes y r = 0.95 contra megapíxeles. Por eso LPT por bytes deja
I = 1.065 en la simulación; por megapíxeles bajaría a 1.026.

### Para cualquiera: el cuello de botella

**¿CPU, red o NFS?**
Se distingue con los ms por foto, que incluyen la lectura del archivo:
- Si los ms por foto suben cuando p pasa los núcleos físicos, es **CPU**.
- Si con p = 1 un worker remoto tarda mucho más por foto que el líder (que lee su propio
  disco) y no se explica por su CPU, es el **NFS sobre la red**.
- Si T(p) es mucho mayor que el cómputo entre p, es el **arranque de pods**.

Resultado: `[clúster]`.

---

## 4. Lo que NO debemos afirmar

- Que el clúster "escala linealmente". Con 16 tareas de pocos segundos, el arranque pesa mucho.
- Que lpt hace más rápido el Job. Reparte mejor (I menor), pero T(p) casi no cambia.
- Que el hyper-threading duplica los núcleos. Dos hilos en un núcleo no rinden el doble.
- Que el NFS es lento o rápido sin mostrar el número de la tabla por nodo.
- Que los pods se comunican entre sí. Cada uno calcula su parte con su índice.
- Que el arranque en frío es lo normal en cada corrida. Se paga una vez por nodo; en el
  barrido todos los nodos ya tienen la imagen.
