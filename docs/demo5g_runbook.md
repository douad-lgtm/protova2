# 📡 Démo téléop 5G ProtoVA2 — runbook (à jour 2026-08-06)

> PC = hub Zenoh `172.16.48.7` · Voiture (Jetson Orin) = `172.16.48.6` · les deux en /28 sur la 5G Bouygues.
> Fix important du 2026-08-06 : **SHM zenoh désactivée** dans `~/zenoh_session_car.json5` (sinon tous les nœuds ROS de la voiture meurent à l'init — `Failed to create POSIX SHM provider`).

## 0. Préparation matérielle
1. **Dongle 5G branché sur le PC** (RM520N-GL) et **sur la Jetson** (RM530N-GL) — LED allumées
2. Voiture sous tension (la Jetson démarre → le service `car5g` se lance **tout seul** au boot)
3. G29 branché au PC

## 1. 💻 PC — Terminal 1 : tout le côté PC en UNE commande
```bash
cd ~/protova2 && ./launch_pc.sh
```
(mot de passe sudo demandé). Le script fait tout : config 5G (+ correction /30→/28, suppression de la route par défaut 5G), **hub Zenoh** (port 7447), `joy_node` et le **retour de force G29**.
✔️ attends : `PC side ready — ROS2 over 5G via Zenoh`
⚠️ **Laisse ce terminal ouvert** (le fermer tue les nœuds).

## 2. 🖥️ Jetson — Terminal 2 : (re)démarrer la pile voiture
```bash
ssh protova2@10.37.11.34        # ou par la 5G : ssh protova2@172.16.48.6
sudo systemctl restart car5g     # mdp : alten
```
Le restart est utile si la voiture était allumée AVANT le hub PC (le routeur se réappaire proprement).
✔️ vérif appairage : `ss -tn | grep 7447` → doit montrer `ESTAB ... 172.16.48.7:7447`

## 3. 📊 Dashboard latence (optionnel mais joli en démo)
Dans le même SSH Jetson :
```bash
systemd-run --user --unit=monitor5g --setenv=IFACE=5g0 --setenv=PEER=172.16.48.7 python3 /home/protova2/monitor_5g.py
```
(déjà lancé ? le relancer : `systemctl --user restart monitor5g`)
Puis sur le PC, navigateur : **http://172.16.48.6:8088** — latence, débit, badge Zenoh en direct à travers la 5G.

## 4. 🚗 Conduire
1. Armer l'ESC de la voiture (interrupteur)
2. Volant → direction, pédales → avance/recul, **le tout à travers la 5G**

## 🩺 Si ça ne marche pas — diagnostic dans l'ordre
```bash
# 1. Le lien 5G ?  (depuis le PC)
ping -c3 172.16.48.6
```
- **KO** → la /30 fantôme est revenue sur la Jetson (piège n°1) :
  ```bash
  ssh protova2@10.37.11.34
  sudo ip addr del 172.16.48.6/30 dev 5g0; sudo ip addr add 172.16.48.6/28 brd 172.16.48.15 dev 5g0
  ```
- toujours KO → dongle : `lsusb | grep 2c7c` des deux côtés ; modem muet → reset AT `AT+CFUN=1,1` (ttyUSB3, 115200), attendre 8 s

```bash
# 2. L'appairage Zenoh ?  (sur la Jetson)
ss -tn | grep 7447          # ESTAB attendu ; sinon : le hub PC tourne-t-il ? (launch_pc.sh)
# 3. Les topics traversent ?  (sur le PC)
source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=125 RMW_IMPLEMENTATION=rmw_zenoh_cpp ZENOH_SESSION_CONFIG_URI=$HOME/zenoh_session_pc.json5
ros2 topic list             # doit lister /cmd_vel, /cmd_vel_G29, /joy...
# 4. Les nœuds voiture vivants ?  (sur la Jetson)
journalctl -u car5g -n 30 --no-pager   # si « Failed to create POSIX SHM provider » → la config SHM a sauté, la remettre
```

## ⏹️ Tout arrêter
- PC : `Ctrl+C` / fermer le Terminal 1 (ou `pkill -f "[r]mw_zenohd"; pkill -f "[j]oy_node"; pkill -f "[g]29_force_feedback"`)
- Jetson : `sudo systemctl stop car5g` (et `systemctl --user stop monitor5g`)
