# Wilfrid — Internet, plugins, agents (chantier 2)

## Internet

`core/internet/engine.py::fetch_url` : HTTPS seule, DNS→TLS→HTTP→
contenu→vérifié (étapes distinguées, jamais de 200 = succès).
SSRF (loopback/privé/réservé refusés), pas de redirection suivie,
taille/type bornés, provenance `https:hôte`. Recherche : aucune
(`SEARCH_UNAVAILABLE`, abstraction prête).

## Plugins

`core/plugins/registry.py` : DECLARED→INSTALLED→CONNECTED→
OPERATIONAL (preuve exigée)→FAILED/DISABLED. Aucune auto-inscription.

## Agents

`core/agents/` : registre (DECLARED→CONFIGURED→CONNECTED→OPERATIONAL,
preuve exigée) + adapters HTTP OpenAI/Gemini/Claude/OmniRoute (sans
SDK) + orchestration (unique/multiple/seconde-opinion/agrégation) +
minimisation (nécessaire/facultatif/sensible/interdit).
Secrets : référence d'env uniquement, jamais en git/logs/provenance.
Agents = ressources (proposent), jamais autorités (n'approuvent pas).

## Gouvernance

Capacités externes = ressources pour missions/outils, approbations via
Approval Gate existant, journal `record()`, vérification par statut.
État réel : OmniRoute health 200 local, `/v1/*` 401 (AUTH_REQUIRED) ;
OpenAI/Gemini/Claude non configurés (AUTH_REQUIRED honnête).
