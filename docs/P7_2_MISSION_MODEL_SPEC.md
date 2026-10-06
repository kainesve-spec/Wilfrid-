# WILFRID — P7.2 / MODÈLE DE MISSIONS LONGUE DURÉE — SPÉCIFICATION CONCEPTUELLE

> STATUS : **PROPOSÉ — EN ATTENTE D'APPROBATION DE MONSIEUR K.**
> Révision de conception uniquement : aucun code/test/registry/permission/réseau
> modifié, P5/P6/P7.1 intacts, R4 non créé, aucun domaine réel sélectionné,
> aucun test réseau. Remplace la logique de durée de `docs/P7_2_R3_NET_SPEC.md`
> (conservée comme historique, voir bandeau) sans la supprimer.
> Principe directeur : la durée d'une mission N'EST PAS limitée par une durée
> maximale arbitraire ; elle appartient au mandat créé/autorisé. Aucune bonne
> pratique proposée ne vaut interdiction permanente tant que Monsieur K ne l'a
> pas validée comme telle.

## A. MODÈLE DE MISSION
Une mission = `{id, objectif, périmètre, fin (durée et/ou condition
d'accomplissement), capacités attachées, autorisations, niveau d'autonomie,
conditions d'arrêt, état}`. États : `PROPOSÉE → AUTORISÉE → ACTIVE →
SUSPENDUE → TERMINÉE/RÉVOQUÉE/EXPIRÉE` (terminaux, sans reprise implicite).
Journal de mission : append-only, disjoint P6, métadonnées seules
(intentions, décisions, effets bornés, preuves), jamais de secret ni de contenu
sensible ; journal indisponible = suspension de fait (aucune action nouvelle).

## B. MISSION / CAPACITÉ / AUTORISATION
Une capacité attachée à une mission = droit d'usage **lié au mandat**
(bail de mission : `capability + mission_id + scope + limites + fin de mission`),
jamais une autorisation globale permanente : hors mandat (autre mission, après
fin, périmètre voisin) = DENY. Fin de mission = extinction automatique de tous
les baux (pas de révocation individuelle requise, traçée comme `EXPIRED`).
Le registre reste vide de droits permanents ; seuls existent des baux
horodatés référençant un mandat valide, vérifiés à chaque action.

