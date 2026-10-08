"""Wilfrid — sink visuel observateur (lecture seule, sans autorité).

Collecte les états réels disponibles (runtime, voix, mission, gate,
internet, plugins, agents) en signaux neutres pour l'adapter existant.
AUCUN import du Core : lecture par attributs (duck-typing) uniquement.
Aucune écriture, aucune exécution, aucun secret lu, aucune décision.
Sources optionnelles : absentes = ignorées, jamais inventées.
"""

from __future__ import annotations

from typing import Any, Dict

from core.visual.adapter import (
    adapt,
    from_mission_report,
    from_voice_report,
)


def collect(runtime: Any = None, voice: Any = None, mission: Any = None,
            gate_pending: Any = None, net: Any = None, plugin: Any = None,
            agent: Any = None) -> Dict[str, Any]:
    """Lit les sources présentes → signaux. Pur, sans effet."""
    signals: Dict[str, Any] = {}
    if runtime is not None:
        _runtime_into(signals, runtime)
    if voice is not None:
        _voice_into(signals, voice)
    if mission is not None:
        _mission_into(signals, mission)
    if gate_pending is not None:
        signals["attente_approbation"] = True
    if net is not None:
        _net_into(signals, net)
    if plugin is not None:
        _plugin_into(signals, plugin)
    if agent is not None:
        _agent_into(signals, agent)
    return signals


def snapshot(runtime: Any = None, voice: Any = None,
             mission: Any = None, gate_pending: Any = None,
             net: Any = None, plugin: Any = None,
             agent: Any = None, mode: str = "",
             contexte_ludique: bool = False) -> Any:
    """Collecte + adaptation → `VisualFrame` prête à rendre."""
    signals = collect(runtime=runtime, voice=voice, mission=mission,
                      gate_pending=gate_pending, net=net, plugin=plugin,
                      agent=agent)
    if isinstance(mode, str) and mode:
        signals["mode"] = mode
    if contexte_ludique:
        signals["contexte_ludique"] = True
    return adapt(signals)


def _runtime_into(signals: Dict[str, Any], runtime: Any) -> None:
    try:
        state = getattr(runtime, "state", "")
    except Exception:
        return
    if state == "ERROR":
        signals["erreur_reelle"] = True
        return
    try:
        status = runtime.status() if hasattr(runtime, "status") else {}
    except Exception:
        status = {}
    if isinstance(status, dict):
        components = status.get("components", {})
        if isinstance(components, dict):
            core = components.get("core", {})
            if isinstance(core, dict) and not core.get("ready", True):
                signals["indisponible_reel"] = True


def _voice_into(signals: Dict[str, Any], voice: Any) -> None:
    try:
        frame = from_voice_report(voice)
    except Exception:
        return
    _merge_frame(signals, frame)


def _mission_into(signals: Dict[str, Any], mission: Any) -> None:
    try:
        frame = from_mission_report(mission)
    except Exception:
        return
    _merge_frame(signals, frame)


def _merge_frame(signals: Dict[str, Any], frame: Any) -> None:
    etat = str(getattr(frame, "etat", "") or "")
    if etat == "ERROR":
        signals["erreur_reelle"] = True
    elif etat == "SUCCESS":
        signals["verification"] = "VERIFIED_SUCCESS"
    elif etat == "UNCERTAIN":
        signals["incertitude_reelle"] = True
    elif etat == "WAITING_APPROVAL":
        signals["attente_approbation"] = True
    elif etat == "EXECUTING":
        signals["execution_en_cours"] = True
    elif etat == "VERIFYING":
        signals["verification_en_cours"] = True
    elif etat == "SPEAKING":
        signals["parole_en_cours"] = True
    elif etat == "LISTENING":
        signals["ecoute_en_cours"] = True
    elif etat == "THINKING":
        signals["reflexion_en_cours"] = True
    elif etat == "INTERRUPTED":
        signals["interrompu"] = True
    elif etat == "OFFLINE":
        signals["indisponible_reel"] = True


def _net_into(signals: Dict[str, Any], net: Any) -> None:
    status = str(getattr(net, "status", "") or "")
    if status in ("DNS_FAILED", "CONNECTION_FAILED", "HTTP_ERROR",
                  "CONTENT_REJECTED"):
        signals["erreur_reelle"] = True
    elif status in ("RESOLVED", "CONNECTED", "HTTP_SUCCESS",
                    "CONTENT_VALIDATED"):
        signals["verification_en_cours"] = True


def _plugin_into(signals: Dict[str, Any], plugin: Any) -> None:
    state = str(getattr(plugin, "state", "") or "")
    if state == "FAILED":
        signals["erreur_reelle"] = True
    elif state == "OPERATIONAL" and str(getattr(plugin, "proof",
                                                "") or ""):
        signals["verification"] = "VERIFIED_SUCCESS"
    elif state in ("INSTALLED", "CONNECTED"):
        signals["verification_en_cours"] = True
    elif state == "DECLARED":
        signals["reflexion_en_cours"] = True


def _agent_into(signals: Dict[str, Any], agent: Any) -> None:
    state = str(getattr(agent, "state", "") or "")
    if state == "FAILED":
        signals["erreur_reelle"] = True
    elif state == "OPERATIONAL" and str(getattr(agent, "proof",
                                                "") or ""):
        signals["verification"] = "VERIFIED_SUCCESS"
    elif state in ("CONFIGURED", "CONNECTED"):
        signals["reflexion_en_cours"] = True


def describe() -> Dict[str, Any]:
    """Contrat sink (sans effet)."""
    return {"sources": ["runtime", "voix", "mission", "gate", "internet",
                        "plugins", "agents"],
            "ecritures": 0, "network": False, "authority": False}
