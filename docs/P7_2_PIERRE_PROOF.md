# VOIX UNIQUE PIERRE — décision utilisateur (complément O2-VOICE-HYBRID-V1)

- Décision : UNE SEULE voix, Pierre (upmc, sid=1), quel que soit l'état
  réseau. ElevenLabs hors pipeline (fichiers historiques intacts :
  `wilfrid_voice.py` avec Voice ID `bIHbv24MWmeRgasZH58o` — identifié par
  preuve, non présumé —, `core/voice/welcome.py`, `jarvis.py`,
  `core/session/identity.py`, `requirements.txt` : conservés, non
  cassés, hors pipeline Wilfrid).
- Retiré du pipeline : branche connectée de `core/voice/voice_router.py`
  (`elevenlabs_available`, `elevenlabs_speak`, `convert_fn`, mode
  `connected`, import `os`/`concurrent`). Le routeur reste utile :
  préparation + Pierre + config + rapport, zéro réseau (vérifié AST :
  aucun token elevenlabs/socket/urllib/http/requests/shell/API_KEY).
- Conservés : normalisation/prononciation, `tts_local.py` (Pierre),
  `audio_turn`/`voice_turn`/LiveSession/Core (0 modification),
  dictionnaire extensible, config persistée (`mode=local`,
  pierre/sid1, sans secret).
- Test réel tokens (Pierre, 14,1 s, 22050 Hz) :
  « Je suis Wilfrid. TAIOS et QanXorus utilisent 100 USDT, puis
  1 500 USDT. En 2026, la valeur est de 97,45 et le taux de 2,5 pour
  cent, minimum 0,05. » → STT-back : nombres entendus comme nombres
  (100, 1500, 2026, 97,45, 2,5 %, 0,05 %), fin du « chiffre à chiffre ».
  Fichier : `~/storage/downloads/Wilfrid-Voix/pierre_tokens_nombres.wav`.
- Résultats : 748/748 (`698 + 24 + 26`) seed défaut et
  `PYTHONHASHSEED=7`. JAIL/P7 intact. Git : commit ci-dessous.
