# WILFRID — P7.0-A / PARTIE A — CONCEPTION (sans code)

> Statut : `DESIGNED` — conception seule.
> Périmètre : P7.0-A uniquement. Aucun code applicatif, aucun skill/plugin/tool/action/exécution,
> aucune permission réellement activée, aucun réseau/API externe, aucune nouvelle dépendance,
> aucun changement P6, aucune conception P7.1, aucun traitement P7.0-B, aucun POST-AUDIT.
> Références : `MASTER_PLAN.md` (phases 4,7,10), `ARCHITECTURE.md`, `CAHIER_DES_CHARGES.md`
> (S-02, S-04, F-05, X-01/X-02/X-03, O-01/O-02), `METHODOLOGIE.md`, `docs/DECISIONS.md`.
> P1–P5 validés. P6.0–P6.6 déclarés terminés par le commanditaire (200/200 PASS, P6.6 POST-AUDIT PASS)
> — pris comme hypothèse d'entrée, non ré-audités ici.
>
> **Annotation P-COH.3 (2026-10-06, historique inchangé) :** ci-dessus = ÉTAT AU
> MOMENT DE LA CONCEPTION (hypothèse d'entrée, sans preuve propre).
> ÉTAT CONSTATÉ APRÈS VALIDATION : preuves réelles dans `docs/POST_AUDIT_P6_6.md`
> (SHA256, 105/105 P6, 200/200 cumulés) et `docs/VALIDATIONS.md`. Lire les deux
> niveaux sans les confondre.

## 0. Principes directeurs (rappels inviolables)

1. **Refus par défaut.** Hérité P6.1 : toute permission est `disabled` à la naissance.
   P7.0-A ne crée aucun état `enabled`. Aucun `enable()` n'est invoqué en conception.
2. **Monsieur K seul souverain d'autorisation.** Aucune extension, aucun document,
   aucun outil, aucun modèle ne peut s'auto-accorder, s'augmenter ou accorder à un tiers.
3. **Core souverain.** Le Core (wake/session/cognitive + gouvernance) arbitre tout.
   Les extensions sont invitées, bornées, révocables. Jamais l'inverse.
4. **Séparation P6 / P7.** P6 = savoir (lire, acquérir, synthétiser, citer).
   P7 = agir (effet borné, journalisé, réversible). Aucun contournement croisé.
5. **Traçabilité.** Toute demande, accord, refus, augmentation, réduction, révocation
   est journalisée avec motif. Pas de journal = pas d'autorisation (principe de validation future).
6. **Moindre privilège + bornes.** Scope étroit, durée courte, limites quantifiées,
   réversibilité préférée. Élargir exige un nouvel accord explicite.
7. **Conception ≠ capacité.** Tout ce qui suit est `DESIGNED`. Rien n'est `IMPLEMENTED`.

## 1. Glossaire et architecture Skills / Plugins / Capabilities / Tools / Permissions

### 1.1 Définitions normatives (P7)

| Notion | Définition P7.0-A | Exemples d'attributs déclaratifs (sans code) |
|---|---|---|
| **Skill** | Description déclarative d'un savoir-faire métier adressable par la Décision (P5). Ne contient aucune exécution. | nom, version, description, kinds P5 couverts, permissions requises, entrées/sorties typées, préconditions, tests exigés |
| **Plugin** | Paquet livrable versionné qui porte 1..n skills + 0..n tools + manifeste + preuves. Unité d'installation / activation / retrait. | id, version pin, provenance, empreinte d'intégrité, liste skills/tools, dépendances (stdlib uniquement), journal de cycle de vie |
| **Capability** | Droit d'usage accordé à un skill/plugin via permissions : « pouvoir faire X dans tel scope ». N'existe que si permission accordée par Monsieur K. | permission_id, scope, limites, durée, version d'accord |
| **Tool** | Fonction d'effet bornée, typée, appelée uniquement via l'Exécution contrôlée après vérification permission+scope+limites. Jamais appelée directement par cognition, session ou plugin. | nom, schéma entrée/sortie, effets déclarés, bornes (timeout, taille, cardinalité), réversibilité, niveau de risque |
| **Permission** | Autorisation explicite, versionnée, accordée par Monsieur K, vérifiée à chaque usage. État : accordée / augmentée / réduite / révoquée / expirée. | id, enabled, scope, limits, version, reason, accordant, horodatage, durée |

### 1.2 Hiérarchie de composition

```
Monsieur K (unique accordant)
  └─ Gouvernance / Core (unique arbitre, registre, vérificateur, journal)
       ├─ Skill (déclaration, sans effet)
       │    └─ requiert → Permission(s) + Scope(s)
       ├─ Plugin (paquet versionné : skills + tools + manifeste + preuves)
       │    └─ fournit → Tool(s) borné(s)
       └─ Tool (effet) ← invoqué UNIQUEMENT par Exécution contrôlée
            └─ si et seulement si Capability active (permission accordée + scope couvert + limites tenues + non expirée)
```

### 1.3 Chaîne d'autorité (rappel P5 → P7)

```
P5 Cognitive Core : NEED_ACTION / NEED_TOOL = intention DÉCLARATIVE, zéro exécution (inchangé)
  → Décision P7 (future) : skill candidat + permissions requises + scope demandé
  → Gouvernance : vérifie registre + scope + limites + risque + journal
  → Monsieur K : accorde / refuse / réduit (seul)
  → Exécution contrôlée (future, P7.0-B et au-delà) : invoque Tool borné + journalise effet
```

Aucune flèche ne court-circuite la Gouvernance. Aucun skill/plugin ne parle au Tool sans elle.

### 1.4 Registres (séparation stricte)

- **Registre P6 existant (intact, non modifié)** : `INTERNET_RESEARCH, SOURCE_ACCESS,
  DOCUMENT_DOWNLOAD, DOCUMENT_PERSIST, KNOWLEDGE_WRITE, KNOWLEDGE_UPDATE,
  CROSS_DOCUMENT_ANALYSIS, NOTIFY_COMPLETION` — savoir et persistance connaissance.
- **Registre P7 futur (conception seule, vide, tout `disabled`)** : espace de noms distinct
  `P7.*` (ex. conceptuel : lecture fichier locale bornée, écriture bornée réversible,
  exécution bornée, notification locale — liste fermée à figer en P7.0-B, non figée ici).
- Règle : aucun id P7 ne recouvre un id P6. Aucune vérification P7 ne se substitue
  à une vérification P6. Un besoin croisé exige les deux accords.

## 2. Modèle de permissions évolutives contrôlées par Monsieur K

### 2.1 États et transitions autorisées

États : `UNKNOWN` (non déclaré) → `DECLARED_DISABLED` (naissance) ⇄
`GRANTED` (accordée, bornée) → `AUGMENTED` / `REDUCED` (ré-accords) →
`REVOKED` / `EXPIRED` (fins). `DENIED` = refus d'une demande (sans changer l'état sauf journal).

