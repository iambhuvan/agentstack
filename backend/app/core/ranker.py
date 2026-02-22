import math
from datetime import datetime, timezone

from app.models.database import Solution


def rank_solutions(
    solutions: list[Solution],
    agent_provider: str | None = None,
    agent_model: str | None = None,
    environment: dict | None = None,
) -> list[Solution]:
    """Rank solutions by a composite score of success rate, recency,
    environment match, and provider affinity."""
    scored = []
    now = datetime.now(timezone.utc)

    for sol in solutions:
        score = _compute_score(sol, now, agent_provider, agent_model, environment)
        scored.append((score, sol))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [sol for _, sol in scored]


def _compute_score(
    sol: Solution,
    now: datetime,
    agent_provider: str | None,
    agent_model: str | None,
    environment: dict | None,
) -> float:
    success_score = sol.success_rate if sol.total_attempts > 0 else 0.5

    confidence = 1 - 1 / (1 + sol.total_attempts * 0.1)

    days_old = max((now - sol.last_verified.replace(tzinfo=timezone.utc)).days, 0) if sol.last_verified else 365
    recency = math.exp(-days_old / 90)

    env_match = 0.5
    if environment and sol.version_constraints:
        matches = 0
        total = 0
        for key, val in sol.version_constraints.items():
            total += 1
            env_val = environment.get(key)
            if env_val and env_val == val:
                matches += 1
        if total > 0:
            env_match = 0.3 + 0.7 * (matches / total)

    provider_bonus = 0.0
    if sol.contributor and agent_provider:
        if sol.contributor.provider == agent_provider:
            provider_bonus = 0.1
        if agent_model and sol.contributor.model == agent_model:
            provider_bonus = 0.2

    return (
        success_score * 0.40
        + confidence * 0.20
        + recency * 0.20
        + env_match * 0.10
        + provider_bonus * 0.10
    )
