# Résultats et limites

Une section par issue (`## Vx.y (#n)`) : ce qui est validé, comment (tests / captures / combat réel), limites connues.

## Socle (harness)
- Géométrie de grille (`core/grid.py`) : convention 560 cellules Dofus, aller-retour id ↔ (x, y) ↔ pixel testé sur toutes les cellules.
- **À valider sur captures Unity** : que Harebourg utilise bien la grille 560 cellules et le sens écran de `rotate90`.
- Carte Harebourg et règles PI : schémas en place, `validated: false` — aucune donnée inventée.

## V1.1 — Modélisation de la carte (#4)
- Modèle : `outside`, `non_walkable`, `non_targetable`, `blocks_los` (marchable et ciblable sont **indépendants** : trou = non marchable mais ciblable).
- Outil de relevé : `uv run pi-tool-map capture.png` (clic = type, Maj+clic = ligne de vue, Ctrl+S = enregistre la carte + la calibration de la capture). Testé hors écran (clic → type → sauvegarde).
- **Reste à faire (utilisateur)** : relever la carte réelle sur captures de référence (bords, rocher central), puis passer `validated: true`. Aucune donnée inventée.

## V1.2 — Overlay transparent (#5)
- Fenêtre Qt sans cadre, toujours au-dessus, `WindowTransparentForInput` + `WS_EX_TRANSPARENT|NOACTIVATE|TOOLWINDOW` : clics traversants, pas de focus, absente d'Alt-Tab. Exclue des captures (`WDA_EXCLUDEFROMCAPTURE`, Win10 2004+) en prévision de V2.1.
- Suivi de Dofus toutes les 100 ms (fenêtre `UnityWndClass` dont le titre contient « Dofus », réglable) ; masquée si Dofus est introuvable, réduit ou pas au premier plan (option).
- Raccourcis globaux (observation seule, aucune touche envoyée) + menu dans la zone de notification.
- Testé : logique de suivi avec fenêtre simulée, rendu offscreen. **Non testé sur Windows réel.**

## V1.3 — Calibration (#6)
- Calibration affine en px physiques relatifs à la zone client (DPI per-monitor v2) : un déplacement de fenêtre ne la casse pas.
- Mode calibration (Ctrl+Alt+C) : seul moment où l'overlay capte la souris ; glisser / molette / Maj+molette / flèches / Entrée / Échap.
- Profils enregistrés par taille dans `%APPDATA%/pi_tool/calibration.json` ; autre taille → profil d'aspect le plus proche mis à l'échelle (`scale_mode` : `fit` par défaut = bandes noires centrées, ou `height`/`width`/`stretch`).
- Détection des bandes noires disponible sur capture (`vision.render.content_rect`), utilisée à partir de V2.
- **À valider** : quel `scale_mode` correspond au comportement réel de Dofus Unity en 16:9 / 21:9 ; écrans à DPI mixtes.

