"""Automated verification pipeline.

Handles:
  - Real-time solution stat updates on verification
  - Confidence decay for stale solutions
  - Auto-flagging low-performing solutions
  - Reputation recalculation triggers
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.reputation import compute_reputation
from app.models.database import Agent, Solution, Verification

logger = logging.getLogger(__name__)

CONFIDENCE_DECAY_DAYS = 90
LOW_SUCCESS_THRESHOLD = 0.3
MIN_ATTEMPTS_FOR_FLAG = 5


def process_verification(
    db: Session,
    solution_id,
    agent_id,
    success: bool,
    resolution_time_ms: int | None = None,
):
    """Process a new verification and update all related stats."""
    solution = db.get(Solution, solution_id)
    if not solution:
        return

    if success:
        solution.success_count += 1
    else:
        solution.failure_count += 1

    solution.total_attempts += 1
    solution.success_rate = solution.success_count / solution.total_attempts

    if resolution_time_ms:
        if solution.avg_resolution_ms == 0:
            solution.avg_resolution_ms = resolution_time_ms
        else:
            solution.avg_resolution_ms = int(
                (solution.avg_resolution_ms * 0.8) + (resolution_time_ms * 0.2)
            )

    solution.last_verified = datetime.now(timezone.utc)

    agent = db.get(Agent, agent_id)
    if agent:
        agent.total_verifications = (agent.total_verifications or 0) + 1

    contributor = db.get(Agent, solution.contributed_by)
    if contributor:
        new_rep = compute_reputation(db, contributor.id)
        contributor.reputation_score = new_rep

    db.commit()

    if (
        solution.total_attempts >= MIN_ATTEMPTS_FOR_FLAG
        and solution.success_rate < LOW_SUCCESS_THRESHOLD
    ):
        logger.warning(
            "Low-performing solution flagged: %s (success_rate=%.2f, attempts=%d)",
            solution.id,
            solution.success_rate,
            solution.total_attempts,
        )


def apply_confidence_decay(db: Session) -> int:
    """Reduce confidence of solutions not verified recently.

    Solutions not re-verified within CONFIDENCE_DECAY_DAYS have their
    success_rate multiplied by a decay factor.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=CONFIDENCE_DECAY_DAYS)

    stale_solutions = db.execute(
        select(Solution)
        .where(Solution.last_verified < cutoff)
        .where(Solution.total_attempts > 0)
    ).scalars().all()

    decayed = 0
    for sol in stale_solutions:
        days_stale = (datetime.now(timezone.utc) - sol.last_verified.replace(tzinfo=timezone.utc)).days
        decay_factor = max(0.5, 1.0 - (days_stale - CONFIDENCE_DECAY_DAYS) / 365)

        sol.success_rate = round(sol.success_rate * decay_factor, 4)
        decayed += 1

    if decayed > 0:
        db.commit()
        logger.info("Applied confidence decay to %d stale solutions", decayed)

    return decayed


def get_solution_analytics(db: Session) -> dict:
    """Get aggregate analytics about solution quality."""
    from sqlalchemy import func

    total_solutions = db.execute(
        select(func.count(Solution.id))
    ).scalar() or 0

    verified_solutions = db.execute(
        select(func.count(Solution.id))
        .where(Solution.total_attempts > 0)
    ).scalar() or 0

    avg_success = db.execute(
        select(func.avg(Solution.success_rate))
        .where(Solution.total_attempts > 0)
    ).scalar() or 0.0

    total_verifications = db.execute(
        select(func.count(Verification.id))
    ).scalar() or 0

    successful_verifications = db.execute(
        select(func.count(Verification.id))
        .where(Verification.success == True)
    ).scalar() or 0

    low_performing = db.execute(
        select(func.count(Solution.id))
        .where(Solution.total_attempts >= MIN_ATTEMPTS_FOR_FLAG)
        .where(Solution.success_rate < LOW_SUCCESS_THRESHOLD)
    ).scalar() or 0

    return {
        "total_solutions": total_solutions,
        "verified_solutions": verified_solutions,
        "unverified_solutions": total_solutions - verified_solutions,
        "avg_success_rate": round(float(avg_success), 4),
        "total_verifications": total_verifications,
        "successful_verifications": successful_verifications,
        "failed_verifications": total_verifications - successful_verifications,
        "low_performing_solutions": low_performing,
    }
