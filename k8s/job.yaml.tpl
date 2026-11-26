# Job indexado de detección de bordes. Plantilla: envsubst sustituye ${...}.
#   CORRIDA    nombre único de la corrida (también la subcarpeta de salida)
#   TAREAS     completions: cuántos índices (0 .. TAREAS-1)
#   P          parallelism: cuántos pods a la vez como máximo
#   ESTRATEGIA block | cyclic | lpt
#   LIMITE     cuántas fotos usar (0 = todas)
#   GUARDAR    1 para guardar las imágenes de bordes (demo), 0 en el barrido
#   FALLAR     índice que falla a propósito en su primer intento (-1 = ninguno)
#   IMAGEN     imagen del worker (bordes:1.0 en kind)
#   CARPETA    subcarpeta de /data/entrada con las fotos (de datos/dataset.env)
apiVersion: batch/v1
kind: Job
metadata:
  name: bordes-${CORRIDA}
  labels:
    app: bordes
    corrida: "${CORRIDA}"
spec:
  completionMode: Indexed      # cada pod recibe JOB_COMPLETION_INDEX
  completions: ${TAREAS}
  parallelism: ${P}
  backoffLimitPerIndex: 2      # reintentos por índice (GA en Kubernetes 1.33)
  maxFailedIndexes: 2          # si más de 2 índices se agotan, el Job falla
  template:
    metadata:
      labels:
        app: bordes
        corrida: "${CORRIDA}"
    spec:
      restartPolicy: Never     # obligatorio con backoffLimitPerIndex
      containers:
        - name: worker
          image: ${IMAGEN}
          imagePullPolicy: IfNotPresent   # en kind la imagen se carga con kind load
          env:
            - name: TAREAS
              value: "${TAREAS}"
            - name: ESTRATEGIA
              value: "${ESTRATEGIA}"
            - name: ENTRADA
              value: /data/entrada/${CARPETA}
            - name: SALIDA
              value: /data/salida/${CORRIDA}
            - name: LIMITE
              value: "${LIMITE}"
            - name: GUARDAR_BORDES
              value: "${GUARDAR}"
            - name: FALLAR_INDICE
              value: "${FALLAR}"
            - name: NODE_NAME          # Downward API: en qué nodo corrió
              valueFrom:
                fieldRef:
                  fieldPath: spec.nodeName
            - name: POD_NAME
              valueFrom:
                fieldRef:
                  fieldPath: metadata.name
          resources:
            requests:                # lo que el scheduler reserva
              cpu: "1"
              memory: 256Mi
            limits:                  # techo: 1 núcleo por pod, así S(p) se puede leer
              cpu: "1"
              memory: 512Mi
          volumeMounts:
            - name: datos
              mountPath: /data
      volumes:
        - name: datos
          hostPath:                  # la carpeta datos/ que kind montó en cada nodo
            path: /data
            type: Directory
