# Wilfrid — MASTER PLAN (validé)

> État : **MASTER PLAN VALIDÉ / MÉTHODOLOGIE VALIDÉE / ARCHITECTURE GÉNÉRALE VALIDÉE**
> Vocabulaire de statut utilisé dans toute la documentation :
> `PLANNED` → `DESIGNED` → `IMPLEMENTED` → `TESTED` → `VALIDATED` → `PRODUCTION`
> (`DEPRECATED` le cas échéant). Aucune capacité future n'est présentée comme implémentée.

## 1. Vision

Wilfrid est un assistant **autonome, généraliste, extensible et évolutif**, à
interaction vocale d'abord (« Wilfrid » comme mot d'éveil), capable d'écouter,
de comprendre, d'agir sur son environnement (applications, fichiers, services)
et de s'améliorer de façon contrôlée. Il fonctionne en local autant que
possible (respect de la vie privée, faible latence) et ne délègue au cloud
que ce qui l'exige (ex. synthèse vocale, recherche).

## 2. Objectif long terme

Un compagnon opérationnel durable : démarrage à la voix, exécution fiable de
tâches hétérogènes via un **système de compétences/plugins** (élément
fondamental), mémoire persistante des faits et préférences, apprentissage de
l'usage, le tout sous **gouvernance et permissions explicites**. Wilfrid doit
rester compréhensible, réparable et réversible à chaque étape.

## 3. Architecture cognitive générale

```
PERCEPTION (audio/texte/contexte)
   → COMPRÉHENSION (intentions, entités, mémoire de travail)
   → DÉCISION (plan, compétence requise, permissions)
   → EXÉCUTION (outils, effets observables, journal)
   → VÉRIFICATION (preuves, tests, critères)
   → APPRENTISSAGE (mémoire, ajustements validés uniquement)
```

Moteurs : perception vocale (wake-word + écoute) · dialogue · mémoire ·
connaissance/recherche · outils et exécution · vérification · apprentissage ·
gouvernance. Voir `ARCHITECTURE.md`.

## 4. Phases 0 à 12

| Phase | Intitulé | Statut |
|---|---|---|
| 0 | Fondations (repo, env, dépendances, outillage) | `IMPLEMENTED` |
| 1 | Entrée/sortie vocale (micro, TTS) | `IMPLEMENTED` / partiellement `TESTED` |
| 2 | Wake-word « Wilfrid » (modèle + runtime) | `DESIGNED`, modèle exporté, intégration en `AUDIT` |
| 3 | Boucle d'assistance (écoute → action → réponse) | `PLANNED` |
| 4 | Système de compétences/plugins | `DESIGNED` (principe validé), `PLANNED` (implémentation) |
| 5 | Mémoire persistante (faits, préférences) | `PLANNED` |
| 6 | Connaissance et recherche (locale + web) | `PLANNED` |
| 7 | Outils et exécution contrôlée | `PLANNED` |
| 8 | Vérification et preuves | `PLANNED` |
| 9 | Apprentissage et amélioration contrôlée | `PLANNED` |
| 10 | Gouvernance et permissions | `DESIGNED`, `PLANNED` |
| 11 | Versions V1/V2/V3 et durcissement | `PLANNED` |
| 12 | Revue d'autonomie et clôture de cycle | `PLANNED` |

Détail d'exécution : voir `ROADMAP.md`.

## 5. Compétences/plugins (fondamental)

Toute capacité au-delà du noyau est une **compétence** déclarée : nom,
version, permissions requises, entrées/sorties, tests. Statut : `DESIGNED`.

## 6. Mémoire, connaissance, outils, vérification, apprentissage

- **Mémoire** (`PLANNED`) : faits, préférences, historique — jamais d'écriture
  implicite, jamais de fuite entre contextes sans règle.
- **Connaissance/recherche** (`PLANNED`) : locale d'abord, web ensuite, sources citées.
- **Outils et exécution** (`PLANNED`) : effets bornés, journalisés, réversibles.
- **Vérification** (`PLANNED`) : chaque bloc prouve son comportement (tests + preuves).
- **Apprentissage / amélioration contrôlée** (`PLANNED`) : aucun ajustement
  automatique persistant sans validation explicite.

## 7. Gouvernance et permissions

Principe : **aucune action à effet sans permission accordée**, scopes minimaux,
secrets jamais versionnés (`.env` local, voir `README.md`). Statut : `DESIGNED`.

## 8. Séparation stricte avec QanXorus/TAIOS

Wilfrid est un projet **indépendant** : dépôts, environnements, modèles,
secrets et runtimes séparés. Aucune dépendance d'exécution croisée, aucun
partage de credentials. Les échanges éventuels passent par des interfaces
documentées, jamais par du code partagé implicite.

## 9. Versions cibles

- **V1** (`PLANNED`) : voix + wake-word fiable + premières compétences utiles.
- **V2** (`PLANNED`) : mémoire + connaissance + exécution contrôlée.
- **V3** (`PLANNED`) : apprentissage contrôlé + autonomie gouvernée.

## 10. Critères de réussite

1. Cycle méthodologique respecté pour chaque bloc (voir `METHODOLOGIE.md`).
2. Wake-word : déclenchement fiable sur le locuteur, zéro régression mesurée.
3. Chaque compétence : tests + permissions + journal.
4. Aucun secret dans le dépôt ; aucun effet non journalisé.
5. L'utilisateur peut arrêter, inspecter et revenir en arrière à tout moment.

## 11. État officiel

- MASTER PLAN : **VALIDÉ**
- MÉTHODOLOGIE : **VALIDÉE**
- ARCHITECTURE GÉNÉRALE : **VALIDÉE**
