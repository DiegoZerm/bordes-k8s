# Guion del día del examen

El orden de los pasos, quién hace cada uno y cuánto tarda. Todos los comandos se
corren en la laptop de Diego (el líder), salvo los que dicen otra cosa. Cada
evidencia que pide el profe se guarda sola en `examen/resultados/evidencias/`
con `examen/evidencias.sh`.

**Tiempo total:** de 1 h 15 min a 1 h 30 min. El barrido se lleva cerca de la mitad.

| # | Paso | Quién | Min |
|---|---|---|---:|
| 0 | Hotspot, IPs y red | todos | 5 |
| 1 | Instalar el líder | Diego | 5 |
| 2 | Unir los workers y sacar la evidencia de los nodos | Irving, César | 5 |
| 3 | Volumen NFS (PV/PVC) | Diego | 2 |
| 4 | Demo: pods por nodo y mosaico | Diego explica, Irving lee los nodos | 3 |
| 5 | Barrido de 36 corridas | nadie toca las laptops | 35–45 |
| 6 | Arranque en frío y en caliente | César | 5 |
| 7 | Drenar un nodo a mitad del Job | Diego drena, Irving explica | 3 |
| 8 | Análisis, comparación y reporte | Axel y Diego | 10 |
| 9 | Subir los resultados a GitHub | Diego | 3 |

---

## Antes del examen, con buen internet (en casa)

**Diego**
1. **Hacer pública la imagen** (si no, el arranque en frío no funciona):
   https://github.com/users/DiegoZerm/packages/container/bordes/settings → *Change visibility* → Public.
2. **Pasar el archivo de la imagen** `examen/imagen/bordes-1.0-amd64.tar.zst` (70 MB) a
   Irving y César por Drive o USB. También pasarles su guía del examen nueva, que ya trae
   la sección "Antes del examen, en tu casa".
3. **Ensayar el líder en tu laptop** (Arch con ufw), con la red de tu casa:
   ```bash
   cd ~/Work/bordes-k8s
   sudo INSTALL_K3S_VERSION=v1.37.2+k3s1 examen/instalar-lider.sh lider-diego 192.168.100.0/24
   export KUBECONFIG=~/.kube/config-k3s
   kubectl get nodes -o wide                          # lider-diego en Ready

   # Dataset al NFS: se copia del proyecto, no se vuelve a bajar
   sudo cp -a datos/entrada datos/dataset.env /srv/datos/
   sudo chown -R 1000:1000 /srv/datos

   # Imagen sin internet: k3s la importa sola al arrancar
   sudo mkdir -p /var/lib/rancher/k3s/agent/images
   sudo cp examen/imagen/bordes-1.0-amd64.tar.zst /var/lib/rancher/k3s/agent/images/
   sudo systemctl restart k3s
   sudo k3s crictl images | grep bordes                # ghcr.io/diegozerm/bordes 1.0

   IP_LIDER=<tu IP> envsubst < examen/k8s/pv-pvc.yaml.tpl | kubectl apply -f -
   kubectl get pv,pvc                                  # Bound
   EVID=/tmp/ensayo examen/evidencias.sh demo          # en un solo nodo, pero prueba todo
   ```
   Si algo falla aquí, se arregla **antes** del examen y no frente al profe.
4. **Dejarlo listo para el examen.** El día del examen se reinstala con la red del hotspot.
   El desinstalador borra el binario y las imágenes, así que primero se respaldan:
   ```bash
   sudo cp /usr/local/bin/k3s /root/k3s.bin
   sudo /usr/local/bin/k3s-uninstall.sh
   sudo install -m 755 /root/k3s.bin /usr/local/bin/k3s
   sudo mkdir -p /var/lib/rancher/k3s/agent/images
   sudo cp examen/imagen/bordes-1.0-amd64.tar.zst /var/lib/rancher/k3s/agent/images/
   ```
   `/srv/datos` no se borra: las fotos se quedan en el NFS.
