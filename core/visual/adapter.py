"""Wilfrid — adaptateur état moteur → état visuel (pur, sans autorité).

RÈGLE DE VÉRITÉ : chaque état visuel exige son signal réel.
SUCCESS exige `verification == VERIFIED_SUCCESS` ; WAITING_APPROVAL
exige une demande en attente réelle ; ERROR exige une erreur réelle.
L'adaptateur ne lit que des dictionnaires de signaux : aucun import du
Core, aucune décision, aucune autorisation.
"""

from __future__ import annotations

from typing import Any, Dict, Tuple

from core.visual.states import frame_for, pick_state


def adapt(signals: Any) -> Any:
    """Signaux moteur → `VisualFrame`. Entrée inconnue → IDLE honnête."""
    candidates = []
    reasons = []
    mode = ""
    if not isinstance(signals, dict):
        return frame_for("IDLE", raison="signaux-invalides")
    if signals.get("erreur_reelle"):
        candidates.append("ERROR")
        reasons.append("erreur-moteur")
    if signals.get("indisponible_reel"):
        candidates.append("OFFLINE")
        reasons.append("indisponibilite-moteur")
    if signals.get("attente_approbation"):
        candidates.append("WAITING_APPROVAL")
        reasons.append("confirmation-en-attente")
    if signals.get("execution_en_cours"):
        candidates.append("EXECUTING")
        reasons.append("action-autorisee-en-cours")
    if signals.get("verification_en_cours"):
        candidates.append("VERIFYING")
        reasons.append("verification-en-cours")
    verification = signals.get("verification", "")
    if verification == "VERIFIED_SUCCESS":
        candidates.append("SUCCESS")
        reasons.append("succes-verifie")
    elif verification in ("VERIFIED_FAILURE", "UNCERTAIN"):
        candidates.append("UNCERTAIN")
        reasons.append("verification-" + str(verification).lower())
    if signals.get("incertitude_reelle"):
        candidates.append("UNCERTAIN")
        reasons.append("incertitude-moteur")
    if signals.get("parole_en_cours"):
        candidates.append("SPEAKING")
        reasons.append("synthese-en-cours")
    if signals.get("ecoute_en_cours"):
        candidates.append("LISTENING")
        reasons.append("capture-en-cours")
    if signals.get("reflexion_en_cours"):
        candidates.append("THINKING")
        reasons.append("traitement-en-cours")
    if signals.get("interrompu"):
        candidates.append("INTERRUPTED")
        reasons.append("interruption")
    requested = signals.get("mode", "")
    from core.visual.states import HUMOROUS, MODES
    if requested in MODES:
        if requested in HUMOROUS and not signals.get("contexte_ludique"):
            reasons.append("mode-ludique-refuse-contexte-grave")
        else:
            mode = requested
            candidates.append("MODE")
            reasons.append("mode:" + requested)
    etat = pick_state(candidates)
    return frame_for(etat, mode=mode, raison=";".join(reasons[:3]))


def from_runtime_status(status: Any) -> Any:
    """État runtime P0-1 → signaux (lecture seule, sans effet)."""
    signals: Dict[str, Any] = {}
    if not isinstance(status, dict):
        return adapt(signals)
    if status.get("state") == "ERROR":
        signals["erreur_reelle"] = True
    components = status.get("components", {})
    if isinstance(components, dict):
        core = components.get("core", {})
        if isinstance(core, dict) and not core.get("ready", True):
            signals["indisponible_reel"] = True
    return adapt(signals)


def from_voice_report(report: Any) -> Any:
    """Rapport vocal → signaux (stades honnêtes uniquement)."""
    signals: Dict[str, Any] = {}
    stage = str(getattr(report, "stage", "") or "")
    if stage in ("echec-capture", "echec-stt", "echec-core", "echec-tts",
                 "echec-lecture"):
        signals["erreur_reelle"] = True
    elif stage == "arret":
        signals["interrompu"] = True
    elif stage in ("capture",):
        signals["ecoute_en_cours"] = True
    elif stage in ("stt", "core"):
        signals["reflexion_en_cours"] = True
    elif stage in ("tts", "termine"):
        signals["parole_en_cours"] = True
    core = str(getattr(report, "core", "") or "")
    if core == "CONFIRM_CREATED":
        signals["attente_approbation"] = True
    elif core == "EXECUTED":
        signals["execution_en_cours"] = True
    if str(getattr(report, "tts_status", "") or "") == "SPOKEN":
        signals["parole_en_cours"] = True
    return adapt(signals)


def from_mission_report(report: Any) -> Any:
    """Rapport mission → signaux (vérification réelle exigée)."""
    signals: Dict[str, Any] = {}
    final = str(getattr(report, "etat_final", "") or "")
    if final == "COMPLETED":
        rapports = getattr(report, "rapports", ()) or ()
        verifs = [str(getattr(r, "verification", "") or "") for r in rapports]
        if verifs and all(v == "VERIFIED_SUCCESS" for v in verifs):
            signals["verification"] = "VERIFIED_SUCCESS"
        elif any(v in ("VERIFIED_FAILURE", "UNCERTAIN") for v in verifs):
            signals["verification"] = "UNCERTAIN"
        else:
            signals["incertitude_reelle"] = True
    elif final in ("FAILED",):
        signals["erreur_reelle"] = True
    elif final in ("PAUSED",):
        signals["attente_approbation"] = True
    return adapt(signals)


def describe() -> Dict[str, Any]:
    """Contrat d'adaptation (sans effet)."""
    return {"entrees": ["runtime", "voix", "mission"],
            "regle": "signal-reel-exige",
            "network": False, "authority": False}
