# Clúster local: 1 control-plane + 3 workers, todos contenedores de Docker.
# La carpeta datos/ del repo se monta en /data de cada nodo, así cualquier pod
# lee las mismas fotos sin copiarlas. ${DATOS_ABS} lo sustituye envsubst con la
# ruta absoluta (kind no acepta rutas relativas).
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
name: bordes
nodes:
  - role: control-plane
  - role: worker
    extraMounts:
      - hostPath: ${DATOS_ABS}
        containerPath: /data
  - role: worker
    extraMounts:
      - hostPath: ${DATOS_ABS}
        containerPath: /data
  - role: worker
    extraMounts:
      - hostPath: ${DATOS_ABS}
        containerPath: /data
