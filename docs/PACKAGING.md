# Wilfrid — PACKAGING & EXPLOITATION (état réel, Master 9)

> Ce document décrit uniquement ce qui existe et est qualifié. Tout composant
> PLANNED reste PLANNED. Version traçable : commit Git + `docs/STATUS.md`.

## 1. Périmètre réel du paquet

`core/` (wake, session, cognitive, knowledge, p7, memory, mission, extensions,
voice, audio, actions, config), `platforms/` (desktop, win32), `tools/`
(harnais P1), `tests/` (496 tests), `models/` (wake 0.665), `docs/`,
`jarvis.py` (point d'entrée), `requirements.txt`, `README.md`.

## 2. Installation / reproduction

```bash
python -m venv .venv && source .venv/bin/activate
python -m pip install -r requirements.txt
```

Versions constatées compatibles : `beautifulsoup4==4.15.0`,
`elevenlabs==2.70.0`, `numpy 2.4.4`, `sounddevice 0.5.6`. Notes :
`onnxruntime`/`openwakeword` (wake runtime) proviennent de l'environnement
Termux local et **ne figurent pas** dans `requirements.txt` — installation
hors requirements documentée comme limite, non modifiée ici. `websockets`
figure dans `requirements.txt` mais n'est importé par aucun module :
dépendance superflue signalée, conservée inchangée.

## 3. Point d'entrée et exécution

`python jarvis.py` (guard `__main__`, import sans effet de bord).
Démarrage : boucle micro → double-clap → actions configurées → TTS.
Arrêt : `Ctrl+C` (code 0) ; erreur PortAudio → code 1 avec message.
Exécution réelle non testée ici (micro requis) : procédure manuelle.

## 4. Configuration

`.env` local, **jamais versionné** (`.gitignore`). Sans clés ElevenLabs :
repli propre (warning + synthèse ignorée, code retour inchangé, prouvé).
Aucun secret dans le dépôt, les logs ou les tests (vérifié).

## 5. Tests reproductibles

```bash
.venv/bin/python -m pytest tests/ -q
```

Référence : **496/496 PASS** (warning ONNX Android sans impact). Les tests ne
dépendent d'aucun secret, d'aucun réseau réel (serveurs HTTPS éphémères
locaux) et passent sous plusieurs `PYTHONHASHSEED`.

## 6. Limites explicites (non négociables dans ce paquet)

Pas de service/daemon, pas de STT, pas de mémoire persistante générale (hors
`core/memory/` bornée), pas de dialogue applicatif complet, pas de R3/R4,
pas de réseau hors O7 gouverné, pas de trading, phases PLANNED inchangées.
