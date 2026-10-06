"""Wilfrid — retrieval O2 LOCAL_ONLY (sélection explicite, sans devinette).

Pont : NEED_SEARCH → KnowledgeQuery → résolution de source locale →
retrieval local (primitives existantes) → provenance/fraîcheur/confiance →
KnowledgeResult → cognition. STRICTEMENT LOCAL : toute source externe ou
politique non locale → DENY contrôlé, aucun réseau (aucun import réseau ici).

Garanties : une requête est une donnée, jamais une autorisation ; aucune
source devinée (défaut NO_SOURCE/AMBIGUOUS/DEFERRED motivé) ; provenance,
fraîcheur et confiance conservées séparément ; contenu récupéré = donnée
inerte, jamais instruction ; contradictions préservées, jamais arbitrées
silencieusement. Déterministe : tris stables, aucune valeur universelle
inventée (TTL/fenêtres = paramètres de la requête).
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from core.knowledge.qa import _keywords as _qa_keywords
from core.knowledge.qa import answer as _qa_answer
from core.knowledge.store import KnowledgeStore, sha256_hex
from core.knowledge.synthesis import get_synthesis, synthesize_document

STATUSES = (
    "SUCCESS", "NO_SOURCE", "NO_MATCH", "PARTIAL", "AMBIGUOUS", "STALE",
    "LOW_CONFIDENCE", "CONTRADICTORY", "UNVERIFIED", "DENIED", "DEFERRED",
    "TIMEOUT", "FAILED", "ERROR",
)

_FRESHNESS = ("CURRENT", "RECENT", "OLD", "EXPIRED", "UNKNOWN")

_WORD_RE = re.compile(r"[a-zàâäéèêëîïôöùûüç0-9]+", re.IGNORECASE)

_EXTERNAL_HINTS = ("://",)


def _looks_external(name: str) -> bool:
    lowered = name.strip().lower()
    return any(hint in lowered for hint in _EXTERNAL_HINTS)


def _clean(text: Any, limit: int) -> Optional[str]:
    if not isinstance(text, str):
        return None
    stripped = text.strip()
    if not stripped or len(stripped) > limit:
        return None
    return stripped


def _terms(text: str) -> List[str]:
    seen, out = set(), []
    for word in _WORD_RE.findall(text.lower()):
        if word not in seen:
            seen.add(word)
            out.append(word)
    return out


def _jaccard(left: str, right: str) -> float:
    a, b = set(_terms(left)), set(_terms(right))
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


@dataclass(frozen=True)
class KnowledgeQuery:
    """Demande d'information : donnée bornée, jamais autorisation d'action."""

    question: str = ""
    context: str = ""
    scope: str = "local"
    policy: str = "local-only"
    document_id: str = ""
    source_id: str = ""
    max_results: int = 3
    min_confidence: float = 0.0
    max_age_days: Optional[float] = None
    require_provenance: bool = True
    timeout_s: int = 30
    synthesize: bool = False


@dataclass(frozen=True)
class SourceCandidate:
    """Source potentielle locale, décrite, non jugée vraie."""

    source_id: str = ""
    source_type: str = "document"
    accessible: bool = False
    reason: str = ""


@dataclass(frozen=True)
class SourceSelectionDecision:
    """Issue de la sélection : un état fermé, jamais de choix silencieux."""

    state: str = "NO_SOURCE"
    candidates: Tuple[SourceCandidate, ...] = ()
    reason: str = ""


@dataclass(frozen=True)
class KnowledgeResult:
    """Résultat : statut + données + métadonnées, jamais preuve d'autorisation."""

    status: str = "ERROR"
    answer: str = ""
    sources: Tuple[str, ...] = ()
    provenance: Tuple[Dict[str, Any], ...] = ()
    freshness: str = "UNKNOWN"
    confidence: float = 0.0
    confidence_basis: str = "heuristic"
    limits: Dict[str, Any] = field(default_factory=dict)
    uncertainty: str = ""
    contradictions: Tuple[Dict[str, Any], ...] = ()
    retrieved_at: float = 0.0
    query: str = ""
    retrieval_id: str = ""
    reason: str = ""


