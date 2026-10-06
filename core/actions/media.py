"""Wilfrid — actions média portables (P2.3, déplacé à l'identique).

`play_song` ouvre une URI (Spotify/YouTube) via le mécanisme natif :
`os.startfile` sur Windows, `webbrowser` ailleurs. Comportement inchangé.
"""

from __future__ import annotations

import logging
import os
import sys
import webbrowser

log = logging.getLogger("clap_listen")


def play_song(uri: str) -> None:
    u = uri.strip()
    if not u:
        return
    try:
        if sys.platform == "win32":
            os.startfile(u)
        else:
            webbrowser.open(u)
    except OSError as e:
        log.warning("Could not open SONG_URI: %s", e)