Transitions (seul Monsieur K déclenche les passages à effet) :

```
DECLARED_DISABLED --accord(Monsieur K)--> GRANTED
GRANTED --augmentation(Monsieur K, nouvel accord)--> AUGMENTED (= GRANTED avec scope/limites élargis, version+1)
GRANTED/AUGMENTED --réduction(Monsieur K)--> REDUCED (= GRANTED avec scope/limites restreints, version+1)
GRANTED/AUGMENTED/REDUCED --révocation(Monsieur K)--> REVOKED (enabled=False, version+1)
GRANTED/AUGMENTED/REDUCED --échéance(durée)--> EXPIRED (enabled=False, version+1, motif=expiry)
DENIED : toute demande sans accord reste sans effet + journalisée
```

Interdits : auto-augmentation par l'extension ; augmentation implicite par usage répété ;
héritage de permission entre plugins ; délégation d'accord ; accord par contenu documentaire
(attaque déjà couverte en P6 : réaffirmée pour P7) ; accord par défaut à l'installation.

### 2.2 Cycle de vie d'une demande

1. **Déclaration.** Le plugin/skill déclare ses permissions requises + scopes minimaux
   demandés + limites proposées + réversibilité. Sans déclaration, pas de demande.
2. **Demande.** La Décision formule `demande = {permission_id, scope demandé, limites, durée, motif, contexte P5}`.
   Une demande = un périmètre. Pas de demande groupée « tout autoriser ».
3. **Arbitrage Core.** Vérifie : id connu, scope bien formé (§4), limites quantifiées,
   niveau de risque (§3), compatibilité P6 (§9), absence de contournement sandbox (§6).
   Avis technique seul, jamais un accord.
4. **Accord / refus de Monsieur K.** Explicite, daté, motivé. Peut être partiel (= réduction
   immédiate du scope demandé). Silence = refus.
5. **Usage vérifié.** À chaque invocation future : `check(id, target)` + contrôle scope couvre
   la cible + limites tenues + non expirée + journal. Échec = `DENY` + erreur explicite, zéro effet.
6. **Évolution.** Augmentation = nouvelle demande + nouvel accord (version+1).
   Réduction = à l'initiative de Monsieur K à tout moment, sans préavis, sans justification
   technique requise (motif journalisé). Révocation = effet immédiat, purge des capabilities
   dérivées, retrait d'ordonnancement des tools concernés.
7. **Clôture.** Expiration automatique à échéance. Révocation manuelle possible à tout moment.
   Journal conservé. Ré-accord exige un nouveau cycle complet.

### 2.3 Garanties du modèle

- Version incrémentée à chaque changement (`version+1`, `reason` obligatoire).
- Journal : `timestamp, action (demand/grant/deny/augment/reduce/revoke/expire/check),
  permission_id, scope, limits, decision, reason, demandeur, accordant=Monsieur K`.
- Aucun contenu utilisateur ou secret dans le journal (politique P4 reconduite).
- Révocation = coupe-circuit : les exécutions en attente du périmètre révoqué ne démarrent pas ;
  les exécutions en cours relèvent du traitement P7.0-B (interruption bornée — non conçu ici, noté en réserve).

## 3. Hiérarchie des risques et niveaux d'autorisation

### 3.1 Échelle de risque (conception, 5 niveaux)

| Niveau | Classe d'effet | Principe d'autorisation | Durée indicative maximale (à valider P7.0-B) |
|---|---|---|---|
| **R0 — Nul** | Pur déclaratif, lecture de catalogue, aide. Zéro effet externe, zéro persistance. | Sans permission à effet ; déclaration suffit. Journal d'usage simple. | N/A |
| **R1 — Faible** | Lecture locale bornée, sans secret, sans réseau, sans persistance. | Accord Monsieur K, scope chemin borné, read-only. | Courte, renouvelable |
| **R2 — Modéré** | Écriture locale réversible dans jail, notification locale, persistance non sensible. | Accord explicite + scope + limites quantifiées + preuve de réversibilité. | Courte, un périmètre à la fois |
| **R3 — Élevé** | Réseau sortant, téléchargement, envoi, exécution bornée, effet observable externe. | Accord explicite restreint + whitelist/bornes + double vérification (permission P7 + permission P6 si savoir concerné). | Très courte, un acte / une cible |
| **R4 — Critique** | Irréversible, système, secrets/credentials, désactivation sécurité/journal, exfiltration potentielle, persistance sensible. | **Refus par défaut renforcé.** Accord uniquement étroit, motivé, horodaté, à usage unique envisagé. Toute augmentation R→R4 = nouvelle demande complète. | Usage unique / expiry immédiate |

### 3.2 Règles de mapping

- Chaque Tool déclare son niveau max (R0–R4). Sous-déclaration = défaut de conception bloquant.
- Chaque permission P7 porte un plafond de risque. Un scope ne peut abaisser le niveau d'un Tool.
- Élévation de niveau (ex. R1→R2, R2→R3) = augmentation au sens §2, donc nouvel accord.
- R4 ne peut jamais être accordé par lot, par défaut, ou par héritage. Aucune permission R4
  n'existe en P7.0-A (registre vide).
- En cas de doute : classer au niveau supérieur + `CLARIFY/REFUSE` par défaut (cohérent P5).

## 4. Scopes précis des permissions

### 4.1 Grammaire conceptuelle (sans code)

Un scope = triplet `ressource : périmètre : limites`, bien formé, fermé, vérifiable :

