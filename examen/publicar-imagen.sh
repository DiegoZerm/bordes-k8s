#!/usr/bin/env bash
# Construye bordes:1.0 para linux/amd64 y linux/arm64 y la publica en GitHub
# Container Registry como ghcr.io/<usuario>/bordes:1.0.
#
# Uso: examen/publicar-imagen.sh <usuario-de-github>
# Antes: gh auth refresh -s write:packages   (permiso para subir paquetes)
# Después: en GitHub > Packages > bordes > Package settings, cambiar a Public.
set -euo pipefail

USUARIO="${1:?Falta tu usuario de GitHub}"
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
IMAGEN="ghcr.io/${USUARIO,,}/bordes:1.0"   # GHCR exige minúsculas

gh auth token | docker login ghcr.io -u "$USUARIO" --password-stdin

# Builder con soporte multi-plataforma (QEMU emula arm64)
docker buildx inspect multi >/dev/null 2>&1 || docker buildx create --name multi --use
docker buildx use multi
docker buildx build --platform linux/amd64,linux/arm64 \
  --label "org.opencontainers.image.source=https://github.com/$USUARIO/bordes-k8s" \
  -t "$IMAGEN" --push "$RAIZ/app"

docker buildx imagetools inspect "$IMAGEN"
echo "Publicada: $IMAGEN"
