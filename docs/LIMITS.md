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
