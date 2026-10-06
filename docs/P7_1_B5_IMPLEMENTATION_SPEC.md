# WILFRID — P7.1 / B5 — SPÉCIFICATION D'IMPLÉMENTATION (documentaire uniquement)

> Statut : `DESIGNED` — spécification fermée, directement implémentable sans
> interprétation libre. Contexte : P7.0-A ACCEPTÉ, B2 VALIDÉ (4 IDs R0–R2),
> B3 DÉCIDÉ v1 2026-10-06, B4 READY WITH CONDITIONS (C1–C8).
> P7.1 NON implémenté, registre P7 vide, jail inexistant, 0 permission active.
> Contraintes : aucun fichier existant modifié, aucun code/registre/répertoire
> créé, P5/P6 intacts, aucun réseau/processus/test/dépendance/secret.
> La création de ce document ne vaut ni autorisation d'implémenter, ni activation,
> ni création du jail. Vocabulaire gelé P7.0-A respecté, aucun concept élargissant
> B2 sans justification (aucun introduit).

## 1. ARCHITECTURE — composants minimaux
- Gouverneur P7 : resp. ordonnancer la séquence §8, seul invocateur d'effets.
  Entrées : Request typée. Sorties : Effect+Proof ou DENY+motif. Invariants :
  DENY défaut, revalidation pré-acte, zéro court-circuit. Dépendances : registre,
  résolveur, journal, horloge. Interdictions : exécuter sans capability valide.
- Demande typée : voir contrat Request §2. Autorisation : voir Approval §2.
- Registre : table vide à la naissance, tout-`disabled`, `check→(bool,motif)`,
  `version+1` par changement, jamais lu/écrit par extensions.
- Résolveur/sandbox jail : resp. canoniser et clore `cible ∈ scope` (§4).
  Entrées : scope + cible déclarée. Sorties : chemin confiné ou DENY.
  Invariants : aucune touche FS avant verdict, `lstat` sans suivi.
  Interdictions : suivre un symlink, résoudre hors racine.
- Contrôle scope / limites : comparaisons exactes + plafonds B2, avant effet.
- Sessions/expiration : monotonic injectable, timeouts R0≤60min/R1≤10min/R2≤5min,
  expiry auto = DENY, jamais de prolongation implicite.
- Backup/restore : copie préalable obligatoire (R2 écriture), restauration
  vérifiable, suppression de création possible ; ABSENT avant implémentation.
- Écrivain borné : 1 fichier/acte, ≤64 Ko, temp+rename, timeout 5 s.
- Notification locale : 1 texte ≤280 c vers `notifications/`, timeout 3 s, single-use.
- Journal P7 : append-only disjoint P6, hard-fail (§7). Fail-closed : §10.

## 2. CONTRATS (vocabulaire P7.0-A)
- Skill : fiche {id, version, kinds, permissions requises, E/S typées, risque max,
  tests exigés} ; sans effet ; états §9.
- Plugin : paquet {id, version pin, skills/tools, manifeste, empreinte, deps
  stdlib-only} ; inerte une fois installé ; états §9.
- Capability : {permission_id, scope clos, limites, durée, version d'accord, motif,
  demandeur, accordant=Monsieur K} ; n'existe que si accord valide non expiré/révoqué.
- Tool : fiche {nom, E/S typées bornées, effets déclarés, bornes, timeout,
  réversibilité+procédure, niveau R0–R2} ; invocable uniquement par gouverneur.
- Permission : {id `P7.*`, enabled, scope, limits, version, reason, accordant,
  horodatage, durée} ; naissance `disabled`.
- Request : {id-demande unique, skill id+version, permission_id connu, scope demandé
  clos, cible exacte, limites, durée demandée, motif, copie P5, double-accord P6 si
  mixte} ; 1 périmètre + 1 cible ; mal formée = DENY.
- Approval : {id-demande, décision (accorde/réduit/refuse), scope accordé exact,
  durée, motif, version capability, horodatage, décideur=Monsieur K} ; silence = refus.
- Effect : {id-demande, capability-version, cible confinée, octets bornés, résultat
  borné} ; uniquement après pré-check vert.
- Proof : {intention P5, demande, avis Core, approval, pré-check, effet, vérification} ;
  chaînon manquant = non autorisé.
