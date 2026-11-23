# Règles du PI — recherche (V3.1, #13)

Statut : **non validé**. Rien ici n'est utilisé par le moteur tant que `data/pi_rules.json` n'a pas `validated: true`.

## Hypothèses (sources à citer, à confirmer par observations)
- …

## Questions ouvertes
- Seuils de PV exacts et arrondi du pourcentage affiché dans le cœur.
- Centre de rotation (joueur ? centre de carte ?) et sens.
- Dépendances éventuelles (sort, orientation, tour…).

## Protocole
Pour chaque test en combat : capture + ligne dans `pi_observations.csv` (cellule joueur, PV %, cellule cliquée, cellule d'impact).
Couvrir chaque tranche de PV et les valeurs exactement sur les seuils.