- **ressource** : classe d'objet (ex. conceptuel : fichier, dossier-jail, réseau-domaine, notification, journal).
- **périmètre** : désignation exacte et étroite (chemin jail absolu, domaine allowlisté, canal local nommé).
  Jamais de joker global (`*`), jamais de racine système, jamais de secret.
- **limites** : quantifiées et contrôlables (taille max, cardinalité, fenêtre temporelle,
  fréquence, timeout, réversibilité oui/non + procédure).

Exemples de forme (illustratifs, non activés, non implémentés) :
`fichier : jail/<nom>/… : lecture-seule, ≤ N octets, ≤ M fichiers/acte` ;
`réseau : domaine-allowlisté-exact : lecture-seule, timeout borné, sans credential` ;
`notification : canal-local : texte ≤ N caractères, sans contenu sensible`.

### 4.2 Règles de validité d'un scope

1. Clos : énumère ce qui est permis, tout le reste est interdit.
2. Minimal : le plus étroit permettant l'acte demandé. Tout élargissement = augmentation.
3. Vérifiable : le Core peut décider `cible ∈ scope ?` par comparaison exacte, sans interprétation.
4. Borné : toute dimension mesurable a un plafond chiffré.
5. Temporel : durée explicite + expiry automatique.
6. Sans secret : aucun credential, token, clé dans scope, demande ou journal.
7. Sans chevauchement ambigu : en cas de chevauchement, le plus restrictif gagne + clarification exigée.
8. Traçable : scope + version + motif journalisés à chaque accord et chaque contrôle.

## 5. Confiance, intégrité et provenance des extensions

1. **Provenance exigée.** Chaque plugin déclare : auteur/source, version exacte, canal
   d'obtention local, historique. Source inconnue = non chargeable (principe futur).
2. **Intégrité.** Manifeste + empreinte d'intégrité + pinning de version. Toute divergence
   manifeste/contenu = refus de chargement futur + journal. Aucune auto-mise-à-jour silencieuse.
3. **Chaîne fermée.** Dépendances limitées au stdlib existant (aucune nouvelle dépendance —
   contrainte P7.0-A reconduite pour l'implémentation). Dépendance externe = défaut bloquant.
4. **Déclaration honnête.** Permissions requises, scopes minimaux, niveau de risque max,
   effets, réversibilité, tests. Sous-déclaration ou effet caché = retrait de confiance
   (révocation + bannissement de version).
5. **Activation ≠ confiance.** L'installation ne confère aucun droit. L'activation ne confère
   aucun droit à effet. Seul l'accord Monsieur K confère une capability bornée.
6. **Retrait propre (X-03).** Désactivation = révocation des capabilities + purge ordonnancement
   + vérification d'absence de résidu (persistance, tâche planifiée, hook). Retrait testé
   avant toute réadmission.
7. **Aucune exécution à la confiance.** Même un plugin « de confiance » passe par
   vérification permission+scope+limites à chaque acte. La confiance réduit le soupçon,
   jamais les contrôles.

## 6. Sandbox et frontières de sécurité

Frontière = ce que l'extension ne peut ni voir, ni toucher, ni contourner :

1. **Aucun import d'autorité.** Extensions sans accès direct à : shell/subprocess, réseau brut,
   SQLite P6, SessionContext P4, Cognitive Core P5, registre de permissions, journal, secrets/`.env`.
   Vérification future par audit statique d'imports (comme P4/P5), à instrumenter en P7.0-B.
2. **Jail filesystem.** Si un accès fichier est un jour accordé (R1/R2) : racine jail dédiée,
   aucun `..`, aucun lien symbolique sortant, aucune racine système, lecture/écriture selon scope.
3. **Réseau fermé par défaut.** `DENY` total sauf permission R3 + cible allowlistée exacte.
   Aucun credential transmis. Aucun serveur à l'écoute ouvert par une extension.
4. **Bornes d'exécution.** Timeout, taille entrée/sortie, cardinalité, profondeur, pas de récursion
   non bornée, pas de tâche de fond persistante sans permission dédiée et révocable.
5. **Isolement mémoire.** Contexte session/cognition fourni par copie (philosophie P5 : deepcopy
   normative) — jamais de référence mutable vers le Core. Pas d'écriture inter-moteur sans contrat.
6. **Journal inviolable par extensions.** Écriture réservée au Core. Les extensions ne lisent
   pas le journal de sécurité, ne le purgent pas, ne le désactivent pas (toute tentative = R4).
7. **Arrêt d'urgence.** Monsieur K peut révoquer tout / couper toute exécution future d'un périmètre
   avec effet immédiat sur les démarrages. Interruption des actes en cours : non conçue ici (réserve P7.0-B).

## 7. Menaces initiales et surfaces d'attaque (P7.0-A, sans test)

| # | Menace / surface | Vecteur | Garde-fou de conception |
|---|---|---|---|
| M1 | Injection (prompt/document) → demande de permission déguisée | Contenu P6/texte/STT futur | Contenu jamais accordant ; seul Monsieur K accorde ; demandes typées du Core seul |
| M2 | Confused deputy : skill bénigne invoquée pour acte malveillant | Cible ambiguë, scope large | Scope clos exact + vérification cible∈scope à chaque acte + niveau supérieur en doute |
| M3 | Escalade par élargissement silencieux | Scope joker, héritage, lot | Joker interdit ; héritage interdit ; un périmètre par accord ; version+motif obligatoires |
| M4 | Supply chain : plugin altéré / dépendance piégée | Manifeste divergent, dep externe | Empreinte + pinning + stdlib-only + refus sur divergence |
| M5 | Exfiltration via tool R3 / canal caché | Réseau, notification, journal | R3 ultra-borné + allowlist exacte + sans secret + journal sans contenu utilisateur |
| M6 | Persistance furtive | Tâche planifiée, hook, fichier résiduel | Retrait propre vérifié ; pas de fond sans permission dédiée ; audit résidus |
| M7 | Contournement journal / effacement traces | Accès journal, désactivation | Journal réservé Core ; tentative = R4 ; pas de journal = pas d'accord |
| M8 | Épuisement / DoS local | Boucle, volume, fork | Bornes quantifiées + timeout + cardinalité + expiry |
| M9 | Contournement P6 via P7 (et inverse) | Lecture savoir sans whitelist, écriture effet sans permission P7 | Double accord croisé (§9) ; aucun pont implicite |
| M10 | Usurpation de Monsieur K | Fausse instruction « Monsieur K a dit » | Accord hors-bande explicite seul ; contenu déclaratif jamais probant ; phrase/rituel d'accord à définir en P7.0-B sans biométrie (cohérent P4 : Monsieur K = paramètre d'interaction) |

