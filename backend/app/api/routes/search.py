import time
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

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

    raw_results = engine.search(
        error_pattern=payload.error_pattern,
        error_type=payload.error_type,
        agent_provider=payload.agent_provider,
        agent_model=payload.agent_model,
        environment=env_dict,
        max_results=payload.max_results,
    )

    results = []
    for r in raw_results:
        bug = r["bug"]
        results.append(
            SearchResult(
                bug=BugResponse.model_validate(bug),
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

    return SearchResponse(
        results=results,
        total_found=len(results),
        search_time_ms=elapsed_ms,
    )