## C. ACTIONS PENDANT UNE MISSION
Une mission autorisée peut produire **plusieurs actions** si son mandat les
couvre : « une action par requête » N'EST PAS une règle fondamentale
(statut : PROPOSÉE NON VALIDÉE, non implémentable en l'état). Chaque action
reste individuellement contrôlée (scope, limites, pré-check, preuve, journal),
mais ne requiert pas une nouvelle autorisation si elle est couverte par le
mandat. Toute limite quantitative (N actions, volumes, fréquences) = PROPOSITION
NON VALIDÉE jusqu'à approbation explicite de Monsieur K.

## D. RÉÉVALUATION
Contrôles périodiques / revalidation / conditions de garde possibles SANS
expiration arbitraire : points de contrôle définis par le mandat (ex. revue
humaine, garde-fou d'anomalie, plafond de coût), jamais une durée couperet
imposée par défaut. Fréquence et nécessité = décision de Monsieur K par
mission, pas règle système. Échec d'un contrôle = suspension, pas prolongation
implicite ni poursuite aveugle.

## E. AUTONOMIE
Wilfrid poursuit une mission sans redemander d'autorisation par action **si et
seulement si** cette autonomie fait explicitement partie du mandat (niveau
d'autonomie : `ACTE_PAR_ACTE` / `MANDAT_BORNÉ` / niveaux supérieurs refusés par
défaut). Hors mandat ou doute = clarification/refus + suspension en attente.

## F. ESCALADE
- Action couverte : exécutable sous contrôles C–E.
- Action non couverte : DENY + zéro effet + journal + poursuite du mandat
  (sauf garde contraire).
- Action nécessitant une nouvelle autorisation : suspension partielle du volet
  concerné, demande explicite à Monsieur K référençant le mandat ; silence =
  refus ; jamais d'auto-élargissement (une capability ne s'étend pas elle-même).

## G. RÉVOCATION ET ARRÊT
Monsieur K peut à tout moment : suspendre (gel des actions nouvelles, état
conservé), révoquer (fin immédiate, baux éteints, pas de nouvel acte),
ordonner l'arrêt propre (finalisation bornée puis clôture journalisée).
Révocation = non-démarrage garanti ; interruption en-cours = réserve R-B4
reconnue, compensée en P7.2 par l'exclusion des effets irréversibles non
gouvernés tant qu'elle n'est pas traitée.

## H. MISSIONS TRÈS LONGUES (sans maximum arbitraire)
1 heure, 6 heures, 24 heures, 1 semaine, plusieurs semaines, durée indéterminée
jusqu'à accomplissement/révocation : toutes représentables par `fin = durée
et/ou condition`. Aucune extinction automatique à 10 minutes ou autre seuil
système (l'ancienne borne de 10 minutes est RETIRÉE de la conception : ce n'était
pas une règle fondamentale validée). Gardes recommandées (non imposées) :
réévaluation §D et exposition des coûts/risques cumulés au journal.

## I. RÉSEAU (réévaluation à la lumière des missions)
`P7.NET_READ_ALLOWLISTED` reste candidat R3 non validé ; ses anciennes bornes
(dont ≤10 min) NE SONT PAS reconduites automatiquement : seule la structure
(scope exact, allowlist versionnée, DNS/SSRF, redirects=DENY, GET seul, HTTPS
obligatoire, contenu ≠ autorisation) est conservée comme proposition.
Durée d'accès réseau, volumes et fréquences = paramètres du mandat de mission,
à valider par Monsieur K, pas constantes système.

## J. CAS D'ÉTUDE TAIOS (analyse seule, sans implémentation ni connexion)
« Connecte-toi à TAIOS et trade pendant 6 heures » se représenterait comme :
mission `{objectif: trading TAIOS borné, fin: 6h, capacités: lecture réseau
allowlistée TAIOS + exécution d'ordres À HOMOLOGUER (R3/R4 à classer),
autonomie: MANDAT_BORNÉ, arrêt: révocation immédiate + kill}.
Questions restées à définir : périmètre exact des ordres (montants, paires,
levier), allowlist TAIOS (domaines, TLS), plafonds de perte, garde-fou
d'anomalie, fréquence de réévaluation,papers pre-trade, R3 vs R4 du placement
d'ordre (potentiellement R4 = exclu tant que non décidé), jamais de secret
de credential dans scope/journal.

## K. TABLEAU DES RESTRICTIONS P7.2
| Restriction | Objectif | Risque réduit | Impact capacités | Techniquement nécessaire ? | Statut | Décision Monsieur K requise |
|---|---|---|---|---|---|---|
| Bail lié au mandat (pas de droit permanent) | empêcher les autorisations globales | persistance furtive, priv-esc | toute capacité reste bornée au mandat | OUI | PROPOSÉE NON VALIDÉE | valider le modèle de bail |
| Fin = durée et/ou condition du mandat | permettre missions longues | coupure arbitraire à 10 min | missions 1h→indéterminée possibles | OUI | PROPOSÉE NON VALIDÉE | valider + fixer par mission |
| Multi-actions sous mandat | autonomie mandatée | blocage arbitraire 1-acte | N actions couvertes sans re-demande | NON (recommandé) | PROPOSÉE NON VALIDÉE | valider principe + plafonds éventuels |
| Réévaluation périodique | détecter dérive | anomalie, coût cumulé | pauses/points de contrôle | NON | PROPOSÉE NON VALIDÉE | valider fréquence/nécessité par mission |
| Niveaux d'autonomie (défaut ACTE_PAR_ACTE) | moindre privilège | action hors mandat | autonomie seulement si explicite | OUI | PROPOSÉE NON VALIDÉE | valider niveaux + défaut |
| Escalade = DENY + demande | anti auto-élargissement | confused deputy, scope creep | actes hors mandat interdits | OUI | PROPOSÉE NON VALIDÉE | valider le flux |
| Révocation/suspension à tout moment | arrêt d'urgence | mission incontrôlée | coupure non-démarrage | OUI | PROPOSÉE NON VALIDÉE | valider rituel d'arrêt |
| Ancienne borne ≤10 min réseau | exemples initiaux prudents | surexposition réseau | missions réseau >10 min impossibles | NON | RETIRÉE (n'était pas validée) | confirmer le retrait |
| GET seul / HTTPS obligatoire / allowlist exacte | surface minimale | SSRF, exfiltration, MITM | lecture restreinte | OUI pour HTTPS+allowlist ; NON pour GET-seul (recommandé) | PROPOSÉE NON VALIDÉE | valider chaque point |
| Protections R4 / EXEC / upload / metadata (contextuelles, pas d'interdiction universelle) | blast-radius | irréversible, secrets, RCE | pas de trading/exécution sans examen | OUI en contexte à risque avéré, NON par défaut système | PROPOSÉE NON VALIDÉE (reconduction en examen) ; R4 non interdit par principe (D8/S7), classification par action + contexte + mandat | valider maintien et périmètres jusqu'à P7.2+ |
| Journal indisponible = DENY TOTAL | traçabilité | actes non prouvés | arrêt si journal down | OUI | VALIDÉE (P7.1, reconduite) | aucune (appliquer) |
| Contenu ≠ autorisation | anti injection | prompt injection, contenu hostile | contenu jamais accordant | OUI | VALIDÉE (P6/P7.1, reconduite) | aucune (appliquer) |

Aucune ligne « PROPOSÉE NON VALIDÉE » ne doit être implémentée.
Aucune permission active créée, aucun domaine réel sélectionné, aucun test
réseau lancé, P5/P6/P7.1 et registre intacts (vérifiés : rien modifié).

**VERDICT : P7.2 MISSION MODEL = READY FOR REVIEW**

## DÉCISION 1 — MODÈLE DE BAIL (validée par Monsieur K, conception seule)
1. V2 bail-registre central = socle : bail conservé au registre du Gouverneur,
   obligatoirement rattaché à une mission (`mission_id, capability, scope,
   limites, état, version, référence mandat, conditions de fin`), jamais une
   permission permanente autonome. Vérification bail + mandat avant chaque
   action ; multi-actions couvertes sans approbation par acte si l'autonomie
   du mandat l'autorise ; révocation/suspension/fin = bail inutilisable.
2. V3 fenêtres = optionnelle, non obligatoire (définies par le mandat si usage ;
   une mission de 6 h peut fonctionner en autonomie continue si autorisée).
3. V1 écarté comme modèle de base. 4. V4 reporté, non implémenté.
Aucun code/registre/permission/réseau modifié par cette décision.

## DÉCISION 2 — DURÉE ET FIN DE MISSION (validée par Monsieur K, conception seule)
1. Aucune durée maximale globale imposée par l'architecture.
2. Durée déterminée par le mandat quand nécessaire (1 h, 6 h, 24 h,
   1 semaine, plusieurs semaines, davantage).
3. Mission possible par condition d'accomplissement sans durée prédéfinie.
4. Fin par mandat : accomplissement, échéance éventuelle, arrêt explicite,
   révocation, condition d'arrêt définie.
5. Capacité réseau sans limite globale arbitraire de 10 minutes (retirée) ;
   active pendant toute la durée autorisée si le mandat l'autorise, liée au
   bail, jamais permission permanente.
6. Aucune fréquence obligatoire de réévaluation déduite (renvoyée à DÉCISION 4).

## DÉCISION 3 — MULTI-ACTIONS ET PLAFONDS (validée par Monsieur K, conception seule)
1. Mission autorisée = plusieurs actions successives couvertes possibles ;
   pas de limite universelle à une action par requête (règle non retenue).
2. Action couverte + autonomie du mandat = exécution sans approbation humaine
   par acte.
3. Plafonds quantitatifs non imposés par l'architecture ; définissables par
   mandat (actions, volume, montant, fréquence, ressources, risque, autres).
4. Hors mandat = refus ou nouvelle autorisation (escalade définie ultérieurement).

## DÉCISION 4 — RÉÉVALUATION DES MISSIONS (validée par Monsieur K, conception seule)
1. Mission longue ≠ interruption auto pour réautorisation ; réévaluation
   (conformité au mandat) distincte de réautorisation.
2. Contrôles de conformité possibles sans nouvelle approbation.
3. Aucune fréquence universelle imposée ; stratégie définie par le mandat :
   autonomie continue, réévaluation auto, sur événements, humaine périodique,
   ou combinaison.
4. Réévaluation n'élargit jamais implicitement le mandat ; sortie de mandat =
   règles d'escalade. Mission longue possible sans réautorisation périodique
   si mandat explicite. Aucun délai universel (10/30/60 min, etc.).

## DÉCISION 5 — NIVEAUX D'AUTONOMIE (validée par Monsieur K, conception seule)
1. Autonomie = propriété du mandat ; distincte de la capacité technique
   (un niveau élevé n'accorde aucune capacité non explicitement accordée).
2. Le niveau détermine jusqu'où Wilfrid décide/agit seul dans le périmètre ;
   modes sélectionnables par mission, pas restrictions universelles.
3. Une mission peut autoriser le choix et l'enchaînement d'actions nécessaires
   dans le mandat ; jamais « accès illimité », jamais d'auto-attribution de
   capacité ni de sortie de périmètre.
4. Nomenclature/nombre de niveaux ouverts ; proposition initiale NON VALIDÉE
   (A0 Observation, A1 Assistance, A2 Autonomie bornée, A3 Autonomie étendue,
   A4 Autonomie complète du mandat), non implémentable telle quelle.

## DÉCISION 6 — ESCALADE HORS MANDAT (validée par Monsieur K, conception seule)
1. Mission = seules capacités/périmètres/actions couvertes ; action couverte =
   exécutable selon l'autonomie accordée.
2. Jamais d'auto-déduction d'autorisation par utilité à l'objectif.
3. Action nécessaire non couverte : distinguer couverte / non couverte mais
   pertinente / clairement hors périmètre ; pas d'exécution automatique.
4. Demande d'extension/nouvelle autorisation possible (distincte du mandat,
   jamais créée automatiquement) ; hors périmètre = refus ou escalade selon
   le    mandat, sans élargissement implicite ; comportement précis définissable
   par mandat ou règles ultérieures.

## DÉCISION 7 — RÉVOCATION ET ARRÊT (validée par Monsieur K, conception seule)
1. États explicites : ACTIVE, SUSPENDUE, TERMINÉE, RÉVOQUÉE ; fin normale =
   condition du mandat satisfaite.
2. Suspension = gel des nouvelles actions jusqu'à reprise autorisée ;
   révocation = retrait immédiat du droit de nouveaux actes ; mission
   terminée/révoquée = baux inutilisables ; nouveaux droits = nouvelle mission.
3. Aucun délai universel d'arrêt forcé. Actions en cours : traitées selon
   capacité/mandat, priorité à l'état sûr ; mécanismes fins définis par
   catégorie si nécessaire. Révocation ≠ autorisation ni modification implicite.
4. Journal : suspension/reprise/fin/révocation avec cause + version de mandat.

Décisions que Monsieur K devra valider avant toute implémentation : 1. modèle
de bail lié au mandat ; 2. fin par durée/condition sans maximum système
(+ confirmer le retrait des 10 min) ; 3. multi-actions sous mandat et plafonds
éventuels ; 4. réévaluation (fréquence/nécessité) ; 5. niveaux d'autonomie et
défaut ; 6. flux d'escalade ; 7. rituel de révocation/arrêt ; 8. maintien des
interdictions R4/EXEC/upload/metadata ; 9. paramètres réseau par mission
(allowlist TAIOS incluse) ; 10. classification R3 vs R4 du placement d'ordres
et plafonds de risque trading avant tout cas TAIOS réel.
