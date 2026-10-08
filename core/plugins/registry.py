"""Wilfrid — registre de plugins (cycle de vie prouvé, sans autorité).

DECLARED → INSTALLED → CONNECTED → OPERATIONAL (preuve d'exécution
sûre exigée), FAILED, DISABLED. Un plugin ne reçoit que les capacités
explicitement listées. Aucune auto-inscription.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Tuple

STATES = ("DECLARED", "INSTALLED", "CONNECTED", "OPERATIONAL", "FAILED",
          "DISABLED")


@dataclass(frozen=True)
class Plugin:
    """Fiche plugin : identité, besoins, état, preuve."""

    id: str = ""
    version: str = ""
    description: str = ""
    dependencies: Tuple[str, ...] = ()
    capabilities: Tuple[str, ...] = ()
    permissions: Tuple[str, ...] = ()
    state: str = "DECLARED"
    provenance: str = ""
    last_error: str = ""
    proof: str = ""


@dataclass
class PluginRegistry:
    """Registre explicite (aucune découverte automatique)."""

    plugins: Dict[str, Plugin] = field(default_factory=dict)

    def declare(self, plugin: Plugin) -> Tuple[bool, str]:
        """Déclare (données validées, sans effet)."""
        if not isinstance(plugin, Plugin) or not plugin.id.strip() \
                or len(plugin.id) > 128:
            return False, "plugin-invalide"
        if plugin.id in self.plugins:
            return False, "deja-declare"
        stored = Plugin(
            id=plugin.id.strip(), version=str(plugin.version)[:32],
            description=str(plugin.description)[:512],
            dependencies=tuple(str(d)[:128] for d in plugin.dependencies
                               if isinstance(d, str)),
            capabilities=tuple(str(c)[:128] for c in plugin.capabilities
                               if isinstance(c, str)),
            permissions=tuple(str(p)[:128] for p in plugin.permissions
                              if isinstance(p, str)),
            state="DECLARED",
            provenance=str(plugin.provenance)[:256])
        self.plugins[stored.id] = stored
        return True, "declare"

    def transition(self, plugin_id: str, target: str, *,
                   proof: str = "", error: str = "") -> Tuple[bool, str]:
        """Transition explicite ; OPERATIONAL exige une preuve."""
        current = self.plugins.get(plugin_id)
        if current is None:
            return False, "plugin-inconnu"
        allowed = {"DECLARED": ("INSTALLED", "DISABLED"),
                   "INSTALLED": ("CONNECTED", "FAILED", "DISABLED"),
                   "CONNECTED": ("OPERATIONAL", "FAILED", "DISABLED"),
                   "OPERATIONAL": ("DISABLED", "FAILED"),
                   "FAILED": ("DISABLED",),
                   "DISABLED": ()}.get(current.state, ())
        if target not in allowed:
            return False, "transition-invalide"
        if target == "OPERATIONAL" and not proof.strip():
            return False, "preuve-requise"
        updated = Plugin(
            id=current.id, version=current.version,
            description=current.description, dependencies=current.dependencies,
            capabilities=current.capabilities, permissions=current.permissions,
            state=target, provenance=current.provenance,
            last_error=str(error)[:256] if target == "FAILED" else "",
            proof=str(proof)[:256] if target == "OPERATIONAL" else "")
        self.plugins[current.id] = updated
        return True, target.lower()

    def get(self, plugin_id: str) -> Any:
        """Fiche exacte, `None` si inconnue."""
        return self.plugins.get(plugin_id)

    def list(self, state: str = "") -> Tuple[Plugin, ...]:
        """Inventaire stable, filtré par état si demandé."""
        items = sorted(self.plugins.values(), key=lambda p: p.id)
        if state:
            items = [p for p in items if p.state == state]
        return tuple(items)


def describe() -> Dict[str, Any]:
    """Contrat registre (sans effet)."""
    return {"etats": list(STATES), "auto_inscription": False,
            "network": False, "authority": False}
