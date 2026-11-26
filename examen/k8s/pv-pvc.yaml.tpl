# Volumen compartido por red: el NFS de la laptop líder.
# ${IP_LIDER} lo sustituye envsubst. Todos los pods, en cualquier nodo, montan
# el mismo /srv/datos en /data (ReadWriteMany).
apiVersion: v1
kind: PersistentVolume
metadata:
  name: datos-nfs
spec:
  capacity:
    storage: 10Gi
  accessModes:
    - ReadWriteMany            # muchos nodos leen y escriben a la vez
  persistentVolumeReclaimPolicy: Retain   # borrar el PVC no borra las fotos
  storageClassName: ""         # PV estático: no usar el local-path de k3s
  mountOptions:
    - nfsvers=4.1
    - hard
  nfs:
    server: ${IP_LIDER}
    path: /srv/datos
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: datos
spec:
  accessModes:
    - ReadWriteMany
  storageClassName: ""
  volumeName: datos-nfs        # se liga a este PV y a ningún otro
  resources:
    requests:
      storage: 10Gi
