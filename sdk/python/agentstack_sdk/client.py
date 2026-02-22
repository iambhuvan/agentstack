from __future__ import annotations

from typing import Any, Optional

import httpx

from agentstack_sdk.types import (
    BugInfo,
    ContributeResponse,
    EnvironmentContext,
    FailedApproachInfo,
    SearchResponse,
    SearchResult,
    SolutionInfo,
    SolutionStep,
    VerifyResponse,
)

DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_TIMEOUT = 30.0


class AgentStackClient:
    """Python client for the AgentStack API."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        api_key: Optional[str] = None,
        agent_model: Optional[str] = None,
        agent_provider: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.agent_model = agent_model
        self.agent_provider = agent_provider
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout,
        )

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
        failed_approaches: Optional[list[dict[str, Any]]] = None,
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
            "failed_approaches": failed_approaches or [],
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
        headers: dict[str, str] = {}
        if auth:
            if not self.api_key:
                raise ValueError("API key required for this operation.")
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
