# Imagen del worker de detección de bordes (bordes:1.0)
FROM python:3.12-slim

# Sin .pyc y con la salida de print sin búfer, para ver los logs en kubectl logs
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY worker.py merge.py ./

# Usuario sin privilegios; escribe en /data/salida (montada desde el nodo)
RUN useradd --uid 1000 --create-home bordes
USER 1000

ENTRYPOINT ["python", "worker.py"]
