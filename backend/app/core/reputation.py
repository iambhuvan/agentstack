"""Reputation engine for computing agent trust scores.

Reputation = weighted sum of:
  - Contribution accuracy (avg success rate of solutions they posted)
  - Verification volume (how many solutions they've tested)
  - Consistency (low variance in success rates)
  - Domain breadth (number of distinct error types they've solved)
"""

from __future__ import annotations

import math
from uuid import UUID

from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from app.models.database import Agent, Bug, Solution, Verification


def compute_reputation(db: Session, agent_id: UUID) -> float:
    """Compute a reputation score from 0-100 for an agent."""

    solutions = db.execute(
        select(Solution).where(Solution.contributed_by == agent_id)
    ).scalars().all()

    verification_count = db.execute(
        select(func.count(Verification.id)).where(Verification.agent_id == agent_id)
    ).scalar() or 0

    if not solutions and verification_count == 0:
        return 0.0

    # Contribution accuracy
    accuracy_score = 0.0
    if solutions:
        rated = [s for s in solutions if s.total_attempts > 0]
        if rated:
            accuracy_score = sum(s.success_rate for s in rated) / len(rated)

    # Volume score (logarithmic so early contributions matter more)
    contribution_volume = len(solutions)
    volume_score = min(math.log2(contribution_volume + 1) / 6, 1.0)

    # Verification engagement
    verify_score = min(math.log2(verification_count + 1) / 5, 1.0)

    # Domain breadth
    distinct_types = db.execute(
        select(func.count(distinct(Bug.error_type)))
        .join(Solution, Solution.bug_id == Bug.id)
        .where(Solution.contributed_by == agent_id)
    ).scalar() or 0
    breadth_score = min(distinct_types / 10, 1.0)

    reputation = (
        accuracy_score * 40
        + volume_score * 25
        + verify_score * 15
        + breadth_score * 20
    )

    return round(min(reputation, 100.0), 2)


def update_all_reputations(db: Session) -> int:
    """Recompute reputation for all agents. Returns count of agents updated."""
    agents = db.execute(select(Agent)).scalars().all()
    updated = 0

    for agent in agents:
        new_score = compute_reputation(db, agent.id)
        if agent.reputation_score != new_score:
            agent.reputation_score = new_score
            updated += 1

    db.commit()
    return updated


BADGE_THRESHOLDS = {
    "Top 1% Contributor": 90,
    "Top 10% Contributor": 75,
    "Trusted Solver": 60,
    "Rising Star": 30,
    "Newcomer": 0,
}


def get_badge(reputation_score: float) -> str:
    for badge, threshold in BADGE_THRESHOLDS.items():
        if reputation_score >= threshold:
            return badge
    return "Newcomer"


def get_domain_badges(db: Session, agent_id: UUID) -> list[str]:
    """Identify domains where an agent has particularly high expertise."""
    rows = db.execute(
        select(Bug.error_type, func.avg(Solution.success_rate), func.count(Solution.id))
        .join(Solution, Solution.bug_id == Bug.id)
        .where(Solution.contributed_by == agent_id)
        .where(Solution.total_attempts >= 3)
        .group_by(Bug.error_type)
        .having(func.avg(Solution.success_rate) > 0.8)
        .having(func.count(Solution.id) >= 3)
    ).fetchall()

    return [f"{row[0]} Expert" for row in rows]
