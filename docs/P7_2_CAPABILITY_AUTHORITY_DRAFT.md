# WILFRID — P7.2 / CAPABILITY & AUTHORITY ARCHITECTURE — VERSION CONSOLIDÉE

> STATUS : **CONSOLIDÉ D1–D21 + S1–S8 — EN ATTENTE DE REVUE.**
> Transformation documentaire du brouillon : aucune décision nouvelle inventée,
> aucune restriction sensible introduite sans marquage explicite, aucun code,
> test, registre, permission, réseau modifié. P5/P6/P7.1 intacts.
> Légende : [VALIDÉ] = validé par Monsieur K · [DÉDUIT] = déduction
> architecturale · [TECHNIQUE] = choix technique · [TECH-JUST] = restriction
> technique justifiée · [SENS-VAL] = restriction sensible validée ·
> [OUVERT] = question ouverte · [NON DÉCIDÉ] = point sans statut.

## Séparation fondamentale [VALIDÉ D1/D11/D15/D16/D20, consolidé S1–S8]
Capacité ≠ permission ≠ mandat ≠ autorité ≠ identité ≠ délégation ≠ secret
≠ environnement. Aucun de ces plans ne se substitue à un autre.

## Modèle de mission et chaîne d'autorité [VALIDÉ D1/D11, DÉDUIT]
Mission → objectif/intention → capacités disponibles → construction progressive
du mandat → autorité/scopes/autonomie → Gouverneur → planification →
invocation de capacité → environnement d'exécution → vérification → preuve →
journal → état de mission. Le mandat se construit progressivement : les
caractéristiques intrinsèques des capacités contribuent à ses paramètres sans
jamais créer d'autorisation [VALIDÉ D8]. Modifications : changement
d'autorité/capacité/scope/effet/autonomie = décision appropriée ; évolution
substantielle sans changement d'autorité = version + trace, approbation
seulement si le mandat l'exige [S6, DÉDUIT de D6/D11/D12].

## 1. Capacité [DÉDUIT de P7.1]
Fiche déclarative inerte. Déclaration non vérifiable = homologation
techniquement impossible ; toute sanction/conséquence de gouvernance reste
explicitement gouvernée, jamais automatique [S5]. Sous-déclaration avérée :
refus d'homologation = [SENS-VAL] à confirmer (proposé, non validé comme
sanction automatique).

## 2. Autorité [DÉDUIT de D1/D11/D17]
Chaîne prouvée mandat valide → bail actif → approbation couvrante → contrôles
par acte verts. Absence d'autorité = aucune action [VALIDÉ D13]. Relationnelle,
jamais propriété d'un compte ou d'un outil [VALIDÉ D16].

## 3. Scopes [VALIDÉ P7.1 reconduit ; TECH-JUST]
Exactitude + canonisation + anti-symlink/traversal : sans elles tout scope est
contournable. Voisin = DENY.

## 4. Autonomie [VALIDÉ D5]
Propriété du mandat, distincte des capacités. Nomenclatures actuelles
(ACTE_PAR_ACTE, MANDAT_BORNÉ, A0–A4) = provisoires et non normatives [S8] ;
employées uniquement comme termes illustratifs en attendant figeage [OUVERT].

## 5. Bail [VALIDÉ D1]
Registre central, rattaché au mandat, jamais permanent ; multi-actions
couvertes ; fin/suspension/révocation = inutilisable. Pas de renouvellement
implicite [TECH-JUST : sinon permanence par usage].

## 6. Governor [DÉDUIT de D7/B5 ; TECH-JUST]
Séquence intention → risque → bail/mandat → approbation → préconditions →
pré-act → effet → vérification → preuve → journal. Revalidation pré-acte
systématique (anti-TOCTOU, anti-évolution accord→acte).

## 7. Classification contextuelle [VALIDÉ D8]
Classe selon action + contexte + mandat, jamais le seul nom. Seuils de bascule
fixés par le mandat ; à défaut de mandat précis : surclassement prudent
[DÉDUCTION] + question du défaut portée en [OUVERT].

