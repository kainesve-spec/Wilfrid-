"""Tests P4 — lifecycle session (synthétique, horloge injectée)."""

from __future__ import annotations

from core.session import events as E
from core.session.identity import (
    ACTIVATION_RESPONSE,
    WilfridIdentity,
)
from core.session.manager import SessionManager
from core.session.state import SessionState
from core.wake.events import WakeDetected


def _wake(t=0.0):
    return WakeDetected(timestamp_monotonic=t, probability=0.9,
                        phrase="Wilfrid", frame_index=3)


def _manager(**kw):
    kw.setdefault("greeting_path", None)
    kw.setdefault("journal_path", None)
    return SessionManager(**kw)


def test_identity_wilfrid():
    """1. identité Wilfrid."""
    ident = WilfridIdentity()
    assert (ident.name, ident.internal_id) == ("Wilfrid", "wilfrid-core")
    assert ident.wake_phrase == "Wilfrid"
    assert ident.voice_id == "bIHbv24MWmeRgasZH58o"


def test_identity_user_mkkwin():
    """2. identité utilisateur Monsieur K (paramètre, pas mémoire)."""
    assert WilfridIdentity().user_name == "Monsieur K"
    assert WilfridIdentity(user_name="Autre").user_name == "Autre"


def test_activation_response_exact():
    """3. réponse d'accusé exacte."""
    assert ACTIVATION_RESPONSE == "Oui, Monsieur K. Je suis là."
    assert _manager().activation_response() == "Oui, Monsieur K. Je suis là."


def test_initial_idle():
    """4. état initial IDLE (aucune session)."""
    manager = _manager()
    assert manager.session is None


def test_wake_to_activating_then_active():
    """5/6. wake depuis IDLE : ACTIVATING transitoire puis ACTIVE."""
    manager = _manager()
    session = manager.on_wake(_wake(t=10.0), now=10.0)
    assert session is not None
    assert session.state == SessionState.ACTIVE
    kinds = {type(e).__name__ for e in manager.events}
    assert {"SessionStarted", "ListeningStarted"} <= kinds


def test_double_wake_single_session():
    """7. double wake : pas de seconde session."""
    manager = _manager()
    first = manager.on_wake(_wake(t=10.0), now=10.0)
    second = manager.on_wake(_wake(t=11.0), now=11.0)
    assert first is not None and second is not None
    assert first.session_id == second.session_id
    assert sum(isinstance(e, E.SessionStarted) for e in manager.events) == 1


def test_timeout_refresh():
    """8. refresh du timeout sur second wake."""
    manager = _manager()
    session = manager.on_wake(_wake(t=10.0), now=10.0)
    assert session is not None
    manager.on_wake(_wake(t=50.0), now=50.0)
    assert session.last_activity_monotonic == 50.0
    assert manager.check_timeout(now=100.0) is session  # 50 < 60 : active
    assert manager.check_timeout(now=111.0).state == SessionState.ENDED


def test_timeout_60s():
    """9. timeout à 60 s par défaut."""
    manager = _manager()
    session = manager.on_wake(_wake(t=0.0), now=0.0)
    assert session is not None
    assert manager.check_timeout(now=60.0) is session
    closed = manager.check_timeout(now=60.1)
    assert closed is not None and closed.state == SessionState.ENDED
    assert any(isinstance(e, E.SessionEnded) and e.cause == "timeout"
               for e in manager.events)


def test_timeout_parametrable():
    """10. timeout paramétrable."""
    manager = _manager(inactivity_timeout_s=5.0)
    manager.on_wake(_wake(t=0.0), now=0.0)
    assert manager.check_timeout(now=5.1).state == SessionState.ENDED


def test_explicit_close():
    """11. fermeture explicite + purge."""
    manager = _manager()
    session = manager.on_wake(_wake(t=0.0), now=0.0)
    assert session is not None
    session.context.add_turn({"role": "user", "text": "bonjour"})
    closed = manager.close("test", now=1.0)
    assert closed is not None and closed.state == SessionState.ENDED
    assert len(closed.context) == 0
    assert any(isinstance(e, E.SessionEnded) for e in manager.events)


def test_error_path():
    """12. erreur explicite."""
    manager = _manager()
    session = manager.on_wake(_wake(t=0.0), now=0.0)
    assert session is not None
    failed = manager.fail("boom", detail="x", now=1.0)
    assert failed is not None and failed.state == SessionState.ERROR
    assert any(isinstance(e, E.SessionError) for e in manager.events)


def test_reactivation_after_close():
    """13. réactivation après fermeture = nouvelle session."""
    manager = _manager()
    first = manager.on_wake(_wake(t=0.0), now=0.0)
    assert first is not None
    manager.close("test", now=1.0)
    second = manager.on_wake(_wake(t=2.0), now=2.0)
    assert second is not None
    assert second.session_id != first.session_id
    assert second.state == SessionState.ACTIVE
