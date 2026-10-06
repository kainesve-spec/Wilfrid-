"""Tests P6.1 — whitelist vide par défaut, refus explicites, sans réseau."""

from __future__ import annotations

import pytest

from core.knowledge.whitelist import Whitelist


def test_empty_whitelist_denies():
    wl = Whitelist()
    assert wl.entries() == []
    allowed, reason = wl.check_url("https://example.com/livre.epub")
    assert allowed is False and reason == "source-absente-whitelist"


def test_non_https_denied():
    wl = Whitelist()
    wl.add("example.com")
    allowed, reason = wl.check_url("http://example.com/x")
    assert allowed is False and reason == "protocole-non-https"


def test_add_check_revoke_cycle():
    logged = []
    wl = Whitelist(log_callback=lambda **kw: logged.append(kw))
    wl.add("https://example.com/livre", limits={"max_mb": 10})
    allowed, reason = wl.check_url("https://example.com/livre.epub")
    assert allowed is True and reason == "autorise"
    assert wl.revoke("example.com") is True
    allowed, reason = wl.check_url("https://example.com/livre.epub")
    assert allowed is False and reason == "source-revoquee"
    assert any(e["decision"] == "DENY" for e in logged)


def test_invalid_domain_rejected():
    wl = Whitelist()
    with pytest.raises(ValueError):
        wl.add("not a domain!!")
    with pytest.raises(ValueError):
        wl.add("")


def test_no_automatic_modification():
    wl = Whitelist()
    wl.check_url("https://attacker.example/payload")
    wl.check_url("http://example.com/")
    assert wl.entries() == []
