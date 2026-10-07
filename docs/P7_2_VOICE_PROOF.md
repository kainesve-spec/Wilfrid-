# VOIX RÉELLE — journal de preuve (V1 PRE-VOICE, interface sans moteur)

- Base : `1a0a292`, boucle vivante textuelle 610/610.
- Ajout : `core/voice/live_voice.py` (`voice_turn`, `_announce`, `describe`).
  STT/TTS injectés uniquement ; aucun moteur réel câblé ; sans `stt_fn`,
  STT FAILED honnête ; sans `synth_fn`, TTS SKIPPED honnête.
- Retouche additive seule : `stt_confidence` (défaut `None`) dans
  `core/loop/loop.py::run_text_turn` et `core/loop/live.py::submit_turn`,
  transmis à `dialogue.respond` qui le supportait déjà. Sémantique texte
  inchangée (défaut `None` = comportement antérieur).
- TTS : parle la réponse validée ; demande de confirmation parlée à la
  création (l'utilisateur doit entendre ce qu'il confirme) ; après
  exécution vérifiée sans texte de réponse, annonce d'issue uniquement
  (`Action exécutée et vérifiée.`, jamais le contenu).
- Autorité : `live_voice.py` ne crée ni gate, ni registre, ni mandat ;
  AST vérifié en test (aucun import `socket/subprocess/urllib/http/os/
  sys/sqlite3/requests` ; aucune occurrence `PermissionRegistry(` ni
  `ApprovalGate(`). La voix emprunte le même Core : clarification,
  confirmation R1, mandat R2, révocation, registre vide hors mandats valides.
- Tests : `tests/test_voice_live.py`, 25 cas (STT valide/accents/vide/
  faible-confiance/panne/absent/limites, R0, R1 complet + second APPROVE
  refusé, R2 complet, clarification, refus, incertitude, panne TTS,
  transcription hostile inerte + registre vide, faux APPROVE, faux mandat,
  session étrangère, confirmation étrangère, mandat révoqué → pas
  d'exécution directe, mémoire hostile inerte, répétition usage unique,
  câblage d'autorité interdit).
- Résultats : 635/635 (`610 + 25`) en deux passages
  (`PYTHONHASHSEED` défaut puis `7`). Échecs intermédiaires constatés
  strictement limités à des dépendances optionnelles absentes de
  l'environnement (`sounddevice`, `python-dotenv`, `pypdf`,
  `beautifulsoup4`), préexistants sur arbre propre, résolus par
  installation locale — aucun lié au changement.
- Environnement : aucune modification hors `core/loop/loop.py`,
  `core/loop/live.py`, `core/voice/live_voice.py`,
  `tests/test_voice_live.py`, le présent journal. `JAIL/P7` intact
  (aucun résidu de fixture).
- Non fait (interdit par le mandat) : STT/TTS réel, microphone, réseau,
  R3/R4, trading/TAIOS.
