# Wilfrid — MÉTHODOLOGIE OFFICIELLE (validée)

Cycle obligatoire pour chaque grand bloc. Aucun saut d'étape.

```
MASTER PLAN
    ↓
AUDIT            (état réel, preuves, sans modification)
    ↓
DIAGNOSTIC       (causes, hypothèses ordonnées, faits vs suppositions)
    ↓
PATCH / IMPLÉMENTATION   (diff minimal, périmètre autorisé uniquement)
    ↓
POST-AUDIT       (le patch fait-il ce qu'il prétend ? preuves)
    ↓
TEST             (unitaires ciblés + non-régression)
    ↓
VALIDATION       (critères du bloc atteints, décision explicite)
    ↓
DOCUMENTATION DU GRAND BLOC   (ce qui a été fait, prouvé, et reste à faire)
    ↓
BLOC SUIVANT
```

## Règles par étape

1. **MASTER PLAN** — vision, phases 0-12, critères. Référence : `MASTER_PLAN.md`.
2. **AUDIT** — lecture seule. Inventaire factuel : fichiers, versions, statuts
   (`PLANNED`…`PRODUCTION`). Aucune modification, aucune installation surprise.
3. **DIAGNOSTIC** — distingue **faits certains** / **hypothèses** / **tests
   recommandés**. Propose des tests, n'invente pas de conclusions.
4. **PATCH / IMPLÉMENTATION** — uniquement sur autorisation explicite :
   périmètre de fichiers fixé, diff minimal, jamais de secret dans le
   code/logs, jamais de capacité présentée comme acquise avant preuve.
5. **POST-AUDIT** — revérifie le périmètre touché + les garde-fous (secrets,
   perms, dépendances). Tout écart bloque la suite.
6. **TEST** — tests ciblés du patch + régression du périmètre. Échec = retour
   au diagnostic, jamais de contournement.
7. **VALIDATION** — verdict explicite (`PASS`/`FAIL`, preuves). Seule une
   validation clôt un bloc.
8. **DOCUMENTATION DU GRAND BLOC** — état final, décisions, dettes, bloc suivant.
9. **BLOC SUIVANT** — ne commence qu'après clôture documentée du précédent.

## Interdits permanents

- Modifier du code/modèles/secrets sans autorisation explicite.
- Présenter du `PLANNED` comme `IMPLEMENTED`.
- Versionner un secret (`.env`, clés, tokens).
- Laisser une mesure non reproductible sans harnais versionné.
