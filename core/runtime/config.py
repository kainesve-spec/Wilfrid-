"""Wilfrid — configuration centrale du runtime (P0-1, sans autorité).

Valeurs par défaut sûres, validation fail-closed, aucun secret en dur.
Séparation stricte configuration / logique. Mode offline imposé.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Tuple

DEFAULT_DATA_DIR = str(Path.home() / ".local" / "share" / "wilfrid")
DEFAULT_SESSION_ID = "wilfrid-runtime"
LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")


@dataclass(frozen=True)
class RuntimeConfig:
    """Configuration du runtime. Données seules, jamais une décision."""

    env: str = "local"
    data_dir: str = DEFAULT_DATA_DIR
    memory_path: str = ""
    knowledge_path: str = ""
    knowledge_pack_dir: str = ""
    journal_path: str = ""
    session_id: str = DEFAULT_SESSION_ID
    max_turns: int = 0
    speak: bool = False
    log_level: str = "INFO"
    offline: bool = True
    dictionary: Dict[str, str] = field(default_factory=dict)

    def resolved(self) -> "RuntimeConfig":
        """Chemins dérivés (mémoire/knowledge/journal sous data_dir)."""
        base = self.data_dir
        memory = self.memory_path or str(Path(base) / "memory.sqlite")
        knowledge = self.knowledge_path or str(Path(base) / "knowledge.sqlite")
        journal = self.journal_path or str(Path(base) / "journal.jsonl")
        try:
            from core.knowledge.pack import pack_dir_default
            pack = self.knowledge_pack_dir or pack_dir_default()
        except Exception:
            pack = self.knowledge_pack_dir
        return RuntimeConfig(
            env=self.env, data_dir=base, memory_path=memory,
            knowledge_path=knowledge, knowledge_pack_dir=pack,
            journal_path=journal,
            session_id=self.session_id, max_turns=self.max_turns,
            speak=self.speak, log_level=self.log_level,
            offline=self.offline, dictionary=dict(self.dictionary))


def _from_mapping(data: Dict[str, Any]) -> RuntimeConfig:
    dictionary = data.get("dictionary", {})
    clean = {str(k): str(v) for k, v in dictionary.items()
             if isinstance(k, str) and isinstance(v, str)
             and k.strip() and v.strip()} \
        if isinstance(dictionary, dict) else {}
    try:
        max_turns = int(data.get("max_turns", 0))
    except (TypeError, ValueError):
        max_turns = 0
    level = str(data.get("log_level", "INFO")).upper()
    if level not in LOG_LEVELS:
        level = "INFO"
    return RuntimeConfig(
        env=str(data.get("env", "local")),
        data_dir=str(data.get("data_dir", DEFAULT_DATA_DIR)),
        memory_path=str(data.get("memory_path", "")),
        knowledge_path=str(data.get("knowledge_path", "")),
        knowledge_pack_dir=str(data.get("knowledge_pack_dir", "")),
        journal_path=str(data.get("journal_path", "")),
        session_id=str(data.get("session_id", DEFAULT_SESSION_ID)),
        max_turns=max_turns,
        speak=bool(data.get("speak", False)),
        log_level=level, offline=True, dictionary=clean)


def load_config(path: Any = None) -> RuntimeConfig:
    """Fichier JSON optionnel + surcharges `WILFRID_*`. Défauts sinon."""
    data: Dict[str, Any] = {}
    if path is not None:
        try:
            data = json.loads(Path(str(path)).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        if not isinstance(data, dict):
            data = {}
    env_map = {
        "data_dir": os.environ.get("WILFRID_DATA_DIR"),
        "session_id": os.environ.get("WILFRID_SESSION_ID"),
        "log_level": os.environ.get("WILFRID_LOG_LEVEL"),
    }
    for key, value in env_map.items():
        if value:
            data[key] = value
    if os.environ.get("WILFRID_MAX_TURNS"):
        data["max_turns"] = os.environ.get("WILFRID_MAX_TURNS")
    return _from_mapping(data)


def validate_config(config: Any) -> Tuple[bool, str]:
    """Validation fail-closed : chemins, session, bornes."""
    if not isinstance(config, RuntimeConfig):
        return False, "config-invalide"
    if not config.offline:
        return False, "offline-requis"
    session = config.session_id
    if not isinstance(session, str) or not session.strip() \
            or len(session) > 128:
        return False, "session-invalide"
    for label, path in (("data_dir", config.data_dir),
                        ("memory_path", config.resolved().memory_path),
                        ("knowledge_path", config.resolved().knowledge_path),
                        ("journal_path", config.resolved().journal_path)):
        if not isinstance(path, str) or not path.strip():
            return False, "chemin-invalide:" + label
        if "\x00" in path:
            return False, "chemin-invalide:" + label
    if not isinstance(config.max_turns, int) \
            or isinstance(config.max_turns, bool) or config.max_turns < 0 \
            or config.max_turns > 100000:
        return False, "borne-invalide:max_turns"
    if config.log_level not in LOG_LEVELS:
        return False, "niveau-log-invalide"
    return True, "ok"
