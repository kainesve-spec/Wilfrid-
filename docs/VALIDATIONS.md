# Wilfrid — VALIDATIONS

## P7.1 — Exécution contrôlée R0–R2 : PASS (consolidation documentaire du 2026-10-06)
- C1 fondations : **16/16 PASS** ; CATALOG_READ (R0) : **14/14 PASS** ;
  C2 jail (JAIL_READ R1 + JAIL_WRITE_REVERSIBLE R2) : **28/28 PASS** ;
  NOTIFY_LOCAL (R2) : **11/11 PASS** ; intégration/séparation/sécurité : **10/10 PASS**.
- Globale : **279/279 PASS** le 2026-10-06 (200 baseline P1–P6 + 79 P7 ;
  1 warning ONNX Runtime `android` non supporté, sans impact).
- Capacités : `P7.CATALOG_READ`, `P7.JAIL_READ`, `P7.JAIL_WRITE_REVERSIBLE`,
  `P7.NOTIFY_LOCAL` — exactement les 4 B2, R0–R2 seuls.
- Registre P7 : ACTIVE = 0, DECLARED = 0 (aucune permission activée pour valider).
- P5/P6 intacts (8 ids P6, seuil 0.665, SHAs inchangés) ; 0 réseau/subprocess/R3/R4.
- Voir `docs/P7_1_FINAL_AUDIT.md` (audit C3, 20/20 points).

## P6.0–P6.6 — Knowledge & Research : VALIDÉE (consolidation baseline du 2026-10-06)
- P6 seule : **105/105 PASS** le 2026-10-06T00:38:02Z (18.12s, EXIT 0).
- Cumul global : **200/200 PASS** le 2026-10-06T00:38:29Z (26.15s, EXIT 0 ;
  1 warning ONNX Runtime `android` non supporté, sans impact).
  200 `nodeids` archivés, `lastfailed={}` corroborant (non preuve seule).
- Refus par défaut (8 ids, `enable/revoke` explicites), whitelist vide défaut,
  contenu hostile inerte, double-accord et provenance couverts (P6.6 : static,
  adversarial, poisoning, integrity, hostile-markup, archives, volume, concurrency).
- Intégrité : SHA256 `core/knowledge/` + `tests/test_knowledge_*` + `wake.json`
  (`c8c62f8b…`) + `wake.onnx` (`87eead45…`) dans `docs/POST_AUDIT_P6_6.md`.
  Seuil 0.665 inchangé. Réserve héritée P3 THRESHOLD STREAMING INCONCLUSIF inchangée.
- Première mention opposable P6 dans ce fichier à cette date (ne réécrit pas P1–P5).

## P5 — Cognitive Core : VALIDÉE
- 41/41 tests P5 (types 3, input 6, classifier 6, decider 4, planner 5,
  core 7, safety 5, non-régression 5) ; cumul global **95/95**
  (41 P5 + 24 P3-spécifiques + 23 P4 + 7 P1 ; P3 historique : 31/31).
- Taxonomie 8 kinds versionnée 1.0 ; copie profonde normative vérifiée
  (5 scénarios, source inchangée) ; déterminisme rejoué à l'identique.
- `NEED_ACTION` déclaratif sans exécuteur ; bornes (2000c, ≤8 étapes/80c,
  champs bornés) ; machine IDLE→…→READY + CLARIFICATION/ERROR.
- Isolation : zéro import/capacité d'action, réseau, IA, mémoire, STT/TTS,
  TAIOS/QanXorus ; aucune écriture ni effet constatés.
- P1/P2/P3/P4 intacts (SHAs, comportements, seuil 0.665).

## P4 — Session et interaction : VALIDÉE
- 54/54 tests PASS (23 P4 : lifecycle 12 + safety 11 ; 24 P3 ; 7 P1).
- Identité : Wilfrid/`wilfrid-core`/0.4.0/« Wilfrid »/**Monsieur K** (paramètre,
  ni mémoire ni biométrie) ; accusé exact « Oui, Monsieur K. Je suis là. ».
- Session locale unique : IDLE→ACTIVATING→ACTIVE→LISTENING⇄WAITING→IDLE
  (+ENDED/ERROR, stubs documentés) ; double wake = refresh (1 seul
  `SESSION_STARTED`) ; timeout 60 s paramétrable (horloge injectée).
- Contexte volatil borné (20 tours + cap octets), purge totale, jamais
  sérialisé. Événements minimaux déterministes.
- Salut quotidien : une date ISO seule dans `.cache/last_greeting`.
- Journal JSONL 64 Ko/1 rotation OFF par défaut, champs techniques seuls
  (rotation prouvée : 3000 écritures → 2 fichiers, zéro contenu utilisateur).
- Isolation : zéro import/capacité shell/réseau/SQLite/TAIOS/QanXorus ;
  aucune mémoire générale, STT/TTS, cognition, action.
- P1/P2/P3 intacts (SHAs, harnais exact, `jarvis` importable).

## Risques résiduels P4
- Timeout de 60 secondes : valeur conventionnelle, mais paramétrable ;
  aucun blocker identifié.
- Version 0.4.0 : convention de versionnement, sans impact fonctionnel
  identifié.
- Journal : OFF par défaut ; rotation testée avec succès, mais le journal
  n'est pas destiné à être un mécanisme de production permanent.
- Seuil streaming 0.665 : statut INCONCLUSIF hérité de P3, hors périmètre
  P4 ; aucun changement du seuil n'est autorisé dans P4.
- AGC/bruit réel et preprocessing streaming : risques résiduels
  documentés dans P3, non réouverts par P4.
Ces risques ne bloquent pas la validation P4, ne constituent pas des
défauts fonctionnels P4 et sont conservés pour suivi ultérieur.

## P3 — Wake Runtime : VALIDÉ
- 31/31 tests PASS (`test_wake_detector`, `test_wake_preproc`,
  `test_wake_capture`, `test_wake_runtime`, `test_wake_harness`).
- Streaming 5 WAV ≡ diagnostic à 0.000000 près :
  max 0.188603 / 0.681117 / 0.336307 / 0.087359 / 0.123839 ;
  above 0/1/0/0/0 ; triggers 0 (clips 1 s : 2 frames consécutives
  structurellement impossibles en 1 fenêtre).
- Micro réel : 20 blocs / 2 s, 0 erreur, 0 under/overrun, arrêt propre.
- Performance : ~17 ms/cycle (p95 ~23 ms), cible < 300 ms tenue.
- Mémoire : ΔRSS 0 Ko / 120 cycles (+29 Mo/sessions ORT = arènes, non fuite).
- Isolation : seul `WAKE_DETECTED` sort ; zéro couplage STT/TTS/mémoire/action.
- Seuil 0.665 non modifié, lu depuis `wake.json`.
- **Réserve : THRESHOLD STREAMING : INCONCLUSIF** — corpus de 5 clips
  insuffisant pour une validation statistique ; à traiter avec un corpus
  représentatif dans une étape dédiée. Cette réserve ne remet pas en
  cause la validation technique P3.

## P2 — Découplage plateforme : VALIDÉ
- Wrappers vérifiés identiques, P1 7/7 pendant et après, gardes Win32 intactes.

## P1 — Harnais : VALIDÉ / GELÉ
- 7/7 tests ; 5 scores T1 reproduits à 6 décimales ; référence immuable.
