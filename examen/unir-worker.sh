#!/usr/bin/env bash
# Une una laptop WORKER (Ubuntu 22.04/24.04 o Arch) al clúster k3s del líder.
# Instala el cliente NFS, comprueba que el NFS del líder se monta a mano y
# luego instala k3s en modo agente.
#
# Uso: sudo examen/unir-worker.sh <nombre-del-nodo> <IP_LIDER> <TOKEN>
#   ej: sudo examen/unir-worker.sh worker-irving 192.168.137.10 K10abc...::server:xyz
# Con dos redes: sudo K3S_EXTRA="--node-ip <IP> --flannel-iface <interfaz>" examen/unir-worker.sh ...
set -euo pipefail

NODO="${1:?Falta el nombre del nodo, ej. worker-irving}"
IP_LIDER="${2:?Falta la IP del líder}"
TOKEN="${3:?Falta el token del líder}"

[ "$(id -u)" = 0 ] || { echo "Córrelo con sudo" >&2; exit 1; }

# 1. Cliente NFS (lo usa el kubelet para montar el PersistentVolume)
if command -v pacman >/dev/null; then
  pacman -S --needed --noconfirm nfs-utils curl
else
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get install -y -qq nfs-common curl >/dev/null
fi

# 2. ¿Se ve el líder? API de Kubernetes y NFS
timeout 5 bash -c "</dev/tcp/$IP_LIDER/6443" \
  || { echo "No llego al puerto 6443 del líder ($IP_LIDER). ¿Misma red? ¿Firewall?" >&2; exit 1; }

# 3. Montaje de prueba del NFS, a mano (evidencia de la Parte 1)
mkdir -p /mnt/prueba-nfs
mount -t nfs4 "$IP_LIDER:/srv/datos" /mnt/prueba-nfs
echo "Contenido del NFS visto desde $NODO:"
ls /mnt/prueba-nfs
touch "/mnt/prueba-nfs/salida/hola-desde-$NODO" && echo "Escritura en el NFS: OK"
umount /mnt/prueba-nfs

# 4. Firewall local (solo si ufw está activo)
if command -v ufw >/dev/null && ufw status | grep -q "Status: active"; then
  ufw allow 10250/tcp
  ufw allow 8472/udp
fi

# 5. k3s agente unido al líder
curl -sfL https://get.k3s.io | \
  K3S_URL="https://$IP_LIDER:6443" K3S_TOKEN="$TOKEN" \
  INSTALL_K3S_EXEC="agent --node-name $NODO ${K3S_EXTRA:-}" sh -

echo
echo "Worker $NODO unido. En el líder revisa: kubectl get nodes -o wide"