- Journal event : {timestamp, event, actor, ids+versions, permission_id, scope, limits,
  decision, reason, capability-version, cible technique, risque} ; sans contenu ni secret.

## 3. QUATRE CAPACITÉS VALIDÉES (exact B2/B3)
- P7.CATALOG_READ, R0, `catalogue:déclaré:lecture-seule`, ≤50 entrées/≤8 Ko/0 effet,
  séance ≤60 min sans capability. Préconditions : skill adressable. Pré-check :
  schéma + séance valide. Effet : réponse déclarative. Preuve : E/S bornées.
  Journal obligatoire. DENY : hors schéma, séance expirée, journal indisponible.
  Zéro-effet : aucun état modifié.
- P7.JAIL_READ, R1, `fichier:~/Wilfrid/JAIL/P7/chemin-exact:lecture-seule`,
  ≤5 fichiers/≤256 Ko total/≤64 Ko/fichier/profondeur ≤3/timeout 5 s, ≤10 min,
  non single-use mais 1 périmètre+1 cible par demande. Pré-check §4+§8. Effet :
  copie bornée. Preuve : octets + bornes. DENY : §10. Zéro-effet : aucun open avant verdict.
- P7.JAIL_WRITE_REVERSIBLE, R2, `fichier:~/Wilfrid/JAIL/P7/chemin-exact:
  écriture-réversible-bornée`, ≤1 fichier/≤64 Ko/timeout 5 s, ≤5 min single-use
  (1 acte puis expiry). Préconditions : backup possible, restauration prouvable.
  Pré-check : tous contrôles + backup prêt. Effet : temp+rename. Preuve : post-vérif
  + preuve restauration. DENY : §10 + backup impossible. Zéro-effet si pré-échec.
- P7.NOTIFY_LOCAL, R2, `notification:~/Wilfrid/JAIL/P7/notifications/:
  textuel-borné`, ≤280 c/1 par demande/timeout 3 s, ≤5 min single-use.
  Pré-check : canal exact, filtres sensible/secret. Effet : 1 fichier/entrée bornée.
  Preuve : taille/canal. DENY : §10. Zéro-effet : aucune écriture avant verdict.

## 4. JAIL (`~/Wilfrid/JAIL/P7`, NON créé)
Résolution : racine exacte B3 ; cible = chemin relatif déclaré joint lexicalement,
normalisé sans toucher FS puis vérifié : rejet si `..`, segment vide, absolu entrant,
`~`, `*`, `//`, encodage ambigu ; égalité exacte avec périmètre ; `lstat` (jamais
`stat` suiveur) : symlink = DENY même interne ; revalidation entre contrôle et usage ;
voisin (préfixe partiel, casse, extension ajoutée) = DENY ; profondeur ≤3 (relatif),
fichiers ≤ bornes, taille ≤ bornes ; deny-list : `.env`, secrets, `core/`, `models/`,
journaux, registres, store P6, hors-racine. Si jail inexistant : tout acte R1/R2 =
`CIBLE_INEXISTANTE` DENY (seul CATALOG_READ reste évaluable). TOCTOU : double
`lstat` + open `O_NOFOLLOW` (ou équivalent sans suivi) + vérification post-open
(chemin réel toujours sous racine), sinon DENY.

## 5. WRITE REVERSIBLE (précis)
Max 1 fichier/action, ≤64 Ko constatés avant écriture. Backup obligatoire : copie
préexistante sous `<cible>.bak.<capability-version>` même répertoire (ou marqueur
`CREATED` si absent), vérifiée lisible. Vérification avant : scope+cible+limites+
durée+capability+journal disponible. Écriture : temp `<cible>.tmp.<id-demande>`
borné puis rename atomique. Restauration : procédure `restore-or-delete-creation`
testable, preuve (hash/taille avant-après + statut restore). Interdits : suppression
irréversible, overwrite-sans-restore, append non borné, exécutable/setuid, 2e fichier,
2e acte même capability single-use. Échec avant écriture : DENY, FS inchangé, backup
nettoyé si créé vide. Échec après écriture : erreur + gel périmètre + journal, restore
tenté et journalisé. Journal indisponible : DENY avant tout, zéro octet écrit.

