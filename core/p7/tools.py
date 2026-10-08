"""Wilfrid — registre d'outils P0-3 (fermé, déterministe, sans autorité).

Couche d'identité outil au-dessus d'`invoke` : un outil = id stable +
capability P7 + paramètres validés + état. Le registre PRÉPARE
(`prepare_call`, pur) puis EXÉCUTE via `invoke.invoke` (garde-fous
existants : Governor, Approval, journal fail-closed). Il ne crée ni
approbation ni mandat : sans `approval` fournie par le chemin humain
(gate) ou sans mandat (chemin boucle, inchangé), les handlers refusent
exactement comme avant. Registre statique : aucune auto-inscription
depuis documents, mémoire, réseau ou texte. DEFAULT DENY : inconnu →
NOT_FOUND, désactivé → DISABLED, invalide → INVALID.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from core.p7 import invoke as _invoke
from core.p7.catalog import scope_for
from core.p7.notify import expected_target
from core.p7.resolver import jail_root, resolve as resolve_path
from core.p7.types import MAX_DURATION_S, MAX_LIMITS, Request

TOOL_STATUSES = ("SUCCESS", "NOT_FOUND", "DENIED", "DISABLED", "INVALID",
                 "FAILED", "UNAVAILABLE")


@dataclass(frozen=True)
class ToolDefinition:
    """Fiche outil : identité + capability + contrat de paramètres."""

    id: str = ""
    description: str = ""
    capability_id: str = ""
    required_params: Tuple[str, ...] = ()
    param_types: Tuple[Tuple[str, str], ...] = ()
    enabled: bool = True
    permission_level: str = "local"
    offline: bool = True
    version: str = "1.0"


@dataclass(frozen=True)
class ToolCall:
    """Appel préparé et validé (sans effet)."""

    tool_id: str = ""
    permission_id: str = ""
    request: Any = None
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolResult:
    """Issue d'exécution : statut fermé + données, jamais de promesse."""

    status: str = "FAILED"
    tool_id: str = ""
    success: bool = False
    data: Any = None
    error: str = ""
    request_id: str = ""
    decision_reason: str = ""


def _definition() -> Tuple[ToolDefinition, ...]:
    return (
        ToolDefinition(
            id="catalog.read", description="Lecture du catalogue P7",
            capability_id="P7.CATALOG_READ", required_params=(),
            param_types=(), enabled=True, permission_level="local",
            offline=True, version="1.0"),
        ToolDefinition(
            id="jail.read", description="Lecture d'un fichier du jail",
            capability_id="P7.JAIL_READ", required_params=("filename",),
            param_types=(("filename", "str"),), enabled=True,
            permission_level="local", offline=True, version="1.0"),
        ToolDefinition(
            id="jail.write",
            description="Écriture réversible bornée dans le jail",
            capability_id="P7.JAIL_WRITE_REVERSIBLE",
            required_params=("filename", "content"),
            param_types=(("filename", "str"), ("content", "bytes")),
            enabled=True, permission_level="local", offline=True,
            version="1.0"),
        ToolDefinition(
            id="notify.send", description="Notification locale textuelle",
            capability_id="P7.NOTIFY_LOCAL", required_params=("message",),
            param_types=(("message", "str"),), enabled=True,
            permission_level="local", offline=True, version="1.0"),
    )


@dataclass(frozen=True)
class ToolRegistry:
    """Registre fermé : base statique + surcharges explicites d'état."""

    overrides: Tuple[Tuple[str, bool], ...] = ()

    def _table(self) -> Dict[str, ToolDefinition]:
        table = {tool.id: tool for tool in _definition()}
        for tool_id, enabled in self.overrides:
            if tool_id in table and isinstance(enabled, bool):
                current = table[tool_id]
                table[tool_id] = ToolDefinition(
                    id=current.id, description=current.description,
                    capability_id=current.capability_id,
                    required_params=current.required_params,
                    param_types=current.param_types, enabled=enabled,
                    permission_level=current.permission_level,
                    offline=current.offline, version=current.version)
        return table

    def list(self) -> Tuple[ToolDefinition, ...]:
        """Inventaire déterministe (ordre stable)."""
        return tuple(self._table()[key] for key in sorted(self._table()))

    def exists(self, tool_id: Any) -> bool:
        """Présence stricte (jamais d'approximation)."""
        return isinstance(tool_id, str) and tool_id in self._table()

    def get(self, tool_id: Any) -> Optional[ToolDefinition]:
        """Fiche par identifiant exact, `None` si inconnu."""
        if not isinstance(tool_id, str):
            return None
        return self._table().get(tool_id)


DEFAULT_REGISTRY = ToolRegistry()


def _valid_params(definition: ToolDefinition,
                  params: Any) -> Tuple[bool, str, Dict[str, Any]]:
    if not isinstance(params, dict):
        return False, "params-invalides", {}
    for name in definition.required_params:
        if name not in params:
            return False, "param-manquant:" + name, {}
    wanted = dict(definition.param_types)
    clean: Dict[str, Any] = {}
    for name, value in params.items():
        if not isinstance(name, str):
            return False, "params-invalides", {}
        kind = wanted.get(name)
        if kind == "str":
            if not isinstance(value, str):
                return False, "param-invalide:" + name, {}
            clean[name] = value
        elif kind == "bytes":
            if not isinstance(value, (bytes, bytearray)) \
                    or isinstance(value, bool):
                return False, "param-invalide:" + name, {}
            clean[name] = bytes(value)
        else:
            return False, "param-inconnu:" + name, {}
    return True, "", clean


