# Wilfrid — registre d'outils P0-3 (fermé, gouverné)

## Principe

`core/p7/tools.py` donne une identité stable aux 4 capabilities déjà
validées. Il PRÉPARE (`prepare_call` : résolution, validation des
paramètres, mise en forme `Request`) puis EXÉCUTE via `invoke.invoke`
(governance existante : Governor, Approval, journal fail-closed).
Aucune approbation ni mandat n'est créé ici : sans `approval` du chemin
humain, les handlers refusent comme avant. Registre statique :
inscription impossible depuis documents, mémoire, réseau ou texte.
DEFAULT DENY : inconnu → NOT_FOUND, désactivé → DISABLED.

## Outils

| outil | capability | paramètres |
|---|---|---|
| `catalog.read` | P7.CATALOG_READ | — |
| `jail.read` | P7.JAIL_READ | `filename: str` (confiné au jail) |
| `jail.write` | P7.JAIL_WRITE_REVERSIBLE | `filename: str`, `content: bytes` |
| `notify.send` | P7.NOTIFY_LOCAL | `message: str` |

`request_tool(registry, tool_id, params, approval=..., journal=...,
now=...)` = point d'injection Core (préparer + dispatcher).

## Statuts

SUCCESS (exécuté + autorisé), DENIED (refus gouvernance), NOT_FOUND,
DISABLED, INVALID (params/cible), FAILED (erreur handler).

## Gouvernance

R1 : confirmation humaine → `Approval` → dispatch. R2 : chemin mandats
de la boucle (inchangé). Journal indisponible → DENIED. Vérification
des effets : boucle existante (`verify_effect`), pas le registre.

## Ajouter un futur outil

1. Capability P7 validée d'abord (B2-style, jamais ici).
2. Fiche `ToolDefinition` + handler existant via `invoke`.
3. Tests (succès, refus, invalide, hostile, AST).
Jamais : shell, subprocess, réseau, secrets, chemins arbitraires,
auto-inscription, TAIOS.