## 6. NOTIFY_LOCAL (`~/Wilfrid/JAIL/P7/notifications/`, NON créé)
Format : 1 entrée texte UTF-8 ≤280 caractères dans 1 fichier du dossier, nom borné
côté gouverneur (pas de nom arbitraire extension). ≤280 c, 1/demande, timeout ≤3 s,
durée ≤5 min single-use. Contenu interdit : secrets/credentials, `.env`, données
sensibles P6/P5 brutes, URLs réseau, pièces jointes, binaire. Aucun réseau, aucune
destination externe, aucune écriture hors canal (dossier exact). Échec/filtre positif/
journal indisponible = DENY + zéro fichier.

## 7. JOURNAL P7 (append-only, disjoint P6)
Chaîne : intention → demande → approbation → périmètre → pré-check → décision →
effet → preuve. Schéma minimal : §2 Journal event + `id-demande` corrélation +
`capability-version` + verdicts pré/post. Événements : propose, declare, verify,
approve/refuse, demand, control-conforme/non-conforme, grant/deny, suspend/
revoke/expire, pre-check, effect, proof, error, withdraw. Champs obligatoires :
timestamp, event, actor, ids+versions, permission/scope/limits, decision, reason,
cible technique (≤256, jamais contenu), risque. Secrets/contenus interdits
(troncature + deny-list). Intégrité : append-only, rotation bornée dédiée, lecture
interdite aux extensions, purge = R4. Indisponible : **JOURNAL_UNAVAILABLE =
DENY TOTAL + ZERO EFFECT** (avant et après effet).

## 8. GOUVERNEUR — séquence exacte
`request → typing (schéma) → approval lookup (capability valide ?) → scope check
(cible∈scope exacte) → expiry check (durée/suspension/révocation) → limits check
(plafonds B2) → target check (résolveur §4, lstat, voisin, secret) → journal
pre-event (dur = échec si indisponible) → effect (borné, timeout) → verification
(bornes post + restauration prouvable si R2) → proof → journal post-event.`
Toute erreur ferme l'opération (pas de poursuite partielle). Cas : absence
d'approbation = DENY ; expirée = DENY ; révoquée/suspendue = DENY ; mauvais scope/
type = DENY ; limite dépassée = DENY ; journal indisponible = DENY TOTAL ;
cible inexistante = DENY (sauf CATALOG) ; ambiguë = DENY + clarification ;
interne = erreur + gel périmètre + journal.

## 9. LIFECYCLE
`PROPOSÉ→DÉCLARÉ→VÉRIFIÉ→APPROUVÉ/REFUSÉ→INSTALLÉ(inert)→ACTIVÉ→SUSPENDU→
RÉVOQUÉ→RETIRÉ(résidu-vérifié)`, capability `DEMANDÉE→CONTRÔLÉE→ACCORDÉE/
REFUSÉE→ACTIVE→EXPIRÉE/RÉVOQUÉE→CLÔTURÉE`. Terminaux : `REFUSÉ/RETIRÉ`
(par version ; réadmission = nouveau cycle). Aucune transition auto (expiry =
automatique mais constatée + journalisée, jamais une autorisation).

## 10. FAIL-CLOSED ET ZERO EFFECT (par point)
Chaque ligne : condition → DENY + raison + event + preuve FS inchangé
(comparaison avant/après) : journal indisponible → DENY TOTAL ; hors scope →
`SCOPE_NON_COUvrant` ; permission absente/désactivée → `PERMISSION_INCONNUE/
DÉSACTIVÉE` ; expirée/révoquée/suspendue → `CAPABILITY_EXPIRÉE/RÉVOQUÉE` ;
taille/nombre/profondeur/durée dépassées → `LIMITES_DÉPASSÉES` ; 2e fichier/acte →
DENY (single-use + 1/demande) ; notif >280 c → DENY ; `..`/symlink/voisin/secret →
`SANDBOX_VIOLATION` ; tool non homologué/demande invalide/double-accord manquant →
DENY. Preuve zéro-effet : aucun `open`/`write` avant verdict + état FS identique.

