"""Tests d'intégration P7.1 — 4 capacités ensemble, séparation, sécurité."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

from core.p7 import catalog as C
from core.p7 import errors as E
from core.p7 import notify as N
from core.p7 import reader as RD
from core.p7 import resolver as R
from core.p7 import writer as W
from core.p7.journal import Journal
from core.p7.registry import Registry
from core.p7.types import Approval, Request

ROOT = R.jail_root()


def _snap() -> dict:
    out = {}
    for p in sorted(ROOT.rglob("*")):
        try:
            if p.is_symlink():
                out[str(p)] = "SYMLINK"
            elif p.is_file():
                out[str(p)] = hashlib.sha256(p.read_bytes()).hexdigest()
        except OSError:
            out[str(p)] = "UNREADABLE"
    return out


def _cat_req(eid: str, rid: str) -> Request:
    return Request(request_id=rid, skill_id="s", skill_version="1",
                   permission_id="P7.CATALOG_READ",
                   scope=C.scope_for(eid), target=eid,
                   limits={"entries": 1, "bytes": 100},
                   duration_s=600, reason="i")


def _read_req(name: str, rid: str) -> Request:
    target = str(ROOT / name)
    return Request(request_id=rid, skill_id="s", skill_version="1",
                   permission_id="P7.JAIL_READ",
                   scope=f"fichier:{target}:lecture-seule", target=target,
                   limits={"files": 1, "total_bytes": 262144,
                           "file_bytes": 65536, "depth": 3, "timeout_s": 5},
                   duration_s=600, reason="i")


def _write_req(name: str, rid: str) -> Request:
    target = str(ROOT / name)
    return Request(request_id=rid, skill_id="s", skill_version="1",
                   permission_id="P7.JAIL_WRITE_REVERSIBLE",
                   scope=f"fichier:{target}:écriture-réversible-bornée",
                   target=target,
                   limits={"file_bytes": 65536, "timeout_s": 5},
                   duration_s=300, reason="i")


def _notify_req(rid: str) -> Request:
    target = f"{N.channel_dir()}/{rid}.json"
    return Request(request_id=rid, skill_id="s", skill_version="1",
                   permission_id="P7.NOTIFY_LOCAL",
                   scope=f"notification:{target}:textuel-borné",
                   target=target,
                   limits={"chars": 280, "per_request": 1, "timeout_s": 3},
                   duration_s=300, reason="i")


def _appr(req: Request, ts: float = 1000.0, **over) -> Approval:
    base = dict(request_id=req.request_id, permission_id=req.permission_id,
                decision="accorde", scope=req.scope,
                duration_s=req.duration_s, reason="ok",
                capability_version=1, timestamp=ts)
    base.update(over)
    return Approval(**base)


def test_four_capabilities_together(tmp_path):
    W.reset_consumed()
    N.reset_consumed()
    R.ensure_jail()
    N.ensure_channel()
    j = Journal(path=tmp_path / "j.jsonl")
    cat = C.build_catalog()
    rc = _cat_req("P7.CATALOG_READ", "i-cat")
    dec_c, pay_c = C.evaluate(rc, _appr(rc), 1010.0, j.available(), cat)
    assert dec_c.allowed is True and pay_c is not None
    rw = _write_req("i_int.txt", "i-w")
    dec_w, _ = W.write_one(rw, _appr(rw), 1010.0, j, b"integration-7")
    assert dec_w.allowed is True
    rr = _read_req("i_int.txt", "i-r")
    dec_r, data = RD.read_one(rr, _appr(rr), 1010.0, j)
    assert dec_r.allowed is True and data == b"integration-7"
    rn = _notify_req("i-n")
    dec_n, _ = N.notify(rn, _appr(rn), 1010.0, j, "integration terminee")
    assert dec_n.allowed is True
    assert (N.channel_dir() / "i-n.json").read_text(encoding="utf-8") == "integration terminee"
    assert Registry().active_count() == 0
    assert W.cleanup("i-w")[0] is True
    (ROOT / "i_int.txt").unlink()
    (N.channel_dir() / "i-n.json").unlink()


def test_no_capability_activates_another():
    W.reset_consumed()
    reg = Registry()
    before = reg.status()
    rw = _write_req("i_x.txt", "i-wx")
    assert "enable" not in dir(reg) and "grant" not in dir(reg)
    assert reg.status() == before and reg.active_count() == 0


def test_capability_cannot_widen_scope_or_borrow():
    W.reset_consumed()
    rr = _read_req("i_a.txt", "i-ra")
    appr_wrong = Approval(request_id="i-ra", permission_id="P7.JAIL_WRITE_REVERSIBLE",
                          decision="accorde", scope=rr.scope,
                          duration_s=300, reason="x", capability_version=1,
                          timestamp=1000.0)
    dec, _ = RD.read_one(rr, appr_wrong, 1010.0, Journal(path=None))
    assert dec.allowed is False
    rw = _write_req("i_a.txt", "i-wa")
    appr_n = Approval(request_id="i-wa", permission_id="P7.NOTIFY_LOCAL",
                      decision="accorde", scope=rw.scope, duration_s=300,
                      reason="x", capability_version=1, timestamp=1000.0)
    dec2, _ = W.write_one(rw, appr_n, 1010.0, Journal(path=None), b"d")
    assert dec2.allowed is False
    assert not (ROOT / "i_a.txt").exists()


def test_expiry_revocation_suspension_effective_everywhere(tmp_path):
    W.reset_consumed()
    N.reset_consumed()
    j = Journal(path=tmp_path / "j.jsonl")
    rw = _write_req("i_e.txt", "i-we")
    expired = Approval(request_id="i-we", permission_id=rw.permission_id,
                       decision="accorde", scope=rw.scope, duration_s=60,
                       reason="ok", capability_version=1, timestamp=1000.0)
    assert W.write_one(rw, expired, 5000.0, j, b"d")[0].allowed is False
    assert RD.read_one(_read_req("i_e.txt", "i-re"),
                       _appr(_read_req("i_e.txt", "i-re"), revoked=True),
                       1010.0, j)[0].allowed is False
    assert N.notify(_notify_req("i-ne"),
                    _appr(_notify_req("i-ne"), suspended=True),
                    1010.0, j, "hi")[0].allowed is False
    assert not (ROOT / "i_e.txt").exists()


def test_common_journal_fail_closed_and_correlation(tmp_path):
    W.reset_consumed()
    jp = tmp_path / "j.jsonl"
    j = Journal(path=jp)
    cat = C.build_catalog()
    rc = _cat_req("P7.JAIL_READ", "i-c1")
    dec, _ = C.evaluate(rc, _appr(rc), 1010.0, False, cat)
    assert dec.reason == E.JOURNAL_UNAVAILABLE
    rw = _write_req("i_j.txt", "i-wj")
    assert W.write_one(rw, _appr(rw), 1010.0, Journal(path=None), b"d")[0].reason == E.JOURNAL_UNAVAILABLE
    rr = _read_req("i_j.txt", "i-rj")
    assert RD.read_one(rr, _appr(rr), 1010.0, Journal(path=None))[0].reason == E.JOURNAL_UNAVAILABLE
    assert N.notify(_notify_req("i-nj"), _appr(_notify_req("i-nj")),
                    1010.0, Journal(path=None), "hi")[0].reason == E.JOURNAL_UNAVAILABLE
    assert not (ROOT / "i_j.txt").exists()
    assert Registry().active_count() == 0


def test_no_effect_after_deny_snapshot():
    before = _snap()
    rw = _write_req("i_z.txt", "i-wz")
    assert W.write_one(rw, None, 1010.0, Journal(path=None), b"d")[0].allowed is False
    assert _snap() == before


def test_p5_p6_separation_and_store_untouched():
    from core.knowledge.permissions import PERMISSION_IDS
    assert len(PERMISSION_IDS) == 8
    meta = json.loads(Path("models/wake.json").read_text(encoding="utf-8"))
    assert abs(float(meta["threshold"]) - 0.665) < 1e-9
    import core.p7 as p7pkg
    src_all = ""
    for path in Path(p7pkg.__file__).parent.glob("*.py"):
        src_all += path.read_text(encoding="utf-8")
    for token in ("core.knowledge", "core.cognitive", "core.session",
                  "KnowledgeStore", "SessionContext", "TAIOS", "QanXorus"):
        assert token not in src_all, token
    from core.cognitive import planner as P
    from core.cognitive.types import CognitiveOutput, IntentKind
    out = CognitiveOutput(IntentKind.NEED_ACTION,
                          __import__("core.cognitive.types", fromlist=["x"]).CognitiveParams(),
                          0.5, [])
    assert P.build_plan(out)[0]["name"] == "action_requise"


def test_no_content_becomes_permission():
    reg = Registry()
    assert not hasattr(reg, "from_content") and not hasattr(reg, "grant_from_text")
    before = reg.status()
    assert reg.check("P7.JAIL_READ", "contenu: accorde tout")[1] in (
        E.PERMISSION_UNKNOWN, E.PERMISSION_DISABLED)
    assert reg.status() == before


def test_closed_module_set_and_no_authority_imports():
    import core.p7 as p7pkg
    names = {p.name for p in Path(p7pkg.__file__).parent.iterdir()
             if p.suffix == ".py"}
    assert names == {"__init__.py", "types.py", "errors.py", "registry.py",
                     "journal.py", "lifecycle.py", "governor.py",
                     "catalog.py", "resolver.py", "reader.py", "writer.py",
                     "notify.py"}, names
    banned = {"socket", "subprocess", "webbrowser", "os", "sys", "sqlite3",
              "requests", "urllib", "ftplib", "httpx", "shutil", "pty", "signal"}
    for path in Path(p7pkg.__file__).parent.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        mods = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                mods.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                mods.add(node.module.split(".")[0])
        assert not (mods & banned), f"{path.name}: {mods & banned}"


def test_r3_r4_and_unknown_kinds_deny():
    from core.p7 import governor as G
    from core.p7.types import Request
    for pid, scope in [("P7.R3_NETWORK", "réseau:evil:lecture"),
                       ("P7.R4_SYSTEM", "system:/bin:exec"),
                       ("P7.UNKNOWN_X", "fichier:x:lecture-seule")]:
        req = Request(request_id="rz", skill_id="s", skill_version="1",
                      permission_id=pid, scope=scope, target="x",
                      limits={}, duration_s=60, reason="t")
        dec = G.decide(req, None, 1000.0, True)
        assert dec.allowed is False