def _shape_request(definition: ToolDefinition, params: Dict[str, Any],
                   request_id: str) -> Optional[Request]:
    capability = definition.capability_id
    if capability not in MAX_LIMITS:
        return None
    if capability == "P7.CATALOG_READ":
        scope, target = scope_for(capability), capability
    elif capability in ("P7.JAIL_READ", "P7.JAIL_WRITE_REVERSIBLE"):
        filename = params.get("filename", "")
        if not isinstance(filename, str) or not filename:
            return None
        target = str(jail_root() / filename)
        scope = (f"fichier:{target}:lecture-seule"
                 if capability == "P7.JAIL_READ"
                 else f"fichier:{target}:écriture-réversible-bornée")
        ok, _, _ = resolve_path(scope, target)
        if not ok:
            return None
    elif capability == "P7.NOTIFY_LOCAL":
        target = expected_target(request_id)
        scope = f"notification:{target}:textuel-borné"
        ok, _, _ = resolve_path(scope, target)
        if not ok:
            return None
    else:
        return None
    return Request(
        request_id=request_id, skill_id="wilfrid-core", skill_version="1.0",
        permission_id=capability, scope=scope, target=target,
        limits=dict(MAX_LIMITS[capability]),
        duration_s=int(MAX_DURATION_S.get(capability, 0)),
        reason="registre-outils")


def prepare_call(registry: Any, tool_id: Any, params: Any = None, *,
                 request_id: str = "tool-req") -> Tuple[bool, Any]:
    """Résout + valide + met en forme. Pur : aucun effet, aucune exécution."""
    table = registry._table() if isinstance(registry, ToolRegistry) \
        else DEFAULT_REGISTRY._table()
    if not isinstance(tool_id, str) or tool_id not in table:
        return False, "outil-inconnu"
    definition = table[tool_id]
    if not definition.enabled:
        return False, "outil-desactive"
    ok, reason, clean = _valid_params(definition, params or {})
    if not ok:
        return False, reason
    rid = request_id if isinstance(request_id, str) and request_id else \
        "tool-req"
    shaped = _shape_request(definition, clean, rid[:64])
    if shaped is None:
        return False, "requete-invalide"
    return True, ToolCall(tool_id=tool_id,
                          permission_id=definition.capability_id,
                          request=shaped, params=clean)


def dispatch(call: Any, *, approval: Any = None, journal: Any = None,
             now: Any = 0.0, payload: Any = None,
             catalog: Any = None) -> ToolResult:
    """Exécute un appel préparé via `invoke` (garde-fous intacts).

    `payload` : octets (jail.write) ou str (notify.send) ; `None` sinon.
    Sans approbation, les handlers R1/R2 refusent comme par le passé.
    """
    if not isinstance(call, ToolCall) or not isinstance(call.request, Request):
        return ToolResult(status="INVALID", error="appel-invalide")
    capability = call.permission_id
    if capability == "P7.JAIL_WRITE_REVERSIBLE":
        if not isinstance(payload, (bytes, bytearray)) \
                or isinstance(payload, bool):
            return ToolResult(status="INVALID", tool_id=call.tool_id,
                              request_id=call.request.request_id,
                              error="contenu-requis")
        payload = bytes(payload)
    elif capability == "P7.NOTIFY_LOCAL":
        message = call.params.get("message", "")
        if not isinstance(message, str):
            return ToolResult(status="INVALID", tool_id=call.tool_id,
                              request_id=call.request.request_id,
                              error="message-requis")
        payload = message
    elif payload is not None:
        return ToolResult(status="INVALID", tool_id=call.tool_id,
                          request_id=call.request.request_id,
                          error="contenu-inattendu")
    try:
        outcome = _invoke.invoke(
            permission_id=capability, request=call.request,
            approval=approval, now=now, journal=journal, payload=payload,
            catalog=catalog)
    except Exception:
        return ToolResult(status="FAILED", tool_id=call.tool_id,
                          request_id=call.request.request_id,
                          error="erreur-dispatch")
    if outcome.status == "ROUTED" and outcome.decision is not None \
            and outcome.decision.allowed:
        return ToolResult(status="SUCCESS", tool_id=call.tool_id,
                          success=True, data=outcome.result,
                          request_id=call.request.request_id,
                          decision_reason=outcome.decision.reason)
    if outcome.status == "ROUTED":
        return ToolResult(status="DENIED", tool_id=call.tool_id,
                          request_id=call.request.request_id,
                          error="refus-gouvernance",
                          decision_reason=outcome.decision.reason
                          if outcome.decision is not None else "")
    reason = getattr(outcome, "reason", "") or "refus-gouvernance"
    return ToolResult(status="DENIED", tool_id=call.tool_id,
                      request_id=call.request.request_id, error=reason,
                      decision_reason=reason)


def request_tool(registry: Any, tool_id: Any, params: Any = None, *,
                 approval: Any = None, journal: Any = None,
                 now: Any = 0.0, payload: Any = None,
                 request_id: str = "tool-req") -> ToolResult:
    """Point d'injection Core : préparer puis dispatcher en un appel."""
    ok, call = prepare_call(registry, tool_id, params,
                            request_id=request_id)
    if not ok:
        status = {"outil-inconnu": "NOT_FOUND"}.get(str(call), "INVALID")
        if str(call) == "outil-desactive":
            status = "DISABLED"
        return ToolResult(status=status, tool_id=str(tool_id)
                          if isinstance(tool_id, str) else "",
                          error=str(call))
    return dispatch(call, approval=approval, journal=journal, now=now,
                    payload=payload)


def describe() -> Dict[str, Any]:
    """Inventaire déclaratif (sans effet)."""
    return {"tools": [tool.id for tool in DEFAULT_REGISTRY.list()],
            "static": True, "dynamic_registration": False,
            "default_deny": True, "network": False, "authority": False}
