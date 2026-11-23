# pi_tool

Overlay Windows pour Dofus Unity (combat du Comte Harebourg) : affiche pour chaque ennemi la cellule à viser pour que le PI renvoie le sort sur lui.
**Analyse visuelle uniquement** — capture d'écran + overlay transparent à clics traversants. Aucun clic automatique, aucune lecture mémoire, aucun sniffing.

Feuille de route : issues #1 (V1 overlay/quadrillage) → #2 (V2 reconnaissance visuelle) → #3 (V3 moteur PI).

## Démarrage
```
uv sync --extra vision --extra win   # Windows
./dev check                           # Linux/macOS  (Windows : dev.cmd check)
```

## Structure
- `src/pi_tool/core` — logique pure (grille, carte, moteur PI), testable partout.
- `src/pi_tool/vision` — détection cercles / OCR PV sur images.
- `src/pi_tool/platform` — Windows : overlay, capture, suivi fenêtre, DPI.
- `src/pi_tool/app` — assemblage et boucle d'état.
- `data/` — carte Harebourg et règles PI (non validées tant que non prouvées).
- `tests/fixtures/screens` — captures réelles annotées.
- `docs/LIMITS.md` — résultats et limites par issue.

`CODEGRAPH.md` (généré) et `.claude/` (skills, hooks) servent au développement assisté par Claude Code.
