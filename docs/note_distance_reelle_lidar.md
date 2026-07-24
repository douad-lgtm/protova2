# Distance inter-véhicules réelle par LiDAR

## Le problème initial
Dans la première version de la chaîne V2V, la distance affichée entre les deux
véhicules était erronée et **figée** (p. ex. « 20,5 m » puis « 8,1 m » alors que les
deux appareils n'étaient distants que de quelques centimètres). La cause : le calcul
de distance repose sur les **positions géographiques échangées dans les messages CAM**,
or **aucun véhicule ne dispose de GPS**. Les coordonnées étaient donc **écrites en dur**
dans les scripts (points fictifs choisis arbitrairement) → la distance n'était qu'une
**constante inventée**, sans lien avec la réalité, immobile quand le robot bougeait.

Pourquoi pas un GPS ? À cette échelle (objets à ~20 cm, en intérieur), le GPS est
inutilisable : son erreur de 2–5 m est bien plus grande que la distance à mesurer, et
il ne capte quasiment pas à l'intérieur.

## La solution : mesurer avec le LiDAR
Le capteur déjà présent et le plus précis à cette échelle est le **LiDAR** (RPLIDAR A1,
balayage 360°). Un nœud dédié en extrait la **distance réelle au véhicule voisin** :

```
/scan ─► lidar_neighbor.py ─► /v2v/neighbor_dist   (objet le plus proche devant, ± cm)
```

Cette mesure est ensuite **injectée dans le message V2V** : le véhicule émetteur se
déclare à une position située **exactement à la distance LiDAR** de la position de
référence du voisin. Le récepteur, qui calcule la distance à partir des positions CAM,
retrouve alors **la vraie distance mesurée** — sans rien changer à la logique existante.

```
lidar_neighbor (D mesuré) ─► v2v_node (positioning=lidar) : se place à D du voisin
   ─► CAM/DENM ─► récepteur : distance affichée = D  (réelle, dynamique)
```

## Résultat
La distance affichée est désormais **réelle, dynamique et vérifiable au centimètre** :
elle évolue correctement dès que le robot ou le véhicule voisin se déplace. Les DENM
d'urgence portent également cette distance réelle.

## Fichiers concernés
- `v2v/nodes/lidar_neighbor.py` — mesure la distance réelle (`/scan → /v2v/neighbor_dist`)
- `v2v/nodes/v2v_node.py` — mode `positioning=lidar`
- `launch/jetson/launch_v2v_lidar.sh` — lidar + lidar_neighbor + v2v_node
- `launch/pc/messages_cam_denm.sh` — récepteur (position de référence du voisin)
