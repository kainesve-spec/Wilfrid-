"""Tests application Android : projet, contrat, sécurité."""

from __future__ import annotations

from pathlib import Path

APP = Path("android")


def _read(rel):
    return (APP / rel).read_text(encoding="utf-8")


def test_projet_present():
    assert (APP / "settings.gradle").is_file()
    assert (APP / "app" / "build.gradle").is_file()
    assert (APP / "app" / "src" / "main" / "AndroidManifest.xml").is_file()
    assert (APP / "app" / "src" / "main" / "java" / "org" / "wilfrid" /
            "app" / "MainActivity.java").is_file()
    assert Path(".github/workflows/android.yml").is_file()


def test_configuration_valide():
    root = _read("build.gradle")
    assert "8.5.2" in root
    app = _read("app/build.gradle")
    assert "org.wilfrid.app" in app
    assert "compileSdk = 34" in app
    assert "minSdk = 26" in app
    assert "JavaVersion.VERSION_17" in app
    manifest = _read("app/src/main/AndroidManifest.xml")
    assert "android.permission.INTERNET" in manifest
    assert "android.permission.RECORD_AUDIO" in manifest
    assert "SEND_SMS" not in manifest
    assert "CALL_PHONE" not in manifest
    assert "ACCESS_FINE_LOCATION" not in manifest
    assert "READ_CONTACTS" not in manifest


def test_activite_sans_pont_autorite():
    src = _read("app/src/main/java/org/wilfrid/app/MainActivity.java")
    assert "addJavascriptInterface" not in src
    assert "127.0.0.1" in src
    assert "shouldOverrideUrlLoading" in src
    assert "localhost" in src
    assert "onPause" in src and "onResume" in src and "onDestroy" in src
    assert "indisponible" in src
    lowered = src.lower()
    assert "taios" not in lowered
    assert "approve" not in lowered
    assert "elevenlabs" not in lowered


def test_workflow_ci():
    workflow = Path(".github/workflows/android.yml").read_text(
        encoding="utf-8")
    assert "17" in workflow
    assert "assembleDebug" in workflow
    assert "sk-" not in workflow
    assert "keystore" not in workflow.lower()
    assert "secrets." not in workflow


def test_contrat_boucle_locale():
    assert "127.0.0.1" in _read(
        "app/src/main/java/org/wilfrid/app/MainActivity.java")
    assert "/api/chat" in Path("core/visual/app.py").read_text(
        encoding="utf-8")
