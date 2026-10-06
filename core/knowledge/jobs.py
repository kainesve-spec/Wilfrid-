"""Wilfrid — jobs P6.1 (transitions contrôlées, checkpoints persistants).

États : QUEUED → DOWNLOADING → PARSING → CHUNKING → INDEXING →
ANALYZING → SYNTHESIZING → REVIEW → DONE, plus FAILED / PARTIAL.
Une étape validée est idempotente (jamais recomptée). Checkpoints
persistés dans le store : reprise après interruption sans perte.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from core.knowledge.store import KnowledgeStore

STATES = (
    "QUEUED", "DOWNLOADING", "PARSING", "CHUNKING", "INDEXING",
    "ANALYZING", "SYNTHESIZING", "REVIEW", "DONE",
)
TERMINAL_FAILURE = ("FAILED", "PARTIAL")

_TRANSITIONS = {
    "QUEUED": ("DOWNLOADING", "FAILED"),
    "DOWNLOADING": ("PARSING", "FAILED", "PARTIAL"),
    "PARSING": ("CHUNKING", "FAILED", "PARTIAL"),
    "CHUNKING": ("INDEXING", "FAILED", "PARTIAL"),
    "INDEXING": ("ANALYZING", "FAILED", "PARTIAL"),
    "ANALYZING": ("SYNTHESIZING", "FAILED", "PARTIAL"),
    "SYNTHESIZING": ("REVIEW", "FAILED", "PARTIAL"),
    "REVIEW": ("DONE", "FAILED", "PARTIAL"),
    "DONE": (),
    "FAILED": ("QUEUED",),
    "PARTIAL": ("QUEUED",),
}


class JobError(ValueError):
    """Transition ou job invalide : refus explicite."""


class JobManager:
    """Moteur de jobs adossé au store (checkpoints persistants)."""

    def __init__(self, store: KnowledgeStore):
        self.store = store

    def create(self, job_id: str, kind: str,
               document_id: Optional[str] = None) -> Dict:
        self.store.create_job(job_id, kind, document_id)
        job = self.store.get_job(job_id)
        assert job is not None
        return job

    def transition(self, job_id: str, target: str) -> Dict:
        job = self.store.get_job(job_id)
        if job is None:
            raise JobError(f"job inconnu: {job_id}")
        if target not in ("QUEUED", "DOWNLOADING", "PARSING", "CHUNKING",
                          "INDEXING", "ANALYZING", "SYNTHESIZING",
                          "REVIEW", "DONE", "FAILED", "PARTIAL"):
            raise JobError(f"état inconnu: {target}")
        if target not in _TRANSITIONS.get(job["status"], ()):
            raise JobError(
                f"transition {job['status']} -> {target} interdite")
        self.store.set_job_status(job_id, target)
        updated = self.store.get_job(job_id)
        assert updated is not None
        return updated

    def complete_step(self, job_id: str, step: str) -> List:
        """Valide une étape (idempotent : jamais recomptée)."""
        job = self.store.get_job(job_id)
        if job is None:
            raise JobError(f"job inconnu: {job_id}")
        steps: List = list(job["completed_steps"])
        if step not in steps:
            steps.append(step)
            self.store.set_job_status(job_id, job["status"], steps)
        return self.store.get_job(job_id)["completed_steps"]

    def stop(self, job_id: str, reason: str = "stopped") -> Dict:
        job = self.store.get_job(job_id)
        if job is None:
            raise JobError(f"job inconnu: {job_id}")
        if job["status"] in ("DONE", "FAILED"):
            return job
        self.store.set_job_status(job_id, "PARTIAL")
        updated = self.store.get_job(job_id)
        assert updated is not None
        return updated

    def resume(self, job_id: str) -> Dict:
        """Reprise : PARTIAL/FAILED → QUEUED, étapes validées conservées."""
        job = self.store.get_job(job_id)
        if job is None:
            raise JobError(f"job inconnu: {job_id}")
        if job["status"] not in ("PARTIAL", "FAILED"):
            raise JobError(f"reprise impossible depuis {job['status']}")
        return self.transition(job_id, "QUEUED")
