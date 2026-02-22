"""GitHub Issues scraper for popular repositories.

Targets repos with high issue volume and extracts closed issues
that have resolution comments.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

GH_API_BASE = "https://api.github.com"

DEFAULT_REPOS = [
    "vercel/next.js",
    "facebook/react",
    "nodejs/node",
    "microsoft/TypeScript",
    "python/cpython",
    "pallets/flask",
    "django/django",
    "fastapi/fastapi",
    "vitejs/vite",
    "webpack/webpack",
    "prisma/prisma",
    "supabase/supabase",
    "docker/compose",
    "kubernetes/kubernetes",
    "rust-lang/rust",
    "golang/go",
]


class GitHubIssueScraper:
    def __init__(self, token: str | None = None, max_pages: int = 3):
        self.token = token
        self.max_pages = max_pages
        headers: dict[str, str] = {"Accept": "application/vnd.github+json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._client = httpx.AsyncClient(headers=headers, timeout=30.0)

    async def scrape_repo(
        self, repo: str, per_page: int = 30
    ) -> list[dict[str, Any]]:
        """Scrape closed issues with comments from a repo."""
        results: list[dict[str, Any]] = []

        for page in range(1, self.max_pages + 1):
            try:
                resp = await self._client.get(
                    f"{GH_API_BASE}/repos/{repo}/issues",
                    params={
                        "state": "closed",
                        "sort": "comments",
                        "direction": "desc",
                        "per_page": per_page,
                        "page": page,
                        "labels": "bug",
                    },
                )
                resp.raise_for_status()
                issues = resp.json()

                if not issues:
                    break

                for issue in issues:
                    if issue.get("pull_request"):
                        continue
                    if issue.get("comments", 0) == 0:
                        continue

                    comments = await self._fetch_comments(repo, issue["number"])

                    results.append({
                        "repo": repo,
                        "issue_number": issue["number"],
                        "title": issue.get("title", ""),
                        "body": issue.get("body", ""),
                        "labels": [l["name"] for l in issue.get("labels", [])],
                        "comments": comments,
                        "html_url": issue.get("html_url", ""),
                        "closed_at": issue.get("closed_at"),
                    })

            except httpx.HTTPError as e:
                logger.error("GH API error for %s page=%d: %s", repo, page, e)
                break

            await asyncio.sleep(0.5)

        logger.info("Scraped %d issues from %s", len(results), repo)
        return results

    async def _fetch_comments(
        self, repo: str, issue_number: int
    ) -> list[dict[str, Any]]:
        try:
            resp = await self._client.get(
                f"{GH_API_BASE}/repos/{repo}/issues/{issue_number}/comments",
                params={"per_page": 10},
            )
            resp.raise_for_status()
            return [
                {
                    "body": c.get("body", ""),
                    "author": c.get("user", {}).get("login", ""),
                    "created_at": c.get("created_at", ""),
                }
                for c in resp.json()
            ]
        except httpx.HTTPError as e:
            logger.error(
                "Failed to fetch comments for %s#%d: %s", repo, issue_number, e
            )
            return []

    async def scrape_all(
        self, repos: list[str] | None = None
    ) -> list[dict[str, Any]]:
        repos = repos or DEFAULT_REPOS
        all_results: list[dict[str, Any]] = []

        for repo in repos:
            logger.info("Scraping repo: %s", repo)
            results = await self.scrape_repo(repo)
            all_results.extend(results)
            await asyncio.sleep(1)

        logger.info("Total scraped: %d issues", len(all_results))
        return all_results

    async def close(self):
        await self._client.aclose()
