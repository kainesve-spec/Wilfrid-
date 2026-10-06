"""Tests P6.1 — permissions (refus par défaut, activation explicite)."""

from __future__ import annotations

from core.knowledge.permissions import PERMISSION_IDS, PermissionRegistry


def test_absent_permission_denied():
    reg = PermissionRegistry()
    allowed, reason = reg.check("NOPE")
    assert allowed is False and reason == "unknown-permission"


def test_disabled_permission_denied():
    reg = PermissionRegistry()
    for pid in PERMISSION_IDS:
        allowed, reason = reg.check(pid, target="x")
        assert allowed is False and reason == "disabled"


def test_explicit_enable_and_revoke():
    logged = []
    reg = PermissionRegistry(
        log_callback=lambda **kw: logged.append(kw))
    perm = reg.enable("SOURCE_ACCESS", scope="example",
                      limits={"max_mb": 50}, reason="test")
    assert perm.enabled is True and perm.scope == "example"
    assert perm.limits == {"max_mb": 50} and perm.version == 2
    allowed, _reason = reg.check("SOURCE_ACCESS", target="example")
    assert allowed is True
    reg.revoke("SOURCE_ACCESS", reason="test-end")
    allowed, reason = reg.check("SOURCE_ACCESS")
    assert allowed is False and reason == "disabled"
    assert any(e["decision"] == "DENY" for e in logged)


def test_status_lists_all():
    reg = PermissionRegistry()
    status = reg.status()
    assert {s["id"] for s in status} == set(PERMISSION_IDS)
    assert all(s["enabled"] is False for s in status)
