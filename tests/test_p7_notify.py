"""Tests NOTIFY_LOCAL — R2 strictement locale, single-use, zéro effet DENY."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

from core.p7 import errors as E
from core.p7 import notify as N
from core.p7 import resolver as R
from core.p7.journal import Journal
from core.p7.registry import Registry
from core.p7.types import Approval, Request

CHANNEL = N.channel_dir()


def _req(rid: str = "n-1", **over) -> Request:
    target = f"{CHANNEL}/{rid}.json"
    base = dict(request_id=rid, skill_id="s", skill_version="1",
                permission_id="P7.NOTIFY_LOCAL",
                scope=f"notification:{target}:textuel-borné",
                target=target,
                limits={"chars": 280, "per_request": 1, "timeout_s": 3},
                duration_s=300, reason="t")
    base.update(over)
    return Request(**base)


def _appr(req: Request, **over) -> Approval:
    base = dict(request_id=req.request_id, permission_id=req.permission_id,
                decision="accorde", scope=req.scope,
                duration_s=req.duration_s, reason="ok",
                capability_version=1, timestamp=1000.0)
    base.update(over)
    return Approval(**base)


def _snap() -> dict:
    out = {}
    for p in sorted(CHANNEL.parent.rglob("*")):
        try:
            if p.is_symlink():
                out[str(p)] = "SYMLINK"
            elif p.is_file():
                out[str(p)] = hashlib.sha256(p.read_bytes()).hexdigest()
        except OSError:
            out[str(p)] = "UNREADABLE"
    return out


def test_channel_created_only_here():
    ok, _, directory = N.ensure_channel()
    assert ok and directory == CHANNEL
    assert directory.is_dir() and not directory.is_symlink()


def test_exact_allow_280_boundary(tmp_path):
    N.reset_consumed()
    req = _req("n-ok-1")
    text = "a" * 280
    dec, detail = N.notify(req, _appr(req), 1010.0,
                           Journal(path=tmp_path / "j.jsonl"), text)
    assert dec.allowed is True and detail is not None
    assert (CHANNEL / "n-ok-1.json").read_text(encoding="utf-8") == text
    (CHANNEL / "n-ok-1.json").unlink()


def test_281_chars_deny_zero_effect(tmp_path):
    N.reset_consumed()
    before = _snap()
    req = _req("n-281")
    dec, detail = N.notify(req, _appr(req), 1010.0,
                           Journal(path=tmp_path / "j.jsonl"), "b" * 281)
    assert dec.allowed is False and detail is None
    assert _snap() == before


def test_second_notification_second_action_deny(tmp_path):
    N.reset_consumed()
    j = Journal(path=tmp_path / "j.jsonl")
    req = _req("n-once")
    assert N.notify(req, _appr(req), 1010.0, j, "first")[0].allowed is True
    dec2, _ = N.notify(req, _appr(req), 1010.0, j, "second")
    assert dec2.allowed is False
    assert (CHANNEL / "n-once.json").read_text(encoding="utf-8") == "first"
    (CHANNEL / "n-once.json").unlink()


def test_neighbor_channel_off_jail_absolute_dotdot_deny():
    N.reset_consumed()
    before = _snap()
    base = _req("n-nb")
    cases = [
        _req("n-nb", scope=f"notification:{CHANNEL.parent}:textuel-borné"),
        _req("n-nb", target="/tmp/n.json",
             scope="notification:/tmp/n.json:textuel-borné"),
        _req("n-nb", target=f"{CHANNEL}/../evil.json",
             scope=f"notification:{CHANNEL}/../evil.json:textuel-borné"),
        _req("n-nb", target=f"{CHANNEL}/n-nb.json",
             scope="notification:~/Wilfrid/JAIL/P7/autre/n-nb.json:textuel-borné"),
    ]
    for req in cases:
        dec, _ = N.notify(req, _appr(req), 1010.0, Journal(path=None), "hi")
        assert dec.allowed is False
    assert base is not None
    assert _snap() == before


def test_expiry_revocation_suspension_no_approval_deny():
    N.reset_consumed()
    before = _snap()
    req = _req("n-ers")
    assert N.notify(req, _appr(req, timestamp=1000.0, duration_s=60),
                    5000.0, Journal(path=None), "hi")[0].reason == E.APPROVAL_EXPIRED
    assert N.notify(req, _appr(req, revoked=True),
                    1010.0, Journal(path=None), "hi")[0].reason == E.CAPABILITY_REVOKED
    assert N.notify(req, _appr(req, suspended=True),
                    1010.0, Journal(path=None), "hi")[0].reason == E.CAPABILITY_SUSPENDED
    assert N.notify(req, None, 1010.0, Journal(path=None), "hi")[0].reason == E.APPROVAL_ABSENT
    assert _snap() == before


def test_wrong_scope_journal_down_timeout_deny(tmp_path):
    N.reset_consumed()
    before = _snap()
    req = _req("n-sc")
    bad = Request(**{**req.__dict__, "scope": "notification:déclaré:textuel-borné"})
    assert N.notify(bad, _appr(bad), 1010.0, Journal(path=None), "hi")[0].allowed is False
    req2 = _req("n-jd")
    assert N.notify(req2, _appr(req2), 1010.0, Journal(path=None), "hi")[0].reason == E.JOURNAL_UNAVAILABLE
    for to in (0, 6):
        req3 = _req(f"n-to-{to}", limits={"chars": 280, "per_request": 1, "timeout_s": to})
        assert N.notify(req3, _appr(req3), 1010.0,
                        Journal(path=tmp_path / f"j-{to}.jsonl"), "hi")[0].reason == E.LIMITS_INVALID
    assert _snap() == before


def test_secret_credential_sensitive_attachment_network_deny():
    N.reset_consumed()
    before = _snap()
    for i, text in enumerate(["le secret est ici", "api_key=ABC",
                              "voici mon Bearer xyz", "voir https://exemple.test/x",
                              "lance $(reboot)", "a;b", "ligne1\nligne2",
                              "mot de passe: hunter2"]):
        req = _req(f"n-f-{i}")
        dec, _ = N.notify(req, _appr(req), 1010.0, Journal(path=None), text)
        assert dec.allowed is False, text
    reqb = _req("n-bytes")
    decb, _ = N.notify(reqb, _appr(reqb), 1010.0, Journal(path=None), b"bytes")  # type: ignore[arg-type]
    assert decb.allowed is False
    assert _snap() == before


def test_exec_attempt_never_executes_no_network(tmp_path):
    N.reset_consumed()
    req = _req("n-inert")
    text = "rappel : verifier le rapport"
    dec, _ = N.notify(req, _appr(req), 1010.0,
                      Journal(path=tmp_path / "j.jsonl"), text)
    assert dec.allowed is True
    stored = (CHANNEL / "n-inert.json").read_text(encoding="utf-8")
    assert stored == text
    (CHANNEL / "n-inert.json").unlink()
    import core.p7.notify as mod
    tree = ast.parse(Path(mod.__file__).read_text(encoding="utf-8"))
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module.split(".")[0])
    assert not (mods & {"socket", "subprocess", "webbrowser", "os", "sys",
                        "sqlite3", "requests", "urllib", "ftplib", "httpx",
                        "shutil", "pty", "signal"})


def test_off_channel_write_attempt_deny():
    N.reset_consumed()
    before = _snap()
    outside = f"{R.jail_root()}/c3_outside.txt"
    req = _req("n-off", target=outside,
               scope=f"notification:{outside}:textuel-borné")
    dec, _ = N.notify(req, _appr(req), 1010.0, Journal(path=None), "hi")
    assert dec.allowed is False
    assert not (R.jail_root() / "c3_outside.txt").exists()
    assert _snap() == before


def test_registry_stays_empty_and_journal_clean(tmp_path):
    assert Registry().active_count() == 0
    jp = tmp_path / "j.jsonl"
    N.reset_consumed()
    req = _req("n-jc")
    N.notify(req, _appr(req), 1010.0, Journal(path=jp), "bonjour")
    lines = jp.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    doc = json.loads(lines[0])
    assert set(doc) <= {"timestamp", "event", "actor", "request_id",
                        "permission", "target", "decision", "reason",
                        "capability_version", "risk"}
    (CHANNEL / "n-jc.json").unlink()