## 11. TEST PLAN (matrice future, NON exécutée)
Chaque test : ID, précondition, requête, résultat attendu, preuve attendue :
- ALLOW : T-ALLOW-{CATALOG,JREAD,JWRITE,NOTIFY} nominaux exacts → ALLOW + preuve §3.
- DENY : T-DENY-{VOISIN,HORS-SCOPE,TYPE} → DENY + zéro effet.
- Limites : T-LIM-{NFILES,SIZE,DEPTH,TIMEOUT,280C,SECOND-FILE,ACTION} → DENY.
- Expiration : T-EXP-{R0,R1,R2} rejoué après délai → DENY.
- Révocation/suspension : T-REV après ordre → non-démarrage + file purgée.
- Journal : T-JOURNAL-DOWN simulé → DENY TOTAL.
- Jail : T-JAIL-{DOTDOT,SYMLINK,ABSOLU,VOISIN,SECRET,ENV} → `SANDBOX_VIOLATION`.
- Restore : T-RESTORE-{CREATE,OVERWRITE} → preuve restauration/suppression.
- Notif : T-NOTIFY-{280C,SECOND,SECRET,RESEAU,HORS-CANAL}.
- Isolation : T-ISO-{P6-STORE,P6-JOURNAL,P5-REF,MEDIA-WEBBROWSER} → DENY/absence import.
- Zéro-effet : chaque DENY avec diff FS avant/après vide.

## 12. PÉRIMÈTRE INTERDIT (réaffirmé)
Réseau, téléchargement, API externe, shell, subprocess, exec/eval, secrets,
credentials, système/root, écriture hors jail, suppression irréversible, tâches
persistantes, scheduler, listeners, serveur entrant, R3, R4, accès direct
store/journal/jobs/whitelist P6, toute modification P6/P5, toute autorité
d'exécution non validée fiche par fiche, toute dépendance nouvelle.

## 13. PLAN D'IMPLÉMENTATION FUTUR (ordonné, NON exécuté)
1. `core/p7/governor.py`+`registry.py`+`errors.py` : check strict, versions, DENY
   défaut. Contrôles : revue imports. Tests : T-DENY de base. Acceptation : registre
   vide tout-disabled, DENY sans accord.
2. `core/p7/journal.py` : append-only fail-closed disjoint P6. Tests : T-JOURNAL-DOWN.
   Acceptation : indisponible = DENY TOTAL.
3. `core/p7/resolver.py` : §4 + anti-TOCTOU. Tests : T-JAIL-*. Acceptation : 0 escape.
4. `core/p7/catalog.py` (CATALOG_READ) : déclaratif borné. Tests : T-ALLOW-CATALOG.
5. `core/p7/reader.py` (JAIL_READ) : lecteur borné. Tests : T-ALLOW-JREAD + T-LIM.
6. `core/p7/backup.py`+`writer.py` (JAIL_WRITE) : §5 + restore. Tests : T-RESTORE.
7. `core/p7/notify.py` (NOTIFY_LOCAL) : §6 confiné. Tests : T-NOTIFY-*.
8. Expiry/révocation/suspension + revalidation pré-acte. Tests : T-EXP/T-REV.
9. Campagne §11 complète + preuves zéro-effet. Acceptation : tout vert, 0 élargissement.
10. Revue isolation P5/P6 + gel dépendances (sans installation). Acceptation : `grep`
    autorité = 0, SHAs P6 inchangés, `requirements.txt` non modifié hors gel décidé.
    Aucune étape n'ajoute R3/R4, réseau, secret, persistance sensible ou 5e ID.

## 14. CRITÈRES DE SORTIE P7.1
Implémenté : §13 livré sans élargissement. Testé : §11 tout PASS + zéro-effet prouvé.
Fail-closed : §10 + journal-down = DENY TOTAL. Isolé : 0 import d'autorité, P5 par
copie, P6 intact (SHAs), jail jamais quitté. Traçable : chaîne §7 complète par acte.
Réversible : restore R2 prouvé. Conforme : 4 IDs B2 exacts (bornes/durées/scopes).
Sans extension : aucun ID/effet/dépendance au-delà B2/B3.

**VERDICT FINAL : B5 = SPEC READY**

*Fin B5 — spécification seule, ni autorisation d'implémenter, ni permission, ni jail.*
