"""Wilfrid — adaptateur Termux:API borné (primitive, sans autorité).

Liste blanche stricte de commandes, arguments structurés (jamais de
shell), timeout borné, sortie capturée. Le subprocess exécute, ne
décide jamais : autorisation et vérification vivent ailleurs.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

ALLOWLIST = {
    "termux-battery-status": {"args": 0, "timeout": 10.0},
    "termux-audio-info": {"args": 0, "timeout": 10.0},
    "termux-camera-info": {"args": 0, "timeout": 15.0},
    "termux-sensor": {"args": 2, "timeout": 15.0},
    "termux-tts-engines": {"args": 0, "timeout": 10.0},
    "termux-info": {"args": 0, "timeout": 15.0},
    "termux-open-url": {"args": 1, "timeout": 15.0},
    "termux-open": {"args": 1, "timeout": 15.0},
    "termux-share": {"args": 1, "timeout": 15.0},
    "termux-saf-read": {"args": 1, "timeout": 20.0},
    "termux-contact-list": {"args": 0, "timeout": 20.0},
    "termux-location": {"args": 0, "timeout": 25.0},
    "termux-sms-send": {"args": 2, "timeout": 25.0},
    "termux-telephony-call": {"args": 1, "timeout": 25.0},
    "termux-saf-rm": {"args": 1, "timeout": 20.0},
    "termux-notification-remove": {"args": 1, "timeout": 15.0},
}

MAX_ARG_LEN = 2048


@dataclass(frozen=True)
class TermuxResult:
    """Issue d'exécution : statut fermé + sorties, jamais d'interprétation."""

    status: str = "FAILED"
    command: str = ""
    returncode: int = -1
    stdout: str = ""
    stderr: str = ""
    reason: str = ""


def run_command(command: Any, args: Any = None, *,
                timeout_s: Any = None) -> TermuxResult:
    """Exécute une commande listée, arguments validés, sans shell."""
    if not isinstance(command, str) or command not in ALLOWLIST:
        return TermuxResult(status="UNKNOWN_COMMAND", command=str(command),
                            reason="hors-liste-blanche")
    if shutil.which(command) is None:
        return TermuxResult(status="UNAVAILABLE", command=command,
                            reason="binaire-absent")
    spec = ALLOWLIST[command]
    argv: List[str] = [command]
    if args is None:
        given: List[str] = []
    elif isinstance(args, (list, tuple)):
        given = list(args)
    else:
        return TermuxResult(status="INVALID_ARGS", command=command,
                            reason="arguments-invalides")
    if len(given) != spec["args"]:
        return TermuxResult(status="INVALID_ARGS", command=command,
                            reason="nombre-arguments-invalide")
    for value in given:
        if not isinstance(value, str) or not value.strip() \
                or len(value) > MAX_ARG_LEN or "\x00" in value:
            return TermuxResult(status="INVALID_ARGS", command=command,
                                reason="argument-invalide")
        argv.append(value)
    try:
        limit = float(timeout_s) if timeout_s is not None \
            else float(spec["timeout"])
    except (TypeError, ValueError):
        return TermuxResult(status="INVALID_ARGS", command=command,
                            reason="delai-invalide")
    limit = min(max(limit, 1.0), 60.0)
    try:
        completed = subprocess.run(argv, capture_output=True, text=True,
                                   timeout=limit, shell=False)
    except FileNotFoundError:
        return TermuxResult(status="UNAVAILABLE", command=command,
                            reason="binaire-absent")
    except PermissionError:
        return TermuxResult(status="REFUSED", command=command,
                            reason="permission-os-refusee")
    except subprocess.TimeoutExpired:
        return TermuxResult(status="TIMEOUT", command=command,
                            reason="delai-depasse")
    except Exception:
        return TermuxResult(status="FAILED", command=command,
                            reason="erreur-execution")
    out = completed.stdout if isinstance(completed.stdout, str) else ""
    err = completed.stderr if isinstance(completed.stderr, str) else ""
    if completed.returncode != 0:
        return TermuxResult(status="FAILED", command=command,
                            returncode=completed.returncode,
                            stdout=out[:4000], stderr=err[:1000],
                            reason="code-retour-non-nul")
    return TermuxResult(status="SUCCESS", command=command, returncode=0,
                        stdout=out[:8000], stderr=err[:1000],
                        reason="ok")


def describe() -> Dict[str, Any]:
    """Contrat d'adaptateur (sans effet)."""
    return {"commandes": sorted(ALLOWLIST),
            "shell": False, "network": False, "authority": False}
