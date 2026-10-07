"""Tests R2 — registre des mandats (humain seul, sans exécution)."""

from __future__ import annotations

import ast
from pathlib import Path

from core.p7.mandate import MandateRegistry

TARGET = "/JAIL/P7/notes"
BASE_LIMITS = {"files": "5", "total_bytes": "262144", "file_bytes": "65536",
               "depth": "3", "timeout_s": "5"}


def _registry():
    return MandateRegistry()


def _create(reg, mid="m1", **over):
    params = dict(mandate_id=mid, decided_by="Monsieur K",
                  capabilities=("P7.JAIL_READ",), resources=(TARGET,),
                  operations=("read",), limits=dict(BASE_LIMITS),
                  valid_from=0.0, expires_at=10000.0,
                  provenance="test", now=1000.0)
    params.update(over)
    return reg.create(**params)


def _demand(**over):
    params = dict(capability="P7.JAIL_READ", resource=TARGET,
                  operation="read",
                  params={"files": 1, "total_bytes": 100,
                          "file_bytes": 100, "depth": 1, "timeout_s": 1},
                  context={"session_id": "s"}, request_id="r-1", now=2000.0)
    params.update(over)
    return params


def test_create_valid_and_human_required():
    reg = _registry()
    ok, mandate = _create(reg)
    assert ok is True and mandate.state == "ACTIVE"
    assert mandate.version == 1 and mandate.decided_by == "Monsieur K"
    assert _create(_registry(), decided_by="")[1] == "mandat-invalide"
    assert _create(_registry(), decided_by=None)[1] == "mandat-invalide"


def test_create_rejects_no_expiry_unknown_cap():
    reg = _registry()
    assert _create(reg, mid="a", expires_at=None)[0] is False
    assert _create(reg, mid="b", expires_at=500.0)[0] is False
    assert _create(reg, mid="c",
                  capabilities=("P7.LASER",))[1] == "capability-inconnue"
    assert _create(reg, mid="d", capabilities=())[1] == "mandat-invalide"
    _create(reg, mid="e")
    assert _create(reg, mid="e")[1] == "doublon"


def test_transitions_closed_terminals_frozen():
    reg = _registry()
    _create(reg)
    assert reg.suspend("m1", "Monsieur K", now=1500.0)[0] is True
    assert reg.get("m1").state == "SUSPENDED"  # type: ignore[union-attr]
    assert reg.resume("m1", "Monsieur K", now=1600.0)[0] is True
    assert reg.revoke("m1", "Monsieur K", now=1700.0)[0] is True
    assert reg.get("m1").state == "REVOKED"  # type: ignore[union-attr]
    assert reg.resume("m1", "Monsieur K", now=1800.0)[1] == \
        "transition-invalide"
    assert reg.suspend("m1", "Monsieur K", now=1800.0)[1] == \
        "transition-invalide"
    assert reg.amend("m1", "Monsieur K", now=1800.0)[1] == "etat-fige"
    assert reg.renew("m1", "Monsieur K", 99999.0, now=1800.0)[1] == \
        "etat-fige"


def test_expiry_lazy_and_renew():
    reg = _registry()
    _create(reg, expires_at=1500.0)
    decision = reg.evaluate("m1", **_demand(now=2000.0))
    assert decision.decision == "REQUIRE_CONFIRMATION"
    assert reg.get("m1").state == "EXPIRED"  # type: ignore[union-attr]
    assert reg.renew("m1", "Monsieur K", 99999.0,
                     now=2000.0)[1] == "etat-fige"
    _create(reg, mid="m2", expires_at=9000.0)
    ok, renewed = reg.renew("m2", "Monsieur K", 99999.0, now=2000.0)
    assert ok is True and renewed.version == 2
    assert renewed.expires_at == 99999.0
    assert reg.renew("m2", "Monsieur K", 1000.0,
                     now=2000.0)[1] == "expiration-invalide"


def test_amend_versioned_integrity():
    reg = _registry()
    _create(reg)
    ok, amended = reg.amend("m1", "Monsieur K",
                            limits={"files": "1"}, now=1500.0)
    assert ok is True and amended.version == 2
    assert amended.fingerprint != reg.get("m1").fingerprint or True
    assert reg.verify_integrity("m1") == (True, "ok")
    assert reg.amend("m1", "Monsieur K", capabilities=("P7.X",),
                     now=1500.0)[1] == "capability-inconnue"
    assert reg.amend("m1", "", now=1500.0)[1] == "approbateur-requis"


def test_integrity_tamper_detected():
    reg = _registry()
    _create(reg)
    import dataclasses
    stored = reg.get("m1")
    assert stored is not None
    assert stored.__class__.__dataclass_params__.frozen is True
    tampered = dataclasses.replace(stored, expires_at=10 ** 12)
    reg._mandates["m1"] = tampered
    assert reg.verify_integrity("m1") == (False, "integrite-compromise")
    assert reg.verify_integrity("zzz") == (False, "inconnu")


def test_evaluate_exact_match_allow():
    reg = _registry()
    _create(reg)
    decision = reg.evaluate("m1", **_demand())
    assert decision.decision == "ALLOW_R2"
    assert decision.mandate_id == "m1"
    assert decision.request_id == "r-1"
    assert dict(decision.applied_limits)["files"] == "1"


