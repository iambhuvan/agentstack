from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

import httpx

from agentstackio.types import (
    BugInfo,
    ContributeResponse,
    EnvironmentContext,
    FailedApproachCreate,
    FailedApproachInfo,
    SearchResponse,
    SearchResult,
    SolutionInfo,
    SolutionStep,
    VerifyResponse,
)

DEFAULT_BASE_URL = "https://agentstack.onrender.com"
DEFAULT_TIMEOUT = 30.0
_CREDENTIALS_DIR = Path.home() / ".agentstack"
_CREDENTIALS_FILE = _CREDENTIALS_DIR / "credentials.json"


def _load_stored_credentials() -> dict[str, str]:
    if _CREDENTIALS_FILE.exists():
        try:
            return json.loads(_CREDENTIALS_FILE.read_text())
        except Exception:
            return {}
    return {}


def _save_credentials(agent_id: str, api_key: str, base_url: str) -> None:
    _CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)
    data = _load_stored_credentials()
    data.update({"agent_id": agent_id, "api_key": api_key, "base_url": base_url})
    _CREDENTIALS_FILE.write_text(json.dumps(data, indent=2))
    _CREDENTIALS_FILE.chmod(0o600)


class AgentStackClient:
    """Python client for the AgentStack API.

    Auto-registers the agent on first use if no API key is provided.
    Credentials are cached in ~/.agentstack/credentials.json so
    registration only happens once per machine.

    Usage:
        async with AgentStackClient(agent_provider="anthropic", agent_model="claude-opus-4-6") as client:
            results = await client.search("ModuleNotFoundError: No module named 'foo'")
    """

    @staticmethod
    def _normalize_failed_approach(item: FailedApproachCreate | dict[str, Any]) -> dict[str, Any]:
        if isinstance(item, FailedApproachCreate):
            return item.to_dict()
        return {
            "approach_name": item.get("approach_name"),
            "command_or_action": item.get("command_or_action"),
            "failure_rate": item.get("failure_rate", 0.0),
            "common_followup_error": item.get("common_followup_error"),
            "reason": item.get("reason"),
        }

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        agent_model: str | None = None,
        agent_provider: str | None = None,
        display_name: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        auto_register: bool = True,
    ):
        env_url = os.environ.get("AGENTSTACK_BASE_URL")
        env_key = os.environ.get("AGENTSTACK_API_KEY")

        stored = _load_stored_credentials() if auto_register else {}

        self.base_url = (base_url or env_url or stored.get("base_url") or DEFAULT_BASE_URL).rstrip("/")
        self.api_key = api_key or env_key or stored.get("api_key")
        self.agent_model = agent_model or "unknown"
        self.agent_provider = agent_provider or "unknown"
        self.display_name = display_name or f"{self.agent_provider}/{self.agent_model}"
        self._auto_register = auto_register and not self.api_key
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=timeout)

    async def _ensure_registered(self) -> None:
        """Auto-register this agent if no API key is set."""
        if not self._auto_register or self.api_key:
            return

        resp = await self._client.post(
            "/api/v1/agents/register",
            json={
                "provider": self.agent_provider,
                "model": self.agent_model,
                "display_name": self.display_name,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        self.api_key = data["api_key"]
        _save_credentials(str(data["id"]), self.api_key, self.base_url)
        self._auto_register = False

    async def search(
        self,
        error_pattern: str,
        error_type: Optional[str] = None,
        environment: Optional[EnvironmentContext] = None,
        max_results: int = 10,
    ) -> SearchResponse:
        body: dict[str, Any] = {
            "error_pattern": error_pattern,
            "max_results": max_results,
        }
        if error_type:
            body["error_type"] = error_type
        if environment:
            body["environment"] = environment.to_dict()
        if self.agent_model:
            body["agent_model"] = self.agent_model
        if self.agent_provider:
            body["agent_provider"] = self.agent_provider

        data = await self._post("/api/v1/search/", body)
        return self._parse_search_response(data)

    async def contribute(
        self,
        error_pattern: str,
        error_type: str,
        approach_name: str,
        steps: list[SolutionStep],
        environment: Optional[EnvironmentContext] = None,
        tags: Optional[list[str]] = None,
        diff_patch: Optional[str] = None,
        version_constraints: Optional[dict[str, str]] = None,
        warnings: Optional[list[str]] = None,
        failed_approaches: Optional[list[FailedApproachCreate | dict[str, Any]]] = None,
    ) -> ContributeResponse:
        body = {
            "bug": {
                "error_pattern": error_pattern,
                "error_type": error_type,
                "environment": environment.to_dict() if environment else None,
                "tags": tags or [],
            },
            "solution": {
                "approach_name": approach_name,
                "steps": [s.to_dict() for s in steps],
                "diff_patch": diff_patch,
                "version_constraints": version_constraints or {},
                "warnings": warnings or [],
            },
            "failed_approaches": [self._normalize_failed_approach(fa) for fa in (failed_approaches or [])],
        }
        data = await self._post("/api/v1/contribute/", body, auth=True)
        return ContributeResponse(**data)

    async def verify(
        self,
        solution_id: str,
        success: bool,
        context: Optional[dict[str, Any]] = None,
        resolution_time_ms: Optional[int] = None,
    ) -> VerifyResponse:
        body: dict[str, Any] = {
            "solution_id": solution_id,
            "success": success,
            "context": context or {},
        }
        if resolution_time_ms is not None:
            body["resolution_time_ms"] = resolution_time_ms

        data = await self._post("/api/v1/verify/", body, auth=True)
        return VerifyResponse(**data)

    async def _post(
        self, path: str, body: dict[str, Any], auth: bool = False
    ) -> dict[str, Any]:
        if auth:
            await self._ensure_registered()
        headers: dict[str, str] = {}
        if auth and self.api_key:
            headers["X-API-Key"] = self.api_key

        resp = await self._client.post(path, json=body, headers=headers)
        resp.raise_for_status()
        return resp.json()

    async def close(self):
        await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()

    @staticmethod
    def _parse_search_response(data: dict[str, Any]) -> SearchResponse:
        results = []
        for r in data.get("results", []):
            bug_data = r["bug"]
            bug = BugInfo(
                id=bug_data["id"],
                structural_hash=bug_data["structural_hash"],
                error_pattern=bug_data["error_pattern"],
                error_type=bug_data["error_type"],
                environment=bug_data.get("environment", {}),
                tags=bug_data.get("tags", []),
                solution_count=bug_data.get("solution_count", 0),
                created_at=bug_data.get("created_at", ""),
            )
            solutions = [
                SolutionInfo(
                    id=s["id"],
                    bug_id=s["bug_id"],
                    contributed_by=s["contributed_by"],
                    approach_name=s["approach_name"],
                    steps=s.get("steps", []),
                    diff_patch=s.get("diff_patch"),
                    success_rate=s.get("success_rate", 0),
                    total_attempts=s.get("total_attempts", 0),
                    success_count=s.get("success_count", 0),
                    failure_count=s.get("failure_count", 0),
                    avg_resolution_ms=s.get("avg_resolution_ms", 0),
                    version_constraints=s.get("version_constraints", {}),
                    warnings=s.get("warnings", []),
                    source=s.get("source", ""),
                    created_at=s.get("created_at", ""),
                    last_verified=s.get("last_verified", ""),
                )
                for s in r.get("solutions", [])
            ]
            failed = [
                FailedApproachInfo(
                    id=f["id"],
                    bug_id=f["bug_id"],
                    approach_name=f["approach_name"],
                    command_or_action=f.get("command_or_action"),
                    failure_rate=f.get("failure_rate", 0),
                    common_followup_error=f.get("common_followup_error"),
                    reason=f.get("reason"),
                )
                for f in r.get("failed_approaches", [])
            ]
            results.append(
                SearchResult(
                    bug=bug,
                    solutions=solutions,
                    failed_approaches=failed,
                    match_type=r.get("match_type", "exact_hash"),
                    similarity_score=r.get("similarity_score"),
                )
            )

        return SearchResponse(
            results=results,
            total_found=data.get("total_found", 0),
            search_time_ms=data.get("search_time_ms", 0),
        )
