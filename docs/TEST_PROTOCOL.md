# Wilfrid — TEST PROTOCOL (P3)

> Le protocole P1 (harnais `tools/score_wavs.py`, 7 tests) est gelé et
> n'est pas modifié par ce document.

## Procédure reproductible de validation P3
1. Intégrité : SHA256 de `models/wake.onnx`, `models/wake.json`, WAV P1,
   `tools/score_wavs.py`, `tests/test_wake_harness.py` — comparer aux
   références (`87eead45…`, `c8c62f8b…`, `269ba8d1…`, `7a09c6a2…`).
2. Suite complète : `.venv/bin/python -m pytest tests/ -q` — attendu 31/31.
3. Streaming : injecter les 5 WAV via `ArraySource` dans `WakeRuntime` ;
   comparer max/above/triggers aux références
   (0.188603 / 0.681117 / 0.336307 / 0.087359 / 0.123839 ; 0/1/0/0/0 ; 0).
4. Micro : `WakeRuntime()` borné à 20 blocs — 0 erreur/under/overrun,
   arrêt < 1 s.
5. Seuil : constater 0.665 lu depuis `wake.json`, non modifié ; noter
   INCONCLUSIF statistique (corpus insuffisant).
6. Isolation : `grep` d'absence STT/TTS/mémoire/action dans `core/wake/`,
   `core/audio/preproc.py`, `core/audio/capture.py`.

## Interdictions pendant la validation
Aucune modification de code, modèle, seuil, données, dépendances.

## Procédure P6 (consolidation baseline du 2026-10-06, sans modifier le code)
1. Intégrité : SHA256 des 15 `core/knowledge/*.py`, 24 `tests/test_knowledge_*.py`,
   `models/wake.json` (`c8c62f8b…`, seuil 0.665), `models/wake.onnx` (`87eead45…`) —
   comparer à `docs/POST_AUDIT_P6_6.md`.
2. Suite P6 : `.venv/bin/python -m pytest tests/test_knowledge_*.py -q` —
   attendu **105/105** (référence 2026-10-06T00:38:02Z, 18.12s).
3. Cumul global : `.venv/bin/python -m pytest tests/ -q` — attendu **200/200**
   (référence 2026-10-06T00:38:29Z, 26.15s, EXIT 0).
4. Dépendances : constater `pypdf==6.19.0`, `beautifulsoup4==4.15.0` via
   `.venv/bin/python -c` (sans installation), compatibles `requirements.txt`.
5. Isolation P6/P7 : `grep P7/capability/plugin` dans `core/` = 0 ; seul
   `docs/P7_0_A_DESIGN.md` comme artefact P7.

## Procédure P7.1 (consolidation documentaire du 2026-10-06)
1. Tests C1 : `.venv/bin/python -m pytest tests/test_p7_foundations.py -q` — attendu 16/16.
2. Tests Catalog : `tests/test_p7_catalog.py` — attendu 14/14.
3. Tests C2 : `tests/test_p7_jail.py` — attendu 28/28.
4. Tests Notify : `tests/test_p7_notify.py` — attendu 11/11.
5. Tests Intégration : `tests/test_p7_integration.py` — attendu 10/10.
6. Suite globale : `.venv/bin/python -m pytest tests/ -q` — attendu **279/279**
   (référence 2026-10-06, 1 warning ONNX android sans impact).
7. Isolation P5/P6 : SHAs (`permissions.py` 120176b6…, `wake.json` c8c62f8b…,
   `wake.onnx` 87eead45…), seuil 0.665, 8 ids P6.
8. Registre P7 : ACTIVE = 0, DECLARED = 0 (instanciation fraîche, sans activation).
9. Absence réseau/subprocess/R3/R4 : revue AST `core/p7/` (stdlib + `core.p7` seuls).

## Procédure P4 (session)
1. Suite complète : `.venv/bin/python -m pytest tests/ -q` — attendu 54/54
   (référence d'époque P4 : 23 P4 + 24 P3-spécifiques + 7 P1).
2. Cycle : `on_wake` → ACTIVE → `close` → ENDED → nouveau `on_wake` (IDs distincts).
3. Timeout : horloge injectée, 60 s défaut + valeur custom.
4. Journal/greeting : chemins temporaires dédiés, contenus vérifiés, résidus supprimés.
5. Isolation : audit statique des imports `core/session/` (stdlib + `core.wake.events` seuls).

## Procédure P5 (cognitif)
1. Suite complète : `.venv/bin/python -m pytest tests/ -q` — attendu 95/95
   (41 P5 + 24 P3-spécifiques + 23 P4 + 7 P1).
2. Corpus : 24 cas `tests/data/cognitive_corpus_v1.json`, assertions exactes.
3. Copie profonde : 5 scénarios (racine, dict, liste, dict+list+dict, source
   inchangée) via `build_input`.
4. Déterminisme : rejouabilité exacte (corpus + `CognitiveCore`).
5. Isolation : audit AST des imports `core/cognitive/` (stdlib + socle,
   zéro capacité d'action/réseau/IA) ; aucune écriture ni effet constatés.
