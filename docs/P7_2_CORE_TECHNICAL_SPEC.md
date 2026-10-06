# WILFRID — P7.2 / SPÉCIFICATION TECHNIQUE — NOYAU MÛR

> STATUS : **PROPOSÉ — EN ATTENTE DE REVUE. DOCUMENTATION UNIQUEMENT.**
> Noyau mûr = tout ce qui est spécifiable maintenant sous D1–D21 + S1–S8.
> Aucun code, test, registre, permission, réseau, dépendance modifié ou créé.
> P5/P6/P7.1 intacts. R3/R4, réseau, trading TAIOS : non implémentés.
> Aucune décision nouvelle de Monsieur K inventée. Légende :
> [VALIDÉ] · [DÉDUCTION] · [TECHNIQUE] · [TECH-JUST] (restriction technique
> justifiée) · [SENS-VAL] (sensible validée) · [OUVERT].

## 1. MODÈLE DE CAPACITÉ
- Objectif : décrire un pouvoir technique sans conférer aucun droit [VALIDÉ D1/D6].
- Données : `{id unique, type, effets déclarés max, scopes admissibles,
  contraintes intrinsèques, provenance, version, état}`.
- Invariants : fiche inerte ; activation uniquement via bail+mandat ; déclaration
  non vérifiable = homologation techniquement impossible [S5].
- Entrées : proposition de fiche. Sorties : fiche HOMOLOGUÉE ou REFUSÉE.
- Erreurs : sous-déclaration avérée → refus (sanction = gouvernée, [SENS-VAL] à confirmer).
- Dépendances : homologation (§12). Niveau : [DÉDUCTION] + [TECH-JUST] partiel.

## 2. MODÈLE DE MANDAT
- Objectif : porter tout ce qui varie par mission [VALIDÉ D11].
- Données : `{mission, objectif, capacités disponibles, scopes, autonomie,
  conditions opérationnelles/temporelles/succès-fin/escalade, état, version,
  historique}`. Paramètres variables portés par le mandat, jamais de valeurs
  universelles arbitraires [VALIDÉ D2/D3/D4].
- Invariants : versionné ; substantiel+autorité = nouvelle décision ; substantiel
  sans autorité = version + trace [S6]. Niveau : [VALIDÉ] structure,
  [DÉDUCTION] mécanique de version.

## 3. GOUVERNEUR
- Objectif : seul chemin vers l'effet [DÉDUCTION B5/D7].
- Chaîne : intention → requête typée → classification → mandat → autorité →
  validation pré-acte → invocation capacité → environnement → action →
  vérification → preuve → journal → état.
- Distingue : proposition (sans effet) / décision (arbitrage) / autorisation
  (droit borné) / exécution (acte) / effet (résultat observé) / vérification
  (conformité effet == autorisé). Niveau : [DÉDUCTION] + [TECH-JUST] (revalidation).

## 4. REVALIDATION PRÉ-ACTE (contrôles obligatoires)
Mission active, mandat/version, capacité, permission, scope, identité/délégation,
révocation/suspension, conditions temporelles, environnement, ressources,
classification risque/contexte, effets déclarés. Une autorisation historique ne
suffit jamais seule [DÉDUCTION D7/D17 ; TECH-JUST anti-TOCTOU].

## 5. BAIL (V2 validé)
Lié au mandat, non permanent, inutilisable après suspension/fin/révocation,
multi-actions couvertes, pas de renouvellement implicite [VALIDÉ D1].
V3 fenêtres = optionnelle par mandat. V1 écarté, V4 reporté.

## 6. AUTONOMIE
Appartient au mandat ; ne crée ni capacité ni permission ni auto-autorisation
[VALIDÉ D5]. Nomenclatures A0–A4 / ACTE_PAR_ACTE / MANDAT_BORNÉ : provisoires,
non normatives [S8, OUVERT O5].

## 7. R3/R4 (classification contextuelle)
Action + contexte + mandat ; aucun seuil numérique universel ; seuils éventuels
= paramètres du mandat [VALIDÉ D8]. Incertitude = surclassement prudent P7.0-A
sans valeur d'interdiction universelle [DÉDUCTION]. R4 non interdit par principe ;
aucun refus universel R4 codé ; catégories concrètes ouvertes [OUVERT O4, S7].

## 8. RÉÉVALUATION (bibliothèque de déclencheurs, activation par mandat)
Cible, état, contexte, événement externe, anomalie, perte de capacité,
modification du mandat, dérive, autres pertinents. Aucun intervalle universel
[VALIDÉ D4]. Distingue réévaluation technique (garde auto) / décisionnelle
(revue humaine) / réautorisation (nouvelle approbation) [DÉDUCTION].
[OUVERT O8 : catalogue exact et fréquences par mission].

## 9. CHAÎNES
Détection de cycles, anti-récursion infinie, détection de boucle, traçage
[TECH-JUST : sinon divergence/boucle infinie, sans restreindre aucune mission
légitime]. Aucun plafond fonctionnel universel ; limites fonctionnelles par
mandat [VALIDÉ D3]. [OUVERT O3 : plafonds par défaut éventuels].

## 10. CONCURRENCE INTER-MANDATS
Détection de conflit ; séquencement, attente, parallélisation compatible,
réservation si couverte, réduction, refus local, escalade [VALIDÉ D19].
Aucune hiérarchie universelle. Priorité générale [OUVERT O6].

