"""Stack Overflow scraper using the public Stack Exchange API.

Uses /2.3/search/advanced and /2.3/questions/{ids}/answers endpoints
to pull bug/error questions with accepted or top-voted answers.

Stack Exchange IP-based rate limit: 10,000 requests/day with an API key.
Answer fetching is batched (up to 100 question IDs per request) to
minimize quota usage.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

SO_API_BASE = "https://api.stackexchange.com/2.3"
ANSWER_BATCH_SIZE = 100  # SE API supports up to 100 semicolon-separated IDs

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
    def __init__(self, api_key: str | None = None, max_pages: int = 200):
        self.api_key = api_key
        self.max_pages = max_pages
        self._client = httpx.AsyncClient(timeout=30.0)
        self._quota_remaining: int | None = None
        self._api_calls = 0

    def _update_quota(self, data: dict[str, Any]) -> None:
        self._quota_remaining = data.get("quota_remaining")
        self._api_calls += 1
        if self._api_calls % 50 == 0 or (self._quota_remaining and self._quota_remaining < 500):
            logger.info(
                "API usage — calls this session: %d, quota remaining: %s",
                self._api_calls, self._quota_remaining,
            )

    def _quota_exhausted(self) -> bool:
        if self._quota_remaining is not None and self._quota_remaining < 100:
            logger.warning("SO API quota critically low: %d remaining — stopping", self._quota_remaining)
            return True
        return False

    async def scrape_tag(self, tag: str, page_size: int = 100) -> list[dict[str, Any]]:
        """Scrape questions for a given tag that contain error-related content."""
        candidates: list[dict[str, Any]] = []

        for page in range(1, self.max_pages + 1):
            if self._quota_exhausted():
                break

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
                self._update_quota(data)

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

                    candidates.append(q)

                if not data.get("has_more", False):
                    break

            except httpx.HTTPError as e:
                logger.error("SO API error for tag=%s page=%d: %s", tag, page, e)
                break

            await asyncio.sleep(0.1)

        if not candidates:
            logger.info("Scraped 0 questions for tag=%s", tag)
            return []

        question_ids = [q["question_id"] for q in candidates]
        answers_map = await self._fetch_answers_batch(question_ids)

        results: list[dict[str, Any]] = []
        for q in candidates:
            qid = q["question_id"]
            answers = answers_map.get(qid, [])
            if not answers:
                continue

            results.append({
                "question_id": qid,
                "title": q.get("title", ""),
                "body": q.get("body", ""),
                "tags": q.get("tags", []),
                "score": q.get("score", 0),
                "accepted_answer_id": q.get("accepted_answer_id"),
                "answers": answers,
                "link": q.get("link", ""),
            })

        logger.info("Scraped %d questions for tag=%s (%d candidates, %d with answers)",
                     len(results), tag, len(candidates), len(results))
        return results

    async def _fetch_answers_batch(self, question_ids: list[int]) -> dict[int, list[dict[str, Any]]]:
        """Fetch answers for multiple questions in batches of up to 100 IDs."""
        answers_map: dict[int, list[dict[str, Any]]] = {}

        for i in range(0, len(question_ids), ANSWER_BATCH_SIZE):
            if self._quota_exhausted():
                break

            batch = question_ids[i : i + ANSWER_BATCH_SIZE]
            ids_str = ";".join(str(qid) for qid in batch)

            params: dict[str, Any] = {
                "order": "desc",
                "sort": "votes",
                "site": "stackoverflow",
                "filter": "withbody",
                "pagesize": 100,
            }
            if self.api_key:
                params["key"] = self.api_key

            try:
                resp = await self._client.get(
                    f"{SO_API_BASE}/questions/{ids_str}/answers", params=params
                )
                resp.raise_for_status()
                data = resp.json()
                self._update_quota(data)

                for a in data.get("items", []):
                    qid = a["question_id"]
                    answers_map.setdefault(qid, [])
                    if len(answers_map[qid]) < 5:
                        answers_map[qid].append({
                            "answer_id": a["answer_id"],
                            "body": a.get("body", ""),
                            "score": a.get("score", 0),
                            "is_accepted": a.get("is_accepted", False),
                        })

            except httpx.HTTPError as e:
                logger.error("Failed to fetch answers for batch starting at idx %d: %s", i, e)

            await asyncio.sleep(0.1)

        return answers_map

    async def scrape_all(self, tags: list[str] | None = None) -> list[dict[str, Any]]:
        tags = tags or DEFAULT_TAGS
        all_results: list[dict[str, Any]] = []

        for tag in tags:
            if self._quota_exhausted():
                break
            logger.info("Scraping tag: %s (%d/%d)", tag, tags.index(tag) + 1, len(tags))
            results = await self.scrape_tag(tag)
            all_results.extend(results)
            await asyncio.sleep(0.25)

        logger.info(
            "Scraping complete — %d questions total, %d API calls, quota remaining: %s",
            len(all_results), self._api_calls, self._quota_remaining,
        )
        return all_results

    async def close(self):
        await self._client.aclose()
