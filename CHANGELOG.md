# Wilfrid — CHANGELOG

## P7.1 — Exécution contrôlée R0–R2 (finalisé et validé, 2026-10-06)
- C1 fondations PASS (`core/p7/` : contrats, registre vide tout-disabled,
  journal fail-closed, gouverneur pur, erreurs fermées) ; C2 PASS (résolveur
  jail `JAIL/P7`, lecture bornée, écriture réversible + backup/restore) ;
  C3 PASS (`notifications/` local, 4 capacités intégrées, audit final 20/20).
- Quatre capabilities B2 : `P7.CATALOG_READ` (R0), `P7.JAIL_READ` (R1),
  `P7.JAIL_WRITE_REVERSIBLE` (R2), `P7.NOTIFY_LOCAL` (R2). C1 16/16,
  CATALOG 14/14, C2 28/28, NOTIFY 11/11, intégration 10/10,
  **globale 279/279 PASS** (2026-10-06). Audit final PASS, post-audit
  PASS WITH DOCUMENTATION GAP, gap documentaire consolidé par la présente
  entrée (ne modifie aucun historique).

## P6.0–P6.6 — Knowledge & Research (consolidation baseline du 2026-10-06)
- Consolidation B1 sans modification du code fonctionnel : 15 modules
  `core/knowledge/` (P6.1 socle permissions/whitelist/store/jobs/accesslog ;
  P6.2 acquire/downloader/parsers TXT+PDF via pypdf ; P6.3 chunking/index/provenance ;
  P6.4 analysis/qa/synthesis ; P6.5 formats EPUB/DOCX stdlib + HTML bs4 + compare ;
  P6.6 durcissement) + 24 suites `tests/test_knowledge_*.py`.
- Preuves 2026-10-06 : P6 seule **105 passed in 18.12s** (00:38:02Z) ;
  cumul global **200 passed in 26.15s** (00:38:29Z, EXIT 0, 1 warning ONNX
  Runtime android sans impact). SHA256 et verdict archivés dans
  `docs/POST_AUDIT_P6_6.md` (PASS). Seuil `wake.json` 0.665 et `wake.onnx`
  `87eead45…` inchangés. Dépendances constatées `.venv` : `pypdf==6.19.0`,
  `beautifulsoup4==4.15.0` (compatibles `requirements.txt`, sans installation
  ni mise à jour). Ne prétend à aucune antériorité : première baseline
  opposable P6 établie à cette date.

## P5 — Cognitive Core (validé)
- Moteur déterministe local (`core/cognitive/`, 7 modules + corpus 24 cas
  + 8 suites) : taxonomie 8 kinds v1.0, `build_input` validé + deepcopy
  normative, classifieur règles/regex, décideur borné, planner abstrait
  (`NEED_ACTION` déclaratif, garde-fou `plan_is_effect_free`), machine
  IDLE→…→READY + CLARIFICATION/ERROR.
- Validation : 41/41 tests P5, cumul global **95/95** (41+24+23+7 ;
  P3 historique 31/31) ; copie profonde, déterminisme, isolation et
  bornes vérifiés ; P1/P2/P3/P4 intacts ; zéro dépendance nouvelle ;
  seuil 0.665 et modèle inchangés.
- Identité « Monsieur K » clôturée (réponse exacte, 0 résidu M.KWIN,
  POST-AUDIT identité PASS).

## P4 — Session et interaction fondamentale (validé)
- Identité (`Wilfrid`/`wilfrid-core`/0.4.0/« Wilfrid »/**Monsieur K**, voix et
  modèle TTS existants) ; accusé exact « Oui, Monsieur K. Je suis là. »
  (donnée, aucun TTS câblé) ; Monsieur K = paramètre d'interaction, ni
  mémoire ni biométrie.
- Session Manager (`core/session/`, 7 modules) : unique consommateur de
  `WAKE_DETECTED` ; session locale unique (UUID, timeout 60 s
  paramétrable, double wake = refresh, fermeture + purge) ; machine
  IDLE→ACTIVATING→ACTIVE→LISTENING⇄WAITING→IDLE (+ENDED/ERROR,
  PROCESSING/RESPONDING stubs) ; contexte volatil borné (20 tours + cap
  octets, purge totale, jamais sérialisé) ; événements minimaux ;
  salut quotidien = une date dans `.cache/last_greeting` ; journal JSONL
  64 Ko/1 rotation OFF par défaut, champs techniques seuls.
- Validation : 54/54 tests PASS (23 P4 + 24 P3 + 7 P1) ; P1/P2/P3
  préservés ; seuil 0.665 et modèle inchangés ; zéro dépendance nouvelle ;
  aucune mémoire, cognition, STT/TTS, action, TAIOS/QanXorus.

## P3 — Wake Runtime (validé)
- Runtime de détection continue « Wilfrid » implémenté et validé :
  `core/audio/capture.py`, `core/audio/preproc.py`, `core/wake/events.py`,
  `core/wake/detector.py`, `core/wake/runtime.py` (+ 4 suites de tests).
- Contrat : PCM16 → float32 → filtres à état → ring 16000 → gate → peak-norm
  → mel 40×101 → ONNX → sigmoid → seuil `wake.json` (0.665) → 2 frames
  consécutives → réfractaire 0.7 s → `WAKE_DETECTED` (aucune action).
- Mesures : 31/31 tests PASS ; streaming ≡ diagnostic à 0.000000 ;
  micro 16 kHz 20 blocs/2 s sans erreur ; ~17 ms/cycle (p95 ~23 ms) ;
  ΔRSS 0 Ko/120 cycles ; `stop()` < 1 s.
- Seuil 0.665 inchangé (lu depuis `wake.json`). Réserve acceptée :
  **THRESHOLD STREAMING : INCONCLUSIF** (corpus insuffisant).
- P1 intact, P2 intact, aucune nouvelle dépendance.
- Le Wake Runtime est officiellement intégré à l'architecture de Wilfrid
  comme seule source des événements `WAKE_DETECTED` (sans effet métier).

## P2 — Découplage plateforme (validé)
- `core/audio`, `core/voice`, `core/actions`, `platforms/desktop`,
  `platforms/win32` extraits depuis `jarvis.py` (1051 → 372 lignes),
  wrappers et gardes préservés, comportement inchangé.

## P1 — Harnais wake-word (validé, gelé)
- `tools/score_wavs.py` + `tests/test_wake_harness.py` (7/7) : référence
  officielle et immuable de toute mesure (pipeline Heed documenté).

## P0 — Audit et documentation de référence
- `MASTER_PLAN.md`, `CAHIER_DES_CHARGES.md`, `METHODOLOGIE.md`,
  `ARCHITECTURE.md`, `ROADMAP.md` validés.
