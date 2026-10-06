# Wilfrid — ARCHITECTURE CIBLE

> Architecture générale **VALIDÉE**. Statuts par moteur :
> `PLANNED` / `DESIGNED` / `IMPLEMENTED` / `TESTED` / `VALIDATED` / `PRODUCTION`.

## Vue d'ensemble

```
┌────────────┐  ┌──────────────┐  ┌──────────┐  ┌────────────┐  ┌───────────┐
│ PERCEPTION │→ │COMPRÉHENSION │→ │ DÉCISION │→ │ EXÉCUTION  │→ │VÉRIF./APP.│
│ voix/texte │  │ intentions   │  │ plan +   │  │ outils,    │  │ preuves,  │
│ contexte   │  │ entités      │  │ permiss. │  │ effets     │  │ mémoire   │
└────────────┘  └──────────────┘  └──────────┘  └────────────┘  └───────────┘
        ↕ MÉMOIRE (faits/préférences) · CONNAISSANCE (locale/web) · GOUVERNANCE
```

## Moteurs et responsabilités

| Moteur | Responsabilité | Statut |
|---|---|---|
| Perception vocale | Wake-word « Wilfrid » (Heed ONNX 40×101), écoute micro, VAD/énergie ; runtime `core/wake/` (capture→filtres à état→ring 16000→gate→mel→ONNX→seuil JSON→2 frames→réfractaire→`WAKE_DETECTED`, aucune action) | `VALIDÉ` (P3 ; seuil 0.665, réserve statistique documentée) |
| Entrée/sortie audio | Capture configurable, lecture TTS, cache | `IMPLEMENTED` (`jarvis.py`, `wilfrid_voice.py`) |
| Voix | Synthèse ElevenLabs, voix dédiée | `IMPLEMENTED` |
| Dialogue | Tours de parole, contexte conversationnel, français | `PLANNED` |
| Session et interaction (P4) | Session locale unique, machine IDLE→…→IDLE, contexte volatil borné+purgé, événements minimaux, identité Wilfrid/Monsieur K, salut date-seule, journal OFF ; sans STT/TTS/mémoire/action | `VALIDÉ` (54/54 avec P1-P3 ; seuil et modèles intacts) |
| Compréhension | Intentions, entités, désambiguïsation | `PLANNED` |
| Décision | Plan d'action, choix de compétence, arbitrage | `PLANNED` |
| Cognition (P5) | Compréhension/décision structurée sans effets : taxonomie 8 kinds, classifieur déterministe local, décideur, planner abstrait (`core/cognitive/`, `NEED_ACTION` déclaratif, zéro exécution) | `VALIDÉ` (41/41, cumul 95/95) |
| Compétences/plugins | Capacités déclarées/versionnées (cœur de l'extensibilité) | `DESIGNED` |
| Mémoire | Faits, préférences, historique ; oubli sur demande | `PLANNED` |
| Connaissance/recherche | Locale d'abord, web ensuite, sources citées | `PLANNED` |
| Outils et exécution | Effets bornés, journalisés, réversibles | `PLANNED` (accueil existant hors gouvernance) |
| Vérification | Tests, preuves, non-régression par bloc | `DESIGNED` |
| Apprentissage | Retours d'usage, ajustements validés uniquement | `PLANNED` |
| Gouvernance | Permissions, scopes, audit des effets | `DESIGNED` |

## Contrats entre moteurs

- Chaque moteur expose : entrées typées, sorties typées, erreurs explicites.
- Aucun moteur n'écrit dans un autre sans contrat versionné.
- Tout effet externe passe par Exécution + journal ; toute persistance
  par Mémoire avec règle explicite.
- Les secrets vivent hors dépôt (`.env`) et hors journaux.

## Séparation QanXorus/TAIOS

Aucun partage d'exécution, de modèle, de secret ni de runtime. Interfaces
documentées uniquement si un échange devient nécessaire (actuellement : aucun).
