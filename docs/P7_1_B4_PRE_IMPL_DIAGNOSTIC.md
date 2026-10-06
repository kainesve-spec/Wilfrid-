# WILFRID — P7.1 / B4 — DIAGNOSTIC TECHNIQUE PRÉ-IMPLÉMENTATION (lecture seule)

> Statut : diagnostic uniquement. Contexte opposable : P7.0-A ACCEPTÉ, B2 VALIDÉ
> (4 IDs), B3 DÉCIDÉ v1 2026-10-06, jail `~/Wilfrid/JAIL/P7`, notifications
> `~/Wilfrid/JAIL/P7/notifications/`. P7.1 NON implémenté, registre P7 vide,
> aucune permission active, aucun répertoire P7 créé, aucun fichier modifié par B4.
> L'exécution de la commande B4 ne vaut pas autorisation d'implémenter.

## 1. ARCHITECTURE EXISTANTE (constatée, sans exécution)
- Core / contrôle central : ABSENT pour P7 (aucun `core/p7/`, aucun gouverneur).
  Patterns réutilisables : `SessionManager` (session unique, transitions fermées),
  `JobManager` (transitions contrôlées, `JobError`), `Cognitive decider/planner`
  (purs, bornés, `NEED_ACTION` déclaratif, garde-fou effect-free).
- Permissions : `core/knowledge/permissions.py` (refus défaut, `enable/revoke/check`,
  version+1, journal) réutilisable comme PATTERN uniquement — registre P6
  interdit pour effets P7 (séparation stricte, double-accord si mixte).
- Journalisation : `AccessLog` (JSONL 64 Ko/1 rotation, champs techniques,
  `target/reason` ≤256, best-effort) + `SessionJournal` (même forme, OFF défaut).
  Forme réutilisable, sémantique à inverser pour P7 (voir §8–§9).
- Validation/revalidation : `decide()` (cohérence, bornes), `build_plan()` (abstrait),
  `JobManager.transition()` (chaîne fermée) comme patterns ; revalidation pré-acte
  P7 MANQUANTE (à créer : revérifier capability juste-avant-effet).
- Erreurs : `JobError`, `ParseError`, `permission.check → (False, motif)` comme
  patterns (codes fermés, zéro effet partiel).
- Sessions/durée/expiration : `Session` (monotonic, timeout 60 s défaut, horloge
  injectable, `expired()`) réutilisable comme pattern de durée/expiry.
- Isolation fichiers / chemins / symlinks / backup / notif : MANQUANTS. Aucun
  helper jail, aucune canonisation dédiée, aucun backup/restore, aucune notif locale
  P7. Stdlib `pathlib` disponible (sans nouvelle dépendance) mais non assemblée.

## 2. P7 — ÉTAT RÉEL
- `core/p7*` : absent (glob 0). Registre P7 : absent (`grep P7/Capability` dans
  `core/` = 0). Permissions P7 actives : 0. Artefacts P7 : `docs/P7_0_A_DESIGN.md`
  + `docs/P7_1_B3_APPROVAL.md` uniquement. État conforme P7.0-A : design accepté,
  zéro activation implicite, zéro exécution.

## 3. P6 / P5 — SÉPARATION FUTURE
- P6 (`store/jobs/whitelist/accesslog`, 8 ids) : ne doit être ni lu ni écrit par P7
  sans accord P6 dédié ; aucun import P7 vers `store/jobs` hors double-accord.
- P5 (`NEED_ACTION/NEED_TOOL` déclaratifs, contexte volatil `SessionContext`
  20 tours/8 Ko, jamais sérialisé) : intentions consommées par COPIE uniquement,
  jamais par référence ; `SessionContext` non transférable tel quel.
- Données sensibles / `.env` : jamais dans scopes, demandes, journaux ; `core/actions/media.py`
  (`webbrowser.open`, `os.startfile`) explicitement HORS P7.1 (vecteur réseau/exécution).

