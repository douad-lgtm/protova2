#!/bin/bash
# =============================================================================
# setup_5g.sh - a lancer UNE FOIS sur la Jetson (avec sudo) apres reflash.
# Equivalent fonctionnel recree d'apres specs. Configure la 5G Quectel :
#   1) regle udev  -> renomme l'interface du dongle 5G en '5g0' (par VID/PID)
#   2) sudoers     -> 'protova2' peut faire ip/ifup/ifdown SANS mot de passe
# Le renommage s'applique apres avoir REBRANCHE physiquement le dongle.
#
# NB : l'adresse IP statique (172.16.48.6/28) et la route sont posees au lancement
#      par launch_car.sh, pas ici. Ce script ne fait que le socle systeme.
# VID/PID Quectel : 2c7c:0801 (RM5xx). Verifie avec 'lsusb' et ajuste si besoin.
# =============================================================================
set -e
if [ "$EUID" -ne 0 ]; then
  echo "A lancer avec sudo :  sudo ./setup_5g.sh"
  exit 1
fi

QVID="2c7c"
QPID="0801"

# 1) regle udev : renomme l'iface reseau du dongle 5G en 5g0 -----------------
cat > /etc/udev/rules.d/70-quectel-5g.rules <<EOF
# Renomme l'interface reseau du dongle 5G Quectel en '5g0' (stable)
SUBSYSTEM=="net", ACTION=="add", ATTRS{idVendor}=="${QVID}", ATTRS{idProduct}=="${QPID}", NAME="5g0"
EOF
echo "[1/3] regle udev creee -> /etc/udev/rules.d/70-quectel-5g.rules"

# 2) sudoers : commandes reseau sans mot de passe pour protova2 --------------
cat > /etc/sudoers.d/protova2-5g <<'EOF'
protova2 ALL=(ALL) NOPASSWD: /usr/sbin/ip, /sbin/ifup, /sbin/ifdown, /usr/bin/dhclient, /usr/bin/systemctl restart ModemManager
EOF
chmod 440 /etc/sudoers.d/protova2-5g
echo "[2/3] sudoers cree -> /etc/sudoers.d/protova2-5g"

# 3) recharger udev ----------------------------------------------------------
udevadm control --reload-rules && udevadm trigger
echo "[3/3] udev recharge."

echo ""
echo "OK. REBRANCHE physiquement le dongle 5G, puis verifie :"
echo "    ip link show 5g0"
echo "    lsusb | grep -i quectel"
echo "Ensuite la 5G se monte via launch_car.sh (IP 172.16.48.6/28)."
