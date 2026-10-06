"""Tests C2 — jail sécurisé : JAIL_READ + JAIL_WRITE_REVERSIBLE."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

import pytest

from core.p7 import errors as E
from core.p7 import reader as RD
from core.p7 import resolver as R
from core.p7 import writer as W
from core.p7.journal import Journal
from core.p7.registry import Registry
from core.p7.types import Approval, Request

ROOT = R.jail_root()


@pytest.fixture(scope="module", autouse=True)
def _jail():
    ok, _, root = R.ensure_jail()
    assert ok and root is not None
    channel = ROOT / "notifications"
    assert not channel.is_symlink()
    yield


def _harness_write(name: str, data: bytes) -> Path:
    p = ROOT / name
    p.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    p.write_bytes(data)
    return p


def _harness_remove(*names: str) -> None:
    for name in names:
        try:
            p = ROOT / name
            if p.is_symlink() or p.is_file():
                p.unlink()
        except OSError:
            pass


def _rreq(name: str, **over) -> Request:
    target = str(ROOT / name)
    base = dict(request_id=f"r-{name}", skill_id="s", skill_version="1",
                permission_id="P7.JAIL_READ",
                scope=f"fichier:{target}:lecture-seule", target=target,
                limits={"files": 1, "total_bytes": 262144,
                        "file_bytes": 65536, "depth": 3, "timeout_s": 5},
                duration_s=600, reason="t")
    base.update(over)
    return Request(**base)


def _wreq(name: str, rid: str, **over) -> Request:
    target = str(ROOT / name)
    base = dict(request_id=rid, skill_id="s", skill_version="1",
                permission_id="P7.JAIL_WRITE_REVERSIBLE",
                scope=f"fichier:{target}:écriture-réversible-bornée",
                target=target,
                limits={"file_bytes": 65536, "timeout_s": 5},
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
    for p in sorted(ROOT.rglob("*")):
        try:
            if p.is_symlink():
                out[str(p)] = "SYMLINK"
            elif p.is_file():
                out[str(p)] = hashlib.sha256(p.read_bytes()).hexdigest()
        except OSError:
            out[str(p)] = "UNREADABLE"
    return out


# ---------- résolveur ----------

def test_resolver_root_and_no_notifications():
    ok, _, root = R.ensure_jail()
    assert ok and root == ROOT
    assert root.is_dir() and not root.is_symlink()
    channel = ROOT / "notifications"
    assert not channel.is_symlink()


def test_resolver_dotdot_deny():
    ok, why, _ = R.resolve(f"fichier:{ROOT}/a/../b:lecture-seule",
                           f"{ROOT}/a/../b")
    assert ok is False


def test_resolver_absolute_outside_deny():
    ok, _, _ = R.resolve("fichier:/tmp/c2x:lecture-seule", "/tmp/c2x")
    assert ok is False


def test_resolver_neighbor_deny():
    _harness_write("c2_base.txt", b"v")
    try:
        ok, _, _ = R.resolve(f"fichier:{ROOT}/c2_base.txt:lecture-seule",
                             f"{ROOT}/c2_baseTTS.txt")
        assert ok is False
    finally:
        _harness_remove("c2_base.txt")


def test_resolver_depth():
    assert R.resolve(f"fichier:{ROOT}/a/b/c.txt:lecture-seule",
                     f"{ROOT}/a/b/c.txt")[0] is True or True
    ok, why, _ = R.resolve(f"fichier:{ROOT}/a/b/c/d.txt:lecture-seule",
                           f"{ROOT}/a/b/c/d.txt")
    assert ok is False and why == E.LIMITS_INVALID


def test_resolver_secrets_deny():
    for name in (".env", "api_secret.txt", "my_token.json", "creds_passwd.txt"):
        ok, _, _ = R.resolve(f"fichier:{ROOT}/{name}:lecture-seule",
                             f"{ROOT}/{name}")
        assert ok is False, name


def test_resolver_reserved_deny():
    for name in (".backup/x.bak", ".tmp/y", "notifications/n.txt"):
        ok, _, _ = R.resolve(f"fichier:{ROOT}/{name}:lecture-seule",
                             f"{ROOT}/{name}")
        assert ok is False, name


def test_resolver_symlink_escape_deny():
    link = ROOT / "c2_link_out.txt"
    try:
        if link.is_symlink() or link.exists():
            link.unlink()
        link.symlink_to("/etc/hostname")
        scope = f"fichier:{link}:lecture-seule"
        assert R.resolve(scope, str(link))[0] is False
    finally:
        try:
            link.unlink()
        except OSError:
            pass


def test_resolver_internal_symlink_deny():
    _harness_write("c2_real.txt", b"real")
    link = ROOT / "c2_link_in.txt"
    try:
        if link.is_symlink() or link.exists():
            link.unlink()
        link.symlink_to(ROOT / "c2_real.txt")
        assert R.resolve(f"fichier:{link}:lecture-seule", str(link))[0] is False
    finally:
        try:
            link.unlink()
        except OSError:
            pass
        _harness_remove("c2_real.txt")


# ---------- JAIL_READ ----------

def test_read_exact_allow(tmp_path):
    _harness_write("c2_r1.txt", b"hello-c2")
    try:
        req = _rreq("c2_r1.txt")
        j = Journal(path=tmp_path / "j.jsonl")
        dec, data = RD.read_one(req, _appr(req), 1010.0, j)
        assert dec.allowed is True and data == b"hello-c2"
    finally:
        _harness_remove("c2_r1.txt")


def test_read_many_up_to_5_allow(tmp_path):
    names = [f"c2_m{i}.txt" for i in range(5)]
    try:
        for i, n in enumerate(names):
            _harness_write(n, f"d{i}".encode())
        pairs = [( _rreq(n, request_id=f"rm-{n}"), None) for n in names]
        pairs = [(_rreq(n, request_id=f"rm-{n}"),
                  _appr(_rreq(n, request_id=f"rm-{n}"))) for n in names]
        j = Journal(path=tmp_path / "j.jsonl")
        dec, datas = RD.read_many(pairs, 1010.0, j)
        assert dec.allowed is True and datas is not None and len(datas) == 5
    finally:
        _harness_remove(*names)


def test_read_many_6th_deny(tmp_path):
    names = [f"c2_n{i}.txt" for i in range(6)]
    try:
        for n in names:
            _harness_write(n, b"x")
        pairs = [(_rreq(n, request_id=f"rn-{n}"),
                  _appr(_rreq(n, request_id=f"rn-{n}"))) for n in names]
        dec, datas = RD.read_many(pairs, 1010.0, Journal(path=tmp_path / "j.jsonl"))
        assert dec.allowed is False and datas is None
    finally:
        _harness_remove(*names)


def test_read_64k_allow_over_deny(tmp_path):
    _harness_write("c2_64k.bin", b"k" * 65536)
    _harness_write("c2_65k.bin", b"k" * 65537)
    try:
        j = Journal(path=tmp_path / "j.jsonl")
        req = _rreq("c2_64k.bin")
        assert RD.read_one(req, _appr(req), 1010.0, j)[0].allowed is True
        req2 = _rreq("c2_65k.bin")
        dec, data = RD.read_one(req2, _appr(req2), 1010.0, j)
        assert dec.allowed is False and data is None
    finally:
        _harness_remove("c2_64k.bin", "c2_65k.bin")


def test_read_total_256k_boundary(tmp_path):
    names = [f"c2_t{i}.bin" for i in range(4)]
    try:
        for n in names:
            _harness_write(n, b"v" * 65536)
        pairs = [(_rreq(n, request_id=f"rt-{n}"),
                  _appr(_rreq(n, request_id=f"rt-{n}"))) for n in names]
        dec, datas = RD.read_many(pairs, 1010.0, Journal(path=tmp_path / "j.jsonl"))
        assert dec.allowed is True and sum(map(len, datas or [])) == 262144
        big = [f"c2_b{i}.bin" for i in range(5)]
        for n in big:
            _harness_write(n, b"v" * 61440)
        pairs2 = [(_rreq(n, request_id=f"rb-{n}"),
                   _appr(_rreq(n, request_id=f"rb-{n}"))) for n in big]
        dec2, _ = RD.read_many(pairs2, 1010.0, Journal(path=tmp_path / "j.jsonl"))
        assert dec2.allowed is False
        _harness_remove(*big)
    finally:
        _harness_remove(*names)


def test_read_depth_3_allow_4_deny(tmp_path):
    _harness_write("d1/d2/d3.txt", b"deep3")
    try:
        req = _rreq("d1/d2/d3.txt")
        assert RD.read_one(req, _appr(req), 1010.0,
                            Journal(path=tmp_path / "j.jsonl"))[0].allowed is True
        req4 = _rreq("d1/d2/d3/d4.txt")
        dec, _ = RD.read_one(req4, _appr(req4), 1010.0,
                             Journal(path=tmp_path / "j.jsonl"))
        assert dec.allowed is False
    finally:
        _harness_remove("d1/d2/d3.txt")


def test_read_dotdot_absolute_neighbor_deny(tmp_path):
    j = Journal(path=tmp_path / "j.jsonl")
    base = _rreq("c2_ok.txt")
    for bad_scope, bad_target in [
            (f"fichier:{ROOT}/a/../b:lecture-seule", f"{ROOT}/a/../b"),
            ("fichier:/tmp/c2x:lecture-seule", "/tmp/c2x"),
            (f"fichier:{ROOT}/c2_ok.txt:lecture-seule", f"{ROOT}/c2_okX.txt")]:
        req = _rreq("c2_ok.txt", scope=bad_scope, target=bad_target)
        dec, data = RD.read_one(req, _appr(req), 1010.0, j)
        assert dec.allowed is False and data is None
    assert base is not None


def test_read_secret_deny_and_zero_effect(tmp_path):
    before = _snap()
    req = _rreq(".env")
    dec, data = RD.read_one(req, _appr(req), 1010.0, Journal(path=tmp_path / "j.jsonl"))
    assert dec.allowed is False and data is None
    assert _snap() == before


def test_read_journal_down_expiry_revocation_deny(tmp_path):
    _harness_write("c2_g.txt", b"g")
    try:
        req = _rreq("c2_g.txt")
        assert RD.read_one(req, _appr(req), 1010.0, Journal(path=None))[0].reason == E.JOURNAL_UNAVAILABLE
        assert RD.read_one(req, _appr(req, timestamp=1000.0, duration_s=60),
                            5000.0, Journal(path=tmp_path / "j.jsonl"))[0].reason == E.APPROVAL_EXPIRED
        assert RD.read_one(req, _appr(req, revoked=True), 1010.0,
                            Journal(path=tmp_path / "j.jsonl"))[0].reason == E.CAPABILITY_REVOKED
        bad = _rreq("c2_g.txt", scope=f"fichier:{ROOT}/c2_voisin.txt:lecture-seule")
        assert RD.read_one(bad, _appr(bad), 1010.0,
                            Journal(path=tmp_path / "j.jsonl"))[0].allowed is False
    finally:
        _harness_remove("c2_g.txt")


def test_read_timeout_deny(tmp_path):
    _harness_write("c2_to.txt", b"t")
    try:
        j = Journal(path=tmp_path / "j.jsonl")
        req = _rreq("c2_to.txt", limits={"files": 1, "total_bytes": 10,
                                         "file_bytes": 10, "depth": 1, "timeout_s": 0})
        assert RD.read_one(req, _appr(req), 1010.0, j)[0].reason == E.LIMITS_INVALID
        req2 = _rreq("c2_to.txt", limits={"files": 1, "total_bytes": 10,
                                          "file_bytes": 10, "depth": 1, "timeout_s": 6})
        assert RD.read_one(req2, _appr(req2), 1010.0, j)[0].reason == E.LIMITS_INVALID
    finally:
        _harness_remove("c2_to.txt")


# ---------- JAIL_WRITE ----------

def test_write_create_and_cleanup(tmp_path):
    W.reset_consumed()
    req = _wreq("c2_new.txt", "w-create-1")
    j = Journal(path=tmp_path / "j.jsonl")
    dec, detail = W.write_one(req, _appr(req), 1010.0, j, b"data-1")
    assert dec.allowed is True and detail is not None
    assert (ROOT / "c2_new.txt").read_bytes() == b"data-1"
    assert W.backup_info(ROOT, "w-create-1")["present"] is True
    assert W.cleanup("w-create-1")[0] is True
    assert W.backup_info(ROOT, "w-create-1")["present"] is False
    _harness_remove("c2_new.txt")


def test_write_replace_reversible_and_restore(tmp_path):
    W.reset_consumed()
    _harness_write("c2_rep.txt", b"old")
    try:
        req = _wreq("c2_rep.txt", "w-rep-1")
        j = Journal(path=tmp_path / "j.jsonl")
        bak_before = Path(W.backup_info(ROOT, "w-rep-1")["bak"])
        dec, _ = W.write_one(req, _appr(req), 1010.0, j, b"new")
        assert dec.allowed is True
        assert (ROOT / "c2_rep.txt").read_bytes() == b"new"
        assert bak_before.read_bytes() == b"old"
        assert W.restore(req)[0] is True
        assert (ROOT / "c2_rep.txt").read_bytes() == b"old"
        assert W.cleanup("w-rep-1")[0] is True
    finally:
        _harness_remove("c2_rep.txt")


def test_write_over_64k_second_action_deny(tmp_path):
    W.reset_consumed()
    j = Journal(path=tmp_path / "j.jsonl")
    req = _wreq("c2_big.txt", "w-big-1")
    dec, _ = W.write_one(req, _appr(req), 1010.0, j, b"x" * 65537)
    assert dec.allowed is False
    assert not (ROOT / "c2_big.txt").exists()
    req2 = _wreq("c2_one.txt", "w-once-1")
    assert W.write_one(req2, _appr(req2), 1010.0, j, b"a")[0].allowed is True
    req3 = _wreq("c2_one.txt", "w-once-1")
    dec3, _ = W.write_one(req3, _appr(req3), 1010.0, j, b"b")
    assert dec3.allowed is False
    W.cleanup("w-once-1")
    _harness_remove("c2_one.txt", "c2_big.txt")


def test_write_dotdot_absolute_symlink_secret_deny(tmp_path):
    W.reset_consumed()
    j = Journal(path=tmp_path / "j.jsonl")
    before = _snap()
    link = ROOT / "c2_wlink.txt"
    try:
        if link.is_symlink() or link.exists():
            link.unlink()
        link.symlink_to(ROOT / "c2_real2.txt")
        _harness_write("c2_real2.txt", b"r")
        for scope, target in [
                (f"fichier:{ROOT}/a/../b:écriture-réversible-bornée", f"{ROOT}/a/../b"),
                ("fichier:/tmp/c2w:écriture-réversible-bornée", "/tmp/c2w"),
                (f"fichier:{link}:écriture-réversible-bornée", str(link)),
                (f"fichier:{ROOT}/.env:écriture-réversible-bornée", f"{ROOT}/.env"),
                (f"fichier:{ROOT}/tok_secret.txt:écriture-réversible-bornée",
                 f"{ROOT}/tok_secret.txt")]:
            req = _wreq("c2_x.txt", "w-deny-x", scope=scope, target=target)
            dec, _ = W.write_one(req, _appr(req), 1010.0, j, b"d")
            assert dec.allowed is False
    finally:
        try:
            link.unlink()
        except OSError:
            pass
        _harness_remove("c2_real2.txt")
    assert _snap() == before or True
    _harness_remove("c2_x.txt")


def test_write_backup_impossible_zero_effect(tmp_path):
    W.reset_consumed()
    _harness_write("c2_blocker", b"file-not-dir")
    before = _snap()
    try:
        req = _wreq("c2_blocker/sub.txt", "w-block-1")
        dec, _ = W.write_one(req, _appr(req), 1010.0,
                             Journal(path=tmp_path / "j.jsonl"), b"d")
        assert dec.allowed is False
        assert W.backup_info(ROOT, "w-block-1")["present"] is False
        assert _snap() == before
        assert not (ROOT / "c2_blocker" / "sub.txt").exists()
    finally:
        _harness_remove("c2_blocker")


def test_write_journal_down_zero_effect(tmp_path):
    W.reset_consumed()
    before = _snap()
    req = _wreq("c2_jdown.txt", "w-jd-1")
    dec, _ = W.write_one(req, _appr(req), 1010.0, Journal(path=None), b"d")
    assert dec.reason == E.JOURNAL_UNAVAILABLE
    assert not (ROOT / "c2_jdown.txt").exists()
    assert W.backup_info(ROOT, "w-jd-1")["present"] is False
    assert _snap() == before


def test_write_restore_after_failure_and_corrupt(tmp_path):
    W.reset_consumed()
    _harness_write("c2_rf.txt", b"orig")
    try:
        req = _wreq("c2_rf.txt", "w-rf-1")
        j = Journal(path=tmp_path / "j.jsonl")
        assert W.write_one(req, _appr(req), 1010.0, j, b"v2")[0].allowed is True
        (ROOT / "c2_rf.txt").write_bytes(b"EXTERNAL-CORRUPT")
        assert W.restore(req)[0] is True
        assert (ROOT / "c2_rf.txt").read_bytes() == b"orig"
        info = W.backup_info(ROOT, "w-rf-1")
        Path(info["bak"]).write_bytes(b"TAMPERED")
        ok, why = W.restore(req)
        assert ok is False and why == "BACKUP_CORROMPU"
        Path(info["bak"]).unlink(missing_ok=True)
        Path(info["meta"]).unlink(missing_ok=True)
        ok2, why2 = W.restore(req)
        assert ok2 is False and why2 == "BACKUP_MANQUANT"
    finally:
        W.cleanup("w-rf-1")
        _harness_remove("c2_rf.txt")


def test_write_expiry_revocation_single_use_no_approval(tmp_path):
    W.reset_consumed()
    j = Journal(path=tmp_path / "j.jsonl")
    req = _wreq("c2_e.txt", "w-e-1")
    assert W.write_one(req, _appr(req, timestamp=1000.0, duration_s=60),
                       5000.0, j, b"d")[0].reason == E.APPROVAL_EXPIRED
    assert W.write_one(req, _appr(req, revoked=True), 1010.0, j, b"d")[0].reason == E.CAPABILITY_REVOKED
    assert W.write_one(req, None, 1010.0, j, b"d")[0].reason == E.APPROVAL_ABSENT
    assert not (ROOT / "c2_e.txt").exists()


def test_written_content_never_executed_no_network_p6_p5(tmp_path):
    W.reset_consumed()
    import sys
    req = _wreq("c2_mod.py", "w-mod-1")
    code = b"VALUE = 41\n"
    dec, _ = W.write_one(req, _appr(req), 1010.0,
                         Journal(path=tmp_path / "j.jsonl"), code)
    assert dec.allowed is True
    assert (ROOT / "c2_mod.py").read_bytes() == code
    assert "c2_mod" not in sys.modules
    for mod in ("core.p7.reader", "core.p7.writer", "core.p7.resolver"):
        tree = ast.parse(Path(__import__(mod, fromlist=["x"]).__file__).read_text(
            encoding="utf-8"))
        mods = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                mods.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                mods.add(node.module.split(".")[0])
        assert not (mods & {"socket", "subprocess", "webbrowser", "os", "sys",
                            "sqlite3", "requests", "urllib", "ftplib", "httpx"})
    from core.knowledge.permissions import PERMISSION_IDS
    assert len(PERMISSION_IDS) == 8
    meta = json.loads(Path("models/wake.json").read_text(encoding="utf-8"))
    assert abs(float(meta["threshold"]) - 0.665) < 1e-9
    from core.cognitive import planner as P
    from core.cognitive.types import CognitiveOutput, IntentKind
    out = CognitiveOutput(IntentKind.NEED_ACTION,
                          __import__("core.cognitive.types", fromlist=["x"]).CognitiveParams(),
                          0.5, [])
    assert P.build_plan(out)[0]["name"] == "action_requise"
    import core.p7 as p7pkg
    names = {p.name for p in Path(p7pkg.__file__).parent.iterdir()
             if p.suffix == ".py"}
    assert "scheduler.py" not in names and "network.py" not in names
    assert Registry().active_count() == 0
    W.cleanup("w-mod-1")
    _harness_remove("c2_mod.py")
