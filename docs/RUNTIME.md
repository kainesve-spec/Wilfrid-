# Wilfrid — runtime P0-1 (lancement, arrêt, restart)

## Lancer

```sh
python3 wilfrid.py [--data-dir DIR] [--session-id ID] [--max-turns N]
                   [--speak] [--log-level LEVEL] [--config run.json]
```

- `READY` affiché avec l'état des composants (`ok`/`ko`).
- Parler : taper une ligne + Entrée. Ligne vide ou Ctrl-D = arrêt.
- `--speak` : vocalise les réponses avec Pierre ( sortie audio requise).
- `--max-turns N` : arrêt après N tours (tests, scripts).
- Codes : `0` propre, `2` config/usage, `3` init/erreur, `130` interrompu.
- SIGINT/SIGTERM : arrêt propre (stores fermés, session libérée).

## Redémarrer

Relancer la même commande. Reprise : réouverture des stores existants
(`memory.sqlite`, `knowledge.sqlite`, `journal.jsonl` sous `data_dir`,
défaut `~/.local/share/wilfrid`). Aucune migration, aucun état global.

## Configuration

JSON optionnel (`--config`) + surcharges `WILFRID_DATA_DIR`,
`WILFRID_SESSION_ID`, `WILFRID_MAX_TURNS`, `WILFRID_LOG_LEVEL`.
Validation fail-closed (session, chemins, bornes). `offline: true`
imposé. Aucun secret dans la config (clé ElevenLabs éventuelle par
variable d'environnement du legacy `jarvis.py`, jamais lue ici).

## Erreurs

Config invalide → `WILFRID ERROR` + code 2/3, jamais de faux READY.
Composant indisponible (mémoire/knowledge/P7/session) → ERROR + cleanup.
Voix (STT/TTS) sondées et rapportées `ok`/`ko` sans bloquer le texte.