## 8. Souveraineté du Core de Wilfrid

1. Le Core = wake + session + cognition + gouvernance + exécution-contrôlée (future).
   Il est le seul à : déclarer les demandes, vérifier les permissions, invoquer les tools,
   écrire le journal, révoquer.
2. Aucune extension ne peut : modifier le Core, désactiver une vérification, élever ses droits,
   lire/écrire la mémoire P4/P5 par référence, toucher au seuil/modèle wake (0.665),
   toucher au registre P6, créer une permission.
3. `NEED_ACTION` (P5) reste déclaratif. P7 ne lui confère aucune exécution implicite.
4. En conflit : le Core gagne toujours — refus + journal + erreur explicite.
5. Toute évolution du Core suit `METHODOLOGIE.md` (audit → diagnostic → patch minimal →
   post-audit → test → validation). Les extensions ne sont jamais un vecteur de patch Core.

## 9. Frontière stricte P6 Knowledge & Research ↔ P7 Exécution

| Axe | P6 (savoir — existant, intact) | P7 (agir — conçu ici, non implémenté) |
|---|---|---|
| Finalité | Lire, acquérir, vérifier, synthétiser, citer | Produire un effet borné, journalisé, réversible |
| Permissions | 8 ids P6, refus défaut, `enable/revoke` explicites | Espace `P7.*` distinct, registre vide en P7.0-A |
| Whitelist / store / jobs | P6 seuls, inchangés | P7 ne lit/écrit le store P6 que via permission P6 accordée + permission P7 si effet ; jamais d'accès direct |
| Réseau | `INTERNET_RESEARCH/SOURCE_ACCESS/DOCUMENT_DOWNLOAD` + whitelist exacte | Tout effet réseau = R3 P7 + accord P7 en plus de l'accord P6 |
| Journal | `accesslog` P6 (champs techniques) | Journal P7 distinct (actes/effets), même politique : sans contenu utilisateur ni secret |
| Contenu hostile | Parsers/markup/poisoning déjà couverts P6 | Réaffirmé : contenu P6 ne peut ni accorder P7 ni élargir un scope P7 |
| Non-régression | P6 200/200 (hypothèse d'entrée) | P7 ne doit ni dégrader P6 ni exiger sa modification ; tout besoin de changement P6 = hors P7.0-A, à traiter comme révision P6 dédiée |

Règle de pont : tout acte « savoir + effet » (ex. : télécharger puis notifier) exige
l'accord P6 couvrant le savoir **et** l'accord P7 couvrant l'effet, chacun avec son scope.
L'absence d'un des deux = `DENY` total, zéro effet partiel.

## 10. Interdits P7.0-A (rappel de conformité)

- Aucun fichier `core/` ou `tests/` créé ou modifié par P7.0-A (cet artefact vit en `docs/` seul).
- Aucun `enable()`, aucune activation, aucun chargement, aucune exécution.
- Aucun appel réseau/API, aucune mesure, aucun micro, aucun TTS/STT.
- Aucune dépendance ajoutée ou modifiée (`requirements.txt` intact).
- Aucune anticipation de P7.1 ni de P7.0-B au-delà des critères d'entrée (§13).

## 11. Architecture proposée (résumé opposable)

Un Core souverain (gouvernance + registres disjoints P6/P7 + journal inviolable + sandbox)
arbitre des intentions déclaratives P5 transformées en demandes typées ; Monsieur K,
unique accordant, délivre des capabilities bornées (permission + scope clos + limites +
durée, versionnées et journalisées) ; une future Exécution contrôlée invoque des Tools
bornés et classés R0–R4, un périmètre par accord, révocables à tout moment avec retrait
propre ; P6 reste le seul canal du savoir, intact et non contourné.

## 12. Décisions de conception P7.0-A

1. Vocabulaire à 5 termes figé : Skill / Plugin / Capability / Tool / Permission (§1).
2. Registres disjoints : P6 intact, `P7.*` vide et tout-`disabled` à la naissance.
3. Modèle évolutif à 4 opérations : accord / augmentation / réduction / révocation (+ expiry),
   toutes versionnées, motivées, journalisées, à l'initiative de Monsieur K pour tout effet.
4. Échelle de risque R0–R4 avec mapping autorisation + durées indicatives + surclassement en doute.
5. Scope clos `ressource:périmètre:limites`, joker global interdit, vérification exacte `cible∈scope`.
6. Confiance ≠ autorisation : provenance + intégrité + pinning + stdlib-only + retrait propre,
   mais vérification à chaque acte même pour plugin « de confiance ».
7. Sandbox par déni : aucun import d'autorité, jail FS, réseau fermé, journal réservé Core,
   copies (pas de références) vers extensions.
8. Frontière P6/P7 par double accord pour tout acte mixte ; contenu jamais accordant.
9. Souveraineté Core absolue : extensions invitées, bornées, révocables ; `NEED_ACTION` sans exécution implicite.

## 13. Réserves P7.0-A

- R-A1 : inventaire exact des ids `P7.*` non figé (volontairement — relève de P7.0-B).
- R-A2 : durées maximales par niveau (§3) indicatives, à calibrer en P7.0-B.
- R-A3 : rituel d'accord explicite de Monsieur K (formulation, canal, horodatage, preuve)
  non défini — à concevoir en P7.0-B sans biométrie ni mémoire implicite (contrainte P4).
- R-A4 : interruption des actes en cours lors de révocation non conçue (seul le non-démarrage est garanti ici).
- R-A5 : format exact du journal P7 et sa rotation non fixés (politique P4 reconduite par principe).
- R-A6 : P6.0–P6.6 pris comme hypothèse d'entrée sur déclaration du commanditaire ;
  non ré-audités dans P7.0-A. Toute divergence constatée en P7.0-B rouvre un diagnostic P6 dédié.

## 14. Critères d'entrée de P7.0-B (ne pas traiter P7.0-B ici)

P7.0-B ne peut commencer que si, cumulativement :

1. Le présent artefact P7.0-A est accepté par Monsieur K sans modification cachée.
2. P6 intact vérifiable (aucun diff `core/knowledge/`, `tests/test_knowledge_*`,
   `requirements.txt`, seuil wake 0.665) — simple constat lecture-seule, pas de ré-implémentation.
3. Liste fermée des ids `P7.*` + plafonds de risque + grammaire de scope validés sur papier.
4. Rituel d'accord Monsieur K défini (format, preuve, journalisation, révocation d'urgence).
5. Harnais de vérification statique (imports interdits, sandbox, double-accord P6/P7)
   spécifié avant tout code, avec jeux de refus par défaut exigés.
