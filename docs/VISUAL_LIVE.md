# Wilfrid — visualisation live (observatrice, sans autorité)

## Architecture

sources réelles → `core/visual/sink.py` (lecture seule, duck-typing,
aucun import Core) → `adapter.py` (grammaire + vérité) →
`renderer.py` (PNG) / `presence.py` (ANSI/JSON). La couche ne décide,
n'autorise et n'exécute rien.

## Table de vérité (extraits)

- READY/IDLE → IDLE ; capture → LISTENING ; STT/Core → THINKING ;
  SPOKEN → SPEAKING ; `pending` → WAITING_APPROVAL (jamais SUCCESS) ;
  EXECUTED non vérifié → EXECUTING ; vérification → VERIFYING ;
  `VERIFIED_SUCCESS` → SUCCESS (seul chemin) ; échec → ERROR ;
  incertain → UNCERTAIN ; stop → INTERRUPTED ; ERROR runtime → OFFLINE.
- Internet : étapes moteur mappées (DNS/HTTP → THINKING/EXECUTING,
  validé → VERIFYING) ; SSRF refusé = erreur, jamais succès.
- Plugins/agents : DECLARED/INSTALLED/CONNECTED ≠ OPERATIONAL ;
  OPERATIONAL sur preuve uniquement ; AUTH_REQUIRED représenté tel quel
  (OpenAI/Gemini/Claude) ; OmniRoute CONFIGURED (health) sans `/v1`.
- Priorité : ERROR > OFFLINE > INTERRUPTED > WAITING_APPROVAL >
  EXECUTING > VERIFYING > SUCCESS > UNCERTAIN > SPEAKING > LISTENING >
  THINKING > MODE > IDLE. L'humour ne masque jamais l'opérationnel.

## Serveur local

`VisualServer` (stdlib, 127.0.0.1:8787 par défaut) : `/health`,
`/snapshot` (JSON), `/png` (image). Vitrine : le moteur tourne sans
lui. Démarrage/arrêt bornés, thread démon unique, requêtes comptées.

## Démarrage / arrêt

Construire `VisualServer(make_provider(get_frame, tick, fmt))`,
`start()`, `stop()`. Aucun processus après arrêt (vérifié en test).

## Lancement --visual

```sh
python3 wilfrid.py --visual [--max-turns N]
```

Affiche `WILFRID VISUEL http://127.0.0.1:8787/page` (`/snapshot` JSON
horodaté, `/png` image). Sans `--visual` : comportement inchangé, aucun
serveur. Arrêt : fin d'entrée / Ctrl-C → serveur stoppé avec le runtime.

## Vérification

Consulter `/page` (état + fraîcheur), `/snapshot` (JSON), `/png`
(signature PNG). Périmé > 30 s signalé. Sans client HTTP : ANSI/JSON
restent disponibles via `presence.py`.

## Limites GUI Android

Aucun toolkit/display/framebuffer : pas de fenêtre native ni de plein
écran démontrables. Rendu = fichiers PNG (galerie via `termux-open`,
manuel) + ANSI terminal + JSON. Ne pas présenter cela comme une
interface graphique embarquée.
