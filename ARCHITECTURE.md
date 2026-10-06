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
| Compréhension | Intentions, entités, désambiguïsation | Partiellement `VALIDÉ` (P5 déclaratif local, voir ligne Cognition ; dialogue/mémoire `PLANNED`) |
| Décision | Plan d'action, choix de compétence, arbitrage | Partiellement `VALIDÉ` (P5 décideur/planner abstrait ; arbitrage avec effets `PLANNED`) |
| Cognition (P5) | Compréhension/décision structurée sans effets : taxonomie 8 kinds, classifieur déterministe local, décideur, planner abstrait (`core/cognitive/`, `NEED_ACTION` déclaratif, zéro exécution) | `VALIDÉ` (41/41, cumul 95/95) |
| Compétences/plugins | Capacités déclarées/versionnées (cœur de l'extensibilité) | Partiellement `PASS` (P7.1 : 4 capabilities R0–R2 ; registre général `PLANNED`) |
| Mémoire | Faits, préférences, historique ; oubli sur demande | `PLANNED` |
| Connaissance/recherche | Locale d'abord, web ensuite, sources citées | Partiellement `VALIDÉ` (P6.0–P6.6 locale 105/105 ; web `PLANNED`) |
| Outils et exécution | Effets bornés, journalisés, réversibles | Partiellement `PASS` (P7.1 R0–R2 ; R3/R4 et boucle complète `PLANNED`, accueil existant hors gouvernance) |
| Vérification | Tests, preuves, non-régression par bloc | Appliquée par bloc (`TESTED`, preuves par validation) ; pas de critic/verifier runtime |
| Apprentissage | Retours d'usage, ajustements validés uniquement | `PLANNED` |
| Gouvernance | Permissions, scopes, audit des effets | Partiellement `PASS` (P7.0-A `DESIGNED`, registre/gouverneur P7.1 ; mandats/baux P7.2 `DESIGNED`) |

## Contrats entre moteurs

- Chaque moteur expose : entrées typées, sorties typées, erreurs explicites.
- Aucun moteur n'écrit dans un autre sans contrat versionné.
- Tout effet externe passe par Exécution + journal ; toute persistance
  par Mémoire avec règle explicite.
- Les secrets vivent hors dépôt (`.env`) et hors journaux.

## Séparation QanXorus/TAIOS

Aucun partage d'exécution, de modèle, de secret ni de runtime. Interfaces
documentées uniquement si un échange devient nécessaire (actuellement : aucun).
