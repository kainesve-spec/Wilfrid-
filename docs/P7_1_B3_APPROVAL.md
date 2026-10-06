# WILFRID — P7.1 / B3 — RITUEL D'APPROBATION EXPLICITE MONSIEUR K

> Statut : `DESIGNED` — documentaire / design uniquement.
> Contraintes : aucun code P7.1, aucune permission active, aucune modification
> `core/` / P6 / registres techniques, aucune dépendance installée, aucun test
> exécuté, aucun réseau ouvert. Références : `docs/P7_0_A_DESIGN.md` (§0–§26),
> résultat B2 (4 IDs R0–R2 proposés), `docs/POST_AUDIT_P6_6.md` (baseline B1 CONSOLIDÉ).
> Le simple fait que la commande de préparation B3 ait été exécutée ne constitue
> en aucun cas une approbation de Monsieur K.

## 1. ACCEPTATION P7.0-A
- État distinct : `P7.0-A ACCEPTÉ PAR MONSIEUR K` ≠ autorisation d'action,
  ≠ accord de permission, ≠ ordre d'implémenter P7.1.
- Attribué exclusivement à Monsieur K, sous forme explicite, datée, versionnée.
- Aucune inférence d'acceptation depuis une action technique (exécution de commande,
  génération de ce document, lecture, test passé, cache pytest) n'est valide.
- Valeur actuelle : `P7.0-A ACCEPTÉ PAR MONSIEUR K = ACCEPTÉ`.
  Version : v1 — Date/heure (UTC) : 2026-10-06 — Décideur : Monsieur K.
  Justification : décision explicite Monsieur K (« P7.0-A : ACCEPTÉ »).

## 2. VALIDATION B2 — fiches de décision individuelles
Décisions explicites de Monsieur K du 2026-10-06 (v1). Aucune ne crée de permission
active ni n'autorise d'exécution (§4).

### P7.CATALOG_READ (R0 — catalogue déclaré, lecture-seule)
- Décision : `VALIDÉ`.
- Borne : ≤50 entrées/requête, ≤8 Ko réponse, 0 effet (proposition B2).
- Durée maximale : séance ≤60 min, sans capability à effet.
- Périmètre exact : `catalogue:déclaré:lecture-seule`.
- Exclusions : fichier, réseau, journal, registre, store P6 direct, secret, toute exécution.
- Justification : décision explicite Monsieur K (« B2 : les 4 capacités VALIDÉES »).
- Version décision : v1 — Date/heure (UTC) : 2026-10-06 — Décideur : Monsieur K.

### P7.JAIL_READ (R1 — lecture locale bornée jail, read-only)
- Décision : `VALIDÉ`.
- Borne : ≤5 fichiers/demande, ≤256 Ko total, ≤64 Ko/fichier, profondeur ≤3, timeout ≤5 s.
- Durée maximale : ≤10 min, 1 demande = 1 périmètre + 1 cible.
- Périmètre exact : `fichier:~/Wilfrid/JAIL/P7/chemin-exact:lecture-seule` (jail root §3).
- Exclusions : écriture, symlink sortant, `..`, secret/`.env`/journal/registre, réseau, hors-jail.
- Justification : décision explicite Monsieur K. — Version : v1 — Date/heure : 2026-10-06 — Décideur : Monsieur K.

### P7.JAIL_WRITE_REVERSIBLE (R2 — écriture locale unique réversible)
- Décision : `VALIDÉ`.
- Borne : ≤1 fichier/acte, ≤64 Ko/acte, sauvegarde préalable + restauration/suppression prouvées, timeout ≤5 s.
- Durée maximale : ≤5 min, usage unique (1 acte puis expiry).
- Périmètre exact : `fichier:~/Wilfrid/JAIL/P7/chemin-exact:écriture-réversible-bornée`.
- Exclusions : écrasement sans restauration, exécutable/setuid, `..`, symlink, hors-jail, secret, persistance sensible, irréversible.
- Justification : décision explicite Monsieur K. — Version : v1 — Date/heure : 2026-10-06 — Décideur : Monsieur K.

