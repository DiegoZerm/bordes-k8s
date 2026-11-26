#!/usr/bin/env bash
# Descarga y descomprime el dataset asignado en datos/entrada/ y escribe
# datos/dataset.env con la carpeta de fotos y cuántas usar.
#
# Uso: scripts/descargar-datos.sh <dataset>
#   dataset: pets (el del equipo 5). Los demás se dejan como referencia.
set -euo pipefail

DATASET="${1:-pets}"
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
DATOS="${DATOS:-$RAIZ/datos}"   # en el examen: DATOS=/srv/datos (el NFS)
ENTRADA="$DATOS/entrada"
mkdir -p "$ENTRADA" "$DATOS/salida" "$DATOS/descargas"

case "$DATASET" in
  pets)
    URL="https://www.robots.ox.ac.uk/~vgg/data/pets/data/images.tar.gz"
    ARCHIVO="$DATOS/descargas/pets-images.tar.gz"
    CARPETA="images"
    FOTOS=7349
    ;;
  imagenette)
    URL="https://s3.amazonaws.com/fast-ai-imageclas/imagenette2.tgz"
    ARCHIVO="$DATOS/descargas/imagenette2.tgz"
    CARPETA="imagenette2/val"
    FOTOS=3925
    ;;
  flowers102)
    URL="https://www.robots.ox.ac.uk/~vgg/data/flowers/102/102flowers.tgz"
    ARCHIVO="$DATOS/descargas/102flowers.tgz"
    CARPETA="jpg"
    FOTOS=8189
    ;;
  *)
    echo "Dataset no soportado: $DATASET (usa pets, imagenette o flowers102)" >&2
    exit 1
    ;;
esac

# 1. Descarga (se salta si ya está completa; -C - reanuda si se cortó)
if [ ! -f "$ARCHIVO.ok" ]; then
  echo "Descargando $DATASET desde $URL"
  curl -L --fail --retry 3 -C - -o "$ARCHIVO" "$URL"
  touch "$ARCHIVO.ok"
fi

# 2. Descompresión
if [ ! -d "$ENTRADA/$CARPETA" ]; then
  echo "Descomprimiendo en $ENTRADA"
  tar -xzf "$ARCHIVO" -C "$ENTRADA"
fi

# 3. Solo cuentan las fotos .jpg (el tar de pets trae también unos .mat)
HAY=$(find "$ENTRADA/$CARPETA" -maxdepth 1 -type f -iname '*.jpg' | wc -l)
echo "Fotos .jpg encontradas: $HAY (la tabla del curso dice $FOTOS; se procesan todas)"
FOTOS=$HAY

cat > "$DATOS/dataset.env" << EOF
DATASET=$DATASET
CARPETA=$CARPETA
FOTOS=$FOTOS
EOF
echo "Listo: $DATOS/dataset.env"
cat "$DATOS/dataset.env"