def validate_query(query: Any) -> Tuple[bool, str]:
    """Valide une requête. Invalide → résultat ERROR contrôlé en aval."""
    if not isinstance(query, KnowledgeQuery):
        return False, "invalid-query-type"
    if _clean(query.question, 2000) is None:
        return False, "invalid-question"
    if not isinstance(query.context, str) or len(query.context) > 2000:
        return False, "invalid-context"
    if query.scope != "local":
        return False, "unsupported-scope"
    if query.policy != "local-only":
        return False, "external-not-authorized"
    for field_name in ("document_id", "source_id"):
        value = getattr(query, field_name)
        if not isinstance(value, str) or len(value) > 256:
            return False, f"invalid-{field_name.replace('_', '-')}"
    if not isinstance(query.max_results, int) \
            or isinstance(query.max_results, bool) \
            or not 1 <= query.max_results <= 10:
        return False, "invalid-max-results"
    if not isinstance(query.min_confidence, (int, float)) \
            or isinstance(query.min_confidence, bool) \
            or not 0.0 <= float(query.min_confidence) <= 1.0:
        return False, "invalid-min-confidence"
    if query.max_age_days is not None and (
            not isinstance(query.max_age_days, (int, float))
            or isinstance(query.max_age_days, bool)
            or not 0.0 < float(query.max_age_days) <= 3650.0):
        return False, "invalid-max-age"
    if not isinstance(query.require_provenance, bool):
        return False, "invalid-provenance-flag"
    if not isinstance(query.timeout_s, int) \
            or isinstance(query.timeout_s, bool) \
            or not 1 <= query.timeout_s <= 3600:
        return False, "invalid-timeout"
    if not isinstance(query.synthesize, bool):
        return False, "invalid-synthesize-flag"
    return True, "ok"


def _freshness(acquired_at: Any, max_age_days: Optional[float],
               now: float) -> str:
    """CURRENT/RECENT/OLD/EXPIRED en tiers du TTL fourni, sinon UNKNOWN."""
    if max_age_days is None or not isinstance(acquired_at, (int, float)):
        return "UNKNOWN"
    age_days = max(0.0, (now - float(acquired_at)) / 86400.0)
    ratio = age_days / float(max_age_days)
    if ratio <= 1.0 / 3.0:
        return "CURRENT"
    if ratio <= 2.0 / 3.0:
        return "RECENT"
    if ratio <= 1.0:
        return "OLD"
    return "EXPIRED"


def _query_id(query: KnowledgeQuery) -> str:
    canonical = "|".join((
        query.question.strip(), query.scope, query.policy,
        query.document_id.strip(), query.source_id.strip(),
        str(query.max_results), str(query.min_confidence),
        str(query.max_age_days), str(query.require_provenance),
        str(query.synthesize)))
    return sha256_hex(canonical.encode("utf-8"))[:16]