5. **Probar el hotspot.** Hay celulares que aíslan a los clientes entre sí. Con dos laptops
   conectadas al hotspot, haz `ping` de una a la otra. Si no responde, usen otro celular.
6. **Integrar los PR** en el orden de `PENDIENTES.md`, para que `develop` tenga todo.

**Irving y César:** la sección "Antes del examen, en tu casa" de su guía. Bajan k3s,
copian la imagen y revisan el `sha256sum`. También deben traer la laptop cargada y el cargador.

**Axel:** no lleva nodo. Repasar `examen/comparar.py`, la Parte 4 del reporte y
`examen/DEFENSA.md`.

---

## 0. Hotspot, IPs y red (todos, 5 min)

Las 3 laptops se conectan al hotspot. Cada uno corre `ip -4 addr` y dice su IP en voz
alta. La red es la IP de Diego con el último número en 0 y `/24`. Ejemplo:
`192.168.137.23` → `192.168.137.0/24`.

Apaguen el Wi-Fi de la universidad y el cable de red, si lo hay. Si una laptop queda con
dos redes, k3s puede elegir la que no es (ver el paso 2).

## 1. Instalar el líder (Diego, 5 min)

```bash
cd ~/Work/bordes-k8s && git switch develop && git pull
docker stop $(docker ps -q --filter name=bordes-) 2>/dev/null   # apaga kind para liberar CPU
sudo INSTALL_K3S_VERSION=v1.37.2+k3s1 examen/instalar-lider.sh lider-diego <RED>
export KUBECONFIG=~/.kube/config-k3s
```
Al final se imprimen `IP_LIDER` y `TOKEN`. Pásaselos a Irving y César por mensaje, para
que no los tengan que copiar a mano.

## 2. Unir los workers (Irving y César, 5 min)

En **su** laptop:
```bash
cd ~/bordes-k8s && git switch develop && git pull
sudo INSTALL_K3S_VERSION=v1.37.2+k3s1 examen/unir-worker.sh worker-irving <IP_LIDER> <TOKEN>
sudo INSTALL_K3S_VERSION=v1.37.2+k3s1 examen/unir-worker.sh worker-cesar  <IP_LIDER> <TOKEN>
```
Debe verse la lista del NFS, `Escritura en el NFS: OK` y `Worker ... unido`.

Si una laptop tiene dos redes:
`sudo K3S_EXTRA="--node-ip <SU_IP> --flannel-iface <interfaz>" INSTALL_K3S_VERSION=v1.37.2+k3s1 examen/unir-worker.sh ...`

En el líder:
```bash
kubectl get nodes -o wide            # los 3 en Ready
examen/evidencias.sh nodos           # → evidencias/01-nodos.txt
```

## 3. Volumen NFS (Diego, 2 min)

```bash
IP_LIDER=<IP_LIDER> envsubst < examen/k8s/pv-pvc.yaml.tpl | kubectl apply -f -
examen/evidencias.sh volumen         # → evidencias/02-volumen.txt (PV y PVC en Bound)
```

## 4. Demo (3 min)

```bash
examen/evidencias.sh demo            # → evidencias/03-demo/ (pods por nodo y mosaico.png)
xdg-open examen/resultados/evidencias/03-demo/mosaico.png
```
Lo que se ve: los 8 índices repartidos en los 3 nodos, gracias a
`topologySpreadConstraints`, y el mosaico con la foto original y sus bordes. Irving lee
en voz alta qué índice cayó en qué nodo.

## 5. Barrido (35–45 min, sin tocar las laptops)

```bash
examen/barrido-cluster.sh DiegoZerm "1 2 4 8 16 24"
```
Son 2 estrategias × 6 valores de p × 3 repeticiones = 36 corridas. Si se corta, se vuelve
a lanzar el mismo comando y se salta las que ya terminaron.

