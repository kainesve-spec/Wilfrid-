"""Wilfrid — renderer graphique local (stdlib+numpy, sans autorité).

Rasterisation logicielle déterministe : même `(frame, tick)` = mêmes
pixels. Sortie : tableau RGB + PNG (écrivain maison, sans PIL).
Aucun toolkit, aucun réseau, aucune décision : le renderer reçoit un
`VisualFrame` et peint. États driveurs : couleurs, intensité, anneaux,
yeux, bouche, accessoires de mode, environnement.
"""

from __future__ import annotations

import struct
import zlib
from typing import Any, Dict, Tuple

WIDTH = 256
HEIGHT = 256


def _grid() -> Any:
    import numpy as np
    ys, xs = np.mgrid[0:HEIGHT, 0:WIDTH].astype(float)
    return (xs - WIDTH / 2.0) / (WIDTH / 2.0), \
        (ys - HEIGHT / 2.0) / (HEIGHT / 2.0)


def _hash_noise(seed: int, shape: Any) -> Any:
    import numpy as np
    rng = np.random.default_rng(seed)
    base = rng.random((shape[0] // 4 + 2, shape[1] // 4 + 2))
    up = np.repeat(np.repeat(base, 4, axis=0), 4, axis=1)
    return up[:shape[0], :shape[1]]


def render_frame(frame: Any, tick: int = 0,
                 width: int = WIDTH, height: int = HEIGHT) -> Any:
    """Scène complète → tableau RGB flottant [0, 1]. Pur et borné."""
    import numpy as np
    from core.visual.states import VisualFrame
    if not isinstance(frame, VisualFrame):
        frame = VisualFrame()
    h, w = int(height), int(width)
    ys, xs = np.mgrid[0:h, 0:w].astype(float)
    xn = (xs - w / 2.0) / (w / 2.0)
    yn = (ys - h / 2.0) / (h / 2.0)
    radius = np.sqrt(xn ** 2 + yn ** 2)
    warm = bool(frame.environnement != "espace")
    if warm:
        bg = np.zeros((h, w, 3))
        bg[:, :, 0] = 0.10 + 0.06 * (1.0 - yn / 2.0)
        bg[:, :, 1] = 0.07 + 0.03 * (1.0 - yn / 2.0)
        bg[:, :, 2] = 0.10 + 0.08 * (yn / 2.0 + 1.0) / 2.0
        bokeh = _hash_noise(7, (h, w))
        glow = np.clip((bokeh - 0.93) * 14.0, 0.0, 1.0)
        bg[:, :, 0] += glow * 0.10
        bg[:, :, 1] += glow * 0.06
    else:
        bg = np.zeros((h, w, 3))
        bg[:, :, 2] = 0.03 + 0.02 * (yn / 2.0 + 1.0) / 2.0
        stars = _hash_noise(21, (h, w))
        star = np.clip((stars - 0.985) * 60.0, 0.0, 1.0)
        bg += star[:, :, None] * 0.5
    img = bg.copy()
    lum = float(frame.noyau.luminosite)
    sphere = np.clip(1.0 - radius / 0.62, 0.0, 1.0)
    plasma = _hash_noise(1000 + tick * 17, (h, w))
    plasma2 = _hash_noise(5000 + tick * 29, (h, w))
    body = (0.15 + 0.5 * plasma * plasma2) * (0.35 + 0.65 * lum)
    blue = np.zeros((h, w, 3))
    blue[:, :, 0] = body * 0.25
    blue[:, :, 1] = body * 0.55
    blue[:, :, 2] = body * 1.0
    rim = np.clip(1.0 - abs(radius - 0.60) / 0.06, 0.0, 1.0)
    blue[:, :, 2] = np.maximum(blue[:, :, 2], rim * (0.5 + 0.5 * lum))
    blue[:, :, 1] = np.maximum(blue[:, :, 1], rim * 0.35)
    mask = (sphere > 0.0).astype(float)
    img = img * (1.0 - mask[:, :, None] * 0.85) + blue * mask[:, :, None]
    halo = np.clip(1.0 - abs(radius - 0.72) / 0.25, 0.0, 1.0) ** 2
    img[:, :, 2] += halo * 0.25 * lum
    img[:, :, 1] += halo * 0.10 * lum
    core_r = 0.10 + 0.05 * lum
    core = np.clip(1.0 - radius / core_r, 0.0, 1.0) ** 1.5
    img[:, :, 0] = np.maximum(img[:, :, 0], core * 0.9)
    img[:, :, 1] = np.maximum(img[:, :, 1], core * 0.95)
    img[:, :, 2] = np.maximum(img[:, :, 2], core * 1.0)
    img = _draw_rings(img, xn, yn, frame, tick)
    img = _draw_face(img, xn, yn, frame, tick)
    img = _draw_accessory(img, xn, yn, frame, tick)
    return np.clip(img, 0.0, 1.0)


def _draw_rings(img: Any, xn: Any, yn: Any, frame: Any,
                tick: int) -> Any:
    import numpy as np
    speeds = {"lents": 0.02, "reactifs-audio": 0.06, "ralentis": 0.01,
              "animes": 0.05, "pulsation-lente": 0.03, "dynamiques": 0.09,
              "desynchronises": 0.07, "instables": 0.11}
    speed = speeds.get(frame.noyau.anneaux_vitesse, 0.03)
    contract = 0.85 if frame.mode == "SAD" else 1.0
    for index, base_r in enumerate((0.78 * contract, 0.92 * contract)):
        phase = tick * speed * (1 if index == 0 else -1)
        if not frame.noyau.anneaux_synchronises and index == 1:
            phase = -tick * speed * 2.3
        ca, sa = np.cos(phase), np.sin(phase)
        xr = xn * ca - yn * sa
        yr = xn * sa + yn * ca
        band = np.abs(np.sqrt(xr ** 2 + (yr * 2.2) ** 2) - base_r)
        line = np.clip(1.0 - band / 0.02, 0.0, 1.0)
        bright = 0.35 + 0.45 * float(frame.noyau.luminosite)
        img[:, :, 0] += line * bright * 0.3
        img[:, :, 1] += line * bright * 0.6
        img[:, :, 2] += line * bright * 1.0
    if frame.noyau.balayage:
        sweep = np.clip(1.0 - abs(xn - np.sin(tick * 0.2) * 0.5) / 0.05,
                        0.0, 1.0)
        img[:, :, 1] += sweep * 0.2
        img[:, :, 2] += sweep * 0.3
    if frame.noyau.expansion:
        img += 0.08
    return img


def _draw_face(img: Any, xn: Any, yn: Any, frame: Any, tick: int) -> Any:
    import numpy as np
    expr = frame.yeux.expression
    look = {"neutre": 0.0, "haut": -0.05, "utilisateur": 0.0,
            "gauche": -0.04, "droite": 0.04}.get(frame.yeux.regard, 0.0)
    size = {"petite": 0.8, "normale": 1.0, "grande": 1.25}.get(
        frame.yeux.taille, 1.0)
    for side, sign in (("g", -1), ("d", 1)):
        cx = sign * 0.20
        cy = -0.08 + look
        if expr == "asymetriques" and side == "d":
            cy += 0.05
        if expr == "fermes":
            line = (np.abs(yn - cy) < 0.012) & (np.abs(xn - cx) < 0.09)
            img[line] = (0.05, 0.05, 0.08)
            continue
        if expr == "en-x-ludique":
            diag = (np.abs((xn - cx) - (yn - cy)) < 0.015) | \
                (np.abs((xn - cx) + (yn - cy)) < 0.015)
            zone = diag & (np.abs(xn - cx) < 0.07) & (np.abs(yn - cy) < 0.07)
            img[zone] = (0.9, 0.95, 1.0)
            continue
        hey = 0.085 * size * (0.55 if expr in ("mi-clos", "tombants")
                              else 1.0)
        white = ((xn - cx) ** 2 / 0.11 ** 2 + (yn - cy) ** 2 / hey ** 2) < 1.0
        img[white] = (0.92, 0.95, 1.0)
        px = cx + look * 0.5
        py = cy + (0.015 if expr in ("haut-concentre",) else 0.0)
        pupil = ((xn - px) ** 2 + (yn - py) ** 2) < (0.035 * size) ** 2
        img[pupil] = (0.02, 0.02, 0.04)
        hi = ((xn - px + 0.015) ** 2 + (yn - py + 0.015) ** 2) < 0.00012
        img[hi] = (1.0, 1.0, 1.0)
    mexpr = frame.bouche.expression
    active = frame.bouche.parole_active and (tick // 2) % 2 == 0
    if mexpr in ("parole", "surprise") or active:
        mouth = (xn ** 2 / 0.05 ** 2 + (yn - 0.22) ** 2 / 0.06 ** 2) < 1.0
        img[mouth] = (0.10, 0.05, 0.08)
    elif mexpr in ("sourire", "leger-sourire"):
        arc = (np.abs(np.sqrt(xn ** 2 + (yn - 0.16) ** 2) - 0.07) < 0.012) \
            & (yn > 0.16) & (np.abs(xn) < 0.08)
        img[arc] = (0.10, 0.05, 0.08)
    elif mexpr == "triste":
        arc = (np.abs(np.sqrt(xn ** 2 + (yn - 0.28) ** 2) - 0.07) < 0.012) \
            & (yn < 0.28) & (np.abs(xn) < 0.08)
        img[arc] = (0.10, 0.05, 0.08)
    elif mexpr == "hesitante":
        wave = np.abs(yn - 0.22 - 0.015 * np.sin(xn * 60.0)) < 0.010
        zone = wave & (np.abs(xn) < 0.07)
        img[zone] = (0.10, 0.05, 0.08)
    else:
        line = (np.abs(yn - 0.22) < 0.010) & (np.abs(xn) < 0.07)
        img[line] = (0.10, 0.05, 0.08)
    return img


def _draw_accessory(img: Any, xn: Any, yn: Any, frame: Any,
                    tick: int) -> Any:
    import numpy as np
    mode = frame.mode
    if mode == "CHEF":
        hat = (np.abs(xn) < 0.16) & (yn > -0.78) & (yn < -0.58)
        img[hat] = (0.95, 0.95, 0.95)
        brim = (np.abs(xn) < 0.20) & (yn > -0.60) & (yn < -0.56)
        img[brim] = (0.90, 0.90, 0.90)
    elif mode == "SECRET":
        fedora = (np.abs(xn) < 0.24) & (yn > -0.72) & (yn < -0.66)
        img[fedora] = (0.12, 0.10, 0.10)
        top = (np.abs(xn) < 0.13) & (yn > -0.88) & (yn < -0.70)
        img[top] = (0.12, 0.10, 0.10)
    elif mode == "COFFEE":
        cup = (np.abs(xn - 0.42) < 0.06) & (yn > 0.05) & (yn < 0.22)
        img[cup] = (0.95, 0.95, 0.95)
    elif mode == "PHILOSOPHER":
        laurel = (np.abs(np.sqrt(xn ** 2 + yn ** 2) - 0.55) < 0.03) \
            & (yn < -0.2)
        img[laurel, 1] = np.maximum(img[laurel, 1], 0.5)
    elif mode == "PARANORMAL":
        qy, qx = -0.55, 0.40
        dot = ((xn - qx) ** 2 + (yn - qy) ** 2) < 0.004
        img[dot] = (0.9, 0.95, 1.0)
    elif mode == "SLEEP":
        moon = ((xn - 0.45) ** 2 + (yn + 0.5) ** 2) < 0.01
        img[moon] = (0.9, 0.9, 0.7)
    elif mode == "TRANSLATION":
        for k in range(3):
            ox = -0.5 + k * 0.12
            orb = ((xn - ox) ** 2 + (yn + 0.55) ** 2) < 0.0016
            img[orb, 2] = np.maximum(img[orb, 2], 0.9)
    elif mode in ("PRODUCTIVITY", "DATA_ANALYSIS"):
        bar = (np.abs(xn + 0.45) < 0.02) & (yn > -0.3) & (yn < 0.3)
        img[bar, 1] = np.maximum(img[bar, 1], 0.5)
    elif mode == "SECURITY":
        shield = (np.abs(np.sqrt(xn ** 2 + yn ** 2) - 0.68) < 0.015)
        img[shield, 1] = np.maximum(img[shield, 1], 0.6)
        img[shield, 2] = np.maximum(img[shield, 2], 0.8)
    return img


def to_png_bytes(rgb: Any) -> bytes:
    """Tableau [0,1] → PNG vrai (sans PIL)."""
    import numpy as np
    arr = (np.clip(np.asarray(rgb, dtype=float), 0.0, 1.0) * 255.0
           ).astype("uint8")
    h, w = arr.shape[0], arr.shape[1]
    raw = b"".join(b"\x00" + arr[y].tobytes() for y in range(h))

    def _chunk(tag: bytes, data: bytes) -> bytes:
        out = struct.pack(">I", len(data)) + tag + data
        return out + struct.pack(">I", zlib.crc32(tag + data) & 0xffffffff)

    png = b"\x89PNG\r\n\x1a\n"
    png += _chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
    png += _chunk(b"IDAT", zlib.compress(raw, 6))
    png += _chunk(b"IEND", b"")
    return png


def render_png(frame: Any, tick: int = 0, path: Any = None) -> bytes:
    """Frame → octets PNG (écrit si `path`). Pur hors écriture."""
    data = to_png_bytes(render_frame(frame, tick))
    if path is not None:
        with open(str(path), "wb") as handle:
            handle.write(data)
    return data


def blend(first: Any, second: Any, alpha: float) -> Any:
    """Transition : interpolation linéaire (0.0→premier, 1.0→second)."""
    import numpy as np
    try:
        weight = min(1.0, max(0.0, float(alpha)))
    except (TypeError, ValueError):
        weight = 0.0
    first_arr = np.asarray(first, dtype=float)
    second_arr = np.asarray(second, dtype=float)
    if first_arr.shape != second_arr.shape:
        return second_arr
    return first_arr * (1.0 - weight) + second_arr * weight


def describe() -> Dict[str, Any]:
    """Capacités du renderer (sans effet)."""
    return {"moteur": "logiciel-numpy", "formats": ["png", "rgb"],
            "dependances": ["numpy"], "graphique-os": False,
            "network": False, "authority": False}
