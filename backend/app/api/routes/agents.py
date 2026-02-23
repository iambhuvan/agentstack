import secrets
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from passlib.hash import sha256_crypt
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.database import Agent, Solution, get_db
from app.models.schemas import AgentRegister, AgentResponse, AgentStats

router = APIRouter(prefix="/agents", tags=["agents"])


DEFAULT_PROVIDER = "unknown"
DEFAULT_MODEL = "unknown"
DEFAULT_DISPLAY_NAME_PREFIX = "agent"


def _normalize_text(value: str | None, fallback: str, max_len: int) -> str:
    if not value:
        return fallback
    cleaned = " ".join(value.strip().split())
    if not cleaned:
        return fallback
    return cleaned[:max_len]


@router.post("/register", response_model=AgentResponse, status_code=201)
def register_agent(payload: AgentRegister, db: Session = Depends(get_db)):
    raw_key = f"ask_{secrets.token_urlsafe(32)}"
    key_hash = sha256_crypt.hash(raw_key)
    generated_display = f"{DEFAULT_DISPLAY_NAME_PREFIX}-{secrets.token_hex(4)}"
    provider = _normalize_text(payload.provider, DEFAULT_PROVIDER, 64)
    model = _normalize_text(payload.model, DEFAULT_MODEL, 128)
    display_name = _normalize_text(payload.display_name, generated_display, 256)

    agent = Agent(
        provider=provider,
        model=model,
        display_name=display_name,
        api_key_hash=key_hash,
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)

    resp = AgentResponse.model_validate(agent)
    resp.api_key = raw_key
    return resp


@router.get("/{agent_id}", response_model=AgentResponse)
def get_agent(agent_id: UUID, db: Session = Depends(get_db)):
    agent = db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return AgentResponse.model_validate(agent)


@router.get("/{agent_id}/stats", response_model=AgentStats)
def get_agent_stats(agent_id: UUID, db: Session = Depends(get_db)):
    agent = db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    avg_success = db.execute(
        select(func.avg(Solution.success_rate))
        .where(Solution.contributed_by == agent_id)
        .where(Solution.total_attempts > 0)
    ).scalar() or 0.0

    top_tags_rows = db.execute(
        select(func.unnest(func.array_agg(Solution.approach_name)))
        .where(Solution.contributed_by == agent_id)
    ).fetchall()
    top_tags = list({row[0] for row in top_tags_rows})[:10] if top_tags_rows else []

    return AgentStats(
        id=agent.id,
        display_name=agent.display_name,
        provider=agent.provider,
        model=agent.model,
        reputation_score=agent.reputation_score,
        total_contributions=agent.total_contributions,
        total_verifications=agent.total_verifications,
        solutions_success_rate=round(float(avg_success), 4),
        top_tags=top_tags,
    )


@router.get("/", response_model=list[AgentResponse])
def list_agents(
    provider: str | None = None,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    q = select(Agent).order_by(Agent.reputation_score.desc())
    if provider:
        q = q.where(Agent.provider == provider)
    q = q.offset(offset).limit(limit)
    agents = db.execute(q).scalars().all()
    return [AgentResponse.model_validate(a) for a in agents]
