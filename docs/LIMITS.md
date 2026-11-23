# Résultats et limites

Une section par issue (`## Vx.y (#n)`) : ce qui est validé, comment (tests / captures / combat réel), limites connues.

## Socle (harness)
- Géométrie de grille (`core/grid.py`) : convention 560 cellules Dofus, aller-retour id ↔ (x, y) ↔ pixel testé sur toutes les cellules.
- **À valider sur captures Unity** : que Harebourg utilise bien la grille 560 cellules et le sens écran de `rotate90`.
- Carte Harebourg et règles PI : schémas en place, `validated: false` — aucune donnée inventée.