## 4. CAPACITÉ PAR CAPACITÉ (sans élargir B2)
- P7.CATALOG_READ (R0) : réutilisable = types/patterns bornés P5 ; manquant = vue
  catalogue déclarative + journal d'usage. Risque : fuite par description trop
  bavarde. Contrôles : schéma fermé, ≤50/8 Ko, 0 effet, séance ≤60 min. Faisable sans élargir.
- P7.JAIL_READ (R1) : réutilisable = `check()` + bornes P5 + expiry session ;
  manquants = résolveur jail (§5) + lecteur borné (5 fichiers, 256 Ko, 64 Ko/fichier,
  profondeur ≤3, timeout 5 s). Risques : traversal, symlink, voisin, TOCTOU.
  Contrôles : pré-checks totaux avant tout open + revalidation. Faisable sans élargir.
- P7.JAIL_WRITE_REVERSIBLE (R2) : réutilisable = transitions fermées + erreurs
  explicites ; manquants = backup obligatoire + écriture atomique (temp+rename)
  + vérification restauration + interdiction overwrite-sans-restore (§6).
  Risque : effet partiel irréversible. Faisable uniquement avec §6 complet.
- P7.NOTIFY_LOCAL (R2) : réutilisable = `AccessLog.record` (forme) ; manquants =
  écrivain notif borné (280 c, 1/demande, timeout 3 s, filtre sensible, single-use
  ≤5 min) cantonné à `notifications/` (§7). Risque : exfiltration/persistance.
  Faisable sans élargir si filtres + confinement stricts.

## 5. JAIL `~/Wilfrid/JAIL/P7` — frontière conceptuelle sans création
Possible sans créer le répertoire : frontière = règle lexicale + vérifications
pré-acte, pas présence FS. Exiger : racine exacte B3 ; cible déclarée exacte ;
normalisation lexicale (refus `..`, segment vide, préfixe `~/` non résolu côté
extension) ; refus chemin absolu hors racine et chemin voisin (égalité exacte,
pas de préfixe implicite) ; `lstat` sans suivi (symlink = DENY, y compris symlink
interne sortant) ; revalidation entre contrôle et usage (anti-swap) ; profondeur
≤3 et tailles §B2 ; deny-list secrets (`.env`, clés, `core/`, `models/`, journaux,
registres) ; tout doute = DENY. Sans ces contrôles, la frontière serait nominale.

## 6. WRITE REVERSIBLE — garanties à implémenter (manquantes)
Exiger dans l'ordre, zéro effet si un point échoue : 1 fichier/acte ; taille
constatée ≤64 Ko avant écriture ; backup préalable obligatoire (copie intacte du
préexistant ou marqueur création) ; écriture via fichier temporaire même
répertoire + rename atomique ; vérification post-écriture (taille/contenu borné) ;
procédure de restauration testée (restore ou suppression de la création) ;
interdiction overwrite-sans-restore et suppression irréversible ; toute
précondition fausse = DENY avant tout octet écrit. Composant backup/restore
actuellement ABSENT : condition d'implémentation.

