"""Wilfrid — point d'entrée principal (P0-1, mince, sans autorité).

`python3 wilfrid.py` : config → validation → init → READY → boucle
texte (stdin) → STOP propre. Codes : 0 ok, 2 config, 3 init,
130 interrompu. SIGINT/SIGTERM → arrêt propre.
"""

from __future__ import annotations

import argparse
import signal
import sys
from typing import Any, List, Optional

from core.runtime.config import RuntimeConfig, load_config
from core.runtime.lifecycle import create_runtime


def _parse(argv: Optional[List[str]] = None) -> RuntimeConfig:
    parser = argparse.ArgumentParser(prog="wilfrid",
                                     description="Wilfrid — runtime local")
    parser.add_argument("--config", default=None)
    parser.add_argument("--data-dir", default=None)
    parser.add_argument("--session-id", default=None)
    parser.add_argument("--max-turns", type=int, default=None)
    parser.add_argument("--speak", action="store_true", default=None)
    parser.add_argument("--log-level", default=None)
    args = parser.parse_args(argv)
    data = {}
    if args.data_dir:
        data["data_dir"] = args.data_dir
    if args.session_id:
        data["session_id"] = args.session_id
    if args.max_turns is not None:
        data["max_turns"] = args.max_turns
    if args.log_level:
        data["log_level"] = args.log_level
    base = load_config(args.config)
    merged = dict(data)
    if args.speak:
        merged["speak"] = True
    config = RuntimeConfig(
        env=base.env, data_dir=merged.get("data_dir", base.data_dir),
        memory_path=base.memory_path, knowledge_path=base.knowledge_path,
        journal_path=base.journal_path,
        session_id=merged.get("session_id", base.session_id),
        max_turns=merged.get("max_turns", base.max_turns),
        speak=merged.get("speak", base.speak),
        log_level=merged.get("log_level", base.log_level),
        offline=True, dictionary=dict(base.dictionary))
    return config


def _speak_text(text: str, config: RuntimeConfig) -> str:
    try:
        from core.voice.voice_router import VoiceConfig, speak_validated
        voice = VoiceConfig(offline_voice="upmc-pierre", offline_sid=1,
                            dictionary=dict(config.dictionary))
        status, audio, _report = speak_validated(text, config=voice)
        if status != "OK" or not audio:
            return "tts:" + status
        from core.voice.tts_local import play_wav
        ok, reason = play_wav(audio)
        return "parle" if ok else "tts:" + reason
    except Exception as exc:
        return "tts:erreur:" + str(exc)[:40]


def run(argv: Optional[List[str]] = None) -> int:
    """Démarre, boucle, arrête proprement. Code de sortie explicite."""
    import logging
    try:
        config = _parse(argv)
    except SystemExit as exc:
        return int(exc.code or 2)
    logging.basicConfig(level=getattr(logging, config.log_level, logging.INFO),
                        format="wilfrid %(levelname)s %(message)s")
    ok, runtime = create_runtime(config)
    if not ok or runtime.state != "READY":
        print("WILFRID ERROR: %s" % runtime.error, file=sys.stderr)
        runtime.stop()
        return 3
    print("WILFRID READY session=%s (fin: ligne vide / Ctrl-D)" %
          runtime.config.session_id)
    print("WILFRID ETAT components=%s" % ",".join(
        "%s=%s" % (name, "ok" if info["ready"] else "ko")
        for name, info in runtime.status()["components"].items()))
    stop_requested = []

    def _handle(_signum: int, _frame: Any = None) -> None:
        stop_requested.append(True)

    previous_int = signal.signal(signal.SIGINT, _handle)
    previous_term = None
    try:
        previous_term = signal.signal(signal.SIGTERM, _handle)
    except (OSError, ValueError):
        previous_term = None
    code = 0
    try:
        ok, reason = runtime.begin_running()
        if not ok:
            print("WILFRID ERROR: %s" % reason, file=sys.stderr)
            return 3
        turns = 0
        while not stop_requested:
            try:
                line = sys.stdin.readline()
            except (OSError, ValueError):
                break
            if not line:
                break
            text = line.strip()
            if not text:
                break
            try:
                from core.runtime.operator import handle_command
                handled, output = handle_command(
                    runtime, text, now=float(turns))
            except Exception:
                handled, output = False, ""
            if handled:
                print("Wilfrid: %s" % output)
                continue
            done, result = runtime.run_turn(text)
            if not done:
                print("WILFRID ERROR: %s" % result, file=sys.stderr)
                code = 3
                break
            answer = result.response.text \
                if result.response is not None and isinstance(
                    result.response.text, str) else result.detail
            print("Wilfrid: %s" % answer)
            if config.speak and result.kind == "RESPONDED":
                print("WILFRID VOIX %s" % _speak_text(answer, config))
            turns += 1
            if config.max_turns and turns >= config.max_turns:
                break
    finally:
        try:
            signal.signal(signal.SIGINT, previous_int)
            if previous_term is not None:
                signal.signal(signal.SIGTERM, previous_term)
        except (OSError, ValueError):
            pass
        runtime.stop()
    print("WILFRID STOPPED tours=%d" % runtime.turn_count)
    if stop_requested:
        return 130
    return code


def main(argv: Optional[List[str]] = None) -> int:
    """Entrée `python -m core.runtime.main` / tests."""
    return run(argv)
