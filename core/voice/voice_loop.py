"""Wilfrid — boucle vocale réelle (P1-B1, orchestration sans autorité).

Enchaîne les composants validés, sans les réimplémenter :
attente (wake optionnel) → capture micro réelle → STT local réel →
`runtime.run_turn` (même Core que le texte) → réponse validée →
Pierre/Piper → lecture locale → retour à l'écoute.

Défauts = chemins réels (micro, whisper, Pierre, sounddevice), jamais
de mocks : les injections ne servent qu'aux tests déterministes. Tout
échec est explicite (FAILED/SKIPPED), jamais simulé. Arrêt explicite,
aucune boucle infinie. Aucune autorité : la voix demande, le Core et
la gouvernance existants décident.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

LOOP_STATES = ("IDLE", "LISTENING", "PROCESSING", "SPEAKING", "STOPPING",
               "STOPPED", "ERROR")


@dataclass
class VoiceTurnReport:
    """Rapport d'un tour vocal : chaque étape, état explicite."""

    stage: str = "attente"
    capture: str = ""
    stt: str = ""
    core: str = ""
    tts: str = ""
    lecture: str = ""
    texte: str = ""
    reponse: str = ""


class VoiceLoop:
    """Boucle vocale : états explicites, arrêt fiable, zéro autorité."""

    def __init__(self, runtime: Any, *,
                 stt_fn: Any = None,
                 synth_fn: Any = None,
                 play_fn: Any = None,
                 capture_fn: Any = None,
                 wake_factory: Any = None,
                 max_turns: int = 0,
                 utter_seconds: float = 6.0,
                 wake_timeout_s: float = 30.0) -> None:
        self.runtime = runtime
        self.state = "IDLE"
        self.max_turns = max_turns
        self.utter_seconds = utter_seconds
        self.wake_timeout_s = wake_timeout_s
        self.turns = 0
        self.reports: List[VoiceTurnReport] = []
        self._stop_event = threading.Event()
        self._stt_fn = stt_fn
        self._synth_fn = synth_fn
        self._play_fn = play_fn
        self._capture_fn = capture_fn
        self._wake_factory = wake_factory
        self._wake: Any = None
        self._run_lock = threading.Lock()

    # ---------------------------------------------------------- défauts réels
    def _stt(self) -> Any:
        if self._stt_fn is not None:
            return self._stt_fn
        from core.voice.stt_local import stt_fn_for
        return stt_fn_for()

    def _synth(self) -> Any:
        if self._synth_fn is not None:
            return self._synth_fn
        from core.voice.voice_router import speak_validated

        def _pierre(text: str) -> bytes:
            status, audio, _report = speak_validated(text)
            if status != "OK" or not audio:
                raise RuntimeError("tts:" + status)
            return audio

        return _pierre

    def _play(self) -> Any:
        if self._play_fn is not None:
            return self._play_fn
        from core.voice.tts_local import play_wav

        def _play_wav_audiowav(wav: bytes) -> Tuple[bool, str]:
            return play_wav(wav)

        return _play_wav_audiowav

    def _capture(self) -> Any:
        if self._capture_fn is not None:
            return self._capture_fn
        from core.voice.audio_backends import sounddevice_pcm_capture

        def _mic() -> Any:
            capture = sounddevice_pcm_capture(self.utter_seconds)
            if capture.status != "OK":
                raise RuntimeError("capture:" + capture.reason)
            return capture.pcm, capture.sample_rate

        return _mic

    def _aborted(self, report: VoiceTurnReport) -> bool:
        if self._stop_event.is_set():
            report.stage = "arret"
            self.state = "LISTENING"
            return True
        return False
    def listen_once(self, timeout_s: Optional[float] = None) -> Tuple[bool,
                                                                       str]:
        """Attente : wake réel si fourni (borné), sinon capture directe."""
        if self._wake_factory is None:
            return True, "ecoute-directe"
        limit = float(timeout_s if timeout_s is not None
                      else self.wake_timeout_s)
        if limit <= 0.0:
            return False, "delai-invalide"
        fired = False
        try:
            from core.wake.runtime import WakeRuntime
            wake = self._wake_factory()
            if not isinstance(wake, WakeRuntime):
                return False, "wake-invalide"
            self._wake = wake
            try:
                before = wake.snapshot().get("last_event_timestamp")
            except Exception:
                before = None
            blocks = max(1, int(limit * 10))
            try:
                wake.run(max_blocks=blocks)
            finally:
                self._wake = None
            if self._stop_event.is_set():
                return False, "arret-demande"
            try:
                after = wake.snapshot().get("last_event_timestamp")
            except Exception:
                after = None
            if after is not None and after != before:
                fired = True
            if fired:
                return True, "reveil-detecte"
            return False, "silence-delai-depasse"
        except Exception as exc:
            self._wake = None
            return False, "wake-erreur:" + type(exc).__name__

    def turn_once(self, pcm: Any = None,
                  sample_rate: int = 16000) -> VoiceTurnReport:
        """Un tour complet : capture/STT → Core → Pierre → lecture."""
        report = VoiceTurnReport(stage="capture")
        if self._stop_event.is_set():
            report.stage = "arret"
            return report
        self.state = "PROCESSING"
        try:
            if pcm is None:
                pcm, sample_rate = self._capture()()
                report.capture = "ok"
            else:
                report.capture = "fourni"
        except Exception as exc:
            report.stage = "echec-capture"
            report.capture = str(exc)[:60]
            self.state = "LISTENING"
            return report
        if self._aborted(report):
            return report
        report.stage = "stt"
        try:
            produced = self._stt()(pcm if isinstance(
                pcm, (bytes, bytearray)) else pcm)
            if not isinstance(produced, (tuple, list)) \
                    or len(produced) != 2:
                raise RuntimeError("stt:format-invalide")
            text, _confidence = produced
            if not isinstance(text, str) or not text.strip():
                report.stage = "silence"
                report.stt = "vide"
                self.state = "LISTENING"
                return report
            report.stt = "ok"
            report.texte = text.strip()[:200]
        except Exception as exc:
            report.stage = "echec-stt"
            report.stt = str(exc)[:60]
            self.state = "LISTENING"
            return report
        if self._aborted(report):
            return report
        report.stage = "core"
        try:
            done, result = self.runtime.run_turn(report.texte)
            if not done:
                report.core = str(result)[:60]
                report.stage = "core-indisponible"
                self.state = "LISTENING"
                return report
            report.core = getattr(result, "kind", "?")
            answer = result.response.text \
                if result.response is not None and isinstance(
                    result.response.text, str) else ""
            report.reponse = answer[:200]
            if not answer.strip():
                report.stage = "sans-reponse"
                self.state = "LISTENING"
                return report
        except Exception as exc:
            report.stage = "echec-core"
            report.core = type(exc).__name__
            self.state = "LISTENING"
            return report
        if self._aborted(report):
            return report
        report.stage = "tts"
        self.state = "SPEAKING"
        try:
            audio = self._synth()(answer)
            if not isinstance(audio, (bytes, bytearray)) or not bytes(audio):
                raise RuntimeError("tts:audio-invalide")
            report.tts = "ok"
        except Exception as exc:
            report.stage = "echec-tts"
            report.tts = str(exc)[:60]
            self.state = "LISTENING"
            return report
        try:
            played = self._play()(bytes(audio))
            if isinstance(played, tuple):
                ok_play, why = played
            else:
                ok_play, why = bool(played), ""
            report.lecture = "ok" if ok_play else str(why)[:60] or "echec"
            report.stage = "termine" if ok_play else "echec-lecture"
        except Exception as exc:
            report.stage = "echec-lecture"
            report.lecture = type(exc).__name__
        self.state = "LISTENING"
        return report

    # ----------------------------------------------------------------- boucle
    def run(self) -> Dict[str, Any]:
        """Boucle bornée : écoute → tours → STOPPED. Arrêt explicite."""
        if not self._run_lock.acquire(blocking=False):
            return {"tours": self.turns, "etat": self.state,
                    "raison": "boucle-deja-active"}
        try:
            if self.state not in ("IDLE", "LISTENING", "ERROR", "STOPPED"):
                return {"tours": self.turns, "etat": self.state,
                        "raison": "etat-inattendu"}
            self.state = "LISTENING"
            self._stop_event.clear()
            while not self._stop_event.is_set():
                if self.max_turns and self.turns >= self.max_turns:
                    break
                heard, why = self.listen_once()
                if self._stop_event.is_set():
                    break
                if not heard:
                    self.reports.append(VoiceTurnReport(
                        stage="attente-" + why))
                    if self.max_turns:
                        self.turns += 1
                    continue
                report = self.turn_once()
                self.reports.append(report)
                self.turns += 1
            self.state = "STOPPED"
            return {"tours": self.turns, "etat": self.state,
                    "raison": "arret-explicite"}
        finally:
            try:
                self._run_lock.release()
            except RuntimeError:
                pass

    def stop(self) -> Dict[str, Any]:
        """Arrêt fiable : signal + wake + état STOPPED."""
        self.state = "STOPPING"
        self._stop_event.set()
        wake, self._wake = self._wake, None
        if wake is not None:
            try:
                wake.stop()
            except Exception:
                pass
        self.state = "STOPPED"
        return {"tours": self.turns, "etat": self.state}


def describe() -> Dict[str, Any]:
    """Contrat de la boucle (sans effet)."""
    return {"etats": list(LOOP_STATES),
            "defauts": ["micro-reel", "whisper-local", "core-runtime",
                        "pierre-locale", "lecture-locale"],
            "wake": "optionnel-injecte",
            "network": False, "authority": False}
