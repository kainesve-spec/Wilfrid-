"""Wilfrid — contexte immédiat strictement volatil (P4).

Borné (tours + octets), purgé à SESSION_ENDED, jamais sérialisé,
jamais écrit (ni journal, ni mémoire), jamais transféré.
"""

from __future__ import annotations

from collections import deque
from typing import Any, Deque, Dict, List

MAX_TURNS = 20
MAX_BYTES = 8192


class SessionContext:
    """File bornée d'échanges + état courant + tâche courante (mémoire vive)."""

    def __init__(self, max_turns: int = MAX_TURNS, max_bytes: int = MAX_BYTES):
        self.max_turns = max_turns
        self.max_bytes = max_bytes
        self._turns: Deque[Dict[str, Any]] = deque()
        self.current_state: str = ""
        self.current_task: str = ""
        self._bytes = 0

    def _size_of(self, turn: Dict[str, Any]) -> int:
        return len(repr(sorted(turn.items())).encode("utf-8", "ignore"))

    def add_turn(self, turn: Dict[str, Any]) -> None:
        size = self._size_of(dict(turn))
        self._turns.append(dict(turn))
        self._bytes += size
        while len(self._turns) > self.max_turns or self._bytes > self.max_bytes:
            old = self._turns.popleft()
            self._bytes -= self._size_of(old)
        self._bytes = max(0, self._bytes)

    def turns(self) -> List[Dict[str, Any]]:
        return [dict(t) for t in self._turns]

    def purge(self) -> None:
        self._turns.clear()
        self._bytes = 0
        self.current_state = ""
        self.current_task = ""

    def __len__(self) -> int:
        return len(self._turns)
