#!/usr/bin/env bash
# Prepara la laptop LÍDER del examen (Ruta A): servidor NFS con /srv/datos y
# k3s en modo servidor (control-plane). Funciona en Ubuntu (apt) y Arch (pacman).
#
# Uso: sudo examen/instalar-lider.sh <nombre-del-nodo> <red-del-equipo>
#   ej: sudo examen/instalar-lider.sh lider-diego 192.168.137.0/24
#
# Al final imprime la IP del líder y el TOKEN que necesitan los workers.
# Si la laptop tiene dos redes (Wi-Fi y cable), fija la del equipo con
#   sudo K3S_EXTRA="--node-ip <IP> --flannel-iface <interfaz>" examen/instalar-lider.sh ...
set -euo pipefail

NODO="${1:?Falta el nombre del nodo, ej. lider-diego}"
RED="${2:?Falta la red del equipo, ej. 192.168.137.0/24}"
EXPORT=/srv/datos
USUARIO="${SUDO_USER:-$USER}"
UID_PODS=1000   # el contenedor corre como uid 1000 (ver app/Dockerfile)

[ "$(id -u)" = 0 ] || { echo "Córrelo con sudo" >&2; exit 1; }

# 1. Paquetes del servidor NFS
if command -v pacman >/dev/null; then
  pacman -S --needed --noconfirm nfs-utils curl
  SERVICIO_NFS=nfsv4-server
else
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get install -y -qq nfs-kernel-server curl >/dev/null
  SERVICIO_NFS=nfs-kernel-server
fi

# 2. Carpeta compartida: entrada/ (fotos) y salida/ (resultados), dueño uid 1000
mkdir -p "$EXPORT/entrada" "$EXPORT/salida"
chown -R "$UID_PODS:$UID_PODS" "$EXPORT"
# all_squash: cualquier cliente escribe como uid 1000, igual que los pods
LINEA="$EXPORT $RED(rw,sync,no_subtree_check,all_squash,anonuid=$UID_PODS,anongid=$UID_PODS)"
grep -qF "$EXPORT " /etc/exports 2>/dev/null && sed -i "\|^$EXPORT |d" /etc/exports
echo "$LINEA" >> /etc/exports
systemctl enable --now "$SERVICIO_NFS"
exportfs -ra
exportfs -v

# 3. Firewall: puertos de k3s y NFS (solo si ufw está activo)
if command -v ufw >/dev/null && ufw status | grep -q "Status: active"; then
  ufw allow from "$RED" to any port 6443 proto tcp    # API de Kubernetes
  ufw allow from "$RED" to any port 10250 proto tcp   # kubelet (logs, exec)
  ufw allow from "$RED" to any port 8472 proto udp    # VXLAN de flannel
  ufw allow from "$RED" to any port 2049 proto tcp    # NFSv4
  ufw allow from 10.42.0.0/16 to any                  # red de pods de k3s
  ufw allow from 10.43.0.0/16 to any                  # red de servicios de k3s
fi

# 4. k3s servidor. --node-name fija el nombre aunque el hostname se repita
#    --write-kubeconfig-mode 644 deja usar kubectl sin sudo
curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="server --node-name $NODO --write-kubeconfig-mode 644 ${K3S_EXTRA:-}" sh -

# kubectl del usuario apuntando a k3s
install -d -o "$USUARIO" "/home/$USUARIO/.kube"
cp /etc/rancher/k3s/k3s.yaml "/home/$USUARIO/.kube/config-k3s"
chown "$USUARIO" "/home/$USUARIO/.kube/config-k3s"

IP=${IP_LIDER:-}; [ -n "$IP" ] || IP=$(ip -4 route get 1.1.1.1 | awk '{for(i=1;i<=NF;i++) if($i=="src") print $(i+1)}')
echo
echo "=================================================================="
echo " Líder listo: $NODO"
echo " IP_LIDER = $IP"
echo " TOKEN    = $(cat /var/lib/rancher/k3s/server/node-token)"
echo " En cada worker:  sudo examen/unir-worker.sh <nombre> $IP <TOKEN>"
echo " kubectl:         export KUBECONFIG=~/.kube/config-k3s"
echo "=================================================================="
