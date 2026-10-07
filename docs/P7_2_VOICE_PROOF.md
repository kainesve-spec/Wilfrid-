# VOIX LOCALE WILFRID V1 — journal de preuve (TTS réel, offline, sans autorité)

- Base : `5a5f954`, arbre retrouvé propre, JAIL/P7 intact.
- Audit : 1 seul moteur TTS système (`com.google.android.tts`, voix non
  listables, offline non garanti) ; `espeak` 1.52 classique présent ;
  `espeak-ng` absent des dépôts ; `sherpa_onnx` 1.13.8 présent (mais son
  VITS refuse la voix piper : sortie silencieuse du constructeur) ;
  `piper-tts`/`piper-phonemize` sans roue cp314 (phonemize max cp311,
  lib glibc incompatible bionic en ctypes) ; cmake système cassé
  (compilation exclue) ; 45 Go libres, 7,6 Go RAM.
- Cartographie : A (Android TTS : non qualifiable, pas de fichier, pas de
  voix choisie), B (espeak : robotique, rejeté), C (piper-vits via
  onnxruntime + espeak-classic IPA : RETENU), D (Kokoro FR : voix
  féminine seule, rejeté — profil masculin), E (clonage : non démarré,
  interdit à cette étape).
- Voie C : voix `fr_FR-upmc-medium` (76,7 Mo, publique `rhasspy/
  piper-voices`, locuteur `pierre` sid=1 masculin ; sid=0=jessica non
  utilisé) + `espeak-ng-data` compilées extraites de la roue
  piper-phonemize (445 fichiers, usage de données uniquement) +
  `tokens` reconstruits depuis `phoneme_id_map` (157 symboles).
  Correctifs déterminants : PAD `_` après chaque phonème (convention
  piper lue dans ses sources), `noise_w=0.8`, francisation
  (ɪ→i, ɹ→ʁ, ʊ→u, ʌ→a, ð→d, θ→t, marqueurs de langue retirés).
- Ajout (zéro fichier existant modifié sauf tests ciblés) :
  - `core/voice/tts_local.py` : `VoiceProfile`/`WILFRID_VOICE`
    (personalization `NONE`), `find_engine`, `synthesize` (clauses,
    bornes, silences), `synth_fn_for` (compatible `speak()`/`audio_turn`
    sans toucher au Core), `play_wav`, `describe`. Stdlib + numpy +
    onnxruntime tardifs uniquement ; aucun import Core/réseau.
  - `tests/test_voice_tts.py` : 26 cas (10 phrases, F0, stabilité,
    R0/R1/R2, échecs A-K, AST, profil).
  - `tests/test_voice_stt.py` : délai moteur 180→300 s (robustesse
    charge ; un passage isolé a dépassé 180 s sous charge extrême,
    puis 24/24 aux repasses).
  - Le présent journal.
- Mesures : 10 phrases OK (0,9-4,7 s audio, 6-14 s génération) ;
  22050 Hz mono16, zéro clipping, pics 16-18k, F0 médian 154 Hz
  (masculin-haut) ; RSS pic ~214 Mo ; modèle 76,7 Mo (+données 16 Mo) ;
  STT-back : contenu reconnu (« Bonjour », « Monsieur » exacts ;
  confabulations whisper en bordure, documentées) ; 3× même phrase :
  durées stables ; aucune autorisation créée (gate vide, registre vide).
- Écart profil : registre médium-haut (154 Hz), pas grave profond —
  aucun pitch-shift appliqué (pas de falsification). Écoute humaine
  impossible headless (qualification instrumentale + STT-back).
- Résultats : 725/725 (`699 + 26`) seed défaut et `PYTHONHASHSEED=7`
  (blocs : 675 + 24 + 26). AST/câblage en tests. Secrets : aucun.
  Un passage mono-processus >15 min sous charge (lenteur, pas de
  blocage) — même couverture en blocs, documenté.
- Personnalisation Monsieur K : NON démarrée, aucune donnée créée.
