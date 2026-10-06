"""Tests P6.1 — pont P5 → P7 (capability resolution, sans autorité)."""

from __future__ import annotations

from core.cognitive.dispatch import DispatchResult, dispatch
from core.cognitive.types import (
    CognitiveOutput,
    CognitiveParams,
    IntentKind,
)
from core.p7 import governor as G
from core.p7.catalog import build_catalog


def _output(kind: IntentKind, outil: str = "", action: str = "") -> CognitiveOutput:
    return CognitiveOutput(
        kind=kind,
        params=CognitiveParams(outil=outil, action=action),
        confidence=0.9,
        missing=[],
    )


def test_nominal_routed_exact():
    out = _output(IntentKind.NEED_TOOL, outil="P7.JAIL_READ")
    res = dispatch(out, request_id="r-1")
    assert isinstance(res, DispatchResult)
    assert res.status == "ROUTED"
    assert res.request is not None
    assert res.request.permission_id == "P7.JAIL_READ"
    assert res.request.target == "P7.JAIL_READ"
    assert res.request.scope == "catalogue:P7.JAIL_READ:lecture-seule"
    assert res.request.limits["files"] == 5
    assert res.request.duration_s == 600


def test_nominal_need_action_routed():
    out = _output(IntentKind.NEED_ACTION, action="P7.NOTIFY_LOCAL")
    res = dispatch(out, request_id="r-2")
    assert res.status == "ROUTED"
    assert res.request is not None
    assert res.request.permission_id == "P7.NOTIFY_LOCAL"


def test_no_route_unknown_tool():
    out = _output(IntentKind.NEED_TOOL, outil="P7.LASER_BEAM")
    res = dispatch(out, request_id="r-3")
    assert res.status == "NO_ROUTE"
    assert res.request is None
    assert res.reason == "unknown-tool"


def test_no_route_neighbor_tool():
    out = _output(IntentKind.NEED_TOOL, outil="P7.JAIL_REA")
    res = dispatch(out, request_id="r-4")
    assert res.status == "NO_ROUTE"
    assert res.request is None


def test_no_route_empty_tool():
    out = _output(IntentKind.NEED_ACTION)
    res = dispatch(out, request_id="r-5")
    assert res.status == "NO_ROUTE"
    assert res.reason == "empty-or-oversize-tool"


def test_no_route_non_routable_kinds():
    for kind in (IntentKind.DIRECT, IntentKind.CLARIFY, IntentKind.PLAN,
                 IntentKind.NEED_SEARCH, IntentKind.REFUSE, IntentKind.UNCERTAIN):
        res = dispatch(_output(kind, outil="P7.JAIL_READ"), request_id="r-6")
        assert res.status == "NO_ROUTE", kind
        assert res.reason.startswith("kind-not-routable")


def test_invalid_output_denied():
    assert dispatch(None, request_id="r-7").status == "NO_ROUTE"
    assert dispatch("texte brut", request_id="r-8").status == "NO_ROUTE"
    assert dispatch(_output(IntentKind.NEED_TOOL, outil="x" * 200),
                    request_id="r-9").reason == "empty-or-oversize-tool"


def test_routed_request_confers_no_authority():
    out = _output(IntentKind.NEED_TOOL, outil="P7.CATALOG_READ")
    res = dispatch(out, request_id="r-10")
    assert res.status == "ROUTED" and res.request is not None
    decision = G.decide(res.request, None, 1000.0, True)
    assert decision.allowed is False
    assert decision.reason == "APPROBATION_ABSENTE"


def test_determinism_and_bounds():
    out = _output(IntentKind.NEED_TOOL, outil="P7.JAIL_READ")
    first = dispatch(out, request_id="r-11")
    second = dispatch(out, request_id="r-11")
    assert first == second
    assert first.request is not None
    assert len(first.request.scope) <= 512
    assert len(first.request.target) <= 512


def test_catalog_entries_all_routable():
    for entry in build_catalog():
        out = _output(IntentKind.NEED_TOOL, outil=entry.id)
        res = dispatch(out, request_id=f"r-{entry.id}")
        assert res.status == "ROUTED", entry.id
        assert res.request is not None
        assert res.request.permission_id == entry.id