## V1.4 — Quadrillage debug (#7)
- Quadrillage affichable indépendamment de l'overlay (Ctrl+Alt+G), identifiants optionnels (Ctrl+Alt+I), opacité réglable. La calibration est conservée quand on masque.
- Couleurs (Okabe-Ito) : obstacle vermillon, non marchable bleu, non ciblable jaune, contour noir épais = bloque la ligne de vue.
- Comparaison aux captures réelles : `./dev render capture.png [--ids]` (affiche le résidu d'ajustement si `calib_points` est annoté).

### Checklist de validation manuelle (Windows, Dofus ouvert sur Harebourg)
- [ ] L'overlay suit la fenêtre (déplacement, redimensionnement, réduction, plein écran fenêtré).
- [ ] Les clics et le survol passent au jeu ; Dofus garde le focus.
- [ ] Calibration en 16:9 puis 21:9 : cellules alignées aux 4 coins et sur le rocher central.
- [ ] Après redimensionnement sans recalibrer : décalage < ¼ de cellule (sinon noter le `scale_mode` qui marche).
- [ ] Windows à 100 %, 125 %, 150 % : alignement identique.
- [ ] Une capture d'écran (Win+Maj+S) n'affiche pas l'overlay.

## V2.1 — Capture sans overlay (#8)
- `platform/capture.py` : zone client en px physiques, BGR. `screen` = mss (overlay invisible grâce à `WDA_EXCLUDEFROMCAPTURE`), `window` = `PrintWindow(PW_CLIENTONLY|PW_RENDERFULLCONTENT)` sur la fenêtre Dofus (overlay jamais dedans).
- `auto` (défaut) : `screen` si l'exclusion a réussi, sinon `window` seul ; image noire/vide ⇒ méthode suivante, puis frame rejetée. Taille ≠ zone client ⇒ frame ignorée.
- Testé : choix de méthode, repli, rejet des images noires (Linux, captures simulées). **Non testé sur Windows réel** (marqueur `win`).
- **À valider** : `PrintWindow` sur Dofus Unity (peut renvoyer du noir selon GPU) ; capture en plein écran exclusif (non supporté, utiliser fenêtré / plein écran fenêtré).

## V2.2 — Cercles alliés / ennemis (#9)
- Détection guidée par la calibration : pour chaque case marchable, échantillonnage de l'anneau attendu (3 rayons × 48 angles) ; case retenue si ≥ 42 % des angles ont la couleur d'équipe. Projection sur la case exacte par construction.
- Rejets : petites taches et lignes (peu d'angles), grandes zones colorées (anneau de contrôle à 0,72 case couvert, contraste < 0,3), anneau voisin plus fort (case adjacente < 60 % du score).
- Testé sur images synthétiques : 1280×720, 1920×1080, 2560×1080, 3840×2160, anneaux à moitié masqués par le personnage, ennemis adjacents, leurres ⇒ précision/rappel 100 % ; ~16 ms par image.
- Scintillement / animations : confirmation 2 images sur 3 (V2.5).
- **À valider sur captures réelles** : plages HSV bleu/rouge (premières estimations), taille réelle des cercles, couleurs de la carte Harebourg (faux positifs ?), invocations, effets de sorts. Mesurer avec `./dev eval` et reporter précision/rappel ici.

## V2.3 — Personnage contrôlé (#10)
- Aucun indice visuel validé pour l'instant : `Frame.player_cue` reste vide (aucune supposition).
- Règles : un seul allié ⇒ c'est le joueur ; sinon sélection manuelle (`Ctrl+Alt+P` + clic sur sa case, l'overlay ne capte la souris que pendant ce mode).
- Suivi : si seul le joueur disparaît et un seul allié apparaît, on le suit ; changement ambigu ⇒ joueur masqué (l'ancre manuelle revient si la case réapparaît).
- **À fournir** : captures avec plusieurs alliés en indiquant `player` dans le .json, pour chercher un indice (cercle différent, timeline, surbrillance de tour).

## V2.4 — OCR du % de PV (#11)
- Lit uniquement le texte « 85 % » du cœur : texte clair non saturé isolé du cœur rouge, glyphes normalisés en hauteur (indépendant de la taille d'interface), corrélation avec des modèles appris.
- Refus (valeur masquée) : score < 0,7, écart avec le 2ᵉ choix < 0,06, texte mal formé, zéro initial, > 100, zone hors image.
- Zone calibrable (`Ctrl+Alt+H`), stockée en fractions de la zone client (`hp_roi` dans settings.json).
- Testé sur cœurs synthétiques (police Hershey, échelles 0,8 à 1,8) : lectures exactes, flou / curseur / > 100 refusés.
- Modèles : `./dev digits` les apprend depuis les captures annotées (`hp_roi` + `hp_pct`) ; `validated` seulement si ≥ 5 captures, 10 chiffres couverts et toutes relues exactement. Non validé ⇒ PV affichés en debug seulement, jamais transmis.
- **À fournir** : ≥ 5 captures (idéalement 10+) avec PV variés couvrant 0–9, à 2 tailles d'interface.

## V2.5 — Actualisation et fiabilité (#12)
- `core/combat.py` : case confirmée si vue dans 2 des 3 dernières images (déplacements, morts, faux positifs ponctuels) ; PV acceptés après 2 lectures identiques.
- Horodatage : tout est masqué au-delà de 1,5 s sans image exploitable (PV : sans lecture valide). Confiance = stabilité sur la fenêtre ; < 60 % ⇒ `reliable = False` (V3 n'affichera rien).
- Redimensionnement / recalibration ⇒ historique vidé. Vision suspendue pendant la calibration ou sans calibration.
- Debug (`Ctrl+Alt+D`) : cases détectées (bleu / rouge, joueur « J »), zone PV, bandeau PV · joueur · nb alliés/ennemis · confiance · âge · OCR brut.
- Testé : transitions (scintillement, déplacement, mort, échec de capture, PV changeant, ambiguïté joueur) et boucle complète contrôleur sur images synthétiques.

### Checklist de validation manuelle V2 (Windows, combat Harebourg)
- [ ] Debug activé : alliés et ennemis encadrés sur la bonne case, y compris personnages superposés aux décors.
- [ ] Un déplacement / une mort est reflété en < 1 s ; aucune case fantôme persistante.
- [ ] Zone PV réglée : la valeur suit les dégâts / soins ; jamais de valeur fausse (au pire « ? »).
- [ ] Plusieurs alliés : `Ctrl+Alt+P` désigne le bon personnage, suivi après déplacement.
- [ ] Win+Maj+S pendant le debug : l'overlay n'apparaît pas sur la capture.
- [ ] Ajouter 5–10 captures annotées puis `./dev eval` et `./dev digits` ; reporter les chiffres ci-dessus.
