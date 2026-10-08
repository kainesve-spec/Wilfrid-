"""Wilfrid — exécution Android gouvernée (orchestration sans autorité).

Flux : capacité connue ? accordée ? confirmation si requise (Approval
Gate existant, `ANDROID.<ID>`) → exécution adaptateur → vérification →
journal → rapport. Refus à chaque étape = zéro effet. Approbation
consommée = non réutilisable (consume du gate). Aucune auto-inscription.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Dict, Tuple

from core.android.adapters.termux_api import TermuxResult, run_command
from core.android.capabilities import AndroidRegistry


@dataclass(frozen=True)
class AndroidResult:
    """Issue d'exécution : statut fermé + preuves, jamais de promesse."""

    status: str = "FAILED"
    capability_id: str = ""
    success: bool = False
    data: Any = None
    error: str = ""
    request_id: str = ""
    verification: str = "sans-objet"


def _request_id(capability_id: str, args: Any, now: Any) -> str:
    seed = "%s|%s|%s" % (capability_id, json.dumps(
        args if isinstance(args, (list, tuple)) else [],
        ensure_ascii=False), str(now))
    return "and-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]


def _verify(capability_id: str, stdout: str) -> Tuple[bool, Any, str]:
    try:
        data = json.loads(stdout) if stdout.strip().startswith(
            ("{", "[")) else None
    except ValueError:
        data = None
    if capability_id == "BATTERY_STATUS":
        ok = isinstance(data, dict) and "percentage" in data
        return ok, data, "verifie-champs" if ok else "champs-absents"
    if capability_id == "AUDIO_INFO":
        ok = isinstance(data, dict) and bool(data)
        return ok, data, "verifie-non-vide" if ok else "vide"
    if capability_id in ("CAMERA_LIST", "SENSOR_LIST", "TTS_ENGINES"):
        ok = isinstance(data, list) and len(data) > 0
        return ok, data, "verifie-liste" if ok else "liste-vide"
    if capability_id == "SYSTEM_INFO":
        ok = bool(stdout.strip())
        return ok, stdout.strip()[:2000], "verifie-non-vide" if ok else "vide"
    return True, stdout.strip()[:2000], "intent-accepte-sans-preuve-distante"


def execute_capability(registry: Any, capability_id: Any, args: Any = None,
                       *, gate: Any = None, journal: Any = None,
                       now: Any = 0.0, session_id: str = "android",
                       decisions: Any = None,
                       run_fn: Any = None) -> AndroidResult:
    """Exécute une capacité accordée et confirmée si requise."""
    from core.p7.approval_gate import ApprovalGate
    run = run_fn if callable(run_fn) else run_command
    decisions = decisions if isinstance(decisions, dict) else {}
    if not isinstance(registry, AndroidRegistry):
        return AndroidResult(status="INVALID", error="registre-invalide")
    capability = registry.get(capability_id)
    if capability is None:
        return AndroidResult(status="UNKNOWN",
                             capability_id=str(capability_id),
                             error="capacite-inconnue")
    rid = _request_id(capability.id, args,
                      now if isinstance(now, (int, float)) else 0.0)
    if not registry.granted(capability.id):
        _journal(journal, "android-denied", "system", rid, capability.id,
                 "non-accordee")
        return AndroidResult(status="DENIED", capability_id=capability.id,
                             request_id=rid, error="non-accordee")
    if not isinstance(gate, ApprovalGate):
        return AndroidResult(status="DENIED", capability_id=capability.id,
                             request_id=rid, error="gate-invalide")
    if capability.confirmation_requise:
        decision = decisions.get(capability.id)
        if not isinstance(decision, (tuple, list)) or len(decision) < 2:
            _journal(journal, "android-blocked", "system", rid,
                     capability.id, "confirmation-attendue")
            return AndroidResult(status="BLOCKED",
                                 capability_id=capability.id,
                                 request_id=rid,
                                 error="confirmation-attendue")
        verdict, decided_by = str(decision[0]), decision[1]
        if verdict != "APPROVE":
            _journal(journal, "android-denied", str(decided_by), rid,
                     capability.id, "refus-humain")
            return AndroidResult(status="DENIED",
                                 capability_id=capability.id,
                                 request_id=rid, error="refus-humain")
        cid = "acfm-" + rid[4:]
        ok, _ = gate.create_confirmation(
            cid, rid, "ANDROID." + capability.id, capability.id,
            capability.commande, limits={}, context_hash="android",
            now=now if isinstance(now, (int, float)) else 0.0)
        if not ok:
            return AndroidResult(status="FAILED",
                                 capability_id=capability.id,
                                 request_id=rid,
                                 error="demande-impossible")
        stored = gate.get(cid)
        fingerprint = getattr(stored, "fingerprint", "")
        ok, _ = gate.approve_confirmation(cid, decided_by, fingerprint,
                                          now=now)
        if not ok:
            return AndroidResult(status="DENIED",
                                 capability_id=capability.id,
                                 request_id=rid,
                                 error="approbation-refusee")
        ok, _ = gate.consume_confirmation(cid, fingerprint, now=now)
        if not ok:
            return AndroidResult(status="DENIED",
                                 capability_id=capability.id,
                                 request_id=rid,
                                 error="consommation-refusee")
        _journal(journal, "android-approved", str(decided_by), rid,
                 capability.id, "approuve-consomme")
    try:
        outcome = run(capability.commande, args)
    except Exception:
        return AndroidResult(status="FAILED",
                             capability_id=capability.id, request_id=rid,
                             error="erreur-adaptateur")
    if not isinstance(outcome, TermuxResult):
        return AndroidResult(status="FAILED",
                             capability_id=capability.id, request_id=rid,
                             error="resultat-invalide")
    if outcome.status == "TIMEOUT":
        _journal(journal, "android-timeout", "system", rid, capability.id,
                 "delai-depasse")
        return AndroidResult(status="TIMEOUT",
                             capability_id=capability.id, request_id=rid,
                             error="delai-depasse")
    if outcome.status != "SUCCESS":
        _journal(journal, "android-failed", "system", rid, capability.id,
                 outcome.reason)
        mapping = {"UNKNOWN": "UNKNOWN", "UNAVAILABLE": "UNAVAILABLE",
                   "REFUSED": "DENIED", "INVALID_ARGS": "INVALID"}
        return AndroidResult(
            status=mapping.get(outcome.status, "FAILED"),
            capability_id=capability.id, request_id=rid,
            error=outcome.reason)
    verified, data, detail = _verify(capability.id, outcome.stdout)
    _journal(journal, "android-executed", "system", rid, capability.id,
             detail)
    if not verified:
        return AndroidResult(status="UNCERTAIN",
                             capability_id=capability.id, request_id=rid,
                             data=data, error=detail,
                             verification="UNCERTAIN")
    return AndroidResult(status="SUCCESS", capability_id=capability.id,
                         success=True, data=data, request_id=rid,
                         verification="VERIFIED")


def _journal(journal: Any, event: str, actor: str, request_id: str,
             capability_id: str, reason: str) -> None:
    try:
        if journal is not None and hasattr(journal, "record"):
            journal.record(event, actor=actor, request_id=request_id,
                           permission_id="ANDROID." + capability_id,
                           reason=reason)
    except Exception:
        pass


def describe() -> Dict[str, Any]:
    """Contrat d'exécution (sans effet)."""
    return {"flux": "connu-accorde-confirme-execute-verifie-journalise",
            "double-execution": "refusee-consommation",
            "network": False, "authority": False}
