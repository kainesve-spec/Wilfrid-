# INTERNET + PLUGINS + AGENTS — journal de preuve (capacités, sans autorité)

- Base : `8556ac7`. Internet réel : DNS+HTTPS OK (Termux).
- Ajout (zéro fichier existant modifié) :
  - `core/internet/engine.py` : HTTPS bornée, étapes RESOLVED→
    CONNECTED→HTTP_SUCCESS→CONTENT_VALIDATED (+VERIFIED côté
    appelant), SSRF loopback/privé, redirections refusées, taille/type
    bornés, provenance. `search.py` : SEARCH_UNAVAILABLE honnête.
  - `core/plugins/registry.py` : cycle preuve-gated, sans
    auto-inscription.
  - `core/agents/` : registre (preuve-gated, secret par référence
    env), 4 adapters HTTP sans SDK, orchestration (agrégation,
    seconde opinion), minimisation (nécessaire/facultatif/sensible/
    interdit, secrets jamais transmis).
  - `tests/test_internet_agents.py` : 13 cas (mocks + serveur local +
    preuves réelles inoffensives). `docs/INTERNET_AGENTS.md`.
- Preuves réelles : `https://example.com/` → CONTENT_VALIDATED
  (200, 577 o, provenance) ; OmniRoute `/api/health` → 200 ok ;
  `/v1/models` → 401 (AUTH_REQUIRED honnête, aucune clé inventée).
- Résultats : 891/891 (`841 + 24 + 26`) seed défaut et
  `PYTHONHASHSEED=7`. Secrets : aucun (valeurs jamais relevées ;
  `TAIOS_*` non touchées). TAIOS : 0 référence. JAIL/P7 intact.
  Aucune action externe dangereuse (0 appel facturable, 0 envoi).
