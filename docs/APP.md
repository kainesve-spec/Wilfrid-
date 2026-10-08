# Wilfrid — application locale (chat + voix + sphère)

## Lancement

```sh
python3 wilfrid.py --app [--data-dir DIR] [--session-id ID]
```

Affiche `WILFRID APP http://127.0.0.1:8787/` (port éphémère si occupé).
UN runtime persistant : la session survit à la fermeture du client.
Arrêt : fermer l'entrée (ligne vide) ou Ctrl-C → `WILFRID APP STOPPED`.

## Interface

`/` : sphère PNG + état + auto-refresh 2 s. Chat : saisie → Core
réel → réponse (même session, mémoire et knowledge branchées). Voix :
bouton micro (PCM 16 kHz côté client, localhost = contexte sécurisé)
→ STT local → Core → réponse Pierre en WAV rejouée.

## Lanceur Android (notification persistante)

Aucun overlay système sans application native (impossible prouvé :
aucun mécanisme). Équivalent livré : notification persistante avec
bouton d'ouverture (à créer pendant que l'app tourne) :

```sh
termux-notification --id wilfrid --title "◉ Wilfrid" \
  --content "Toucher pour ouvrir" --ongoing \
  --action "termux-open http://127.0.0.1:8787/"
termux-notification-remove wilfrid  # au retrait
```

## Approbations

NON exposées (ni bouton ni route : `/approve` → 404). Autorisations
uniquement via REPL/opérateur (`/approve`, `/mrun …`), jamais depuis
l'interface. La voix ne vaut jamais approbation.

## Limites

Pas d'appli native/APK (aucun SDK sur l'appareil — prouvé : ni
gradle, ni sdkmanager, ni adb) ; pas d'overlay flottant système ;
navigateur non vérifié (page standard + micro localhost) ; audibilité
headless non vérifiable ; mono-processus lent sous charge.
