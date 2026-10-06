# Wilfrid — POST-AUDIT P6.6 (consolidation baseline du 2026-10-06)

> Artefact créé lors de la consolidation B1 du 2026-10-06.
> Ne prétend à aucune antériorité : les preuves ci-dessous sont celles constatées
> le 2026-10-06, sans rétroactivité. Aucun code fonctionnel modifié.

## 1. Périmètre P6.0–P6.6
- P6.0 : cadrage (aucun fichier dédié identifié ; socle couvert à partir de P6.1).
- P6.1 socle : `core/knowledge/__init__.py, permissions.py, whitelist.py, store.py,
  jobs.py, accesslog.py`.
- P6.2 acquisition : `acquire.py, downloader.py, parsers.py` (TXT + PDF).
- P6.3 découpage : `chunking.py` (+ index/provenance via store/jobs).
- P6.4 analyse : `analysis.py, qa.py, synthesis.py`.
- P6.5 formats/comparaison : `formats.py` (EPUB/DOCX stdlib + HTML bs4),
  `compare.py`.
- P6.6 durcissement : 8 suites `security_static, adversarial, poisoning, integrity,
  hostile_markup, archives, volume, concurrency`.

## 2. Intégrité des fichiers (SHA256 constatés 2026-10-06)
- `6ce1d0ef…7718a7e8` `core/knowledge/__init__.py`
- `664f7961…162c5cc9c5` `core/knowledge/accesslog.py`
- `612be568…18049ac5c9` `core/knowledge/acquire.py`
- `1e2cd3f5…d3c5c0fe90` `core/knowledge/analysis.py`
- `898a2ca1…b2f90ed37a` `core/knowledge/chunking.py`
- `a602ce71…72501cc4e2` `core/knowledge/compare.py`
- `150b4cf6…5aad67fc61` `core/knowledge/downloader.py`
- `df3200fa…aad8519944` `core/knowledge/formats.py`
- `d05a156e…f5092bcbde` `core/knowledge/jobs.py`
- `9239c850…ba27ddf18be` `core/knowledge/parsers.py`
- `120176b6…cd4dfb43179` `core/knowledge/permissions.py`
- `65905bd8…17a55aaa03` `core/knowledge/qa.py`
- `c46de19d…8a60ceb5a6f` `core/knowledge/store.py`
- `92cf075f…780b57ace4f` `core/knowledge/synthesis.py`
- `5592f783…47441eed` `core/knowledge/whitelist.py`
- 24 fichiers `tests/test_knowledge_*.py` (SHA complets repris §7 du rapport B1 ;
  extrait : `f3690ad0…5723f9` permissions, `939ccc40…eeb4cc77bd` security_static).
- `c8c62f8b…7169dc09e06` `models/wake.json` (threshold 0.665).
- `87eead45…8f5a68fa6d333` `models/wake.onnx` (inchangé, réf. P1/P3).
- Aucune modification `core/knowledge/*.py`, `models/wake.json`, `models/wake.onnx`.

## 3. Permissions / refus par défaut
- `PERMISSION_IDS` = 8 ids P6 (`INTERNET_RESEARCH, SOURCE_ACCESS, DOCUMENT_DOWNLOAD,
  DOCUMENT_PERSIST, KNOWLEDGE_WRITE, KNOWLEDGE_UPDATE, CROSS_DOCUMENT_ANALYSIS,
  NOTIFY_COMPLETION`), tous `disabled` à la naissance, `enable()/revoke()` explicites seuls.
- Contenu documentaire jamais accordant (couvert `security_static, adversarial,
  poisoning, security`). Aucune permission activée par le post-audit (constat seul).

## 4. Secrets
- Aucun secret dans `core/knowledge/`, `tests/test_knowledge_*/`, journaux P6
  (champs techniques seuls, politique P4 reconduite). `.env` non versionné, non lu
  par P6. Recherche `TAIOS/QanXorus` couverte par `security_static` : PASS.

## 5. Dépendances (constatées, sans installation ni modification)
- Déclaré `requirements.txt` : `numpy>=1.24,<3`, `sounddevice>=0.4.6,<0.6`,
  `elevenlabs>=1.50,<3`, `websockets>=13`, `python-dotenv>=1.0,<2`,
  `pypdf>=6,<7`, `beautifulsoup4>=4.12,<5`.
- Installé (`.venv`, Python 3.14.6) : `pypdf==6.19.0`, `beautifulsoup4==4.15.0`
  (via `bs4 4.15.0`), `numpy 2.4.4`, `sounddevice 0.5.6`, `elevenlabs 2.70.0`,
  `websockets 17.2`, `python-dotenv 1.2.4`, `pytest 9.1.1`.
- Usages justifiés : `pypdf` import local `parsers.py:51` (PDF lecture seule),
  `bs4` import local `formats.py:268` (`html.parser`, jamais `lxml`).
  `downloader.py` stdlib seule (socket/tcp + http.client + urllib.parse).
- Divergence `requirements.txt` vs index git : évolution P6 légitime non committée
  (index obsolète, 5 commits jarvis initiaux, `core/`, `tests/`, `docs/` untracked).
  Aucune mise à jour de dépendance effectuée. Proposition de gel : voir §6 rapport B1.

## 6. Séparation P6/P7
- `docs/P7_0_A_DESIGN.md` seul artefact P7.0-A. Aucune chaîne `P7.`, `capability`,
  `plugin installé`, `skill activé` dans `core/` (grep 0). Aucun `core/p7/`,
  aucun test P7, aucune permission P7 activée. P6 non modifié par P7.

## 7. Résultat des tests (preuves réelles horodatées, non `lastfailed` seul)
- P6 seule : `2026-10-06T00:38:02Z`, 24 fichiers `tests/test_knowledge_*.py`,
  **105 passed in 18.12s**, EXIT 0 (`.venv/bin/python -m pytest tests/test_knowledge_*.py -q`).
- Cumul global : `2026-10-06T00:38:29Z`, **200 passed in 26.15s**, EXIT 0
  (`.venv/bin/python -m pytest tests/ -q`, 1 warning ONNX Runtime `android`
  non supporté, sans impact verdict). Correspond aux 200 `nodeids` archivés
  (`.pytest_cache/v/cache/nodeids`, `lastfailed={}` corroborant, non preuve seule).

## 8. Verdict : PASS
Post-audit P6.6 : PASS le 2026-10-06 sur le périmètre ci-dessus,
code non modifié, seuil/modèle intacts, séparation P6/P7 vérifiée.

## 9. Limites / résidus explicitement acceptés
- P6.0 sans fichier dédié (couvert par socle P6.1).
- Baseline git inexistante (tout P6 untracked) : opposable par SHA + résultats,
  pas par commit/tag (aucun commit/tag effectué, conformément à l'interdit).
- Cache pytest volatil : conservé comme corroboration, preuve = sorties horodatées §7.
- Seuil streaming 0.665 : réserve INCONCLUSIVE héritée P3, inchangée, hors P6.
