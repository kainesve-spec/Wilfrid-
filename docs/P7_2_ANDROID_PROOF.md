# ANDROID CHANTIER 1 — journal de preuve (capacités contrôlées)

- Base : `8f28c5c`. Environnement : Android 15, Termux:API 83 commandes,
  daemon répondant (batterie/audio/caméras/capteurs/TTS vérifiés ;
  données personnelles jamais invoquées).
- Ajout (zéro composant existant modifié) :
  - `core/android/capabilities.py` : 16 capacités déclaratives
    (état/risque/vérification/restrictions), `AndroidRegistry`
    (grant/revoke tracés, défaut refus), 6 lectures inoffensives
    accordées par défaut (documentées).
  - `core/android/adapters/termux_api.py` : 16 commandes listées,
    argv structurés sans shell, timeout 1-60 s, `TermuxResult` fermé.
  - `core/android/execution.py` : connu→accordé→confirmation
    (Approval Gate `ANDROID.<ID>`, consommation unique)→adaptateur→
    vérification→journal→`AndroidResult`. Refus = zéro effet.
  - `tests/test_android_capabilities.py` : 14 cas (registre, états,
    grants, refus, inconnu, réel inoffensif, blocage, approbation,
    DENY vocalique, timeout/erreurs/args, UNCERTAIN, journal,
    AST sans-réseau/sans-TAIOS).
  - `docs/ANDROID.md` : principe, capacités, exécution, extension.
- Gouvernance réutilisée : Approval Gate, journal append-only,
  registre P7 vide de droits. Aucun second système.
- Résultats : 878/878 (`828 + 24 + 26`) seed défaut et
  `PYTHONHASHSEED=7`. Latence Termux:API instable constatée
  (timeout honnête accepté, jamais simulé).
- JAIL/P7 intact. Aucune action externe dangereuse exécutée
  (0 SMS/appel/suppression/publication). Aucun secret, aucune donnée
  personnelle en dépôt. TAIOS : 0 référence.