## 8. R3/R4 [VALIDÉ D8 + S7]
R3 autorisable sous mandat et conditions. R4 non interdit par principe ;
classification contextuelle ; aucune interdiction technique universelle cachée.
Posture prudente renforcée = proposition, jamais nécessité technique.

## 9. Réseau N3 HYBRID [VALIDÉ D9/D21]
Internet général possible si mandaté ; destinations/actions sensibles =
autorisation supplémentaire possible ; pas de durée maximale universelle ;
découverte ≠ autorisation ; contenu = donnée. Protections techniques
proportionnées : denylist privé/metadata/secrets, validation/canonisation
d'URL, DNS/SSRF, isolation des secrets — jamais de restriction fonctionnelle
générale déguisée. Aucune allowlist exhaustive universelle (contraire à D21 ;
allowlist = option de mandat, pas règle système).

## 10. Redirects [S1]
Autorisables si la cible reste compatible avec mandat + contrôles techniques,
revalidation SSRF à chaque saut, compteur borné par mandat ; destinations
dangereuses/non mandatées = refus. Défaut DENY = proposition, pas loi technique.

## 11. HTTPS [S2]
Privilégié techniquement [TECHNIQUE] ; HTTP possible en contexte mandaté
(contenu public, 0 secret/auth, source mandatée, pas d'action sensible
dérivée). Risques nommés : secrets, authentification, intégrité/MITM.

## 12. Schémas/protocoles [OUVERT partiel]
`https` (+ `http` sous S2) autorisables ; autre schéma = DENY par défaut
[TECH-JUST], sauf homologation dédiée si un mandat l'exige [SENS-VAL à venir].

## 13. Identités/délégations [VALIDÉ D16 ; DÉDUIT]
Délégation = objet du mandat `{identité, périmètre, fin}`, révocable avec lui.
Pas d'auto-délégation.

## 14. Secrets [VALIDÉ D15 ; TECH-JUST]
Couche dédiée + handles/références + redaction (sans quoi tout journal fuit).
Accès direct = capacité distincte explicitable. Jamais en mémoire normale/logs.

## 15. Environnements [S3]
Isolation proportionnelle au contexte/risque/données/effet [VALIDÉ D20].
Protégé par défaut [TECH-JUST] : secrets hors env, vars dangereuses nommées
(`LD_PRELOAD` et assimilées, pas `PATH`/`LANG` en bloc), anti-injection argv,
pas de chargement dynamique non homologué, chemins canonisés, fichiers = jail.
Aucune allowlist binaire exhaustive universelle, aucun env vide universel :
allégeables par mandat à faible risque [S3].

## 16. Planification/chaînage [VALIDÉ D3/D5/D12]
Enchaînement couvert si mandat ; incertitude locale = clarification du volet.
Profondeur/longueur sans plafond par défaut ; plafonds par mandat
recommandables sans imposition [SENS-VAL à venir si proposés].

## 17. Vérification [DÉDUIT ; TECH-JUST]
Pré-act + post-acte (effet == autorisé) ; un seul point = contournement unique.

## 18. Preuve/journal [VALIDÉ D17 ; TECH-JUST]
Autorisé ≠ exécuté ≠ réussi ≠ effet ; corrélation request_id + versions ;
refus de gouvernance tracés ; append-only vérifiable ; 0 secret en clair.

## 19. Erreurs/UNKNOWN [VALIDÉ D18 ; TECH-JUST]
NOT_EXECUTED/SUCCESS/FAILED/PARTIAL/UNKNOWN ; UNKNOWN jamais auto-résolu ;
reconstruction d'état avant reprise ; restauration jamais auto d'autorité
révoquée/suspendue/expirée ; compensation = action séparée autorisée.

## 20. Concurrence [VALIDÉ D19 ; OUVERT]
Autorisation individuelle ≠ commune ; pas de hiérarchie universelle ;
résolution contextuelle ; pas de contournement inter-missions. Priorité entre
mandats de même niveau : [OUVERT] (arbitrage cas par cas ou règle à définir).