6. Engagement : première implémentation P7.0-B sans R3/R4, sans réseau, sans persistance
   sensible, avec retrait propre démontré.

*Fin P7.0-A / PARTIE A — conception seule, aucune capacité conférée.*

---

# WILFRID — P7.0-A / PARTIE B — COMPLÉMENT DE CONCEPTION (sans code)

> Statut : `DESIGNED` — complément de P7.0-A, conception seule.
> Contraintes reconduites : aucun code applicatif, aucune modification P6,
> aucun skill/plugin/tool/action réel, aucune permission activée, aucun réseau/API,
> aucune dépendance, pas de lancement P7.1, pas de fonctionnalité métier, pas de POST-AUDIT.
> La Partie A (§0–§14) est inchangée et reste normative. La Partie B (§15–§26) la complète.
> En cas de conflit, la règle la plus restrictive gagne.

## 15. Cycle de vie Skill / Plugin / Capability / Tool

### 15.1 Skill (déclaration, sans effet)

États : `PROPOSÉ → DÉCLARÉ → VÉRIFIÉ → APPROUVÉ / REFUSÉ → ACTIF / SUSPENDU → RETIRÉ`.
`REFUSÉ` et `RETIRÉ` sont terminaux pour cette version (nouvelle version = nouveau cycle).

- `PROPOSÉ` : fiche déclarative reçue (nom, version, kinds P5, permissions requises,
  entrées/sorties typées, préconditions, niveau de risque max déclaré, tests exigés).
- `DÉCLARÉ` : fiche complète et bien formée, sans droit conféré.
- `VÉRIFIÉ` : contrôles statiques de conception réussis (§21) : complétude, risque plausible,
  scopes minimaux proposés, absence d'effet caché déclaré.
- `APPROUVÉ` : Monsieur K a approuvé la fiche sur avis technique du Core. N'ouvre aucun droit
  d'exécution par elle-même.
- `ACTIF` : skill adressable par la Décision pour formuler des demandes typées (§17).
  Activité = droit de demander, jamais droit d'agir.
- `SUSPENDU` : adressabilité gelée (doute, incident, demande de réexamen). Les capabilities
  déjà accordées à ses tools sont gelées au démarrage (non-démarrage garanti) ; interruption
  des actes en cours : voir réserve R-B4.
- `RETIRÉ` : fin définitive de version (retrait propre §16). Toute demande issue du skill
  devient `DENY` systématique.

Règle : un skill ne change jamais d'état de lui-même. Seuls Core (vérification technique)
et Monsieur K (approbation/suspension/retrait) font avancer le cycle, avec journal.

### 15.2 Plugin (paquet livrable, unité de confiance)

États : `RÉCEPTIONNÉ → MANIFESTE_VÉRIFIÉ → INTÉGRITÉ_VÉRIFIÉE → APPROUVÉ / REFUSÉ → INSTALLÉ → ACTIVÉ / SUSPENDU → RÉVOQUÉ → RETIRÉ (résidu-vérifié)`.

- `RÉCEPTIONNÉ` : paquet local uniquement (aucun téléchargement en P7.0-A). Provenance déclarée.
- `MANIFESTE_VÉRIFIÉ` : manifeste complet (id, version pin, liste skills/tools, permissions
  requises, scopes minimaux, dépendances déclarées stdlib-only, empreinte annoncée).
- `INTÉGRITÉ_VÉRIFIÉE` : empreinte conforme au manifeste, version pinnée, divergence = refus.
- `APPROUVÉ` : accord Monsieur K pour installation. Installation ≠ droit à effet.
- `INSTALLÉ` : paquet présent, inerte, non adressable. Aucune exécution.
- `ACTIVÉ` : skills adressables + tools invocables uniquement via §17. Aucun droit implicite.
- `SUSPENDU` : gel adressabilité + gel démarrages. Diagnostic avant toute réactivation.
- `RÉVOQUÉ` : capabilities purgées, ordonnancement purgé, retour à l'inertie.
- `RETIRÉ` : paquet désinstallé + preuve d'absence de résidu (persistance, tâche, hook).
  Réadmission = nouveau cycle complet, jamais de réactivation directe depuis `RETIRÉ`.

### 15.3 Capability (droit borné, dérivé d'un accord)

États : `DEMANDÉE → CONTRÔLÉE → ACCORDÉE / REFUSÉE → ACTIVE → RÉDUITE / AUGMENTÉE (ré-accords) → EXPIRÉE / RÉVOQUÉE → CLÔTURÉE`.

- Une capability = `permission_id + scope clos + limites + durée + version d'accord + motif`.
  Elle n'existe qu'adossée à un accord Monsieur K valide, non expiré, non révoqué.
- `AUGMENTÉE` / `RÉDUITE` = nouvelle version d'accord (§2 Partie A), jamais une mutation silencieuse.
- `EXPIRÉE` : passage automatique à échéance, sans intervention. `RÉVOQUÉE` : à tout moment
  par Monsieur K. Les deux interdisent tout nouveau démarrage ; `CLÔTURÉE` = archivage journalier.
- Zéro capability en P7.0-A (registre vide, aucun accord sollicité ni délivré).

### 15.4 Tool futur (effet borné, jamais direct)

États : `DÉCLARÉ → CLASSÉ(R0–R4) → VÉRIFIÉ → HOMOLOGUÉ / REFUSÉ → INVOCABLE (si capability active) → GELÉ → RETIRÉ`.

