# AUDIO RÉEL LOCAL V1 — journal de preuve (interface, sans autorité)

- Base : `43124ed` (Voice Live 635/635).
- Ajout (aucune modification de fichier existant) :
  - `core/voice/audio_backends.py` : `AudioCapture`, `run_capture` (bornes
    strictes, échecs honnêtes), `sounddevice_pcm_capture` (PCM réel si
    présent), `termux_mic_capture` (conteneur déclaré non-PCM),
    `termux_tts_speak` (TTS système réel si présent), `play_pcm`,
    `probe_backends`/`describe` (détection seule). Zéro import du Core.
  - `core/voice/audio_live.py` : `audio_turn` + `AudioTurnReport`.
    Chemin unique : capture → `transcribe` → `voice_turn` →
    `LiveSession.submit_turn()` → Core existant → TTS de la sortie validée.
    Capture en échec = aucune soumission, session et gate inchangés.
  - `tests/test_voice_audio.py` : 40 cas A-G.
  - Le présent journal.
- STT inchangé et réutilisé (`core/voice/interaction.py::transcribe`,
  aucune duplication). Aucun moteur STT réel câblé.
- Résultats : 675/675 (`635 + 40`) en deux passages (`PYTHONHASHSEED`
  défaut puis `7`). Audit AST/câblage en test (aucun appel
  `invoke/approve/revoke/mandate/registry`, aucun import réseau/SQL).
- Batterie hostile : transcriptions hostiles, faux approbateur (tracé,
  jamais auto-approuvé par l'audio), mandats expiré/révoqué/suspendu/
  hors-périmètre (repli, jamais d'exécution directe), mémoire hostile
  inerte, session/confirmation étrangères refusées, double APPROVE à
  usage unique, expiration de demande respectée.
- JAIL/P7 intact (aucun résidu de fixture). Aucun secret, aucun réseau
  rendu obligatoire, aucune dépendance installée par ce changement.
