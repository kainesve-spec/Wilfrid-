# WILFRID — P7.2 / R3 NET READ ALLOWLISTED — SPÉCIFICATION (documentaire)

> STATUS : **SUPERSEDÉE — HISTORIQUE.** Remplacée pour sa logique de durée par
> `docs/P7_2_MISSION_MODEL_SPEC.md` (missions longue durée, READY FOR REVIEW).
> Conservée sans autre modification comme historique (révision P7.2 du 2026-10-06 :
> retrait de la borne ≤10 min, non validée comme règle fondamentale).
> Statut d'origine : PROPOSÉ — EN ATTENTE D'APPROBATION DE MONSIEUR K.
> Contexte : P7.1 PASS, post-audit PASS, documentation PASS, 279/279,
> registre ACTIVE=0/DECLARED=0, diagnostic P7.2 DESIGN READY FOR REVIEW,
> orientation R3 réseau validée par Monsieur K, R4 interdit, R3 EXEC hors périmètre.
> Contraintes : aucun `core/p7/` modifié, aucune capability/permission créée ou
> activée, registre intact, aucun réseau ouvert ou testé, aucune dépendance,
> P5/P6 et 4 capabilities P7.1 intacts. Ne modifie pas les documents P7.1.

## 1. Identité provisoire
- ID candidat : `P7.NET_READ_ALLOWLISTED` — PROPOSÉ / NON VALIDÉ / NON IMPLÉMENTÉ,
  absent du registre. Classe R3. Nature : lecture HTTP(S) sortante, sans écriture
  externe, sans exécution, sans persistance implicite.

## 2. Scope (grammaire fermée `RESSOURCE:PÉRIMÈTRE:LIMITES`)
- RESSOURCE = `reseau`. PÉRIMÈTRE = destination exacte
  `https://<hostname-exact>[:<port>][/chemin-exact]` (représentation canonique :
  schéma minuscule imposé `https`, hostname minuscule punycode, port explicite
  ou défaut 443, chemin sensible à la casse, sans userinfo, sans fragment,
  sans whitespace). Interdits : wildcard, suffixe implicite, IP littérale,
  localhost, RFC1918/loopback/link-local/multicast, metadata endpoints,
  destination non déclarée, changement de destination par redirect, proxy non
  déclaré. Aucune interprétation implicite : tout écart lexical = DENY.

## 3. Allowlist (modèle seul, aucun domaine réel choisi)
- Structure : liste versionnée `{version, entries[]}` ; entrée =
  `{id, hostname exact, port, protocole=https, chemin-préfixe exact optionnel,
  pin-TLS optionnel (SPKI), expires_at}` ; identité unique = `id` stable.
- Expiration par entrée + version globale incrémentée à tout changement.
  Ajout/retrait d'un domaine réel = décision explicite ultérieure de Monsieur K
  (demande + motif + version). Sans entrée correspondante exacte : DENY.

## 4. DNS / SSRF
- Résolution au moment de l'acte (pas de cache inter-actes) ; toutes les adresses
  A/AAAA du résultat doivent être globales-unicast publiques, sinon DENY
  (anti-rebinding : revalidation post-résolution ; si l'ensemble change entre
  deux résolutions rapprochées : DENY). Interdits : RFC1918, loopback, link-local,
  multicast, adresses réservées, metadata endpoints (169.254.169.254, fd00::/8
  réservés cloud, etc.). Revalidation avant connexion. Ambiguïté = DENY.

## 5. Redirections
- Défaut : tout 3xx = DENY (`redirect = DENY`), corps ignoré et écarté.
  Exception future uniquement par homologation explicite (même origine :
  même schéma + même hostname + même port, compteur ≤ plafond, jamais vers
  privé/metadata/non-allowlisté). Jamais de suivi automatique.

## 6. HTTP
- Méthode : GET uniquement (HEAD/POST/PUT/PATCH/DELETE/CONNECT/OPTIONS/TRACE
  interdites). User-Agent fixe minimal déclaré (ex. `Wilfrid-P7/1.0`, valeur à
  figer). Headers autorisés : `Accept` borné, `Accept-Encoding: identity`
  (pas de compression négociée, voir §15), `User-Agent` fixe. Interdits :
  `Authorization`, `Cookie`, `Proxy-*`, credentials/userinfo dans l'URL,
  secrets dans URL/headers, cookies persistants (jar désactivé).

## 7. Limites quantitatives (strictes, justifiées au minimum nécessaire)
- Timeout total ≤10 s, connexion ≤5 s (lecture documentaire petite ; borne basse
  anti-lenteur). Réponse ≤1 Mo, headers ≤16 Ko, URL ≤512 caractères
  (anti-géant/anti-bombe). Redirects suivis : 0 par défaut. Requêtes : 1/acte,
  single-use, autorisation ≤10 min. Mémoire de traitement ≤2× taille max
  (≤2 Mo). Justification unique : toute valeur supérieure augmente SSRF/
  exfiltration/bombe sans besoin P7.2 démontré.

