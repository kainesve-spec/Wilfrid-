# Wilfrid — application Android (coquille, zéro moteur)

## Architecture

APK = WebView vers `http://127.0.0.1:8787/` servi par
`python3 wilfrid.py --app` (Termux). UN SEUL moteur : le runtime
Python. L'APK ne décide, n'autorise et n'exécute rien : aucun pont
JavaScript natif (`addJavascriptInterface` interdit), communication
HTTP locale uniquement, navigation externe bloquée.

## Contrat local

- `GET /` : chat + sphère + micro (contexte sécurisé localhost).
- `POST /api/chat` : texte → Core → réponse (même session).
- `POST /api/voice` : PCM 16 kHz → STT → Core → Pierre WAV.
- `GET /snapshot|/png|/page` : états réels uniquement.
- Approbations : NON exposées (404). Autorisations via REPL/opérateur.
- Sans serveur : page d'indisponibilité embarquée (jamais d'état
  inventé). Micro refusé : texte maintenu, voix désactivée honnêtement.

## Hors-ligne

Aucune ressource distante : page/APK autonomes, runtime local,
voix/STT/mémoire locaux. Seules les capacités Internet explicites
restent indisponibles sans réseau.

## Build

GitHub Actions (`.github/workflows/android.yml`) : JDK 17 + Gradle 8.7
→ `:app:assembleDebug` → APK debug en artefact. Pas de SDK dans
Termux (prouvé absent). Pas de secret dans le dépôt.
