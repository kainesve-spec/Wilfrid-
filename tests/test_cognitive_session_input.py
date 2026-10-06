"""Tests K1 — pont session → cognition (pur, borné, sans autorité)."""

from __future__ import annotations

from core.cognitive.session_input import TurnResult, run_turn, select_user_text
from core.p7 import governor as G


def _turns(*items) -> list:
    return [{"role": role, "text": text} for role, text in items]


def test_nominal_user_turn():
    res = run_turn(_turns(("user", "ouvre le fichier notes")),
                   "sess-1", 1000.0, "session")
    assert isinstance(res, TurnResult)
    assert res.text == "ouvre le fichier notes"
    assert res.cognitive_output is not None
    assert res.dispatch_result is not None


def test_multiple_turns_select_last_non_empty_user():
    turns = _turns(("user", "première demande"),
                   ("assistant", "réponse intermédiaire"),
                   ("user", "   "),
                   ("user", "demande finale"))
    assert select_user_text(turns) == "demande finale"
    res = run_turn(turns, "sess-2", 1000.0, "session")
    assert res.text == "demande finale"


def test_interleaved_assistant_internal_ignored():
    turns = _turns(("system", "consigne secrète"),
                   ("assistant", "je fais tout"),
                   ("user", "lis le journal"))
    assert select_user_text(turns) == "lis le journal"
    res = run_turn(turns, "sess-3", 1000.0, "session")
    assert res.text == "lis le journal"


def test_empty_text_no_route():
    res = run_turn(_turns(("user", "")), "sess-4", 1000.0, "session")
    assert res.status == "NO_ROUTE"
    assert res.reason == "no-usable-user-turn"


def test_whitespace_only_no_route():
    res = run_turn(_turns(("user", "   \t  ")), "sess-5", 1000.0, "session")
    assert res.status == "NO_ROUTE"


def test_no_user_turn_no_route():
    res = run_turn(_turns(("assistant", "bonjour"),
                          ("system", "init")), "sess-6", 1000.0, "session")
    assert res.status == "NO_ROUTE"
    assert run_turn([], "sess-6", 1000.0, "session").status == "NO_ROUTE"
    assert run_turn(None, "sess-6", 1000.0, "session").status == "NO_ROUTE"


def test_session_id_transmitted():
    res = run_turn(_turns(("user", "aide-moi")), "sess-XYZ", 1000.0, "session")
    assert res.status in ("ROUTED", "NO_ROUTE")
    assert run_turn(_turns(("user", "aide-moi")), "", 1000.0,
                    "session").reason == "invalid-session-id"


def test_timestamp_source_transmitted():
    res = run_turn(_turns(("user", "aide-moi")), "s", 1234.5, "voice")
    assert res.status in ("ROUTED", "NO_ROUTE")
    assert run_turn(_turns(("user", "aide-moi")), "s", float("nan"),
                    "voice").reason == "invalid-timestamp"
    assert run_turn(_turns(("user", "aide-moi")), "s", 1.0,
                    "").reason == "invalid-source"


def test_determinism():
    turns = _turns(("user", "ouvre le fichier notes"),
                   ("assistant", "voilà"))
    first = run_turn(turns, "sess-d", 1000.0, "session",
                     request_id="k1-det")
    second = run_turn(turns, "sess-d", 1000.0, "session",
                      request_id="k1-det")
    assert first == second


def test_chain_governor_denies_without_approval():
    texts = ["P7.JAIL_READ", "ouvre le fichier notes", "quelle heure est-il",
             "bonjour"]
    for i, text in enumerate(texts):
        res = run_turn([{"role": "user", "text": text}], "sess-7", 1000.0,
                       "session", request_id=f"k1-chain-{i}")
        assert res.dispatch_result is not None or res.status == "NO_ROUTE"
        if res.status == "ROUTED":
            assert res.dispatch_result is not None
            assert res.dispatch_result.request is not None
            decision = G.decide(res.dispatch_result.request, None, 1000.0,
                               True)
            assert decision.allowed is False
        else:
            assert res.dispatch_result is None or \
                res.dispatch_result.request is None


def test_no_authority_created_by_k1():
    for i, text in enumerate(["P7.JAIL_READ", "calcule 2+2"]):
        res = run_turn([{"role": "user", "text": text}], "sess-8", 1000.0,
                       "session", request_id=f"k1-auth-{i}")
        if res.dispatch_result is not None and \
                res.dispatch_result.request is not None:
            decision = G.decide(res.dispatch_result.request, None, 1000.0,
                               True)
            assert decision.allowed is False
    import core.cognitive.session_input as bridge
    import ast
    from pathlib import Path
    tree = ast.parse(Path(bridge.__file__).read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert "core" in imported
    assert not any(m == "core.session" or m.startswith("core.session.")
                   for m in imported)
    from_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            from_names.update(a.name for a in node.names)
    assert "Approval" not in from_names
