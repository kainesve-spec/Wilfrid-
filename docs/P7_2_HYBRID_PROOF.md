# VOIX HYBRIDE O2-V1 — journal de preuve (sélection utilisateur gelée)

- Base : `94b5195`. Sélection utilisateur : VOIX 1 — Pierre (upmc,
  sid=1) comme voix offline officielle. Config persistée hors dépôt :
  `~/.local/share/wilfrid/voice_config.json` (mode auto, pierre/sid1,
  sans Voice ID connecté — non présumé, cf. ambiguïté ci-dessous).
- ElevenLabs : provider présent (`core/voice/welcome.py`, env
  `ELEVENLABS_API_KEY` seule dans `.env` ignoré par git). AUCUN
  `ELEVENLABS_VOICE_ID` identifiable dans le projet → identification
  non établie, non présumée, non modifiée. Connecté = non qualifié
  (pas de clé/ID testables ici) ; routeur prévoit le chemin + repli.
- Ajout (zéro composant d'autorité touché) :
  - `core/voice/pronunciation.py` : `int_to_french` (0..999999999),
    nombres (milliers, décimales virgule/point, %, monnaies), dates
    jj/mm/aaaa, heures, dictionnaire extensible + défaut
    (Wilfrid/TAIOS/QanXorus/USDT/Monsieur K), épellation acronymes.
    Affichage préservé, substitutions tracées.
  - `core/voice/voice_router.py` : `VoiceConfig` + persistance,
    `elevenlabs_available` (sans sonde réseau), `elevenlabs_speak`
    (1 tentative bornée 15 s + repli), `speak_validated`
    (préparation → connecté → repli local), `describe`. Aucun import
    Core/réseau ; secret jamais journalisé/stocké.
  - `core/voice/tts_local.py` : défauts regelés pierre (revert V1.1) ;
    correctifs conservés (sid dynamique, taux par modèle).
  - `tests/test_voice_pronunciation.py` (7 cas rapides),
    `tests/test_voice_hybrid.py` (16 cas A-J + R0/R1 + AST + offline).
- Nombres (mandat) : 100→cent, 20→vingt, 97→quatre-vingt-dix-sept,
  1000→mille, 1500→mille cinq cents, 2026→deux mille vingt-six,
  97,45→…virgule quarante-cinq, 2,5 %→…pour cent,
  0,05→zéro virgule zéro cinq. Limite : versions pointées
  (« 1.2.3 » partiel → via dictionnaire).
- 5 voix présentées (même texte, `~/storage/downloads/Wilfrid-Voix/`,
  STT-back documenté) : pierre/tom/jessica/siwis/gilles. gilles
  exclue instrumentalement (2026→2006, 97,45→87,45).
- Résultats : 748/748 (`698 + 24 + 26`) seed défaut et
  `PYTHONHASHSEED=7`. AST/câblage en tests (routeur+TTS : aucune
  autorisation, aucun secret, aucun shell). Secrets : aucun exposé.
- JAIL/P7 intact. Git : commit ci-dessous, dépôt propre.