- `CLASSÉ` : niveau max R0–R4 déclaré par fiche + plafond confirmé par Core. Sous-déclaration = refus.
- `HOMOLOGUÉ` : Monsieur K a homologué la fiche tool (bornes, réversibilité, schéma E/S).
  Homologation ≠ autorisation d'acte : chaque acte exige une capability active couvrant la cible.
- `INVOCABLE` : état conditionnel et révocable à chaque appel (capability active + scope couvre
  cible + limites tenues + non expiré). Sinon `DENY`, zéro effet.
- `GELÉ / RETIRÉ` : suit suspension/révocation/retrait du plugin parent + purge ordonnancement.

## 16. Processus en 7 étapes (installation → retrait)

Ordre strict, sans saut, sans regroupement. Échec à une étape = arrêt + `DENY` + journal,
sans passage à la suivante.

1. **Installation (inerte).** Dépôt local du paquet, sans exécution, sans droit.
   Contrôle : provenance déclarée, paquet complet. Sortie : `INSTALLÉ` ou refus.
2. **Vérification technique (Core, avis seul).** Complétude manifeste, intégrité vs empreinte,
   dépendances stdlib-only, permissions requises connues, scopes bien formés (§4 Partie A),
   niveau de risque plausible, absence d'import d'autorité déclaré, réversibilité documentée.
   Sortie : dossier `VÉRIFIÉ` + avis motivé (favorable / favorable-sous-réduction / défavorable).
   Le Core n'approuve jamais.
3. **Approbation (Monsieur K, seul décidant).** Sur dossier vérifié uniquement.
   Réponses possibles : approuver / approuver-en-réduit (scope/limites resserrés d'office) /
   refuser (motif journalisé). Silence = refus. Sortie : `APPROUVÉ` ou `REFUSÉ`.
   L'approbation d'installation n'est pas un accord de permission à effet.
4. **Activation (adressabilité sans droit d'effet).** Le skill devient adressable pour demander ;
   le tool devient homologué-invocable-sous-condition. Contrôle : approbation valide +
   versions pinnées inchangées. Aucune capability créée ici.
5. **Suspension (gel réversible).** Déclenchée par Monsieur K (doute, incident, réexamen)
   ou proposée par Core (anomalie) et décidée par Monsieur K. Effet : gel adressabilité +
   gel démarrages + journal. Les actes en cours relèvent de R-B4. Réactivation = nouvelle
   décision explicite, jamais automatique.
6. **Révocation (purge des droits).** Décidée par Monsieur K à tout moment, sans préavis.
   Effet : capabilities du périmètre → `RÉVOQUÉE`, ordonnancement purgé, démarrages interdits,
   journal. Irréversible pour la version d'accord concernée (ré-accord = nouveau cycle §2).
7. **Retrait (désinstallation propre, X-03).** Révocation préalable obligatoire, puis :
   désinstallation paquet + vérification d'absence de résidu (persistance, tâche planifiée,
   hook, fichier hors jail) + journal de retrait. Sans preuve de retrait propre, le retrait
   est réputé incomplet et bloque toute réadmission du même id.

## 17. Modèle d'appel (intention → exécution future)

Chaîne normative à 6 maillons. Chaque maillon peut répondre `DENY` / `CLARIFY` / `REFUSE`,
auquel cas zéro effet et journal. Aucun court-circuit.

1. **Intention (P5, déclarative).** Sortie cognitive existante : `kind ∈ {… NEED_TOOL, NEED_ACTION …}`,
   `payload`, `confidence`, `missing[]`. Aucune exécution, aucune permission inférée.
   Si `UNCERTAIN/CLARIFY/REFUSE` : arrêt ici.
2. **Demande typée (Décision future, sans autorité).** Forme fermée :
   `demandeur (skill id + version), permission_id P7.* connu, scope demandé clos,
   limites quantifiées, cible exacte, durée demandée, motif, contexte P5 (copie, jamais référence),
   double-accord P6 si savoir concerné`. Une demande = un périmètre + une cible.
   Demande mal formée = `DENY` technique.
3. **Contrôle Core (vérification, jamais accord).** Ordre fixe :
   a) permission connue et non-R4-par-lot ; b) scope bien formé et minimal ;
   c) `cible ∈ scope` par comparaison exacte ; d) limites tenues et chiffrées ;
   e) risque R0–R4 tenu + plafond permission respecté ; f) sandbox (pas de contournement) ;
   g) double-accord P6 si mixte ; h) capability non expirée/non révoquée/suspension levée.
   Sortie : avis `CONFORME (transmis à Monsieur K)` ou `NON_CONFORME (DENY + motif)`.
4. **Accord (Monsieur K, seul).** Accorde / réduit-d'office / refuse. Accord = création ou
   nouvelle version de capability bornée + journal. Refus = `DENY` + journal, sans création.
   En P7.0-A : aucun accord sollicité ni délivré (registre vide).
5. **Ordonnancement conditionnel (futur).** L'acte conforme + accordé est mis en file bornée
   (un acte = une capability active). Vérification répétée juste-avant-invocation
   (anti-évolution entre accord et acte : expiry/révocation/suspension entre-temps = `DENY`).
6. **Exécution future + preuve (futur, non conçue ici).** Invocation du Tool par la seule
   Exécution contrôlée, dans sandbox + bornes, avec journal d'effet. Preuve = entrée typée +
   décision d'accord + contrôle pré-acte + résultat borné + effet journalisé. Toute anomalie =
   erreur explicite + gel du périmètre en attente de décision Monsieur K.

## 18. Refus, expirations, erreurs, interruptions

- **Refus.** Sources : demande mal formée, avis Core `NON_CONFORME`, refus Monsieur K,
  silence (= refus), capability absente/expirée/révoquée, suspension, doute (surclassement R).
  Effet : zéro effet, réponse explicite `DENY + motif + ce-qui-manque`, journal sans contenu
  sensible. Un refus n'ouvre jamais un droit partiel. Réessai = nouvelle demande complète.
- **Expirations.** Toute capability porte une durée. À échéance : `EXPIRÉE` automatique,
  démarrages interdits, ordonnancement purgé pour ce périmètre, journal `expire`.
  Renouvellement = nouvelle demande + nouvel accord, jamais de prolongation implicite.