## 8. Contenu récupéré — CONTENU RÉSEAU ≠ AUTORISATION
- Contenu = donnée non fiable : ne modifie jamais le registre, n'accorde rien,
  n'élargit aucun scope, ne déclenche ni R3 ni R4, jamais traité comme
  instruction de gouvernance. Protections : prompt injection (contenu jamais
  concaténé à une intention/décision sans marquage + double-accord si usage P6),
  HTML hostile neutralisé (pas de rendu, pas de suivi de liens/URLs secondaires
  vers non-allowlisté), fausse instruction système ignorée, fichiers déguisés
  refusés (pas de sniffing-acte : type déclaré + taille + stockage §9 seuls).

## 9. Stockage
- Par défaut : uniquement jail validé via capability d'écriture distincte
  (le présent READ ne stocke rien lui-même) ; si stockage direct jugé nécessaire :
  écriture réversible bornée (≤64 Ko comme P7.1 ou plafond §7 le plus bas),
  jamais hors jail, jamais de secret, jamais implicite. Le téléchargement
  persistant est une capability distincte et N'EST PAS inclus ici.

## 10. Gouverneur
`typed request → identification capability → classification R3 → approval
Monsieur K → version/scope/allowlist check → expiry check → limits check →
DNS/SSRF check → TLS check → journal pre-event → GET unique → contrôle réponse
(taille/statut/type) → vérification → preuve → journal post-event.`
Étape manquante = DENY + ZERO EFFECT ; journal indisponible = DENY TOTAL.

## 11. Approbation par acte
`{request_id, capability_id, version allowlist, cible exacte, scope exact,
limites, expiration, motif, confirmation explicite Monsieur K}`.
Absence = DENY. Domaine A ≠ domaine B (aucune transitivité, aucun wildcard).

## 12. Journal (métadonnées seules, fail-closed)
Jamais : corps de réponse, credentials, cookies, `Authorization`, secrets.
Toujours : request_id, capability, version allowlist, cible, timestamp, décision,
taille, statut HTTP, preuve (hash), erreur éventuelle (motif technique borné).

## 13. Transport
HTTPS obligatoire : validation chaîne complète, vérification hostname,
pas de désactivation TLS ni d'exception silencieuse (pin optionnel §3).
HTTP clair = DENY par défaut (exception uniquement par homologation explicite,
jamais automatique).

## 14. P5 / P6
Intention P5 par copie, données P6 par double-accord ; ni P5 ni P6 ni le contenu
réseau ne valent autorisation. Aucun accès direct au store P6 hors mécanisme
homologué.

## 15. Risques
SSRF/BLOQUANT (allowlist+DNS §4) ; rebinding/BLOQUANT ; redirect bypass/À TRAITER
(défaut DENY) ; credential leakage/BLOQUANT (interdiction §6) ; prompt
injection/À TRAITER (marquage+double-accord) ; exfiltration/À TRAITER (GET seul,
pas d'upload, bornes) ; réponse géante/lente/ACCEPTABLE-contrôlé (§7) ;
TLS malformé/À TRAITER (validation stricte) ; HTML hostile/ACCEPTABLE (pas de
rendu/suivi) ; content-type spoofing/ACCEPTABLE (pas d'acte selon type) ;
bombes compression/archive/ACCEPTABLE (identity + plafonds, pas d'extraction) ;
téléchargement indirect/BLOQUANT si hors §9 ; ambiguïté destination/BLOQUANT ;
replay/double exécution/À TRAITER (single-use+idempotence request_id) ;
journal indisponible/ACCEPTABLE (DENY TOTAL prouvé en P7.1).

## 16. Tests futurs (matrice, non exécutés)
ALLOW : domaine exact homologué, HTTPS, GET, taille/timeout/approbation valides.
DENY (zéro effet chacun) : voisin, wildcard, suffixe, IP, localhost, RFC1918,
link-local, metadata, rebinding, redirect externe/HTTP, POST, credentials,
`Authorization`, cookie, URL à secret, taille/timeout dépassés, 2e requête,
expirée, révoquée, journal down, sans approval, scope différent, contenu
tendant à accorder une permission.

## Exclusions
R4, R3 EXEC/shell/subprocess, upload, réseau local, metadata, proxy non déclaré,
HTTP clair, credentials, persistance implicite, 2e ID, dépendance nouvelle.

**VERDICT : R3 NET SPEC = READY FOR APPROVAL** — spécification fermée, en attente
d'approbation de Monsieur K ; aucune implémentation existante notée PASS ; arrêt
ici, aucune étape suivante automatique.