def select_source(store: KnowledgeStore,
                  query: KnowledgeQuery) -> SourceSelectionDecision:
    """Résolution déterministe : explicite d'abord, FTS bornée sinon.

    Règle d'ambiguïté : sans document nommé, le gagnant FTS (occurrences,
    puis id croissant) n'est retenu que s'il dépasse strictement le second ;
    sinon AMBIGUOUS avec candidats. Aucune devinette.
    """
    try:
        documents = store.list_documents()
    except Exception:
        return SourceSelectionDecision("NO_SOURCE", (), "store-unreadable")
    usable = [d for d in documents if d.get("status") == "ACQUIRED"]
    if query.document_id.strip():
        wanted = query.document_id.strip()
        match = [d for d in usable if d.get("id") == wanted]
        if not match:
            return SourceSelectionDecision("NO_SOURCE", (),
                                           "unknown-document")
        doc = match[0]
        return SourceSelectionDecision(
            "SELECTED", (SourceCandidate(
                source_id=str(doc.get("id", "")), source_type="document",
                accessible=True, reason="explicit-document"),),
            "explicit-document")
    if query.source_id.strip():
        wanted = query.source_id.strip()
        if _looks_external(wanted):
            return SourceSelectionDecision("DEFERRED", (),
                                           "external-awaiting-authorization")
        match = [d for d in usable
                 if str(d.get("id", "")) == wanted
                 or str(d.get("source", "") or "") == wanted
                 or str(d.get("source_id", "") or "") == wanted]
        if not match:
            return SourceSelectionDecision("NO_SOURCE", (),
                                           "unknown-source")
        candidates = tuple(SourceCandidate(
            source_id=str(d.get("id", "")), source_type="document",
            accessible=True, reason="explicit-source")
            for d in sorted(match, key=lambda d: str(d.get("id", ""))))
        return SourceSelectionDecision("SELECTED", candidates,
                                       "explicit-source")
    if not usable:
        return SourceSelectionDecision("NO_SOURCE", (), "empty-corpus")
    keywords = [w for w in _qa_keywords(query.question)][:8]
    if not keywords:
        return SourceSelectionDecision("NO_SOURCE", (), "question-vide")
    pattern = " OR ".join(f'"{term}"' for term in keywords)
    try:
        hits = store.search_chunks(pattern, limit=query.max_results * 4)
    except Exception:
        return SourceSelectionDecision("NO_SOURCE", (), "search-failed")
    counts: Dict[str, int] = {}
    for hit in hits:
        chunk_id = str(hit.get("id", "") or "")
        if not chunk_id:
            continue
        try:
            doc_id = store.chunk_document(chunk_id) or ""
        except Exception:
            continue
        if not doc_id:
            continue
        counts[doc_id] = counts.get(doc_id, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    known = {str(d.get("id", "")) for d in usable}
    ranked = [(doc_id, count) for doc_id, count in ranked if doc_id in known]
    if not ranked:
        return SourceSelectionDecision("NO_SOURCE", (), "no-candidate")
    if len(ranked) > 1 and ranked[0][1] == ranked[1][1]:
        candidates = tuple(SourceCandidate(
            source_id=doc_id, source_type="document", accessible=True,
            reason="fts-tie") for doc_id, _ in ranked[:query.max_results])
        return SourceSelectionDecision("AMBIGUOUS", candidates, "fts-tie")
    winner = ranked[0][0]
    return SourceSelectionDecision(
        "SELECTED", (SourceCandidate(
            source_id=winner, source_type="document", accessible=True,
            reason="fts-winner"),), "fts-winner")


def _answer_one(store: KnowledgeStore, doc_id: str, question: str,
                synthesize: bool) -> Tuple[str, Dict[str, Any]]:
    """Réponse mono-document : (état, réponse qa). Échec → FAILED contrôlé."""
    try:
        answer = _qa_answer(store, doc_id, question, top_k=3)
    except Exception:
        return "FAILED", {"type": "ERROR", "answer": "",
                          "document_id": doc_id}
    if not isinstance(answer, dict) or \
            answer.get("type") != "SOURCE" or not answer.get("answer"):
        return "NO_MATCH", answer if isinstance(answer, dict) else {}
    if synthesize:
        try:
            existing = get_synthesis(store, doc_id)
            if existing is None:
                synthesize_document(store, doc_id)
                existing = get_synthesis(store, doc_id)
            if isinstance(existing, str) and existing.strip():
                answer = dict(answer)
                answer["synthesis"] = existing
        except (ValueError, KeyError):
            answer = dict(answer)
            answer["synthesis_unavailable"] = True
    return "ANSWERED", answer


def _contradictory(answers: List[Tuple[str, Dict[str, Any]]],
                   threshold: float) -> bool:
    """Règle explicite O2 : ≥2 réponses confiantes à preuves disjointes."""
    confident = [(doc_id, ans) for doc_id, ans in answers
                 if isinstance(ans.get("confidence"), (int, float))
                 and not isinstance(ans.get("confidence"), bool)
                 and float(ans["confidence"]) >= threshold
                 and ans.get("answer")]
    if len(confident) < 2:
        return False
    for index, (doc_a, ans_a) in enumerate(confident):
        chunks_a = {str(c) for c in ans_a.get("chunks", [])}
        for _doc_b, ans_b in confident[index + 1:]:
            chunks_b = {str(c) for c in ans_b.get("chunks", [])}
            if chunks_a and chunks_b and not (chunks_a & chunks_b) \
                    and _jaccard(str(ans_a.get("answer", "")),
                                 str(ans_b.get("answer", ""))) < 0.2:
                return True
    return False


def retrieve(store: KnowledgeStore, query: KnowledgeQuery,
             now: Optional[float] = None) -> KnowledgeResult:
    """Pipeline O2 LOCAL_ONLY : sélection → retrieval → QA → résultat typé."""
    started = time.time()
    moment = float(now) if isinstance(now, (int, float)) else time.time()
    limits = {"max_results": query.max_results if isinstance(query,
              KnowledgeQuery) else 0}
    ok, why = validate_query(query)
    if not ok:
        if why == "external-not-authorized":
            return KnowledgeResult(
                status="DENIED", query=query.question
                if isinstance(query, KnowledgeQuery) else "",
                retrieval_id="", reason=why, limits=limits)
        return KnowledgeResult(
            status="ERROR",
            query=query.question if isinstance(query, KnowledgeQuery)
            else "", retrieval_id="", reason=why, limits=limits)
    rid = _query_id(query)
    if query.policy != "local-only":
        return KnowledgeResult(status="DENIED", query=query.question,
                               retrieval_id=rid, reason="external-denied",
                               limits=limits)
    selection = select_source(store, query)
    if selection.state != "SELECTED":
        mapping = {"NO_SOURCE": "NO_SOURCE", "AMBIGUOUS": "AMBIGUOUS",
                   "DEFERRED": "DEFERRED"}
        return KnowledgeResult(
            status=mapping.get(selection.state, "NO_SOURCE"),
            query=query.question, retrieval_id=rid, reason=selection.reason,
            limits=limits)
    gathered: List[Tuple[str, Dict[str, Any]]] = []
    failed = 0
    empty = 0
    for candidate in selection.candidates[:query.max_results]:
        state, answer = _answer_one(store, candidate.source_id,
                                    query.question.strip(),
                                    query.synthesize)
        if state == "ANSWERED":
            gathered.append((candidate.source_id, answer))
        elif state == "FAILED":
            failed += 1
        else:
            empty += 1
    if not gathered:
        if failed and not empty:
            return KnowledgeResult(status="FAILED", query=query.question,
                                   retrieval_id=rid,
                                   reason="retrieval-failed", limits=limits)
        return KnowledgeResult(status="NO_MATCH", query=query.question,
                               retrieval_id=rid, reason="aucun-passage",
                               limits=limits)
    if time.time() - started > float(query.timeout_s):
        return KnowledgeResult(status="TIMEOUT", query=query.question,
                               retrieval_id=rid, reason="timeout",
                               limits=limits)
    threshold = max(float(query.min_confidence), 0.5) \
        if len(gathered) > 1 else float(query.min_confidence)
    if _contradictory(gathered, threshold):
        contradictions = tuple(
            {"document_id": doc_id, "answer": str(ans.get("answer", ""))[:400],
             "confidence": ans.get("confidence", 0.0)}
            for doc_id, ans in gathered)
        provenances: List[Dict[str, Any]] = []
        for _doc_id, ans in gathered:
            for prov in ans.get("provenance", []) or []:
                if isinstance(prov, dict):
                    provenances.append(prov)
        return KnowledgeResult(
            status="CONTRADICTORY", sources=tuple(doc for doc, _ in gathered),
            provenance=tuple(provenances), freshness="UNKNOWN",
            confidence=max(float(a.get("confidence", 0.0)) for _, a in gathered),
            confidence_basis="heuristic",
            uncertainty="réponses-confidentes-divergentes",
            contradictions=contradictions, retrieved_at=moment,
            query=query.question, retrieval_id=rid,
            reason="preuves-disjointes", limits=limits)
    ordered = sorted(gathered,
                     key=lambda pair: (-float(pair[1].get("confidence", 0.0)),
                                       pair[0]))
    best_doc, best = ordered[0]
    confidence = float(best.get("confidence", 0.0))
    if confidence < float(query.min_confidence):
        status, uncertainty = "LOW_CONFIDENCE", "sous-seuil-confiance"
    else:
        status, uncertainty = "SUCCESS", ""
    provenances = [p for p in best.get("provenance", []) or []
                   if isinstance(p, dict)]
    if query.require_provenance and not provenances:
        return KnowledgeResult(
            status="UNVERIFIED", answer=str(best.get("answer", "")),
            sources=(best_doc,), provenance=(),
            freshness="UNKNOWN", confidence=confidence,
            confidence_basis="heuristic", uncertainty="provenance-absente",
            retrieved_at=moment, query=query.question, retrieval_id=rid,
            reason="provenance-absente", limits=limits)
    freshness = "UNKNOWN"
    try:
        docs = {str(d.get("id", "")): d for d in store.list_documents()}
        acquired = (docs.get(best_doc) or {}).get("acquired_at")
        freshness = _freshness(acquired, query.max_age_days, moment)
    except Exception:
        freshness = "UNKNOWN"
    if freshness == "EXPIRED":
        status, uncertainty = "STALE", "source-expirée"
    result_status = "PARTIAL" if failed and status == "SUCCESS" else status
    result_uncertainty = ("partiel-egalement-sans-preuve" if failed and status
                          == "SUCCESS" else uncertainty)
    result = {"answer": str(best.get("answer", ""))}
    if isinstance(best.get("synthesis"), str):
        result["synthesis"] = str(best["synthesis"])
    return KnowledgeResult(
        status=result_status, sources=(best_doc,),
        provenance=tuple(provenances), freshness=freshness,
        confidence=confidence, confidence_basis="heuristic",
        limits=limits, uncertainty=result_uncertainty, retrieved_at=moment,
        query=query.question, retrieval_id=rid,
        reason="ok" if result_status == "SUCCESS" else result_uncertainty,
        **result)


def query_from_cognition(output: Any) -> Optional[KnowledgeQuery]:
    """Adaptateur NEED_SEARCH → KnowledgeQuery, sans toucher P5.

    Duck-typé (aucun import cognitif) : kind NEED_SEARCH + besoin_recherche
    non vide (≤500 c) → requête ; sinon None (le dispatch P6.1 existant
    continue de répondre NO_ROUTE pour ces kinds).
    """
    try:
        kind = getattr(output, "kind", None)
        kind_value = getattr(kind, "value", kind)
        if kind_value != "NEED_SEARCH":
            return None
        params = getattr(output, "params", None)
        text = getattr(params, "besoin_recherche", "")
        question = _clean(text, 500)
        if question is None:
            return None
        return KnowledgeQuery(question=question)
    except Exception:
        return None
