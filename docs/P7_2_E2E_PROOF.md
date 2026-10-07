# AUDIO E2E RÉEL V1 — journal de qualification physique (9fd9ec1 +0 code)

- Base : `9fd9ec1`, arbre propre avant et après (aucune modification de code
  requise : la chaîne s'est comportée honnêtement). JAIL/P7 intact
  (`d1`, `notifications` seuls ; JAIL ignoré par git).
- Moteur STT : `~/.local/share/wilfrid/stt/whisper-cli` (v1.5.4, ARM64) +
  `ggml-base.bin`, offline. TTS : `termux-tts-speak` (Google TTS système,
  seul moteur : `com.google.android.tts`). Mic : sounddevice/OpenSLES
  16 kHz. Aucune installation ajoutée par ce Master Command.
- Interaction physique réelle (zéro injection, zéro mock) :
  parole TTS-aloud FR → mic 8 s → trim/normalisation (conditionnement
  documenté, pas de simulation) → whisper base `-l fr` → LiveSession →
  Core → TTS-aloud de la réponse :
  - capture 0.00 s (mémoire) ; STT+Core 24.7 s ; TTS 7.5 s (rc=0) ;
  - `core_kind=RESPONDED`, `CONTINUE / Bien reçu.`, réponse revocalisée ;
  - `gate_audit=[]`, `registry_active=0`.
- Écart documenté : la phrase prononcée (« Bonjour Wilfrid, lis le fichier
  notes. ») a été transcrite « bonjour, brillez l'offrir » — le chemin
  acoustique de cet émulateur headless dégrade les consonnes au-delà de
  l'exploitable pour commandes (essais : débit 0.7 → rejeté comme
  [Musique] ; débit normal + trim → détecté mais déformé ; 2 énoncés +
  analyse d'enveloppe). Le Core a répondu honnêtement à ce qui a été
  entendu (smalltalk), sans exécution par défaut. Moteur hors de cause :
  FR naturel (VoxForge) quasi-parfait ; mic hors de cause (signal fort).
- R1/R2 live : impossibles ici (mots de commande perdus dans l'acoustique)
  — prouvés par ailleurs via même `audio_turn` (699/699). Non simulés.
- TTS : commandes acceptées rc=0 sans erreur, moteur unique identifié ;
  audibilité haut-parleur non vérifiable headless → PASS-CONDITIONNEL
  maintenu explicitement (rc=0 ≠ preuve d'écoute, cf. règle §5).
- Stabilité : 5 tours consécutifs `RESPONDED`, `turn_counter=5`, session
  ACTIVE, `pending=None`, gate vide, registre vide — aucune autorisation
  implicite entre tours.
- Échecs (tests, jamais de bypass) : micro/STT/TTS indisponibles ou en
  erreur, transcription vide, session fermée/étrangère, action non
  autorisée → états honnêtes, aucun effet (batteries existantes vertes).
- Validation : 699/699 seed défaut et `PYTHONHASHSEED=7` (675 + 24 par
  seed) ; AST/câblage en tests (STT/TTS/mic = interfaces, jamais
  autorités ; unique chemin audio→STT→LiveSession→Core→gouvernance→TTS) ;
  secrets : aucun exposé (seule mention : lecture d'env ElevenLabs
  préexistante dans `welcome.py`, hors chaîne) ; Git propre.
- Latences mesurées : STT ~5 s/s audio (8 threads) ; tour R0 physique
  ~32 s de bout en bout (capture 8 s incluse).
