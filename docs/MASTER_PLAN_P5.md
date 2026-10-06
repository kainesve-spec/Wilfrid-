# Wilfrid — MASTER PLAN P5 : Cognitive Core (corrigé après audit)

> P5 = premier bloc cognitif : compréhension/décision structurée, zéro effet.
> Corrections d'audit intégrées : copie profonde normative (§4),
> terminologie des compteurs clarifiée (§12). Aucun code modifié.

## 1. Nom et position
**P5 — Cognitive Core.** Chaîne : WAKE RUNTIME → SESSION MANAGER →
INTERACTION STATE → futur STT → **COGNITIVE CORE (P5)** → future RESPONSE
→ futur TTS. Moteur de compréhension/décision isolé, jamais d'action.

## 2. Objectif et périmètre IN
Entrée textuelle structurée → intention (taxonomie fermée versionnée) →
type de demande → paramètres simples → niveau de traitement → plan
abstrait → clarification si insuffisant → sortie structurée → erreurs
explicites. COMPRENDRE/DÉCIDER/PLANIFIER oui ; EXÉCUTER jamais.

## 3. Périmètre OUT (interdit)
STT, TTS, mémoire persistante (SQLite, embeddings, web), réseau, shell,
subprocess, navigateur, actions, skills/plugins, apprentissage, TAIOS,
QanXorus, trading, wakeword, « Will », toute modification P1/P2/P3/P4.

## 4. Contrat d'entrée (CORRIGÉ — réserve copie profonde levée)
`{text ≤ 2000c, session_id, context_snapshot, timestamp, source,
stt_confidence?}`. Le snapshot est une **COPIE PROFONDE** indépendante
du `SessionContext` P4 ; le Cognitive Core ne peut modifier ni le
contexte source, ni ses structures internes, ni objets/listes/dicts
imbriqués. **La copie profonde est la stratégie normative P5. Une
simple copie superficielle n'est pas considérée comme suffisante.**
Tests futurs exigés (non implémentés ici) : mutation valeur niveau 1,
structure imbriquée, liste, dict imbriqué, contexte source inchangé —
échec si une mutation du snapshot altère la source. Pas de dépendance
micro/STT direct.

## 5. Contrat de sortie
`{kind ∈ DIRECT, CLARIFY, PLAN, NEED_SEARCH, NEED_TOOL, NEED_ACTION,
REFUSE, UNCERTAIN ; payload ; confidence ; missing[]}`.
`NEED_ACTION` = intention déclarée, exécution interdite. Incertitude,
manquant, clarification, intention et plan abstrait représentables.

## 6. États et raisonnement borné
`IDLE→INPUT_RECEIVED→ANALYZING→DECIDING→PLANNING→READY`
(+`CLARIFICATION_REQUIRED`, `ERROR`). Profondeur/temps/taille bornés,
zéro récursion, zéro auto-modification, zéro accès implicite.

## 7. Sécurité et gouvernance
Aucune autorité : subprocess, shell, réseau, fichiers sensibles,
navigateur, services externes, TAIOS, QanXorus, trading, persistance.
Vérification par test statique d'imports. Capacités futures uniquement
via interfaces contrôlées et autorisées.

## 8. Moteur : logique déterministe locale (stdlib+regex)
Autonomie, coût nul, confidentialité totale, reproductible, latence ms.
Ni modèle local ni API distante pour valider P5. Aucune installation.

## 9. Tests prévus (non implémentés)
Normales/ambiguës/vides/complexes/contradictoires, contexte
absent/limité, erreurs, limites de taille, déterminisme, isolation
(aucun fichier/réseau créés), sécurité, non-régression. Mutations
snapshot (§4) incluses. PASS/FAIL par assertions exactes.

## 10. Observabilité
États, durées, types de décision, erreurs, compteurs, limites — sans
persister de contenu utilisateur (politique journal P4).

## 11. Extensibilité
Mémoire, knowledge, web, tools, skills, learning : consommables en aval
sans surcroît d'autorité pour P5. Aucune préemption des couches futures.

## 12. Non-régression (CORRIGÉ — réserve comptage levée)
- P1 : **7** tests spécifiques validés.
- P2 : validation et compatibilité validées selon le protocole P2.
- **P3 historique : 31/31** = cumul exécuté lors de la validation P3
  (detector 9 + preproc 7 + capture 2 + runtime 6 + harness 7).
- **Tests P3-spécifiques de non-régression : 24** (31 hors harness P1).
- P4 : **23** tests spécifiques.
- **Référence cumulée : 54/54 = 7 + 24 + 23.** Ne jamais écrire
  « P3 = 24/24 » d'une façon remplaçant le 31/31 historique ; employer
  « P3 historique : 31/31 » et « Tests P3-spécifiques de
  non-régression : 24 ». Ce cumul n'est pas une nouvelle exécution
  tant que les tests n'ont pas été relancés.

## 13. Fichiers envisagés (non créés)
`core/cognitive/{__init__,types,input,classifier,decider,planner,core}.py`
+ `tests/test_cognitive_*.py`. Aucune modification P1/P2/P3/P4 requise.

## 14. Risques
Hallucination (taxonomie fermée + `UNCERTAIN` par défaut), mauvaise
classification (corpus versionné), ambiguïté (clarification), complexité
prématurée (périmètre restreint), couplage futur (contrats versionnés),
latence/mémoire (négligeables en logique déterministe).

## 15. Validation P5 (critères)
Contrats respectés ; machine correcte ; bornes prouvées ; contexte lu
non écrit ; zéro persistance/action/shell/réseau/TAIOS ; déterminisme ;
tests complets ; docs ; P1-P4 intacts ; incertitudes explicites.

## 16. Compatibilité P1–P4
P1 (onnx/json/seuil 0.665/harnais), P2 (découplage, `jarvis.py`), P3
(runtime, `WAKE_DETECTED`, preprocessing, seuil), P4 (identité Monsieur K,
session, contexte volatil lu-seul, journal, contrats STT/TTS) : préservés.

## 17. Méthodologie
MASTER PLAN → AUDIT → DIAGNOSTIC → PATCH → POST-PATCH AUDIT →
TEST/VALIDATION → DOCUMENTATION → AUDIT DOCUMENTATION. Sans saut.
