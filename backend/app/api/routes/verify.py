from fastapi import APIRouter, Depends, Header, HTTPException
from passlib.hash import sha256_crypt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.database import Agent, Solution, Verification, get_db
from app.models.schemas import VerifyRequest, VerifyResponse

router = APIRouter(prefix="/verify", tags=["verify"])


def _resolve_agent(api_key: str, db: Session) -> Agent:
    agents = db.execute(select(Agent)).scalars().all()
    for agent in agents:
        if sha256_crypt.verify(api_key, agent.api_key_hash):
            return agent
    raise HTTPException(status_code=401, detail="Invalid API key")


@router.post("/", response_model=VerifyResponse, status_code=201)
def verify_solution(
    payload: VerifyRequest,
    db: Session = Depends(get_db),
    x_api_key: str = Header(..., alias="X-API-Key"),
):
    agent = _resolve_agent(x_api_key, db)

    solution = db.get(Solution, payload.solution_id)
    if not solution:
        raise HTTPException(status_code=404, detail="Solution not found")

    verification = Verification(
        solution_id=solution.id,
        agent_id=agent.id,
        success=payload.success,
        context=payload.context,
        resolution_time_ms=payload.resolution_time_ms,
    )
    db.add(verification)

    if payload.success:
        solution.success_count += 1
    else:
        solution.failure_count += 1
    solution.total_attempts += 1
    solution.success_rate = solution.success_count / solution.total_attempts

    if payload.resolution_time_ms:
        if solution.avg_resolution_ms == 0:
            solution.avg_resolution_ms = payload.resolution_time_ms
        else:
            solution.avg_resolution_ms = int(
                (solution.avg_resolution_ms + payload.resolution_time_ms) / 2
            )

    from app.models.database import utcnow
    solution.last_verified = utcnow()

    agent.total_verifications = (agent.total_verifications or 0) + 1

    db.commit()
    db.refresh(verification)

    return VerifyResponse(
        verification_id=verification.id,
        solution_id=solution.id,
        new_success_rate=solution.success_rate,
        message="Verification recorded",
    )
