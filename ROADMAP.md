# Wilfrid — ROADMAP (phases 0 → 12, ordre d'exécution)

> Chaque phase suit le cycle `METHODOLOGIE.md` et se clôt par validation
> documentée. Statuts : `PLANNED` / `DESIGNED` / `IMPLEMENTED` / `TESTED` /
> `VALIDATED` / `PRODUCTION`.

| Ordre | Phase | Contenu | Statut |
|---|---|---|---|
| 1 | **0 — Fondations** | Dépôt, `.env`, `requirements.txt`, outillage, conventions | `IMPLEMENTED` |
| 2 | **1 — Voix I/O** | Micro configurable, TTS ElevenLabs + cache, lecture | `IMPLEMENTED` (tests partiels) |
| 3 | **2 — Wake-word** | Modèle Heed « Wilfrid », runtime continu (`core/wake/` validé P3 : 31/31, streaming mesuré, micro 16 kHz, ~17 ms/cycle), calibration et non-régression suivies | `IMPLEMENTED` + `TESTED` (runtime validé ; validation statistique du seuil repoussée à corpus élargi) |
| 4 | **3 — Boucle d'assistance** | Écoute → compréhension → action → réponse, en français | `PLANNED` (prérequis posés : wake validé P3 + session P4 validée ; STT/dialogue/mémoire restants) |
| 5 | **4 — Compétences/plugins** | Registre, manifeste, activation, isolation | `DESIGNED` → `PLANNED` |
| 6 | **5 — Mémoire** | Faits/préférences, persistance, oubli | `PLANNED` |
| 7 | **6 — Connaissance** | Recherche locale puis web, citations | `PLANNED` |
| 8 | **7 — Exécution contrôlée** | Outils typés, effets bornés et journalisés | `PLANNED` |
| 9 | **8 — Vérification** | Preuves par bloc, non-régression systématique | `PLANNED` |
| 10 | **9 — Apprentissage** | Retours d'usage, améliorations validées uniquement | `PLANNED` |
| 11 | **10 — Gouvernance** | Permissions, scopes, audit, arrêt d'urgence | `DESIGNED` → `PLANNED` |
| 12 | **11 — Versions V1/V2/V3** | V1 voix+wake, V2 mémoire+connaissance, V3 autonomie gouvernée | `PLANNED` |
| 13 | **12 — Revue d'autonomie** | Bilan, critères de réussite, clôture de cycle | `PLANNED` |

## Règle d'avancement

On ne passe à la phase N+1 qu'après **VALIDATION documentée** de la phase N.
Les phases 2 (wake-word) et 10 (gouvernance) portent la conception déjà
validée ; leur implémentation reste à exécuter dans l'ordre ci-dessus.