- **Erreurs.** Typologie fermée : `DEMANDE_INVALIDE, SCOPE_NON_COUvrant, LIMITES_DÉPASSÉES,
  PERMISSION_INCONNUE/DÉSACTIVÉE, CAPABILITY_EXPIRÉE/RÉVOQUÉE, DOUBLE_ACCORD_MANQUANT,
  SANDBOX_VIOLATION, TOOL_NON_HOMOLOGUÉ, JOURNAL_INDISPONIBLE`.
  `JOURNAL_INDISPONIBLE` = `DENY` systématique (pas d'acte non journalisable).
  Toute erreur = zéro effet partiel + message explicite + journal technique.
- **Interruptions.** Garanti en P7.0-A : aucun acte d'un périmètre révoqué/suspendu/expiré ne
  démarre. Non conçu ici (réserve R-B4 reconduite) : interruption d'un acte déjà en cours,
  compensation d'effet partiel, procédure de rollback. En attendant leur conception,
  la règle d'engagement P7.0-B reste : premiers actes uniquement R0–R2 réversibles,
  bornés et sans R3/R4, pour que le non-démarrage suffise comme garde-fou.

## 19. Journalisation et traçabilité des décisions

- **Deux journaux disjoints.** `accesslog` P6 (savoir, existant, intact) et futur journal P7
  (actes/effets). Aucune fusion, aucune lecture par extensions, écriture réservée au Core.
- **Événements P7 à journaliser (conception).** `propose, declare, verify (avis),
  approve/refuse, install, activate, demand, control-conforme/non-conforme,
  grant/deny, augment/reduce, suspend/reactivate, revoke, expire, pre-act-check,
  invoke-futur, effect-futur, error, withdraw (+ preuve-retrait-propre)`.
- **Champs par événement.** `timestamp, event, actor (core / Monsieur K / système-échéance),
  skill/plugin/tool id+version, permission_id, scope, limits, decision, reason,
  capability-version, cible (forme technique, sans contenu sensible), risque R0–R4`.
- **Politique contenu.** Reconduction P4 : aucun contenu utilisateur, aucun secret, aucune clé
  dans les journaux. Cible = désignation technique (ex. chemin jail, domaine exact),
  jamais le contenu lu/écrit/notifié.
- **Chaînage et rotation.** Principe : append-only, rotation bornée (philosophie 64 Ko/1 rotation
  P4 reconduite comme principe, calibrage exact réservé), purge interdite aux extensions,
  tentative de désactivation = R4. `JOURNAL_INDISPONIBLE` bloque tout acte.
- **Traçabilité de bout en bout.** Toute exécution future doit pouvoir citer :
  intention P5 → demande typée → avis Core → accord Monsieur K (version) → contrôle pré-acte →
  effet. Chaînon manquant = acte réputé non autorisé a posteriori (constat d'audit futur).

## 20. Contrats entre Core, extensions et futurs Tools

- **C1 — Adressage unique.** Extensions → Core uniquement. Jamais extension → tool,
  extension → session/cognition/mémoire/store/journal/registre, tool → extension.
  Tout besoin croisé passe par demande typée + double-accord.
- **C2 — Typage strict.** Entrées/sorties déclarées et bornées (taille, cardinalité, profondeur).
  Entrée hors schéma = `DENY`. Sortie hors schéma = erreur + gel périmètre.
- **C3 — Données par copie.** Contexte session/cognition transmis par copie indépendante
  (philosophie deepcopy P5). Aucune référence mutable vers Core/Session/P6-store.
- **C4 — Effets déclarés et réversibles d'abord.** Tout Tool déclare effets + bornes + timeout +
  réversibilité + procédure. Effet non déclaré = défaut bloquant + retrait de confiance.
- **C5 — Vérification à chaque acte.** Homologation et confiance ne dispensent jamais du
  contrôle pré-acte (§17-3 + §17-5). Même plugin « de confiance ».
- **C6 — Erreurs explicites.** Codes fermés §18, sans fuite de secret ni de contenu.
  Erreur Core = `DENY` + gel démarrages du périmètre jusqu'à décision Monsieur K.
- **C7 — Non-préemption.** Extensions ne modifient ni Core, ni registres, ni journaux,
  ni seuil/modèle wake, ni whitelist/store/jobs P6. Toute tentative = R4 + suspension.
- **C8 — Versionnage.** Tout contrat (skill fiche, plugin manifeste, tool fiche, scope,
  capability) est versionné. Changement = nouvelle version + nouvel avis + nouvel accord
  si élargissement. Aucune mutation silencieuse.

## 21. Stratégie de tests statiques et dynamiques (avant toute implémentation — plan seul)

Aucun test exécuté en P7.0-A. Ce § définit le plan exigible avant tout code P7.1,
sans créer ni lancer aucun test.

### 21.1 Statiques (sans exécution, à instrumenter en premier)

- **S1 imports d'autorité** : tout import direct/indirect vers shell/subprocess, réseau brut,
  SQLite P6, SessionContext, Cognitive Core, registre, journal, secrets/`.env` = FAIL.
  Référence méthode : revues statiques P4/P5 reconduites.
- **S2 manifeste vs contenu** : divergence (skills/tools/effets/risque/dépendances) = FAIL.
- **S3 scopes** : joker global, racine système, secret, périmètre non clos, limites non
  chiffrées, durée absente = FAIL.
- **S4 risque** : tool sans niveau R0–R4, sous-déclaration manifeste, R4 en lot = FAIL.
- **S5 pont P6/P7** : lecture savoir sans permission P6, effet sans permission P7,
  substitution d'une vérification par l'autre = FAIL.
- **S6 journal** : événement non journalisable, champ secret/contenu-utilisateur, écriture
  journal par extension = FAIL.

### 21.2 Dynamiques (environnement confiné futur, sans réseau, sans R3/R4 d'abord)

- **D1 refus par défaut** : sans accord, toute demande = `DENY`, zéro effet constaté.
- **D2 un-périmètre-par-accord** : accord étroit n'autorise ni cible voisine ni second acte.
- **D3 cible ∉ scope** : `DENY` systématique, même à un caractère près.
- **D4 limites** : dépassement taille/cardinalité/timeout = erreur + zéro effet partiel.
- **D5 expiry/révocation/suspension** : post-échéance et post-révocation = non-démarrage prouvé ;
  file purgée.
- **D6 retrait propre** : après retrait, audit résidus (persistance/tâche/hook/fichier) = vide.
- **D7 double-accord mixte** : acte savoir+effet sans l'un des deux accords = `DENY` total.
- **D8 journal** : chaque décision retrouve sa chaîne intention→demande→avis→accord→pré-acte ;
  `JOURNAL_INDISPONIBLE` simulé = `DENY` total.
- **D9 hostile** : jeux d'injection (demande déguisée en contenu), scope ambigu, usurpation
  « Monsieur K a dit » = `DENY` systématique (sans exécution réelle d'effet).

Exigence transversale : chaque test dynamique prouve `zéro effet` en cas de `DENY`
(vérification d'état avant/après), et chaque `ALLOW` futur n'est admis qu'avec preuve
de traçabilité complète §19.

## 22. Critères précis de passage P7.0-A → P7.1 (P7.1 non lancé, non conçu)

P7.1 ne peut être envisagé que si, cumulativement (tout manquement = `FAIL` d'entrée) :

1. **Artefact accepté.** `docs/P7_0_A_DESIGN.md` (Parties A+B) accepté par Monsieur K,
   sans modification cachée, statut `DESIGNED` maintenu.
2. **P6 intact.** Constat lecture-seule : aucun diff `core/knowledge/`, `tests/test_knowledge_*`,
   `requirements.txt`, seuil wake 0.665, modèle inchangé. Toute divergence = diagnostic P6
   dédié avant tout P7.1.
3. **Registre vide prouvé.** Aucune permission P7 activée, aucune capability existante,
   aucun plugin installé/activé (constat, pas d'action).
4. **Fiches fermées sur papier.** Liste fermée ids `P7.*` initiaux (R0–R2 seuls pour P7.1),
   plafonds de risque, grammaire scope, codes d'erreur §18, champs journal §19 — validés
   sans code.
5. **Rituel Monsieur K défini.** Format d'accord/refus/réduction/révocation, preuve,
   horodatage, révocation d'urgence — défini sans biométrie ni mémoire implicite (contrainte P4).
6. **Plan de tests opposable.** S1–S6 + D1–D9 spécifiés avec verdicts `PASS/FAIL` exacts et
   preuve `zéro effet` en `DENY`. Aucun R3/R4, aucun réseau, aucune persistance sensible en P7.1.
7. **Engagement de périmètre P7.1.** Premiers actes uniquement R0–R2 réversibles, bornés,
   retrait propre démontrable ; interruption en-cours et rollback restent hors P7.1
   (réserve assumée) — compensés par l'exclusion R3/R4.
8. **Méthodologie.** P7.1 suivra `METHODOLOGIE.md` (audit → diagnostic → patch minimal →
   post-audit → test → validation). Tout écart bloque la suite.

## 23. Décisions de conception (Partie B, ajoutées à §12)

10. Cycles de vie disjoints à états explicites pour Skill/Plugin/Capability/Tool (§15) ;
    `REFUSÉ/RETIRÉ` terminaux par version ; aucune auto-transition.
11. Pipeline en 7 étapes sans saut : installation → vérification → approbation →
    activation → suspension → révocation → retrait, avec retrait propre vérifié obligatoire.
12. Modèle d'appel en 6 maillons sans court-circuit : intention → demande typée →
    contrôle Core → accord Monsieur K → ordonnancement conditionnel → exécution future + preuve ;
    revérification pré-acte obligatoire.
13. Politique d'échec fermée : refus/expiry/erreur = zéro effet + motif + journal ;
    `JOURNAL_INDISPONIBLE` = `DENY` total ; codes d'erreur fermés §18.
14. Journal P7 disjoint de P6, append-only, réservé Core, sans contenu utilisateur ni secret,
    chaîne intention→effet reconstituable, chaînon manquant = acte non autorisé.
15. Contrats C1–C8 (adressage, typage, copie, effets déclarés, vérification à chaque acte,
    erreurs explicites, non-préemption, versionnage).
16. Plan de tests S1–S6 (statiques) + D1–D9 (dynamiques confinés, R0–R2 d'abord) avec preuve
    `zéro effet` en `DENY` ; aucun test exécuté en P7.0-A.
17. Passage P7.0-A → P7.1 conditionné aux 8 critères §22 ; R3/R4, réseau et persistance
    sensible exclus de P7.1.

## 24. Réserves (Partie B — s'ajoutent à R-A1–R-A6)

- R-B1 : inventaire `P7.*` toujours non figé (requis §22-4 avant P7.1).
- R-B2 : durées maximales et calibrages journal/rotation non fixés.
- R-B3 : rituel d'accord Monsieur K toujours non défini (requis §22-5).
- R-B4 : interruption d'acte en cours + compensation/rollback non conçues ; couvertes
  provisoirement par exclusion R3/R4 en P7.1 + garantie non-démarrage.
- R-B5 : ordonnanceur borné et préemption non conçus (relèvent de l'implémentation future,
  sous contraintes §17-5 et bornes §6 Partie A).
- R-B6 : P6 toujours hypothèse d'entrée non ré-auditée ; toute divergence future rouvre
  un diagnostic P6 dédié, jamais un patch P6 via P7.

## 25. Fichiers modifiés

- `docs/P7_0_A_DESIGN.md` seul : ajout Partie B (§15–§26), Partie A (§0–§14) inchangée.
- Aucun fichier `core/`, `tests/`, `requirements.txt`, `.env`, modèle ou seuil modifié.
- Aucun fichier créé en complément (un seul artefact évolutif, pas de second fichier).

## 26. Verdict d'entrée vers P7.1

Statut P7.0-A (A+B) : `DESIGNED` — complet sur papier, aucune capacité conférée,
aucune permission activée, aucun acte exécuté. Passage vers P7.1 : `NON AUTORISÉ À CE STADE`
jusqu'à satisfaction cumulative des 8 critères §22, acceptation explicite de Monsieur K,
et constat P6 intact + registre P7 vide. P7.1 n'est ni lancé ni conçu ici. Prochaine étape
relevante si verdict levé : cadrage P7.1 sous `METHODOLOGIE.md`, périmètre R0–R2 réversibles
d'abord, sans réseau, sans R3/R4, avec harnais S1–S6 + D1–D9.

*Fin P7.0-A / PARTIE B — conception seule, aucune capacité conférée.*
