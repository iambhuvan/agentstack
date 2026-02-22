"""Stack Overflow scraper using the public Stack Exchange API.

Uses /2.3/search/advanced and /2.3/questions/{ids}/answers endpoints
to pull bug/error questions with accepted or top-voted answers.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

SO_API_BASE = "https://api.stackexchange.com/2.3"

DEFAULT_TAGS = [
    "python", "javascript", "typescript", "node.js", "react", "next.js",
    "java", "c#", "go", "rust", "ruby", "php", "swift", "kotlin",
    "docker", "kubernetes", "postgresql", "mongodb", "redis", "aws",
    "npm", "pip", "webpack", "vite", "django", "flask", "fastapi",
    "express", "spring", "rails", "angular", "vue.js", "svelte",
]

ERROR_KEYWORDS = [
    "error", "exception", "traceback", "failed", "cannot", "unable",
    "undefined", "null", "crash", "bug", "issue",
]


class StackOverflowScraper:
    def __init__(self, api_key: str | None = None, max_pages: int = 5):
        self.api_key = api_key
        self.max_pages = max_pages
        self._client = httpx.AsyncClient(timeout=30.0)

    async def scrape_tag(self, tag: str, page_size: int = 50) -> list[dict[str, Any]]:
        """Scrape questions for a given tag that contain error-related content."""
        results: list[dict[str, Any]] = []

        for page in range(1, self.max_pages + 1):
            params: dict[str, Any] = {
                "order": "desc",
                "sort": "votes",
                "tagged": tag,
                "site": "stackoverflow",
                "filter": "withbody",
                "pagesize": page_size,
                "page": page,
            }
            if self.api_key:
                params["key"] = self.api_key

            try:
                resp = await self._client.get(
                    f"{SO_API_BASE}/search/advanced", params=params
                )
                resp.raise_for_status()
                data = resp.json()

                questions = data.get("items", [])
                if not questions:
                    break

                for q in questions:
                    if not q.get("accepted_answer_id") and q.get("answer_count", 0) == 0:
                        continue

                    title = q.get("title", "")
                    body = q.get("body", "")
                    has_error = any(kw in title.lower() or kw in body.lower() for kw in ERROR_KEYWORDS)
                    if not has_error:
                        continue

                    answers = await self._fetch_answers(q["question_id"])
                    if not answers:
                        continue

                    results.append({
                        "question_id": q["question_id"],
                        "title": title,
                        "body": body,
                        "tags": q.get("tags", []),
                        "score": q.get("score", 0),
                        "accepted_answer_id": q.get("accepted_answer_id"),
                        "answers": answers,
                        "link": q.get("link", ""),
                    })

                if not data.get("has_more", False):
                    break

                quota = data.get("quota_remaining", 0)
                if quota < 10:
                    logger.warning("SO API quota low: %d remaining", quota)
                    break

            except httpx.HTTPError as e:
                logger.error("SO API error for tag=%s page=%d: %s", tag, page, e)
                break

            await asyncio.sleep(0.5)

        logger.info("Scraped %d questions for tag=%s", len(results), tag)
        return results

    async def _fetch_answers(self, question_id: int) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "order": "desc",
            "sort": "votes",
            "site": "stackoverflow",
            "filter": "withbody",
            "pagesize": 5,
        }
        if self.api_key:
            params["key"] = self.api_key

        try:
            resp = await self._client.get(
                f"{SO_API_BASE}/questions/{question_id}/answers", params=params
            )
            resp.raise_for_status()
            data = resp.json()
            return [
                {
                    "answer_id": a["answer_id"],
                    "body": a.get("body", ""),
                    "score": a.get("score", 0),
                    "is_accepted": a.get("is_accepted", False),
                }
                for a in data.get("items", [])
            ]
        except httpx.HTTPError as e:
            logger.error("Failed to fetch answers for q=%d: %s", question_id, e)
            return []

    async def scrape_all(self, tags: list[str] | None = None) -> list[dict[str, Any]]:
        tags = tags or DEFAULT_TAGS
        all_results: list[dict[str, Any]] = []

        for tag in tags:
            logger.info("Scraping tag: %s", tag)
            results = await self.scrape_tag(tag)
            all_results.extend(results)
            await asyncio.sleep(1)

        logger.info("Total scraped: %d questions", len(all_results))
        return all_results

    async def close(self):
        await self._client.aclose()
