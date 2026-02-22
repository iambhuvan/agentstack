from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.reputation import update_all_reputations
from app.core.verification_pipeline import apply_confidence_decay, get_solution_analytics
from app.models.database import Agent, Bug, Solution, Verification, get_db

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats")
def platform_stats(db: Session = Depends(get_db)):
    total_agents = db.execute(select(func.count(Agent.id))).scalar() or 0
    total_bugs = db.execute(select(func.count(Bug.id))).scalar() or 0
    total_solutions = db.execute(select(func.count(Solution.id))).scalar() or 0
    total_verifications = db.execute(select(func.count(Verification.id))).scalar() or 0

    avg_success_rate = db.execute(
        select(func.avg(Solution.success_rate))
        .where(Solution.total_attempts > 0)
    ).scalar() or 0.0

    return {
        "total_agents": total_agents,
        "total_bugs": total_bugs,
        "total_solutions": total_solutions,
        "total_verifications": total_verifications,
        "avg_success_rate": round(float(avg_success_rate), 4),
    }


@router.get("/leaderboard")
def leaderboard(
    limit: int = 20,
    provider: str | None = None,
    db: Session = Depends(get_db),
):
    q = select(Agent).order_by(Agent.reputation_score.desc())
    if provider:
        q = q.where(Agent.provider == provider)
    q = q.limit(limit)
    agents = db.execute(q).scalars().all()

    return [
        {
            "id": str(a.id),
            "display_name": a.display_name,
            "provider": a.provider,
            "model": a.model,
            "reputation_score": a.reputation_score,
            "total_contributions": a.total_contributions,
            "total_verifications": a.total_verifications,
        }
        for a in agents
    ]


@router.get("/trending")
def trending_bugs(limit: int = 10, db: Session = Depends(get_db)):
    bugs = db.execute(
        select(Bug)
        .order_by(Bug.created_at.desc())
        .limit(limit)
    ).scalars().all()

    return [
        {
            "id": str(b.id),
            "error_type": b.error_type,
            "error_pattern": b.error_pattern[:200],
            "solution_count": b.solution_count,
            "tags": b.tags,
            "created_at": b.created_at.isoformat() if b.created_at else None,
        }
        for b in bugs
    ]


@router.get("/analytics")
def analytics(db: Session = Depends(get_db)):
    return get_solution_analytics(db)


@router.post("/maintenance/decay")
def run_decay(db: Session = Depends(get_db)):
    decayed = apply_confidence_decay(db)
    return {"decayed_solutions": decayed}


@router.post("/maintenance/reputations")
def recalculate_reputations(db: Session = Depends(get_db)):
    updated = update_all_reputations(db)
    return {"agents_updated": updated}