### P7.NOTIFY_LOCAL (R2 — notification locale texte seul)
- Décision : `VALIDÉ`.
- Borne : ≤280 caractères, ≤1 notification/demande, timeout ≤3 s, sans contenu sensible ni secret.
- Durée maximale : ≤5 min, usage unique.
- Périmètre exact : `notification:~/Wilfrid/JAIL/P7/notifications/:textuel-borné` (fichier local dédié §3).
- Exclusions : réseau, envoi externe, pièce jointe, persistance, credential, contenu P6 brut.
- Justification : décision explicite Monsieur K. — Version : v1 — Date/heure : 2026-10-06 — Décideur : Monsieur K.

## 3. PARAMÈTRES CHOISIS PAR MONSIEUR K (décision v1 du 2026-10-06)
- Jail root exact : `~/Wilfrid/JAIL/P7` (décision explicite Monsieur K).
- Canal exact de notification locale : fichier local dédié
  `~/Wilfrid/JAIL/P7/notifications/` (décision explicite Monsieur K).
- Répertoires non créés par B3 (document seul ; création éventuelle hors B3,
  sans permission ni exécution conférée).

## 4. RÈGLE FONDAMENTALE
L'acceptation de P7.0-A ou de B2, même si exprimée :
- n'active aucune permission ;
- n'autorise aucune exécution ;
- n'autorise aucun réseau ;
- n'autorise aucun R3/R4 ;
- n'autorise aucun accès aux secrets ;
- n'autorise aucune modification de P6 ;
- n'autorise aucune compétence future non explicitement approuvée fiche par fiche (§2).
Registre P7 reste vide jusqu'à une phase d'implémentation distincte, hors B3.

## 5. PRÉREQUIS FERMÉS AVANT D'AUTORISER L'IMPLÉMENTATION P7.1
1. `P7.0-A ACCEPTÉ PAR MONSIEUR K` explicite, daté, versionné (§1).
2. Les 4 fiches §2 décidées (VALIDÉ ou REFUSÉ explicite ; `EN ATTENTE` = NON AUTORISÉ).
3. `<JAIL_ROOT>` et `<CANAL_LOCAL_EXACT>` fixés si les IDs correspondants sont VALIDÉS.
4. Baseline B1 toujours intacte (SHA `docs/POST_AUDIT_P6_6.md`, seuil 0.665, modèle
   `87eead45…`, `requirements.txt` non modifié hors gel décidé).
5. Séparation P6/P7 vérifiée (seul `docs/P7_0_A_DESIGN.md` + présent document comme
   artefacts P7 ; `grep P7/capability/plugin` dans `core/` = 0).
6. Rituel d'accord par acte (intention → demande typée → contrôle Core → accord
   explicite → portée → durée → révocation ; absence = DENY) rappelé
   `docs/P7_0_A_DESIGN.md` §17–§19, non contourné.
7. Engagement R0–R2 seuls, sans R3/R4, sans réseau, sans persistance sensible,
   avec retrait propre démontrable. Tout manquement = P7.1 NON AUTORISÉ.

## 6. TRAÇABILITÉ
Chaîne reconstructible exigée : proposition B2 → décision Monsieur K (§2, version,
date/heure) → périmètre exact → paramètres §3 → état (VALIDÉ/REFUSÉ/EN ATTENTE).
Journalisation future réservée au Core, sans contenu utilisateur ni secret.
Règle : décision absente, ambiguë, sans version/date, ou expirée = NON AUTORISÉE.
Aucune décision Muse, aucun cache technique, aucune exécution de commande ne se
substitue à la décision Monsieur K.

## 7. ÉTAT FINAL
- Techniquement proposé : périmètre initial P7.1 R0–R2 en 4 IDs avec bornes, durées,
  scopes, exclusions, matrice et testabilité (B2) ; présent rituel d'approbation (B3).
- Décidé par Monsieur K (v1, 2026-10-06) : P7.0-A ACCEPTÉ (§1) ; 4 fiches VALIDÉES (§2) ;
  `~/Wilfrid/JAIL/P7` et `~/Wilfrid/JAIL/P7/notifications/` fixés (§3).
- Explicitement interdit ( inchangé ) : toute exécution, toute permission active, tout réseau,
  tout R3/R4, tout secret, toute modification P6/`core`/registres, toute compétence
  non approuvée, toute inférence d'approbation depuis un acte technique.
- État global : **B3 = DÉCIDÉ PAR MONSIEUR K (acceptation + 4 validations enregistrées)** ;
  P7.1 reste non implémenté et non autorisé à s'exécuter jusqu'à phase d'implémentation
  distincte. Registre P7 toujours vide.

*Fin B3 — document seul, aucune autorisation conférée.*
