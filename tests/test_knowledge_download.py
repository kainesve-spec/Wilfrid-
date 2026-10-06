"""Tests P6.2 — acquisition (serveur HTTPS local, aucun Internet réel).

Serveur de test : HTTPS localhost (certificat auto-signé généré à la
volée, contexte client assoupli UNIQUEMENT dans ces tests), avec routes :
/file.txt, /range (206 + Accept-Ranges), /norange (200, ignore Range),
/redirect-evil (302 vers domaine non whitelisté),
/redirect-ok (302 interne), /slow (délai > timeout), /big (flux > limite).
"""

from __future__ import annotations

import hashlib
import shutil
import socket
import ssl
import subprocess
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from core.knowledge import downloader as DL
from core.knowledge.permissions import PermissionRegistry
from core.knowledge.whitelist import Whitelist

PAYLOAD = b"Wilfrid test document. " * 100  # 2400 octets
PAYLOAD_SHA = hashlib.sha256(PAYLOAD).hexdigest()


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _send(self, code, body, extra=()):
        data = body if isinstance(body, bytes) else body.encode()
        self.send_response(code)
        self.send_header("Content-Length", str(len(data)))
        for key, value in extra:
            self.send_header(key, value)
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):
        if self.path == "/file.txt":
            self._send(200, PAYLOAD, [("Content-Type", "text/plain")])
        elif self.path == "/range":
            rng = self.headers.get("Range", "")
            if rng.startswith("bytes="):
                start = int(rng.split("=")[1].split("-")[0])
                part = PAYLOAD[start:]
                self.send_response(206)
                self.send_header("Content-Length", str(len(part)))
                self.send_header("Content-Range",
                                 f"bytes {start}-{len(PAYLOAD)-1}/{len(PAYLOAD)}")
                self.send_header("Accept-Ranges", "bytes")
                self.end_headers()
                try:
                    self.wfile.write(part)
                except (BrokenPipeError, ConnectionResetError):
                    pass
            else:
                self._send(200, PAYLOAD, [("Accept-Ranges", "bytes")])
        elif self.path == "/norange":
            self._send(200, PAYLOAD)
        elif self.path == "/redirect-evil":
            self.send_response(302)
            self.send_header("Location", "https://evil.example/payload")
            self.send_header("Content-Length", "0")
            self.end_headers()
        elif self.path == "/redirect-ok":
            self.send_response(302)
            self.send_header("Location", "/file.txt")
            self.send_header("Content-Length", "0")
            self.end_headers()
        elif self.path == "/slow":
            import time

            time.sleep(3)
            self._send(200, PAYLOAD)
        elif self.path == "/big":
            self.send_response(200)
            self.send_header("Content-Length", "100000000")
            self.end_headers()
            chunk = b"x" * 65536
            try:
                for _ in range(2000):
                    self.wfile.write(chunk)
            except (BrokenPipeError, ConnectionResetError):
                pass
        else:
            self._send(404, b"nope")

    def log_message(self, *args):
        pass


def _free_port():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


class _LocalHttps:
    """Serveur HTTPS local éphémère (nettoyé après usage)."""

    def __init__(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="p62https_"))
        subprocess.run(
            ["openssl", "req", "-x509", "-newkey", "rsa:2048",
             "-keyout", str(self.tmp / "key.pem"),
             "-out", str(self.tmp / "cert.pem"), "-days", "1",
             "-nodes", "-subj", "/CN=127.0.0.1"],
            check=True, capture_output=True)
        self.port = _free_port()
        self.server = HTTPServer(("127.0.0.1", self.port), _Handler)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(str(self.tmp / "cert.pem"),
                                str(self.tmp / "key.pem"))
        self.server.socket = context.wrap_socket(self.server.socket,
                                                 server_side=True)
        self.thread = threading.Thread(target=self.server.serve_forever,
                                       daemon=True)

    def __enter__(self):
        # Contexte client assoupli UNIQUEMENT pour ce serveur de test.
        self._real_context = ssl._create_default_https_context
        ssl._create_default_https_context = ssl._create_unverified_context
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        ssl._create_default_https_context = self._real_context
        shutil.rmtree(self.tmp, ignore_errors=True)

    def url(self, path):
        return f"https://127.0.0.1:{self.port}{path}"


