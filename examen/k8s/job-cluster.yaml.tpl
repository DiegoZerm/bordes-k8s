# Job indexado para el clúster real. Es el mismo de k8s/job.yaml.tpl con tres cambios:
#   1. la imagen viene de GHCR (${IMAGEN} = ghcr.io/<usuario>/bordes:1.0)
#   2. los datos llegan por el PVC "datos" (NFS) en lugar de hostPath
#   3. topologySpreadConstraints reparte los pods entre nodos
# Variables: CORRIDA TAREAS P ESTRATEGIA LIMITE GUARDAR FALLAR IMAGEN CARPETA
apiVersion: batch/v1
kind: Job
metadata:
  name: bordes-${CORRIDA}
  labels:
    app: bordes
    corrida: "${CORRIDA}"
spec:
  completionMode: Indexed
  completions: ${TAREAS}
  parallelism: ${P}
  backoffLimitPerIndex: 2      # si se drena un nodo, sus índices se reintentan en otro
  maxFailedIndexes: 2
  podFailurePolicy:
    rules:
      # Un pod expulsado por drenar o apagar un nodo NO cuenta como fallo del índice
      - action: Ignore
        onPodConditions:
          - type: DisruptionTarget
  template:
    metadata:
      labels:
        app: bordes
        corrida: "${CORRIDA}"
    spec:
      restartPolicy: Never
      # El líder también trabaja; quitar esta línea si se quiere solo en workers
      tolerations:
        - key: node-role.kubernetes.io/control-plane
          operator: Exists
          effect: NoSchedule
        # Si una laptop se apaga o pierde la red, expulsar sus pods a los 30 s
        # (por defecto Kubernetes espera 300 s)
        - key: node.kubernetes.io/not-ready
          operator: Exists
          effect: NoExecute
          tolerationSeconds: 30
        - key: node.kubernetes.io/unreachable
          operator: Exists
          effect: NoExecute
          tolerationSeconds: 30
      topologySpreadConstraints:
        - maxSkew: 1                         # a lo más 1 pod de diferencia entre nodos
          topologyKey: kubernetes.io/hostname
          whenUnsatisfiable: ScheduleAnyway  # si un nodo se cae, el Job sigue
          labelSelector:
            matchLabels:
              corrida: "${CORRIDA}"
      containers:
        - name: worker
          image: ${IMAGEN}
          imagePullPolicy: IfNotPresent
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
            - name: NODE_NAME
              valueFrom:
                fieldRef:
                  fieldPath: spec.nodeName
            - name: POD_NAME
              valueFrom:
                fieldRef:
                  fieldPath: metadata.name
          resources:
            requests:
              cpu: "1"
              memory: 256Mi
            limits:
              cpu: "1"
              memory: 512Mi
          volumeMounts:
            - name: datos
              mountPath: /data
      volumes:
        - name: datos
          persistentVolumeClaim:
            claimName: datos
