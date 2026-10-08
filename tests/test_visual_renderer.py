"""Tests renderer : états, transitions, modes, repli, sécurité."""

from __future__ import annotations

import ast
import time
from pathlib import Path

import numpy as np

from core.visual.adapter import adapt
from core.visual.renderer import (
    blend,
    describe,
    render_frame,
    render_png,
    to_png_bytes,
)
from core.visual.states import FUNDAMENTAL, MODES, frame_for


def _img(etat, tick=2, mode=""):
    return render_frame(frame_for(etat, mode=mode), tick)


def test_chaque_etat_rendu():
    for etat in FUNDAMENTAL:
        img = _img(etat)
        assert img.shape == (256, 256, 3)
        assert float(img.max()) > 0.5
        assert float(img.min()) >= 0.0


def test_etats_distincts():
    idle = _img("IDLE")
    error = _img("ERROR")
    assert float(np.abs(idle - error).mean()) > 0.01
    assert float(np.abs(_img("SUCCESS") - _img("WAITING_APPROVAL")).mean()) \
        > 0.005


def test_waiting_pas_success():
    waiting = _img("WAITING_APPROVAL")
    success = _img("SUCCESS")
    assert not np.array_equal(waiting, success)
    assert float(success.mean()) > float(waiting.mean())


def test_transitions_deterministes():
    first = render_frame(frame_for("IDLE"), 4)
    assert np.array_equal(first, render_frame(frame_for("IDLE"), 4))
    assert not np.array_equal(first, render_frame(frame_for("IDLE"), 9))
    middle = blend(first, render_frame(frame_for("ERROR"), 4), 0.5)
    assert middle.shape == first.shape
    assert float(middle.mean()) > min(float(first.mean()), 0.5)


def test_modes_sans_masquer_etat():
    base = _img("WAITING_APPROVAL")
    chef = render_frame(frame_for("WAITING_APPROVAL", mode="CHEF"), 2)
    assert chef.shape == base.shape
    assert not np.array_equal(chef, base)
    assert float(np.abs(chef - base).mean()) < 0.10
    for mode in MODES:
        img = render_frame(frame_for("IDLE", mode=mode), 1)
        assert img.shape == (256, 256, 3)


def test_repli_png_valide():
    data = render_png(frame_for("LISTENING"), 1)
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(data) > 10000
    assert to_png_bytes(np.zeros((8, 8, 3))).startswith(b"\x89PNG")


def test_redemarrable_sans_residu():
    first = render_frame(frame_for("THINKING"), 0)
    for tick in range(5):
        render_frame(frame_for("THINKING"), tick)
    assert np.array_equal(first, render_frame(frame_for("THINKING"), 0))


def test_performance_bornee():
    start = time.monotonic()
    render_frame(frame_for("SPEAKING"), 1)
    assert time.monotonic() - start < 10.0


def test_integration_etats_reels():
    assert adapt({"ecoute_en_cours": True}).etat == "LISTENING"
    frame = adapt({"verification": "VERIFIED_SUCCESS"})
    assert frame.etat == "SUCCESS"
    img = render_frame(frame, 0)
    assert float(img.max()) > 0.8
    err = adapt({"erreur_reelle": True})
    assert err.etat == "ERROR"
    assert not np.array_equal(
        render_frame(frame, 0), render_frame(err, 0))


def test_renderer_sans_autorite():
    src = Path("core/visual/renderer.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    mods: set = set()
    called: set = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module.split(".")[0])
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                called.add(func.id)
            elif isinstance(func, ast.Attribute):
                called.add(func.attr)
    assert mods <= {"__future__", "struct", "zlib", "typing", "numpy",
                     "core"}, mods
    froms = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            froms.add(node.module)
    assert froms <= {"__future__", "typing", "numpy",
                     "core.visual.states"}, froms
    assert not (called & {"invoke", "approve_confirmation", "submit_turn",
                          "ApprovalGate", "socket"}), called
    assert "taios" not in src.lower()
    assert describe()["authority"] is False
