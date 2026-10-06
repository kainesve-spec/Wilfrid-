"""Tests P4 — contexte, journal, salut, isolation (nettoyés après run)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from core.session import events as E
from core.session.context import SessionContext
from core.session.manager import (
    SessionJournal,
    SessionManager,
    greeting_done_today,
    mark_greeting_done,
)
from core.wake.events import WakeDetected

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TMP_BASE = PROJECT_ROOT / "tests" / "tmp_session_p4"


def _wake(t=0.0):
    return WakeDetected(timestamp_monotonic=t, probability=0.9,
                        phrase="Wilfrid", frame_index=1)


def _tmpdir(name: str) -> Path:
    path = TMP_BASE / name
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)
    return path


def _clean(tmp: Path) -> None:
    import shutil as _shutil

    _shutil.rmtree(tmp, ignore_errors=True)
    try:
        TMP_BASE.rmdir()  # parent vide : ne subsiste aucun résidu
    except OSError:
        pass


def _manager(tmp: Path, **kw):
    kw.setdefault("greeting_path", tmp / "last_greeting")
    kw.setdefault("journal_path", None)
    return SessionManager(**kw)


def test_context_bounded():
    """14. contexte borné (tours + octets)."""
    ctx = SessionContext(max_turns=3, max_bytes=10**9)
    for i in range(10):
        ctx.add_turn({"role": "user", "text": f"message {i}"})
    assert len(ctx) == 3
    assert [t["text"] for t in ctx.turns()] == ["message 7", "message 8",
                                               "message 9"]


def test_context_purge():
    """15. purge complète à SESSION_ENDED."""
    tmp = _tmpdir("purge")
    try:
        manager = _manager(tmp)
        session = manager.on_wake(_wake(), now=0.0)
        assert session is not None
        session.context.add_turn({"role": "user", "text": "x" * 5000})
        session.context.current_task = "tache"
        manager.close("test", now=1.0)
        assert len(session.context) == 0
        assert session.context.current_task == ""
        assert session.context.current_state == ""
    finally:
        _clean(tmp)


def test_no_context_serialization():
    """16. aucune sérialisation du contexte (pas de save/persist)."""
    assert not hasattr(SessionContext, "save")
    assert not hasattr(SessionContext, "persist")
    assert not hasattr(SessionContext, "to_file")
    assert not hasattr(SessionContext, "dump")


def test_minimal_events_only():
    """17. événements minimaux uniquement."""
    manager = _manager(_tmpdir("events"))
    try:
        manager.on_wake(_wake(), now=0.0)
        manager.stop_listening(now=1.0)
        manager.close("test", now=2.0)
        kinds = {type(e).__name__ for e in manager.events}
        assert kinds <= {"SessionStarted", "ListeningStarted",
                         "ListeningStopped", "SessionEnded", "SessionError"}
        for event in manager.events:
            assert hasattr(event, "session_id")
            assert hasattr(event, "timestamp_monotonic")
            assert hasattr(event, "cause")
    finally:
        _clean(TMP_BASE / "events")


def test_clock_injectable():
    """18. horloge injectable (déterminisme)."""
    ticks = iter([100.0, 200.0])
    manager = SessionManager(greeting_path=None, journal_path=None,
                             now=lambda: next(ticks))
    first = manager.on_wake(_wake())
    assert first is not None
    assert first.created_monotonic == 100.0
    assert manager.check_timeout().state.value == "ENDED"


def test_journal_off_by_default():
    """19. journal OFF par défaut (aucune écriture nulle part)."""
    manager = SessionManager(greeting_path=None, journal_path=None)
    assert manager.journal.enabled is False
    manager.on_wake(_wake(), now=0.0)
    manager.close("test", now=1.0)


def test_journal_diagnostic_no_user_content():
    """20. mode diagnostic : champs techniques seuls, pas de contenu utilisateur."""
    tmp = _tmpdir("journal")
    try:
        journal_path = tmp / "session.log"
        manager = SessionManager(greeting_path=None, journal_path=journal_path)
        assert manager.journal.enabled is True
        session = manager.on_wake(_wake(), now=0.0)
        assert session is not None
        session.context.add_turn({"role": "user", "text": "SECRET_UTILISATEUR_123"})
        manager.close("test", now=1.0)
        content = journal_path.read_text(encoding="utf-8")
        assert "SECRET_UTILISATEUR_123" not in content
        for line in content.strip().splitlines():
            keys = set(json.loads(line).keys())
            assert keys <= {"event", "session_id", "timestamp_monotonic",
                            "cause", "counters", "state"}
        # rotation : fichier unique + .1 maximum
        assert len(list(tmp.glob("session.log*"))) <= 2
    finally:
        _clean(tmp)


def test_greeting_date_only():
    """21. salut quotidien : une date, rien d'autre."""
    tmp = _tmpdir("greet")
    try:
        path = tmp / "last_greeting"
        assert greeting_done_today(path, today="2030-01-02") is False
        mark_greeting_done(path, today="2030-01-02")
        assert greeting_done_today(path, today="2030-01-02") is True
        assert greeting_done_today(path, today="2030-01-03") is False
        assert path.read_text(encoding="utf-8").strip() == "2030-01-02"
        manager = SessionManager(greeting_path=path, journal_path=None)
        assert manager.should_greet_today(today="2030-01-03") is True
        manager.mark_greeted(today="2030-01-03")
        assert manager.should_greet_today(today="2030-01-03") is False
    finally:
        _clean(tmp)


def test_no_general_memory():
    """22. aucune mémoire générale (pas de db/embeddings, pas d'autosave)."""
    import core.session.manager as manager_mod

    src = Path(manager_mod.__file__).read_text(encoding="utf-8")
    for token in ("sqlite", "embedding", "vector", "memory.db", "autosave"):
        assert token not in src


def test_no_new_dependency_no_forbidden_imports():
    """23. aucune dépendance nouvelle ni import interdit dans core/session/."""
    import ast

    session_dir = PROJECT_ROOT / "core" / "session"
    forbidden = {"subprocess", "socket", "webbrowser", "sqlite3", "urllib",
                 "requests", "elevenlabs", "sounddevice", "onnxruntime"}
    allowed_third_party = {"numpy"}
    for path in sorted(session_dir.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        bad = (imported & forbidden) - allowed_third_party
        assert not bad, f"{path.name}: {sorted(bad)}"
    # TAIOS/QanXorus nulle part, même en commentaire/docstring.
    for path in sorted(session_dir.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        assert "TAIOS" not in text and "QanXorus" not in text


def test_p1_p2_p3_non_regression():
    """24. non-régression P1/P2/P3 (imports + harnais intact)."""
    import jarvis  # noqa: F401
    import core.audio  # noqa: F401
    import core.voice  # noqa: F401
    from tools import score_wavs  # noqa: F401

    assert jarvis.SAMPLE_RATE == 44100
