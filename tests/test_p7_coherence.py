"""Tests K-γ — vérificateur de cohérence (pur, vocabulaire fermé, 0 I/O)."""

from __future__ import annotations

import ast
from pathlib import Path

from core.p7 import coherence as C
from core.p7.audit import AuditRecord


def _ev(event: str, decision: str, version: int = 1) -> dict:
    return {"event": event, "decision": decision, "capability_version": version,
            "permission": "P7.JAIL_READ", "target": "t", "reason": "ok"}


def _rec(**over) -> AuditRecord:
    base = dict(request_id="r-1", p7_present=True, p6_present=False,
                session_present=False, p7_events=(), p6_events=(),
                session_events=(), corrupt_lines=0, reason="ok")
    base.update(over)
    return AuditRecord(**base)


def test_coherent_nominal():
    rec = _rec(p7_events=(_ev("pre-read", "ALLOW"), _ev("proof", "ALLOW")))
    verdict = C.verify(rec)
    assert verdict.verdict == C.COHERENT == "COHERENT"
    assert verdict.reason == "ok"


def test_incoherent_conflicting_decisions():
    rec = _rec(p7_events=(_ev("proof", "ALLOW"), _ev("proof", "DENY")))
    verdict = C.verify(rec)
    assert verdict.verdict == C.INCOHERENT == "INCOHERENT"
    assert verdict.reason == "conflicting-decisions"


def test_sequence_allow_then_error_is_coherent():
    rec = _rec(p7_events=(_ev("pre-read", "ALLOW"), _ev("error", "DENY")))
    assert C.verify(rec).verdict == "COHERENT"


def test_incomplete_no_traces():
    rec = _rec(p7_present=False, p7_events=())
    verdict = C.verify(rec)
    assert verdict.verdict == C.INCOMPLET == "INCOMPLET"
    assert verdict.reason == "no-decision-trace"


def test_incomplete_partial_observation():
    rec = _rec(p7_events=(_ev("proof", "ALLOW"),), corrupt_lines=2)
    verdict = C.verify(rec)
    assert verdict.verdict == "INCOMPLET"
    assert verdict.reason == "partial-observation"


def test_incoherent_beats_partial():
    rec = _rec(p7_events=(_ev("proof", "ALLOW"), _ev("proof", "DENY")),
               corrupt_lines=3)
    assert C.verify(rec).verdict == "INCOHERENT"


def test_invalid_records_controlled():
    assert C.verify(None).reason == "invalid-record"
    assert C.verify("texte").reason == "invalid-record"
    assert C.verify(_rec(request_id="")).reason == "invalid-record"
    assert C.verify(_rec(request_id=None)).reason == "invalid-record"


def test_unhashable_and_malformed_entries_controlled():
    rec = _rec(p7_events=({"event": "proof", "decision": "ALLOW",
                           "capability_version": ["v1"]},))
    assert C.verify(rec).verdict == "COHERENT"
    rec2 = _rec(p7_events=("pas-un-dict",))
    assert C.verify(rec2).verdict in ("COHERENT", "INCOMPLET")
    assert C.verify_many("nope")[0].reason == "invalid-record"


def test_verify_many_order_deterministic():
    recs = (_rec(request_id="a",
                 p7_events=(_ev("proof", "ALLOW"),)),
            _rec(request_id="b", p7_events=()))
    first = C.verify_many(recs)
    second = C.verify_many(recs)
    assert first == second
    assert tuple(v.verdict for v in first) == ("COHERENT", "INCOMPLET")


def test_determinism():
    rec = _rec(p7_events=(_ev("pre-read", "ALLOW"), _ev("proof", "ALLOW")))
    assert C.verify(rec) == C.verify(rec)


def test_no_io_no_authority_in_module():
    src = Path(__import__("core.p7.coherence", fromlist=["x"]).__file__).read_text(
        encoding="utf-8")
    tree = ast.parse(src)
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module.split(".")[0])
    assert mods <= {"__future__", "dataclasses", "typing"}
    assert "core" not in mods
    for token in ("open(", "read_bytes", "write_bytes", "unlink(", "mkdir(",
                  "decide(", "Approval(", "Journal(", "socket", "subprocess",
                  "os.", "sys."):
        assert token not in src, token


def test_end_to_end_audit_then_verify(tmp_path):
    from core.p7 import audit as A
    import json
    p7 = tmp_path / "p7.jsonl"
    with open(p7, "ab") as fh:
        fh.write((json.dumps(
            {"request_id": "r-e2e", "event": "proof", "decision": "ALLOW",
             "capability_version": 1}) + "\n").encode())
    rec = A.audit("r-e2e", p7_path=p7)
    assert rec.p7_present
    assert C.verify(rec).verdict == "COHERENT"
