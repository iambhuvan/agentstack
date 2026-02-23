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
    max_pages: int = 200,
):
    if not api_key:
        api_key = settings.so_api_key or None

    from app.scraper.stackoverflow import DEFAULT_TAGS
    tags = tags or DEFAULT_TAGS

    scraper = StackOverflowScraper(api_key=api_key, max_pages=max_pages)
    db = SessionLocal()
    total_seeded = 0

    try:
        agent = _get_or_create_system_agent(db)

        for i, tag in enumerate(tags, 1):
            if scraper._quota_exhausted():
                logger.warning("Quota exhausted, stopping at tag %d/%d", i, len(tags))
                break

            logger.info("Scraping tag: %s (%d/%d)", tag, i, len(tags))
            raw = await scraper.scrape_tag(tag)

            if not raw:
                logger.info("No results for tag=%s, skipping", tag)
                continue

            normalized = normalize_batch(raw, "stackoverflow")
            count = import_normalized(db, normalized, agent.id)
            total_seeded += count
            logger.info("Seeded %d bugs for tag=%s (total so far: %d)", count, tag, total_seeded)

            del raw, normalized
            await asyncio.sleep(0.25)

        logger.info(
            "Stack Overflow seeding complete — %d bugs total, %d API calls, quota remaining: %s",
            total_seeded, scraper._api_calls, scraper._quota_remaining,
        )
    finally:
        await scraper.close()
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


def backfill_embeddings(batch_size: int = 512):
    """Regenerate embeddings for all bugs using the current embedding provider."""
    from sqlalchemy import text as sql_text
    from app.core.embeddings import generate_embeddings_batch
    from app.core.fingerprint import fingerprint

    init_db()

    db = SessionLocal()
    try:
        db.execute(sql_text("ALTER TABLE bugs ALTER COLUMN embedding TYPE vector(384) USING NULL"))
        db.commit()
        logger.info("Altered embedding column to vector(384)")
    except Exception as e:
        db.rollback()
        logger.info("Column alter skipped (may already be correct): %s", e)

    try:
        total = db.query(Bug).count()
        logger.info("Backfilling embeddings for %d bugs...", total)

        offset = 0
        updated = 0
        while offset < total:
            bugs = db.query(Bug).order_by(Bug.created_at).offset(offset).limit(batch_size).all()
            if not bugs:
                break

            texts = []
            for bug in bugs:
                normalized, _ = fingerprint(bug.error_pattern)
                texts.append(normalized)

            embeddings = generate_embeddings_batch(texts)

            for bug, emb in zip(bugs, embeddings):
                bug.embedding = emb

            db.commit()
            updated += len(bugs)
            offset += batch_size
            logger.info("Backfilled %d/%d bugs", updated, total)

        logger.info("Embedding backfill complete: %d bugs updated", updated)
    finally:
        db.close()


if __name__ == "__main__":
    source = sys.argv[1] if len(sys.argv) > 1 else "all"
    if source == "stackoverflow":
        asyncio.run(seed_stackoverflow())
    elif source == "github":
        asyncio.run(seed_github())
    elif source == "backfill":
        backfill_embeddings()
    else:
        asyncio.run(seed_all())
