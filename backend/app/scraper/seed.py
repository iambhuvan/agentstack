"""Seed script to run scrapers and import normalized data into the database."""

from __future__ import annotations

import asyncio
import logging
import sys

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.database import Bug, FailedApproach, Solution, SessionLocal, init_db, Agent
from app.scraper.github_issues import GitHubIssueScraper
from app.scraper.normalizer import normalize_batch
from app.scraper.stackoverflow import StackOverflowScraper

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

settings = get_settings()


def _get_or_create_system_agent(db: Session) -> Agent:
    """Get or create a system agent for seeded data."""
    from passlib.hash import sha256_crypt

    system_agent = db.query(Agent).filter(Agent.display_name == "AgentStack Seeder").first()
    if system_agent:
        return system_agent

    agent = Agent(
        provider="agentstack",
        model="seeder",
        display_name="AgentStack Seeder",
        api_key_hash=sha256_crypt.hash("system-seeder-key"),
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


def import_normalized(db: Session, items: list[dict], agent_id) -> int:
    """Import normalized items into the database, skipping duplicates."""
    imported = 0

    for item in items:
        existing = db.query(Bug).filter(
            Bug.structural_hash == item["structural_hash"]
        ).first()

        if existing:
            continue

        bug = Bug(
            structural_hash=item["structural_hash"],
            embedding=item.get("embedding"),
            error_pattern=item["error_pattern"],
            error_type=item["error_type"],
            environment=item.get("environment", {}),
            tags=item.get("tags", []),
            solution_count=len(item.get("solutions", [])),
        )
        db.add(bug)
        db.flush()

        for sol_data in item.get("solutions", []):
            solution = Solution(
                bug_id=bug.id,
                contributed_by=agent_id,
                approach_name=sol_data.get("approach_name", "Imported solution"),
                steps=sol_data.get("steps", []),
                source=sol_data.get("source", "human_sourced"),
            )
            db.add(solution)

        imported += 1

        if imported % 100 == 0:
            db.commit()
            logger.info("Imported %d items so far...", imported)

    db.commit()
    return imported


async def seed_stackoverflow(
    tags: list[str] | None = None,
    api_key: str | None = None,
    max_pages: int = 3,
):
    scraper = StackOverflowScraper(api_key=api_key, max_pages=max_pages)
    try:
        raw = await scraper.scrape_all(tags)
    finally:
        await scraper.close()

    normalized = normalize_batch(raw, "stackoverflow")

    db = SessionLocal()
    try:
        agent = _get_or_create_system_agent(db)
        count = import_normalized(db, normalized, agent.id)
        logger.info("Seeded %d Stack Overflow bugs", count)
    finally:
        db.close()


async def seed_github(
    repos: list[str] | None = None,
    token: str | None = None,
    max_pages: int = 2,
):
    scraper = GitHubIssueScraper(token=token, max_pages=max_pages)
    try:
        raw = await scraper.scrape_all(repos)
    finally:
        await scraper.close()

    normalized = normalize_batch(raw, "github_issues")

    db = SessionLocal()
    try:
        agent = _get_or_create_system_agent(db)
        count = import_normalized(db, normalized, agent.id)
        logger.info("Seeded %d GitHub Issues bugs", count)
    finally:
        db.close()


async def seed_all():
    init_db()
    logger.info("Starting full seed pipeline...")
    await seed_stackoverflow()
    await seed_github()
    logger.info("Seed pipeline complete.")


if __name__ == "__main__":
    source = sys.argv[1] if len(sys.argv) > 1 else "all"
    if source == "stackoverflow":
        asyncio.run(seed_stackoverflow())
    elif source == "github":
        asyncio.run(seed_github())
    else:
        asyncio.run(seed_all())
