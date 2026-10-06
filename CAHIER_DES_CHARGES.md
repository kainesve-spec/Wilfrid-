# Wilfrid — CAHIER DES CHARGES

> Transforme la vision (`MASTER_PLAN.md`) en exigences. Statuts :
> `PLANNED` / `DESIGNED` / `IMPLEMENTED` / `TESTED` / `VALIDATED` /
> `PRODUCTION` / `DEPRECATED`.

## 1. Exigences fonctionnelles

| ID | Exigence | Statut |
|---|---|---|
| F-01 | Écoute micro et capture audio configurable (périphérique, taux) | `IMPLEMENTED` (`jarvis.py`) |
| F-02 | Synthèse et lecture vocale (voix « Wilfrid ») | `IMPLEMENTED` (`wilfrid_voice.py`, cache) |
| F-03 | Détection du mot d'éveil « Wilfrid » en continu | `VALIDÉ` (P3 runtime 31/31 ; réserve statistique seuil 0.665, sync P-COH.2) |
| F-04 | Exécution d'actions (applications, fichiers, services) | Partiellement `PASS` (P7.1 R0–R2 locaux ; boucle complète + R3/R4 `PLANNED`, hors accueil existant) |
| F-05 | Compétences déclarées, versionnées, activables/désactivables | Partiellement `PASS` (P7.1 : 4 capabilities ; registre général `PLANNED`) |
| F-06 | Réponses en français, adaptées au contexte | Partiellement (P5 déclaratif local ; dialogue `PLANNED`) |

## 2. Exigences techniques

| ID | Exigence | Statut |
|---|---|---|
| T-01 | Python + dépendances fixées (`requirements.txt`), install reproductible | `IMPLEMENTED` |
| T-02 | Configuration par `.env` local, jamais versionné | `IMPLEMENTED` |
| T-03 | Audio 16 kHz ; inférence locale (ONNX) prioritaire | `DESIGNED` |
| T-04 | Fonctionnement Termux/Android et desktop | `PLANNED` (Termux partiel) |
| T-05 | Latence de réaction < 1 s après mot d'éveil (cible V1) | `PLANNED` |

## 3. Exigences de sécurité

| ID | Exigence | Statut |
|---|---|---|
| S-01 | Aucune clé/secret dans le dépôt | `IMPLEMENTED` (à maintenir à chaque revue) |
| S-02 | Permissions explicites par compétence, portée minimale | Partiellement `PASS` (P6 : 8 ids + registre P7 vide deny-by-default ; mandats/baux P7.2 `DESIGNED`) |
| S-03 | Micro : activation visible, arrêt immédiat possible | `PLANNED` |
| S-04 | Journal des actions à effet, consultable | Partiellement `PASS` (journaux append-only session/P6/P7 ; consultabilité applicative `PLANNED`) |

## 4. Extensibilité

| ID | Exigence | Statut |
|---|---|---|
| X-01 | Ajout d'une compétence sans toucher au noyau | `DESIGNED` |
| X-02 | Compétences testées isolément avant intégration | `PLANNED` |
| X-03 | Suppression propre (retrait sans résidu) | `PLANNED` |

## 5. Mémoire

| ID | Exigence | Statut |
|---|---|---|
| M-01 | Faits et préférences persistés, relus à bon escient | `PLANNED` |
| M-02 | Oubli/correction sur demande | `PLANNED` |
| M-03 | Aucune écriture mémoire implicite | `DESIGNED` (principe) |

## 6. Raisonnement

| ID | Exigence | Statut |
|---|---|---|
| R-01 | Intention explicite avant action | Partiellement (P5 déclaratif ; exécution gouvernée `PLANNED` au-delà de P7.1) |
| R-02 | Incertitude exprimée plutôt que devinée | Partiellement (`UNCERTAIN`/`CLARIFY` P5 ; généralisation `PLANNED`) |
| R-03 | Traçabilité décision → preuve | Partiellement (chaîne P5→P7.1 prouvée ; preuve/audit P7.2 `DESIGNED`) |

## 7. Outils

| ID | Exigence | Statut |
|---|---|---|
| O-01 | Catalogue d'outils typés, effets déclarés | Partiellement `PASS` (catalogue P7.1 R0 ; généralisation `PLANNED`) |
| O-02 | Exécution bornée (timeout, périmètre, réversibilité) | Partiellement `PASS` (P7.1 R0–R2 ; R3/R4 + env P7.2 `DESIGNED`) |

## 8. Vérification

| ID | Exigence | Statut |
|---|---|---|
| V-01 | Chaque bloc : audit → diagnostic → patch → post-audit → test → validation | Appliqué par bloc (`TESTED`, preuves par validation ; voir `METHODOLOGIE.md`) |
| V-02 | Non-régression mesurée avant clôture de bloc | Appliquée par bloc (suites + SHAs ; pas de CI) |

## 9. Apprentissage

| ID | Exigence | Statut |
|---|---|---|
| A-01 | Retours d'usage collectés explicitement | `PLANNED` |
| A-02 | Aucune modification persistante sans validation | `DESIGNED` (principe) |

## 10. Traçabilité

Chaque exigence `IMPLEMENTED` ou au-delà doit citer sa preuve (fichier, test,
mesure). Les exigences `PLANNED`/`DESIGNED` ne sont pas des capacités.