## 7. NOTIFY_LOCAL `~/Wilfrid/JAIL/P7/notifications/` — sans créer
Imposer : 1 fichier/cible exacte dans ce dossier, nom borné server-side (pas de
nom fourni par l'extension hors suffixe sûr) ; ≤280 caractères, 1/demande,
timeout ≤3 s ; filtre contenu sensible/secret (refus si motif de fuite) ;
aucun réseau (interdiction `socket/webbrowser/subprocess` dans le chemin P7) ;
aucune persistance hors périmètre (pas de copie ailleurs, pas de tâche) ;
durée ≤5 min single-use puis expiry ; pré-checks + revalidation comme §5.
Écrivain notif ABSENT : condition d'implémentation.

## 8. FAIL-CLOSED — garanties techniques
- DENY par défaut : `check()` pattern (`unknown/disabled → (False, motif)`),
  registre P7 naissant vide et tout-`disabled`.
- Journal indisponible ⇒ DENY TOTAL : INVERSION requise du best-effort actuel
  (`AccessLog`/`SessionJournal` n'échouent jamais l'appelant) vers échec dur
  côté P7 (impossibilité de prouver = interdiction d'agir).
- Cible hors scope ⇒ DENY + zéro effet : contrôle avant tout accès FS, aucune
  lecture anticipée, aucun `open` avant verdict.
- Limite dépassée ⇒ DENY + zéro effet : tailles/nombre/timeout/profondeur
  vérifiés avant effet, pas de troncation silencieuse.
- Expirée/révoquée/suspendue/sans approbation ⇒ DENY + zéro effet : revalidation
  pré-acte obligatoire (anti-évolution accord→acte).

## 9. JOURNAL — reconstruire intention→preuve
Existant : `AccessLog` (timestamp, action, permission, target≤256, decision,
reason≤256, job_id, config_version) et `SessionJournal` (technique seul).
Manquant P7 : `id-demande`, avis Core, `capability-version`, scope/limites/durée,
résultat pré-check, effet borné, preuve ; durcissement fail-closed (§8) ;
rotation/chemin dédié P7 disjoint de P6 ; garantie sans secret/contenu sensible
(tronquer + deny-list, jamais le contenu lu/écrit/notifié, jamais `.env`).
Chaînon manquant = acte réputé non autorisé.

## 10. TEST PLAN (matrice proposée, NON exécutée)
Par ID : ALLOW nominal exact (1 cible, bornes tenues, capability valide, journal
complet) ; DENY voisin (1 caractère, 2e fichier/acte, profondeur 4, 65e Ko,
281e caractère, canal voisin) ; DENY limites (chaque plafond §B2) ; DENY
expiration (rejouer après 10/5 min / fin séance) ; DENY révocation/suspension ;
DENY journal indisponible simulé ; chaque DENY avec preuve zéro effet
(état FS avant/après identique hors effet ALLOW prouvé). Exclure R3/R4, réseau,
persistance sensible de la campagne P7.1.

## 11. DÉPENDANCES (sans rien installer)
Suffisantes déjà présentes : stdlib (`pathlib, json, time, os` borné) ; patterns
`core/session, core/cognitive, core/knowledge` (lecture de référence seule).
Inutiles à P7.1 : `pypdf, beautifulsoup4, numpy, onnxruntime, sounddevice,
elevenlabs, websockets`. Nouvelle dépendance potentielle : AUCUNE admise ;
tout besoin (`lxml, requests, httpx`, exécuteur, scheduler) = élargissement
interdit et FAIL d'entrée.

## 12. VERDICT : READY WITH CONDITIONS
Conditions fermées (blockers si absentes) : C1 gouverneur P7 + registre vide
tout-disabled + `check` strict ; C2 résolveur jail §5 + revalidation anti-TOCTOU ;
C3 lecteur borné R1 ; C4 écrivain réversible + backup/restore §6 ; C5 écrivain
notif §7 confiné ; C6 journal P7 fail-closed §8–§9 disjoint P6 ; C7 erreurs
fermées + zéro effet partiel ; C8 campagne §10 verte. Aucune condition n'exige
d'élargir B2, d'ajouter une dépendance, de toucher P5/P6, de créer le jail avant
l'implémentation, ni d'activer quoi que ce soit par anticipation.
Étapes d'implémentation (fermées, non exécutées) : 1. gouverneur+registre+erreurs ;
2. journal P7 fail-closed ; 3. résolveur jail + tests DENY voisins ; 4. CATALOG_READ ;
5. JAIL_READ borné ; 6. WRITE_REVERSIBLE + backup/restore ; 7. NOTIFY_LOCAL confiné ;
8. revalidation pré-acte + expiry/révocation ; 9. campagne §10 (ALLOW/DENY/zéro-effet) ;
10. revue séparation P5/P6 + gel `requirements.txt` sans installation.

*Fin B4 — DIAGNOSTIC UNIQUEMENT, aucune implémentation autorisée par ce document.*
