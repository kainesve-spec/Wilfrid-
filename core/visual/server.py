"""Wilfrid — serveur visuel local (stills honnêtes, sans autorité).

Expose le dernier snapshot visuel (`/snapshot` JSON, `/png` image)
sur localhost. Le serveur est une vitrine : si absent ou en panne, le
moteur continue. Démarrage/arrêt/redémarrage propres, thread unique
démon, aucune boucle active après arrêt. Jamais de commande reçue :
GET seuls, aucun paramètre exécuté.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Callable, Dict, Optional, Tuple

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8787


class _Handler(BaseHTTPRequestHandler):
    provider: Optional[Callable[[], Tuple[str, bytes, str]]] = None

    def log_message(self, *args: Any) -> None:
        pass

    def do_GET(self) -> None:
        try:
            server = self.server
            server.wilfrid_requests = int(
                getattr(server, "wilfrid_requests", 0)) + 1
        except Exception:
            pass
        if self.path not in ("/snapshot", "/png", "/health", "/page"):
            self.send_response(404)
            self.end_headers()
            return
        provider = type(self).provider
        if provider is None:
            self.send_response(503)
            self.end_headers()
            return
        try:
            kind, payload, ctype = provider(self.path)
        except Exception:
            self.send_response(500)
            self.end_headers()
            return
        if self.path == "/snapshot" and kind != "snapshot":
            self.send_response(404)
            self.end_headers()
            return
        if self.path == "/png" and kind != "png":
            self.send_response(404)
            self.end_headers()
            return
        if self.path == "/page" and kind != "page":
            self.send_response(404)
            self.end_headers()
            return
        if self.path == "/health":
            payload, ctype = b'{"status": "ok"}', "application/json"
        body = payload if isinstance(payload, bytes) else b""
        try:
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (OSError, ValueError):
            pass


class VisualServer:
    """Serveur local : démarrage/arrêt bornés, état observable."""

    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT,
                 provider: Optional[Callable[[], Tuple[str, bytes,
                                                       str]]] = None
                 ) -> None:
        self.host = host
        self.port = int(port)
        self._provider = provider
        self._server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self.requests = 0

    def start(self) -> Tuple[bool, str]:
        """Démarre (idempotent refusé si déjà actif)."""
        if self._thread is not None and self._thread.is_alive():
            return False, "deja-actif"
        provider = self._provider

        class Bound(_Handler):
            pass

        Bound.provider = staticmethod(provider) \
            if provider is not None else None
        try:
            server = HTTPServer((self.host, self.port), Bound)
        except OSError as exc:
            return False, "liaison-impossible:" + type(exc).__name__
        actual = server.server_address[1]
        self.port = int(actual)
        server.timeout = 0.5
        self._server = server
        thread = threading.Thread(target=server.serve_forever, daemon=True,
                                  name="wilfrid-visual")
        thread.start()
        self._thread = thread
        return True, "demarre"

    def stop(self) -> Tuple[bool, str]:
        """Arrêt : plus de boucle après retour."""
        server, self._server = self._server, None
        thread, self._thread = self._thread, None
        if server is not None:
            try:
                server.shutdown()
            except Exception:
                pass
            try:
                server.server_close()
            except Exception:
                pass
        if thread is not None and thread.is_alive():
            thread.join(timeout=2.0)
        if thread is not None and thread.is_alive():
            return False, "thread-persistant"
        return True, "arrete"

    def running(self) -> bool:
        """Actif et bouclé (sans effet)."""
        return self._thread is not None and self._thread.is_alive()

    def snapshot(self) -> Dict[str, Any]:
        """État observable (sans effet)."""
        count = 0
        if self._server is not None:
            try:
                count = int(getattr(self._server, "wilfrid_requests", 0))
            except Exception:
                count = 0
        return {"host": self.host, "port": self.port,
                "actif": self.running(), "requetes": count}


def make_provider(get_frame: Callable[[], Any], tick: int = 0,
                  fmt: str = "png") -> Callable[[Any], Tuple[str, bytes,
                                                             str]]:
    """Fabrique le fournisseur (compatible tests, sans effet)."""
    from core.visual.presence import render_json
    from core.visual.renderer import render_png

    def _provide(path: Any = None) -> Tuple[str, bytes, str]:
        try:
            frame = get_frame()
        except Exception:
            raise RuntimeError("frame-indisponible")
        if fmt == "json":
            try:
                return "snapshot", render_json(frame).encode("utf-8"), \
                    "application/json"
            except Exception:
                raise RuntimeError("rendu-impossible")
        try:
            return "png", render_png(frame, tick), "image/png"
        except Exception:
            try:
                return "snapshot", render_json(frame).encode("utf-8"), \
                    "application/json"
            except Exception:
                raise RuntimeError("rendu-impossible")

    return _provide


def describe() -> Dict[str, Any]:
    """Contrat serveur (sans effet)."""
    return {"hote": DEFAULT_HOST, "commandes": ["GET"],
            "graphique-os": False, "network": "localhost-uniquement",
            "authority": False}
