"""Wilfrid — continuité session → mémoire → reprise (pont minimal).

`record_turn()` consigne un tour comme note traçable ; `recall_context()`
restitue un contexte borné et déterministe pour une reprise. La mémoire
fournit du contexte : jamais d'approbation, permission, autorité ni
exécution. Aucune politique de consignation inventée au-delà de ce pont
explicite : l'appelant décide quoi consigner et quoi rappeler.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from core.memory.store import MemoryStore

MAX_RECALL_TURNS = 10


def record_turn(store: MemoryStore, record_id: str, role: str, text: str, *,
                session_id: str = "") -> Tuple[bool, str]:
    """Consigne un tour brut comme note. Données uniquement."""
    if not isinstance(role, str) or role not in ("user", "wilfrid"):
        return False, "role-invalide"
    if not isinstance(text, str) or not text.strip():
        return False, "texte-vide"
    return store.write(record_id, "note", text.strip(),
                       session_id=session_id, provenance_source="session",
                       provenance_ref=role)


def recall_context(store: MemoryStore, *, session_id: str = "",
                   limit: int = MAX_RECALL_TURNS
                   ) -> List[Dict[str, Any]]:
    """Restitue des notes actives, ordre stable, sans interpréter."""
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        return []
    try:
        rows = store.list_active(limit=100)
    except Exception:
        return []
    selected = [row for row in rows
                if not session_id or row.get("session_id", "") in (
                    "", session_id)]
    selected.sort(key=lambda row: str(row.get("id", "")))
    window = MAX_RECALL_TURNS if limit > MAX_RECALL_TURNS else limit
    recent = selected[-window:] if len(selected) > window else selected
    out = []
    for row in recent:
        try:
            record = store.read(str(row.get("id", "")), now=None)
        except Exception:
            continue
        if record is None or record.status != "active":
            continue
        out.append({"role": "wilfrid-memory", "text": record.content,
                    "record_id": record.id, "freshness": record.freshness,
                    "provenance": record.provenance_source})
    return out
