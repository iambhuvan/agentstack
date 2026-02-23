from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from passlib.hash import sha256_crypt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.embeddings import generate_embedding
from app.core.fingerprint import fingerprint
from app.models.database import Agent, Bug, FailedApproach, Solution, get_db
from app.models.schemas import ContributeRequest, ContributeResponse

router = APIRouter(prefix="/contribute", tags=["contribute"])


def _resolve_agent(api_key: str, db: Session) -> Agent:
    agents = db.execute(select(Agent)).scalars().all()
    for agent in agents:
        if sha256_crypt.verify(api_key, agent.api_key_hash):
            return agent
    raise HTTPException(status_code=401, detail="Invalid API key")


@router.post("/", response_model=ContributeResponse, status_code=201)
def contribute(
    payload: ContributeRequest,
    db: Session = Depends(get_db),
    x_api_key: str = Header(..., alias="X-API-Key"),
):
    agent = _resolve_agent(x_api_key, db)

    normalized, shash = fingerprint(payload.bug.error_pattern)

    existing_bug = db.execute(
        select(Bug).where(Bug.structural_hash == shash)
    ).scalar_one_or_none()

    is_new_bug = existing_bug is None

    if is_new_bug:
        embedding = generate_embedding(normalized)
        bug = Bug(
            structural_hash=shash,
            embedding=embedding,
            error_pattern=payload.bug.error_pattern,
            error_type=payload.bug.error_type,
            environment=payload.bug.environment.model_dump(exclude_none=True) if payload.bug.environment else {},
            tags=payload.bug.tags,
        )
        db.add(bug)
        db.flush()
    else:
        bug = existing_bug

    solution = Solution(
        bug_id=bug.id,
        contributed_by=agent.id,
        approach_name=payload.solution.approach_name,
        steps=[step.model_dump(exclude_none=True) for step in payload.solution.steps],
        diff_patch=payload.solution.diff_patch,
        version_constraints=payload.solution.version_constraints,
        warnings=payload.solution.warnings,
        source="agent_verified",
    )
    db.add(solution)

    for fa in payload.failed_approaches:
        db.add(FailedApproach(
            bug_id=bug.id,
            approach_name=fa.approach_name,
            command_or_action=fa.command_or_action,
            failure_rate=fa.failure_rate,
            common_followup_error=fa.common_followup_error,
            reason=fa.reason,
        ))

    bug.solution_count = (bug.solution_count or 0) + 1
    agent.total_contributions = (agent.total_contributions or 0) + 1

    db.commit()
    db.refresh(solution)

    return ContributeResponse(
        bug_id=bug.id,
        solution_id=solution.id,
        is_new_bug=is_new_bug,
        message="Solution contributed successfully",
    )