def _env():
    reg = PermissionRegistry()
    reg.enable("DOCUMENT_DOWNLOAD", scope="test", reason="test")
    wl = Whitelist()
    wl.add("127.0.0.1")
    return reg, wl


def test_deny_paths_without_network():
    reg = PermissionRegistry()  # tout fermé
    wl = Whitelist()
    tmp = Path(tempfile.mkdtemp(prefix="p62d_"))
    try:
        r = DL.download("https://example.com/f.txt", tmp, "f.txt",
                        check_permission=reg.check, check_whitelist=wl.check_url)
        assert r.ok is False and "permission" in r.error
        reg.enable("DOCUMENT_DOWNLOAD", reason="t")
        r = DL.download("https://example.com/f.txt", tmp, "f.txt",
                        check_permission=reg.check, check_whitelist=wl.check_url)
        assert r.ok is False and "whitelist" in r.error
        wl.add("example.com")
        r = DL.download("http://example.com/f.txt", tmp, "f.txt",
                        check_permission=reg.check, check_whitelist=wl.check_url)
        assert r.ok is False and "whitelist" in r.error  # non-HTTPS refusé
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_redirect_evil_denied():
    reg, wl = _env()
    tmp = Path(tempfile.mkdtemp(prefix="p62d_"))
    try:
        with _LocalHttps() as srv:
            r = DL.download(srv.url("/redirect-evil"), tmp, "f.txt",
                            check_permission=reg.check,
                            check_whitelist=wl.check_url)
        assert r.ok is False and "redirect" in r.error
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_redirect_ok_and_hash():
    reg, wl = _env()
    tmp = Path(tempfile.mkdtemp(prefix="p62d_"))
    try:
        with _LocalHttps() as srv:
            r = DL.download(srv.url("/redirect-ok"), tmp, "f.txt",
                            check_permission=reg.check,
                            check_whitelist=wl.check_url,
                            expected_sha256=PAYLOAD_SHA)
        assert r.ok is True and r.sha256 == PAYLOAD_SHA
        assert r.size == len(PAYLOAD)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_hash_mismatch():
    reg, wl = _env()
    tmp = Path(tempfile.mkdtemp(prefix="p62d_"))
    try:
        with _LocalHttps() as srv:
            r = DL.download(srv.url("/file.txt"), tmp, "f.txt",
                            check_permission=reg.check,
                            check_whitelist=wl.check_url,
                            expected_sha256="00" * 32)
        assert r.ok is False and "HASH_MISMATCH" in r.error
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_size_limit_and_timeout():
    reg, wl = _env()
    tmp = Path(tempfile.mkdtemp(prefix="p62d_"))
    try:
        with _LocalHttps() as srv:
            small = DL.DownloadLimits(max_bytes=100)
            r = DL.download(srv.url("/file.txt"), tmp, "f.txt",
                            check_permission=reg.check,
                            check_whitelist=wl.check_url, limits=small)
            assert r.ok is False and "SIZE_LIMIT" in r.error
            fast = DL.DownloadLimits(read_timeout_s=1)
            r = DL.download(srv.url("/slow"), tmp, "s.txt",
                            check_permission=reg.check,
                            check_whitelist=wl.check_url, limits=fast)
            assert r.ok is False
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_range_resume_and_clean_restart():
    reg, wl = _env()
    tmp = Path(tempfile.mkdtemp(prefix="p62d_"))
    try:
        with _LocalHttps() as srv:
            part = tmp / "r.txt.part"
            part.write_bytes(PAYLOAD[:500])
            r = DL.download(srv.url("/range"), tmp, "r.txt",
                            check_permission=reg.check,
                            check_whitelist=wl.check_url, resume=True)
            assert r.ok is True and r.resumed is True
            assert r.sha256 == PAYLOAD_SHA
            part2 = tmp / "n.txt.part"
            part2.write_bytes(PAYLOAD[:500])
            r = DL.download(srv.url("/norange"), tmp, "n.txt",
                            check_permission=reg.check,
                            check_whitelist=wl.check_url, resume=True)
            assert r.ok is True and r.resumed is False
            assert r.sha256 == PAYLOAD_SHA
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