## 11. APPROBATION / PREUVE
Format commun compatible B3 : `{mandat_id, version, portée, fin/conditions,
décideur, horodatage}` [DÉDUCTION]. Interface multi-modèles (par acte, par
mandat, par extension) sans imposer ACTE_PAR_ACTE [VALIDÉ D3/D5].
Modèle R3 [OUVERT O7].

## 12. EXTENSIONS / PLUGINS
Chaîne : provenance → vérification technique → homologation → capacité →
permission → mandat → utilisation [DÉDUCTION P7.0-A]. Empreinte, version,
vérification, audit imports, isolation, preuve [TECH-JUST]. Pinning obligatoire
tiers/distant/sensible, recommandé local [S4]. Politique des sources
[OUVERT O2]. Homologation ≠ autorisation ; vérification ≠ attribution.

## 13. RÉSEAU (D21 + S1 + S2)
Internet général mandaté, sans allowlist exhaustive universelle ; découverte
autorisée si couverte, découverte ≠ autorisation nouvelle [VALIDÉ D21].
Techniques : canonisation URL, DNS + SSRF, blocage privé/loopback/link-local/
metadata tranché par le mécanisme technique de validation de destination du
Gouverneur (contexte de la requête + mandat + propriétés techniques de la
destination : classe d'adresse, résolution effective, schéma), revalidation
avant acte et après changement de résolution,
contrôle redirects (pas de DENY universel ; revalidation par saut ; refus si
dangereux/non compatible) [S1]. Ces protections restent techniques et ne
constituent ni une allowlist exhaustive déguisée ni une restriction de
l'Internet général mandaté [D21]. HTTPS préféré, HTTP possible en contexte
mandaté [S2]. Contenu = donnée, jamais autorisation.

## 14. SCHÉMAS
Registre extensible ; `https` (+ `http` sous S2) autorisables ; autre schéma =
indisponible jusqu'à homologation, NON « interdit universellement » [DÉDUCTION].
FTP/FILE/WS/WSS/DATA non implémentés, régime [OUVERT O10].

## 15. ENVIRONNEMENT (proportionnel : risque/données/effet/capacité/contexte)
Secrets hors env, vars dangereuses nommées filtrées, anti-injection, chemins
canonisés, fichiers contrôlés, chargements dynamiques contrôlés [TECH-JUST].
Jamais imposés universellement : env vide, allowlist binaire exhaustive,
absence PATH/LANG, isolation uniforme [S3].

## 16. SECRETS
Secret ≠ accès ≠ autorité [VALIDÉ D15]. Handles/références, exposition minimale,
0 secret en mémoire normale/journal (audit par métadonnées) [TECH-JUST].

## 17. IDENTITÉ / DÉLÉGATION
Identité ≠ compte ≠ délégation ≠ mandat ≠ capacité [VALIDÉ D16]. Tout acte
externe relié à : agent, mission, mandat/version, délégation, identité/compte,
capacité [DÉDUCTION D17].

## 18. PREUVE / JOURNAL
Autorisé ≠ exécuté ≠ réussi ≠ effet observé [VALIDÉ D17]. Append-only,
preuves corrélées (request_id + versions), refus significatifs tracés,
0 secret en clair [TECH-JUST].

## 19. ERREURS / INCERTITUDE
NOT_EXECUTED / EXECUTED_SUCCESS / EXECUTED_FAILED / PARTIAL / EXECUTION_UNKNOWN
[VALIDÉ D18]. UNKNOWN jamais auto-converti ; vérification d'état si disponible ;
pas de retry universel [TECH-JUST : retry aveugle = double effet].

## 20. MISSIONS À EFFET EXTERNE SENSIBLE (gabarit technique seul)
Principe : Wilfrid est domaine-agnostique ; le domaine d'une mission est fourni
par son contexte, ses objectifs, ses capacités et ses ressources autorisées —
jamais une hypothèse architecturale. Champs génériques : compte/identité,
capacités du domaine, données, stratégie, paramètres, conditions, risques,
effets, vérification, journal [DÉDUCTION D10]. Exemple travaillé (non
normatif, non finalité) : trading/TAIOS — valeurs, limites, paires, montants,
classifications, garde-fous réels = [OUVERT O9], validation séparée requise.
Aucune connexion, aucun ordre. TAIOS/trading = intégration spécialisée parmi
d'autres, extensible aux domaines futurs non définis.

## 21. OUVERTS PRÉSERVÉS
O2 sources, O4 usages R4, O5 nomenclature, O6 priorité générale, O7 rituel R3,
O9 trading réel, O10 non-HTTP : non fermés. O1/O3/O8 : sans valeurs universelles.

## 22. CONCLUSION
A. Spécifiable maintenant : §§1–6, 8–9 (mécanismes), 11 (format), 12 (chaîne),
   13–19 (contrôles), 20 (gabarit). B. Interfaces ouvertes : seuils R, sources,
   plafonds chaîne, rituel R3, schémas, priorité, nomenclature, trading réel.
C. Décisions indispensables par partie : O2 avant extensions tierces ; O4 avant
   tout R4 ; O7 avant tout R3 ; O9 avant trading réel ; O10 avant non-HTTP(S).
D. NE DOIT PAS être codé maintenant : R3/R4, réseau, trading, schémas non-HTTP,
   renouvellement/rituels non validés, toute valeur universelle non validée.
E. Prochaine étape recommandée : validations Monsieur K O2/O7 (débloquent R3
   réseau), puis O9 (trading), sans rouvrir le noyau mûr.

*Fin spec noyau mûr — documentaire, en attente de revue.*
