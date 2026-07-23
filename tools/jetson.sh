#!/bin/bash
# Trouve la Jetson par sa MAC (l'IP change avec le DHCP) et s'y connecte en SSH.
# Usage :  ./jetson.sh            -> ouvre une session SSH
#          ./jetson.sh ip         -> affiche juste l'IP
MAC="14:75:5b:15:59:32"

find_ip() { ip neigh | awk -v m="$MAC" 'tolower($0) ~ tolower(m) {print $1; exit}'; }

ip=$(find_ip)
if [ -z "$ip" ]; then
    echo "Pas dans la table ARP — balayage du réseau..."
    sub=$(ip -4 route get 1.1.1.1 2>/dev/null | grep -oP 'src \K[0-9.]+' | cut -d. -f1-3)
    for i in $(seq 1 254); do ping -c1 -W1 "$sub.$i" >/dev/null 2>&1 & done
    wait
    ip=$(find_ip)
fi

if [ -z "$ip" ]; then
    echo "Jetson introuvable. Vérifie qu'elle est allumée et sur le MÊME WiFi."
    exit 1
fi

echo "Jetson trouvée -> $ip"
[ "$1" = "ip" ] && exit 0

ssh-keygen -R "$ip" >/dev/null 2>&1        # évite le blocage 'host key changed'
exec ssh -o StrictHostKeyChecking=accept-new "protova2@$ip"
