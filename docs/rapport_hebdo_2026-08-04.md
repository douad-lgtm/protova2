# 📅 Rapport hebdomadaire — Semaine du 28 juillet au 4 août 2026

**Douae Sebti — PFE ALTEN Labs (ProtoVA) · Véhicules autonomes coopératifs**

## 🎯 Résumé de la semaine

Deux avancées majeures : la **campagne de mesures réseau WiFi vs 5G** sur ProtoVA2 est terminée et analysée (la latence est confirmée comme facteur déterminant pour la téléopération), et **ProtoVA1 est de nouveau opérationnelle** — téléopérable au volant G29 avec retour de force, premier roulage au sol effectué. L'objectif des deux plateformes opérationnelles pour la démonstration V2V (échange de messages DENM) se rapproche.

---

## 🚙 ProtoVA2 — Campagne de mesures réseau (téléopération WiFi vs 5G)

### Méthodologie
Trois scripts de mesure développés (rejouables sur n'importe quel lien, courbes régénérées à chaque campagne) :
- **Latence** : extraction des RTT ping seconde par seconde
- **Débit** : iperf3 bidirectionnel PC ↔ véhicule
- **Cadence vidéo** : comptage des images du flux caméra ROS 2 (720p)

### Résultats

| Grandeur | WiFi | 5G | Écart |
|---|---|---|---|
| **Latence moyenne (gigue)** | 68 ms (pointes à 237) | **26 ms** (17–37, stable) | 5G ×2,6 |
| Débit montant PC→véhicule | **186 Mbps** | 69 Mbps | WiFi ×2,7 |
| Débit descendant véhicule→PC | **183 Mbps** | 77 Mbps | WiFi ×2,4 |
| Cadence vidéo 720p | 30,5 im/s | 30,5 im/s | égalité |

### Analyse
Le point clé : **débit et cadence d'images sont des critères *à seuil*** — les deux réseaux dépassent largement le nécessaire (la vidéo 720p passe à 30,5 im/s dans les deux cas) — tandis que **la latence est un *facteur de mérite* continu** : chaque milliseconde compte pour la boucle volant→véhicule→retour vidéo. À 1 m/s, les 68 ms moyens du WiFi (et surtout ses pointes à 237 ms) dégradent directement la contrôlabilité, là où la 5G offre 26 ms **stables**. La 5G est donc supérieure pour la téléopération malgré son débit plus faible. Perspective : le *handover* 5G (continuité de session en mobilité) contre le *roaming* WiFi (coupure à chaque changement de borne).

Ce travail alimente le **chapitre 5 du mémoire** (rédigé cette semaine : contexte, architecture Zenoh hub-and-spoke pour la 5G, campagne de mesures, discussion).

---

## 🚗 ProtoVA1 — Remise en service complète (téléopération G29)

### Chaîne validée de bout en bout
```
G29 + retour de force (PC) → joy_node → pont UDP → Jetson Nano
   → g29_teleop → twist_mux → TX → Raspberry Pi Pico → servo + moteur
```

### Travaux réalisés
- **Firmware Pico réécrit et flashé** (FreeRTOS, 3 tâches : réception série, contrôle, encodeur) — protocole `CTRL,angle,vitesse` / `TICKS,n` à 50 Hz
- **Bug critique corrigé** : neutre ESC à 1400 µs au lieu de 1500 → la voiture partait en marche arrière rapide à la commande « stop »
- **Encodeur KY-040 + filtre RC + trigger de Schmitt 74HC14** intégré : décodage ×2 retenu → **40 ticks/tour**, paramètres d'odométrie mis en cohérence côté ROS
- **Pont UDP /joy développé** : le partage de connexion utilisé bloque les données DDS entre machines (découverte OK, données non) → pont unicast maison PC→Jetson
- **Armement ESC automatique** : le firmware émettait le signal neutre seulement après ouverture du port série → il fallait débrancher/rebrancher l'alimentation à chaque session ; corrigé (neutre dès la mise sous tension)
- **Réglages de conduite** après premier roulage : plage de vitesse élargie (20 % → 35 % de puissance max) et zone morte de l'ESC contournée → meilleure réactivité et précision à la pédale
- Service systemd + runbook 4 terminaux documentés (reproductible)

### Premier roulage au sol ✔️
Voiture téléopérée par terre au G29 avec retour de force. Constats (retards à l'accélération, vitesse bridée, armement ESC manuel) → tous corrigés (voir ci-dessus), validation des nouveaux réglages au prochain essai.

---

## ⚠️ Difficultés rencontrées et solutions

| Problème | Solution |
|---|---|
| Données DDS bloquées entre PC et Jetson (hotspot) | Pont UDP unicast maison pour /joy |
| ESC : neutre firmware faux (1400 µs) | Recalibration : 1500 µs (mesuré) |
| ESC à réarmer en débranchant à chaque session | Neutre émis dès la mise sous tension du Pico |
| Retards et manque de précision à la pédale | Plage élargie + sortie de la zone morte ESC |
| Coupures ponctuelles de téléopération | Procédure de diagnostic en place (commandes visibles ou non pendant la coupure → voiture vs réseau) |

---

## 📋 Semaine prochaine

1. **Valider la conduite** de ProtoVA1 avec les nouveaux réglages (réactivité, vitesse, arrêt net)
2. **Odométrie** ProtoVA1 (ackermann_odom, 40 ticks/tour, roue Ø104 mm, empattement 245 mm)
3. **Portage V2V sur ProtoVA1** : compilation de Vanetza/socktap sur la Jetson Nano (Ubuntu 20.04) + nœud CAM/DENM léger
4. **Objectif démo** : ProtoVA2 freine (AEB) → message **DENM** → ProtoVA1 réagit — sécurité coopérative entre deux véhicules réels
5. Rapport : chapitres 6 (Perception) et 7 (V2V) à rédiger, matériel prêt
