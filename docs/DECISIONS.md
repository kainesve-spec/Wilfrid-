# Wilfrid — DECISIONS structurantes

## P7.1 — Exécution contrôlée R0–R2 (validé 2026-10-06, 279/279 PASS)
- Exactement 4 capabilities : `P7.CATALOG_READ` (R0), `P7.JAIL_READ` (R1),
  `P7.JAIL_WRITE_REVERSIBLE` (R2), `P7.NOTIFY_LOCAL` (R2) ; R0–R2 uniquement.
- Jail root = `~/Wilfrid/JAIL/P7` ; notification = `~/Wilfrid/JAIL/P7/notifications/`
  (fichier local dédié, texte ≤280 c, single-use).
- Fail-closed (DENY + zéro effet, journal indisponible = DENY TOTAL), journal P7
  commun append-only disjoint P6, registre vide sans API d'activation :
  aucune permission active par défaut.
- Aucune extension R3/R4, aucun réseau, P6 séparé de P7 (0 import croisé),
  P5/P6 intacts. Historique P1–P6 ci-dessous inchangé.

## P6.0–P6.6 — Knowledge & Research (consolidation baseline du 2026-10-06)
- Socle P6.1 refus défaut (8 ids, whitelist vide, store SQLite FTS5, jobs,
  accesslog champs minimaux) ; acquisition P6.2 (downloader stdlib, parsers
  TXT+PDF via pypdf, EPUB/DOCX/HTML refusés) ; chunking/index/provenance P6.3
  (IDs stables, idempotence) ; analyse/qa/synthesis P6.4 (extractif sourcé,
  `INSUFFICIENT_EVIDENCE`) ; formats/compare P6.5 (EPUB/DOCX stdlib, HTML bs4
  `html.parser`, scripts neutralisés) ; durcissement P6.6 (static, adversarial,
  poisoning, integrity, hostile-markup, archives, volume, concurrency).
- Dépendances : `pypdf==6.19.0`, `beautifulsoup4==4.15.0` constatées `.venv`
  (imports locaux, `ParseError` si absentes), compatibles `requirements.txt`,
  sans installation ni mise à jour. Baseline opposable : SHA + 105/105 et
  200/200 du 2026-10-06 dans `docs/POST_AUDIT_P6_6.md` (PASS). Historique P1–P5
  ci-dessous inchangé.

## P5 — Cognitive Core
- Moteur déterministe local (stdlib+regex), ni modèle ni API : autonomie,
  coût nul, confidentialité totale, reproductible.
- Taxonomie fermée v1.0 (8 kinds) ; `UNCERTAIN`/`CLARIFY` par défaut en
  cas de doute ; confiance par règles, non calibrée statistiquement.
- Copie profonde du contexte normative (superficielle insuffisante).
- Adoption officielle de « Monsieur K » comme identité d'interaction
  (réponse exacte « Oui, Monsieur K. Je suis là. », 0 occurrence
  résiduelle « M.KWIN », POST-AUDIT identité PASS).

## P4 — Session et interaction
- Session locale unique ; double wake = refresh, jamais de doublon.
- Timeout 60 s par défaut, paramétrable, horloge injectable en test.
- Monsieur K = paramètre d'interaction (ni mémoire ni biométrie) ; accusé
  exact « Oui, Monsieur K. Je suis là. » comme donnée, aucun TTS câblé.
- Contexte volatil borné (20 tours + cap octets), purge totale, jamais
  sérialisé ; aucune autosave vers une mémoire.
- Événements minimaux (STARTED/ENDED/LISTENING_*/ERROR) ; stubs
  PROCESSING/RESPONDING réservés sans moteurs.
- Salut quotidien = une date ISO seule (`.cache/last_greeting`), rien d'autre.
- Journal JSONL 64 Ko/1 rotation OFF par défaut, champs techniques seuls.
- Session Manager sans autorité d'action (revue statique des imports).
- « Will » hors P4 (gap modèle, nouvelle validation wake requise).

## P3 — Wake Runtime
- Streaming **sans trim ni center** (buffer glissant ; trim/center réservés
  à l'offline P1) ; HPF/notch **à état** (bit-identique au continu, prouvé).
- Ring buffer 16000 préalloué, blocs 1600 (100 ms), 10 inférences/s.
- Gate énergétique sur signal filtré, avant ONNX (−55 dBFS, 100-7000 Hz, 0.15).
- Seuil **chargé depuis `wake.json`**, jamais codé en dur, jamais modifié.
- 2 frames consécutives + réfractaire 0.7 s ; EMA observabilité seule.
- Événement `WAKE_DETECTED` pur, callback injecté, **aucune action en P3**.
- Priorité : CORRECTNESS > ROBUSTESSE > OBSERVABILITÉ > PERFORMANCE.

## P2 — Découplage
- Extraction progressive avec wrappers (stratégie B) ; `platforms/android/`
  volontairement absent ; `ctypes` local ; gardes `sys.platform` conservées.

## P1 — Harnais gelé
- `tools/score_wavs.py` est l'unique référence de mesure ; seuil 0.665.
