"""Tests P6.1 — jobs : transitions, checkpoints, reprise, idempotence."""

from __future__ import annotations

import pytest

from core.knowledge.jobs import JobError, JobManager
from core.knowledge.store import KnowledgeStore


def _manager():
    return JobManager(KnowledgeStore(":memory:"))


def test_create_and_valid_chain():
    mgr = _manager()
    mgr.create("j1", "ingest")
    for state in ("DOWNLOADING", "PARSING", "CHUNKING", "INDEXING",
                  "ANALYZING", "SYNTHESIZING", "REVIEW", "DONE"):
        job = mgr.transition("j1", state)
        assert job["status"] == state


def test_invalid_transitions_rejected():
    mgr = _manager()
    mgr.create("j1", "ingest")
    with pytest.raises(JobError):
        mgr.transition("j1", "DONE")  # saut interdit
    with pytest.raises(JobError):
        mgr.transition("j1", "NOPE")  # état inconnu
    with pytest.raises(JobError):
        mgr.transition("ghost", "PARSING")  # job inconnu


def test_checkpoint_resume_no_double_count():
    mgr = _manager()
    mgr.create("j1", "ingest")
    mgr.transition("j1", "DOWNLOADING")
    assert mgr.complete_step("j1", "downloaded") == ["downloaded"]
    assert mgr.complete_step("j1", "downloaded") == ["downloaded"]  # idempotent
    stopped = mgr.stop("j1")
    assert stopped["status"] == "PARTIAL"
    resumed = mgr.resume("j1")
    assert resumed["status"] == "QUEUED"
    assert resumed["completed_steps"] == ["downloaded"]  # conservées
    with pytest.raises(JobError):
        mgr.resume("j1")  # QUEUED : reprise impossible


def test_terminal_states_coherent():
    mgr = _manager()
    mgr.create("j1", "ingest")
    mgr.transition("j1", "FAILED")
    assert mgr.stop("j1")["status"] == "FAILED"  # terminal : inchangé
    with pytest.raises(JobError):
        mgr.transition("j1", "DONE")  # FAILED -> DONE interdit direct
