# STT LOCAL V1 — journal de preuve (moteur réel, offline, sans autorité)

- Base : `3bb6abc` (Audio local 675/675). Décision d'audit : CAS B —
  aucun moteur présent, mais voie locale légère viable identifiée et
  intégrée avec justification (ci-dessous). Aucun faux PASS.
- Audit : aarch64, CPython 3.14.6, Termux. `vosk` : aucune distribution
  compatible (`pip index` vide). `pocketsphinx` : téléchargement impraticable
  (délai dépassé). Modèles `csukuangfj` (zipformer FR) : 401 Unauthorized
  (accès sous conditions, refusé sans compte). `whisper` python : pile
  lourde (torch) exclue. `termux-speech-to-text` présent mais : aucune
  sortie en silencieux, dépendance au service Android (hors-ligne non
  garanti, non déterministe) → exclu du STT local V1.
- Voie retenue : whisper.cpp v1.5.4 compilé localement (toolchain présente ;
  cmake système cassé — contourné par tag à Makefile classique, documenté),
  modèle `ggml-base.bin` 148 Mo (public, `ggerganov/whisper.cpp`).
  `ggml-tiny.bin` 77 Mo testé puis écarté : français inutilisable
  (« Bonjour Wilfrid » → « On a bien avion... »). Base sur parole
  naturelle FR : quasi-parfait (VoxForge, cf. asset).
- Installation durable hors dépôt : `~/.local/share/wilfrid/stt/`
  (`whisper-cli` 1 Mo + `ggml-base.bin`, sha256
  `60ed5bc3dd14eea856493d334349b405782ddcaf0028d4b5df4088345fba2efe`).
- Ajout (zéro fichier existant modifié) :
  - `core/voice/stt_local.py` : `find_engine`, `transcribe_wav`,
    `write_pcm_wav`, `stt_fn_for` (compatible `transcribe()`/`voice_turn`/
    `audio_turn`), `describe`. Stdlib seule, aucun import Core/réseau.
    Confiance `None` honnête (moteur sans score), moteur déclaré,
    raisons explicites (`moteur-absent`, `pas-de-parole`, `erreur-stt`...).
  - `tests/test_voice_stt.py` : 24 cas A-G (moteur réel exigé, 0 simulation
    pour `real_*`).
  - `tests/data/stt_fr_naturel.wav` : 224 Ko, parole FR naturelle
    (VoxForge `4h-20100505-vgm`, paquet `fr-sb-758`, licence GPL dans
    l'archive d'origine) + référence `QUE CELUI QUI NE CONNAîT PAS VOTRE
    VIE FASSE LE DéGOûTé`. Sortie moteur exacte et déterministe :
    « Que celui qui ne connaît pas votre vie face le déouté. »
  - Le présent journal.
- Mesures : ~5 s d'inférence / seconde audio (8 threads, 7 s → ~33-45 s),
  RSS pic mesuré ~90 Mo, modèle 148 Mo. Captures ≤ 10 s respectées.
- Chaînage : PCM mic (ou asset) → `stt_fn_for` → `audio_turn` →
  `LiveSession.submit_turn()` → Core/gouvernance inchangés → TTS du validé.
  R0 réel prouvé ; R1/R2 via même `audio_turn` (STT injecté, même chemin
  de code — asset littéraire non-commande) ; STT/micro défectueux →
  ERROR honnête, gate et registre intacts.
- Résultats : 699/699 (`675 + 24`) seed défaut et `PYTHONHASHSEED=7`
  (exécutés en deux blocs par seed : sous-ensemble rapide + STT —
  un passage mono-processus a dépassé 15 min sous charge, les deux blocs
  couvrent 100 % des tests). AST/câblage en test (aucun appel
  autorisation, aucun import Core/réseau dans `stt_local.py`).
- JAIL/P7 intact. Aucun secret, aucun réseau obligatoire à l'exécution.
  Recherche : `sherpa-onnx` 1.13.8 installé via pip pendant l'exploration
  mais non retenu et inutilisé par le code (moteur non packagé pour
  l'usage direct sans modèle compatible accessible) ; `espeak` installé
  via pkg comme utilitaire de génération d'échantillons uniquement.
  Seul le binaire whisper.cpp + modèle ggml-base constituent le STT V1.
