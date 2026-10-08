"""Wilfrid — crochet visuel opérationnel (observateur, sans autorité).

`VisualHook` : `refresh(runtime)` lit le statut + pending live ;
`note_voice` / `note_mission` / `note_net` reçoivent des rapports déjà
produits ; `snapshot()` horodate ; `png()` rend la frame. Aucune
écriture vers le moteur, aucune décision, aucun secret. Erreur
visuelle = snapshot d'erreur, jamais de blocage du moteur.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Tuple

from core.visual import sink as _sink
from core.visual.adapter import adapt
from core.visual.presence import render_json
from core.visual.renderer import render_png
from core.visual.states import frame_for


class VisualHook:
    """Collecteur d'instantanés (lecture seule, thread-compatible simple)."""

    def __init__(self) -> None:
        self._signals: Dict[str, Any] = {}
        self._mode = ""
        self._updated = 0.0
        self._errors = 0

    def refresh(self, runtime: Any, *, now: Any = None) -> Dict[str, Any]:
        """Relit le runtime (statut + pending live). Sans effet moteur."""
        try:
            status = runtime.status() if hasattr(runtime, "status") else {}
        except Exception:
            status = {}
        signals: Dict[str, Any] = {}
        if isinstance(status, dict):
            if status.get("state") == "ERROR":
                signals["erreur_reelle"] = True
            components = status.get("components", {})
            if isinstance(components, dict):
                core = components.get("core", {})
                if isinstance(core, dict) and not core.get("ready", True):
                    signals["indisponible_reel"] = True
        try:
            live = getattr(runtime, "_live", None)
            if getattr(live, "pending", None) is not None:
                signals["attente_approbation"] = True
        except Exception:
            pass
        self._signals.update(signals)
        self._updated = float(now) if isinstance(now, (int, float)) \
            else time.time()
        return dict(self._signals)

    def note_voice(self, report: Any) -> Dict[str, Any]:
        """Enregistre un rapport vocal déjà produit (lecture seule)."""
        try:
            frame = _sink_from_voice(report)
            self._remember(frame)
        except Exception:
            self._errors += 1
        return dict(self._signals)

    def note_mission(self, report: Any) -> Dict[str, Any]:
        """Enregistre un rapport mission déjà produit (lecture seule)."""
        try:
            frame = _sink_from_mission(report)
            self._remember(frame)
        except Exception:
            self._errors += 1
        return dict(self._signals)

    def note_net(self, result: Any) -> Dict[str, Any]:
        """Enregistre un résultat internet déjà produit (lecture seule)."""
        try:
            status = str(getattr(result, "status", "") or "")
            if status in ("DNS_FAILED", "CONNECTION_FAILED", "HTTP_ERROR",
                          "CONTENT_REJECTED"):
                self._signals["erreur_reelle"] = True
            elif status in ("RESOLVED", "CONNECTED", "HTTP_SUCCESS",
                            "CONTENT_VALIDATED"):
                self._remember_verifying()
            self._updated = time.time()
        except Exception:
            self._errors += 1
        return dict(self._signals)

    def _remember(self, frame: Any) -> None:
        etat = str(getattr(frame, "etat", "") or "")
        if etat == "ERROR":
            self._signals["erreur_reelle"] = True
        elif etat == "SUCCESS":
            self._signals["verification"] = "VERIFIED_SUCCESS"
        elif etat == "UNCERTAIN":
            self._signals["incertitude_reelle"] = True
        elif etat == "WAITING_APPROVAL":
            self._signals["attente_approbation"] = True
        elif etat == "EXECUTING":
            self._signals["execution_en_cours"] = True
        elif etat == "VERIFYING":
            self._signals["verification_en_cours"] = True
        elif etat == "SPEAKING":
            self._signals["parole_en_cours"] = True
        elif etat == "LISTENING":
            self._signals["ecoute_en_cours"] = True
        elif etat == "THINKING":
            self._signals["reflexion_en_cours"] = True
        elif etat == "INTERRUPTED":
            self._signals["interrompu"] = True
        elif etat == "OFFLINE":
            self._signals["indisponible_reel"] = True
        self._updated = time.time()

    def _remember_verifying(self) -> None:
        self._signals["verification_en_cours"] = True
        self._updated = time.time()

    def snapshot(self, *, now: Any = None) -> Dict[str, Any]:
        """Instantané horodaté (frame + âge calculé par la page)."""
        moment = float(now) if isinstance(now, (int, float)) else time.time()
        try:
            frame = adapt(dict(self._signals))
        except Exception:
            frame = frame_for("IDLE", raison="adaptation-impossible")
            self._errors += 1
        return {"etat": frame.etat, "mode": frame.mode,
                "horodatage": self._updated,
                "demande_a": moment,
                "raison": frame.raison, "erreurs_visuelles": self._errors,
                "frame": frame}

    def png(self, tick: int = 0) -> bytes:
        """Rend la frame courante (dégradé JSON jamais ici : octets ou rien)."""
        data = self.snapshot()
        frame = data.get("frame")
        return render_png(frame, tick)

    def serve(self, path: Any, tick: int = 0) -> Tuple[str, bytes, str]:
        """Fournit snapshot/png/page au serveur (lecture seule)."""
        from core.visual.presence import render_json
        from core.visual.page import page_html
        data = self.snapshot()
        frame = data.get("frame")
        public = {"etat": data.get("etat", "INCONNU"),
                  "mode": data.get("mode", ""),
                  "horodatage": data.get("horodatage", 0.0),
                  "raison": data.get("raison", "")}
        if path == "/snapshot":
            import json as _json
            return "snapshot", _json.dumps(
                public, ensure_ascii=False).encode("utf-8"), \
                "application/json"
        if path == "/page":
            return "page", page_html(public).encode("utf-8"), \
                "text/html; charset=utf-8"
        if path == "/png":
            return "png", render_png(frame, tick), "image/png"
        return "unknown", b"", "text/plain"


def _sink_from_voice(report: Any) -> Any:
    from core.visual.adapter import from_voice_report
    return from_voice_report(report)


def _sink_from_mission(report: Any) -> Any:
    from core.visual.adapter import from_mission_report
    return from_mission_report(report)


def describe() -> Dict[str, Any]:
    """Contrat crochet (sans effet)."""
    return {"ecritures_moteur": 0, "network": False, "authority": False}
