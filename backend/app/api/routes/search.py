import time
import re
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.embeddings import generate_embedding
from app.core.fingerprint import fingerprint
from app.core.search_engine import SearchEngine
from app.models.database import Bug, get_db
from app.models.schemas import (
    BugResponse,
    FailedApproachResponse,
    SearchRequest,
    SearchResponse,
    SearchResult,
    SolutionResponse,
)

router = APIRouter(tags=["search"])
settings = get_settings()


def _infer_error_type(error_pattern: str, explicit_error_type: str | None) -> str:
    if explicit_error_type and explicit_error_type.strip():
        return explicit_error_type.strip()[:256]
    match = re.match(r"\s*([A-Za-z_][A-Za-z0-9_.-]*(?:Error|Exception)|ER[A-Z0-9_]+)\b", error_pattern)
    if match:
        return match.group(1)[:256]
    return "UnknownError"


@router.get("/bugs/{bug_id}", response_model=BugResponse)
def get_bug(bug_id: UUID, db: Session = Depends(get_db)):
    bug = db.get(Bug, bug_id)
    if not bug:
        raise HTTPException(status_code=404, detail="Bug not found")
    return BugResponse.model_validate(bug)


@router.post("/search/", response_model=SearchResponse)
def search_bugs(payload: SearchRequest, db: Session = Depends(get_db)):
    start = time.time()

    engine = SearchEngine(db)
    env_dict = payload.environment.model_dump(exclude_none=True) if payload.environment else None
    inferred_error_type = _infer_error_type(payload.error_pattern, payload.error_type)
    search_error_type = None if inferred_error_type == "UnknownError" else inferred_error_type

    raw_results = engine.search(
        error_pattern=payload.error_pattern,
        error_type=search_error_type,
        agent_provider=payload.agent_provider,
        agent_model=payload.agent_model,
        environment=env_dict,
        max_results=payload.max_results,
    )

    auto_contributed_bug_id = None
    if not raw_results and payload.auto_contribute_on_miss:
        normalized, shash = fingerprint(payload.error_pattern)
        existing_bug = db.execute(
            select(Bug).where(Bug.structural_hash == shash)
        ).scalar_one_or_none()
        if existing_bug:
            auto_contributed_bug_id = existing_bug.id
        else:
            environment_payload = env_dict or {}
            if payload.context_packet:
                environment_payload = {
                    **environment_payload,
                    "context_packet": payload.context_packet,
                }
            bug = Bug(
                structural_hash=shash,
                embedding=generate_embedding(normalized),
                error_pattern=payload.error_pattern,
                error_type=_infer_error_type(payload.error_pattern, payload.error_type),
                environment=environment_payload,
                tags=[],
            )
            db.add(bug)
            db.commit()
            db.refresh(bug)
            auto_contributed_bug_id = bug.id

    results = []
    for r in raw_results:
        bug = r["bug"]
        bug_resp = BugResponse.model_validate(bug)
        safe_env = dict(bug_resp.environment or {})
        safe_env.pop("context_packet", None)
        bug_payload = bug_resp.model_dump()
        bug_payload["environment"] = safe_env
        results.append(
            SearchResult(
                bug=BugResponse(**bug_payload),
                solutions=[SolutionResponse.model_validate(s) for s in r["solutions"]],
                failed_approaches=[
                    FailedApproachResponse.model_validate(fa)
                    for fa in r["failed_approaches"]
                ],
                match_type=r["match_type"],
                similarity_score=r.get("similarity_score"),
            )
        )

    elapsed_ms = int((time.time() - start) * 1000)
    top_similarity = results[0].similarity_score if results else None
    is_confident_match = False
    if results:
        top = results[0]
        if top.match_type == "exact_hash":
            is_confident_match = len(top.solutions) > 0
        else:
            has_verified_signal = any(
                (s.total_attempts or 0) >= settings.search_min_verified_attempts_for_confidence
                for s in top.solutions
            )
            is_confident_match = bool(
                top_similarity is not None
                and top_similarity >= settings.search_semantic_confidence_threshold
                and has_verified_signal
            )

    return SearchResponse(
        results=results,
        total_found=len(results),
        search_time_ms=elapsed_ms,
        auto_contributed_bug_id=auto_contributed_bug_id,
        top_similarity=top_similarity,
        is_confident_match=is_confident_match,
    )