**No usen las laptops mientras corre**, porque meten ruido en los tiempos (ya nos pasó en
kind). Este es el momento para repasar `DEFENSA.md` en voz alta.

## 6. Arranque en frío y en caliente (César, 5 min)

En la laptop de **Irving** se borra la imagen, para que tenga que bajarla de GHCR:
```bash
sudo k3s crictl rmi ghcr.io/diegozerm/bordes:1.0
```
En el líder:
```bash
examen/arranque.sh DiegoZerm worker-irving frio        # baja ~70 MB por el hotspot
examen/arranque.sh DiegoZerm worker-irving caliente
examen/evidencias.sh arranque                          # → evidencias/06-arranque.txt
```
Si el frío marca error de permisos, la imagen sigue privada (ver "Antes del examen", punto 1).

## 7. Drenar un nodo a mitad del Job (3 min)

```bash
examen/evidencias.sh drenado worker-cesar              # → evidencias/04-drenado/drenado.txt
```
El script lanza 4 tareas largas, espera a que haya un pod corriendo en `worker-cesar`,
lo drena y espera a que el Job termine. Al final regresa el nodo con `uncordon`. Lo que
debe verse: el índice expulsado se vuelve a crear en otro nodo, `completedIndexes=0-3` y
`failedIndexes` vacío. Para mostrarlo en vivo, en otra terminal:
`kubectl get pods -o wide -L batch.kubernetes.io/job-completion-index -w`.

## 8. Análisis, comparación y reporte (Axel y Diego, 10 min)

```bash
python3 scripts/analyze.py examen/resultados/tiempos-cluster.csv examen/resultados \
  --titulo "k3s en 3 laptops (Oxford-IIIT Pet, 16 tareas)"
python3 examen/comparar.py                             # comparacion.png y comparacion.md
examen/evidencias.sh reparto                           # → evidencias/05-reparto.txt
python3 examen/reporte/llenar.py                       # números y tablas del reporte
(cd examen/reporte && xelatex reporte.tex && xelatex reporte.tex)
```
`llenar.py` dice qué datos faltan. Lo que queda en rojo en el PDF es la interpretación:
se escribe con los números reales.

## 9. Subir los resultados (Diego, 3 min)

```bash
git switch -c feature/examen-resultados
git add examen/resultados examen/reporte
git commit -m "data(examen): barrido, arranque, drenado y reporte del clúster real"
git push -u origin feature/examen-resultados
```
Después se abre el PR hacia `develop`.

## Al terminar

En los workers: `sudo /usr/local/bin/k3s-agent-uninstall.sh`.
En el líder: `sudo /usr/local/bin/k3s-uninstall.sh`. Las fotos de `/srv/datos` se
borran a mano si ya no se necesitan.

## Si algo falla

| Síntoma | Qué hacer |
|---|---|
| El worker no llega al 6443 | No están en el mismo hotspot, o el celular aísla a los clientes. Hagan `ping` entre laptops. |
| `mount` del NFS falla | En el líder: `sudo exportfs -v` y `sudo ufw status`. La red del export debe ser la del hotspot. |
| Un nodo sale con otra IP | Tenía dos redes. Reinstálalo con `K3S_EXTRA="--node-ip ... --flannel-iface ..."`. |
| Pods en `ImagePullBackOff` | El nodo no importó la imagen y GHCR la tiene privada. Hazla pública o copia el `.tar.zst` a su carpeta de imágenes y `sudo systemctl restart k3s-agent`. |
| Pods en `Pending` | `kubectl describe pod`: si dice `Insufficient cpu`, bajen la p máxima: `"1 2 4 8 16"`. |
| Una laptop se apaga a mitad | `kubectl taint node <nodo> node.kubernetes.io/out-of-service=nodeshutdown:NoExecute`. El Job repone sus índices. |
| Solo se unió un worker | Sigan con 2 nodos y díganlo en el reporte. La comparación sigue valiendo. |