## 21. Extensions de mandat [VALIDÉ D12 ; DÉDUIT]
Adaptation (méthode) vs extension (autorité) ; extension = nouvelle version +
approbation ; adaptation tracée sans approbation si le mandat le permet.

## 22. Révocation/suspension [VALIDÉ D7 ; TECH-JUST]
ACTIVE/SUSPENDED/TERMINATED/REVOKED ; non-démarrage garanti par lookup ;
en-cours selon capacité (état sûr prioritaire) ; tout journalisé.

## 23. Apprentissage/mémoire [VALIDÉ D14 ; DÉDUIT]
Séparées de l'autorisation ; influence seulement si mandat ; provenance
conservée ; mémoire = ressource lue sous mandat, jamais canal d'autorisation.

## 24. Séparation P6/P7 [VALIDÉ P7.1/D14 ; DÉDUIT]
Savoir vs agir ; double-accord mixte ; contenu jamais accordant ; consommation
P6 via capacité déclarée.

## 25. Plugins/skills/tools [DÉDUIT de P7.0-A ; TECH-JUST partiel]
Inerte/versionné/Gouverneur-seul ; homologation des effets déclarés +
retrait propre. Pinning obligatoire tiers/distant/sensible, recommandé local
[S4]. Sources admises : [OUVERT]. Homologation ≠ autorisation d'usage ;
vérification ≠ attribution [DÉDUCTION].

## 26. Proposition par Wilfrid [DÉDUCTION ; TECH-JUST]
PROPOSITION → homologation → approbation → bail ; sans effet propre ;
silence = refus ; proposeur/décideur séparés.

## Éléments ouverts (pourquoi / options / conséquences / validation requise)
- O1 seuils de bascule R : mandat muet → surclassement prudent actuel ;
  options = défaut prudent vs défaut permissif-tracé ; conséquence = frictions
  vs surface ; validation Monsieur K : OUI.
- O2 sources de plugins : local seul vs tiers signé ; conséquence = surface
  d'approvisionnement ; validation : OUI.
- O3 plafonds de chaîne : aucun vs recommandés ; conséquence = dérive de
  coût/effet ; validation : OUI si proposés.
- O4 usages R4 : cas par cas ; conséquence = ouverture contrôlée ; validation :
  OUI, jamais en lot.
- O5 nomenclature autonomie : figeage ; conséquence = normativité ; validation :
  OUI.
- O6 priorité inter-mandats : arbitrage vs règle ; validation : OUI si règle.
- O7 rituel d'approbation R3 : format/preuve ; validation : OUI.
- O8 réévaluation par mission : calibrage ; validation : OUI si imposée.
- O9 ordres TAIOS R3/R4 : classification + plafonds ; validation : OUI.
- O10 schémas non-HTTP : homologation dédiée ; validation : OUI si besoin.

## Tableau de statut
| Élément | Statut |
|---|---|
| Baux mandatés, anti-permanence, multi-actions, fin par mandat, anti auto-autorisation, états révocation, N3 HYBRID, preuve/audit, UNKNOWN, concurrence sans hiérarchie, mémoire/secrets/identités/env séparés | VALIDÉ |
| Chaîne d'autorité, mandat versionné, délégation-objet, corrélation preuves, homologation≠autorisation, proposeur/décideur | DÉDUIT |
| HTTPS préféré, revalidation pré-acte, corrélation, scopes exacts, denylist SSRF/privé/metadata, secrets isolés, non-renouvellement, lookup révocation | TECHNIQUE |
| (aucune — toute sensible reste marquée ouverte ci-dessus) | SENSIBLE VALIDÉ |
| O1–O10 | OUVERT |
| Sanction sous-déclaration, réapprobation non-autorité, usages R4, sources plugins, plafonds chaîne | NON DÉCIDÉ |

*Fin consolidation — documentaire, aucune implémentation, en attente de revue.*