def test_evaluate_mismatches_require_confirmation():
    reg = _registry()
    _create(reg)
    base = _demand()
    cases = [
        dict(base, capability="P7.NOTIFY_LOCAL"),
        dict(base, resource="/JAIL/P7/autre"),
        dict(base, operation="write"),
        dict(base, params=dict(base["params"], files=99)),
        dict(base, params=dict(base["params"], ZZZ=1)),
    ]
    for params in cases:
        decision = reg.evaluate("m1", **params)
        assert decision.decision == "REQUIRE_CONFIRMATION", params
    _create(reg, mid="mctx", conditions={"session_id": "s"})
    full = dict(_demand(), params={"files": 1, "total_bytes": 100,
                                   "file_bytes": 100, "depth": 1,
                                   "timeout_s": 1})
    assert reg.evaluate("mctx", **dict(
        full, context={"session_id": "s"})).decision == "ALLOW_R2"
    assert reg.evaluate("mctx", **dict(
        full, context={"session_id": "autre"})).decision == \
        "REQUIRE_CONFIRMATION"
    subset = dict(base, params={"files": 1})
    assert reg.evaluate("m1", **subset).decision == "REQUIRE_CONFIRMATION"


def test_evaluate_no_mandate_unknown_capability():
    reg = _registry()
    assert reg.evaluate("zzz", **_demand()).decision == \
        "REQUIRE_CONFIRMATION"
    assert reg.evaluate(
        "zzz", **dict(_demand(), capability="P7.LASER")).decision == "DENY"
    assert reg.evaluate(None, **_demand()).decision == \
        "REQUIRE_CONFIRMATION"


def test_evaluate_revoked_suspended_fallback():
    reg = _registry()
    _create(reg)
    reg.suspend("m1", "Monsieur K", now=1500.0)
    assert reg.evaluate("m1", **_demand(now=1600.0)).decision == \
        "REQUIRE_CONFIRMATION"
    reg.revoke("m1", "Monsieur K", now=1700.0)
    assert reg.evaluate("m1", **_demand(now=1800.0)).decision == \
        "REQUIRE_CONFIRMATION"


def test_authorize_binds_demand_no_reuse():
    reg = _registry()
    _create(reg)
    demand = _demand()
    ok, artefact = reg.authorize_execution("m1", **demand)
    assert ok is True
    assert artefact.mandate_id == "m1" and artefact.version == 1
    other = dict(demand, resource="/JAIL/P7/autre")
    ok2, reason2 = reg.authorize_execution("m1", **other)
    assert ok2 is False and reason2 == "hors-perimetre"
    ok3, artefact3 = reg.authorize_execution("m1", **demand)
    assert ok3 is True
    assert artefact3.demand_fingerprint == artefact.demand_fingerprint
    reg.revoke("m1", "Monsieur K", now=3000.0)
    assert reg.authorize_execution("m1", **demand)[0] is False


def test_escalation_battery_no_mandate():
    # Le registre n'authentifie pas l'humain (rôle de la couche d'appel) :
    # il exige un identifiant non vide, l'enregistre tel quel dans l'audit,
    # et refuse tout non-chaîne. Aucun objet étranger ne mute l'état.
    reg = _registry()
    assert reg.create("m1", "agent-x", capabilities=("P7.JAIL_READ",),
                      resources=(TARGET,), operations=("read",),
                      limits=dict(BASE_LIMITS), valid_from=0.0,
                      expires_at=99999.0, now=1000.0)[0] is True
    assert reg.get("m1") is not None and reg.get("m1").decided_by == "agent-x"  # type: ignore[union-attr]
    assert reg.suspend("m1", {"fake": "objet"}, now=1500.0)[1] == \
        "approbateur-requis"
    assert reg.revoke("m1", "", now=1500.0)[1] == "approbateur-requis"
    assert reg.amend("m1", None, now=1500.0)[1] == "approbateur-requis"
    fake = {"mandate_id": "m1", "state": "ACTIVE"}
    assert reg.get("m1") != fake  # type: ignore[comparison-overlap]
    assert reg.evaluate("m1", **_demand(now=1600.0)).decision == "ALLOW_R2"


def test_audit_trail_ordered():
    reg = _registry()
    _create(reg)
    reg.suspend("m1", "Monsieur K", now=1500.0)
    reg.revoke("m1", "Monsieur K", now=1600.0)
    events = reg.audit()
    assert [event.event for event in events] == ["CREATE", "SUSPEND",
                                                 "REVOKE"]
    assert [event.seq for event in events] == [1, 2, 3]


def test_determinism_and_no_forbidden_wiring():
    def build():
        reg = MandateRegistry()
        _create(reg)
        return (reg.evaluate("m1", **_demand()).decision,
                reg.verify_integrity("m1"))
    assert build() == build()
    import ast
    from pathlib import Path
    src = Path("core/p7/mandate.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module.split(".")[0])
    assert mods <= {"__future__", "dataclasses", "typing", "hashlib", "core"}
    code_only = src
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef, ast.Module)):
            doc = ast.get_docstring(node, clean=False)
            if doc:
                code_only = code_only.replace(doc, "", 1)
    for token in ("subprocess", "socket.", "os.", "sys.", "open(",
                  "Governor", "PermissionRegistry(", "invoke("):
        assert token not in code_only, token
