# pi_tool

Overlay Windows d'aide visuelle pour **Dofus Unity**, combat du **Comte Harebourg**.
Pour chaque ennemi, l'outil affiche deux losanges de la même couleur : la cellule occupée par l'ennemi et la cellule à viser pour que le PI renvoie le sort sur lui.

> **Analyse visuelle uniquement.** Capture d'écran + overlay transparent à clics traversants.
> Aucun clic ni touche envoyés au jeu, aucune lecture mémoire, aucune interception réseau.

## Fonctionnement

```
capture fenêtre Dofus ──► vision (cercles alliés/ennemis, % PV du cœur)
                                     │
calibration ◄── grille iso 560 cellules ──► moteur PI (règles validées)
     │                                           │
     └──────────► overlay transparent ◄──────────┘  (losanges, quadrillage debug)
```

| Version | Contenu | Issues |
|---|---|---|
| **V1** | Overlay transparent, quadrillage isométrique calé sur la carte, calibration multi-résolutions | #1, #4–#7 |
| **V2** | Reconnaissance visuelle : capture sans overlay, cercles, joueur contrôlé, OCR des PV | #2, #8–#12 |
| **V3** | Moteur PI et paires de cellules colorées | #3, #13–#17 |

La formule exacte du PI et la carte relevée restent à valider sur captures réelles : tant qu'elles ne le sont pas, l'outil **n'affiche aucun résultat deviné**.

## Installation (Windows 10 2004+ / 11)

```powershell
# Python 3.11+ et uv (https://docs.astral.sh/uv/)
git clone https://github.com/Kahinh/pi_tool && cd pi_tool
uv sync --extra vision --extra win
uv run pi-tool
```

## Utilisation (V1–V2 — à valider sur Windows)

Lancer Dofus, puis `uv run pi-tool`. L'overlay suit automatiquement la fenêtre du jeu et se masque quand Dofus n'est pas au premier plan. Une icône dans la barre des tâches donne accès aux mêmes réglages.

| Raccourci | Action |
|---|---|
| `Ctrl+Alt+O` | Afficher / masquer l'overlay |
| `Ctrl+Alt+G` | Afficher / masquer le quadrillage (debug) |
| `Ctrl+Alt+I` | Afficher / masquer les identifiants de cellules |
| `Ctrl+Alt+C` | Mode calibration (voir ci-dessous) |
| `Ctrl+Alt+D` | Debug vision : alliés / ennemis / joueur détectés, PV lus, confiance, âge |
| `Ctrl+Alt+H` | Régler la zone PV (le pourcentage dans le cœur) |
| `Ctrl+Alt+P` | Désigner son personnage (clic sur sa case) si la détection auto ne suffit pas |
| `Ctrl+Alt+Q` | Quitter |

**Calibration** (une fois par résolution) : en mode calibration, l'overlay capte la souris le temps du réglage.
Glisser = déplacer la grille · molette = taille · `Maj`+molette = aplatissement · flèches = ajustement au pixel · `Entrée` = enregistrer · `Échap` = annuler.
Les profils sont enregistrés par taille de fenêtre et réutilisés (mis à l'échelle) pour les autres tailles.

**Reconnaissance visuelle** (V2 — à valider sur captures réelles) : une fois la grille calibrée, pi_tool capture la fenêtre de Dofus (sans son propre overlay) ~4 fois par seconde, repère les cercles bleus (alliés) et rouges (ennemis) sous les personnages et lit le pourcentage de PV dans le cœur. Données périmées (> 1,5 s) ou incertaines ⇒ masquées.
- Zone PV : `Ctrl+Alt+H`, encadrer le « 85 % » du cœur (glisser / molette / `Maj`+molette), `Entrée`.
- Lecture des PV : apprise sur vos captures annotées (`./dev digits`, ≥ 5 captures couvrant les chiffres 0–9) ; tant que ce n'est pas validé, la valeur n'apparaît qu'en debug.
- Personnage contrôlé : automatique s'il n'y a qu'un allié ; sinon `Ctrl+Alt+P` puis clic sur sa case (suivi ensuite tant que le déplacement est non ambigu).

**Relevé de carte** (V1.1) : `uv run pi-tool-map <capture.png>` ouvre l'éditeur. Clic = changer le type de cellule (normale → obstacle → non marchable → non ciblable → hors carte), `Maj`+clic = bloque la ligne de vue, `Ctrl+S` = enregistrer dans `data/maps/harebourg.json`.

## Contribuer des captures

Les tests d'intégration reposent sur des captures réelles annotées dans `tests/fixtures/screens/` (une image `.png` + un fichier `.json` décrivant cellules, alliés, ennemis, PV…). Format détaillé : `.claude/skills/fixtures/SKILL.md`.
Les observations en combat pour valider le PI vont dans `docs/research/pi_observations.csv`.

## Développement

```bash
./dev check      # lint + règles d'architecture + tests (Windows : dev.cmd check)
./dev affected   # tests impactés par les modifications en cours
./dev render IMG # dessine le quadrillage calibré sur une capture (.cache/view/)
./dev eval       # précision/rappel cercles + exactitude PV sur les captures annotées
./dev digits     # apprend les chiffres du cœur depuis les captures annotées (data/hp_digits)
```

- `src/pi_tool/core` — logique pure (grille, calibration, carte, moteur PI), testable partout.
- `src/pi_tool/vision` — traitement d'images (OpenCV) : cercles, OCR des PV.
- `src/pi_tool/platform` — Windows : overlay Qt, capture, Win32, DPI, raccourcis.
- `src/pi_tool/app` — application, éditeur de carte, réglages.
- `data/` — carte Harebourg et règles PI (`validated: false` tant que non prouvées).
- `docs/LIMITS.md` — résultats et limites connues par issue.

Le projet est outillé pour Claude Code : `CLAUDE.md`, `CODEGRAPH.md` (carte du code générée), skills et hooks dans `.claude/`.
