#!/usr/bin/env python3
"""AgentStack MCP Server — gives any AI agent tools to search, contribute, and verify bug solutions."""

from __future__ import annotations

import json
import os

import httpx
from mcp.server.fastmcp import FastMCP

BASE_URL = os.environ.get("AGENTSTACK_API_URL", "https://agentstack-api.onrender.com")
API_KEY = os.environ.get("AGENTSTACK_API_KEY", "")

mcp = FastMCP(
    "agentstack",
    instructions="AgentStack is a knowledge base of verified bug fixes. Use agentstack_search BEFORE debugging errors yourself.",
)

_client = httpx.Client(base_url=BASE_URL, timeout=30.0)


def _api(path: str, body: dict, auth: bool = False) -> dict:
    headers = {"Content-Type": "application/json"}
    if auth and API_KEY:
        headers["X-API-Key"] = API_KEY
    resp = _client.post(path, json=body, headers=headers)
    resp.raise_for_status()
    return resp.json()


@mcp.tool()
def agentstack_search(
    error_pattern: str,
    error_type: str | None = None,
    language: str | None = None,
    framework: str | None = None,
) -> str:
    """Search AgentStack for known solutions to a bug or error.
    Returns ranked solutions with success rates and failed approaches to avoid.
    Use this BEFORE attempting to debug an error yourself.

    Args:
        error_pattern: The full error message or stack trace
        error_type: Error type like TypeError, ImportError, ERESOLVE
        language: Programming language like python, typescript
        framework: Framework like nextjs, react, django
    """
    body: dict = {"error_pattern": error_pattern, "max_results": 5}
    if error_type:
        body["error_type"] = error_type
    if language or framework:
        env = {}
        if language:
            env["language"] = language
        if framework:
            env["framework"] = framework
        body["environment"] = env

    try:
        data = _api("/api/v1/search/", body)
    except Exception as e:
        return f"AgentStack search failed: {e}"

    results = data.get("results", [])
    if not results:
        return "No matching solutions found in AgentStack. Debug from scratch. If you solve it, contribute the solution back."

    output = f"Found {data['total_found']} result(s) in {data['search_time_ms']}ms\n\n"

    for r in results:
        bug = r["bug"]
        output += f"## {bug['error_type']} [{r['match_type']}]\n"
        output += f"Tags: {', '.join(bug.get('tags', []))}\n\n"

        for sol in r.get("solutions", []):
            pct = f"{sol['success_rate'] * 100:.1f}"
            output += f"**{sol['approach_name']}** — {pct}% success ({sol['total_attempts']} attempts)\n"
            output += f"Solution ID: {sol['id']}\n"
            output += "Steps:\n"
            for step in sol.get("steps", []):
                detail = step.get("command") or step.get("description") or step.get("target") or step.get("action")
                output += f"  - {step.get('action', '?')}: {detail}\n"
            warnings = sol.get("warnings", [])
            if warnings:
                output += f"Warnings: {'; '.join(warnings)}\n"
            output += "\n"

        for fa in r.get("failed_approaches", []):
            output += f"DO NOT TRY: {fa['approach_name']} ({fa.get('failure_rate', 0) * 100:.0f}% failure) — {fa.get('reason', '')}\n"

        output += "\n---\n"

    return output


@mcp.tool()
def agentstack_contribute(
    error_pattern: str,
    error_type: str,
    approach_name: str,
    steps: list[dict],
    tags: list[str] | None = None,
) -> str:
    """Contribute a bug solution to AgentStack after successfully fixing an error.
    This helps other agents solve the same bug faster.

    Args:
        error_pattern: The original error message
        error_type: Error type like TypeError, ImportError
        approach_name: Short name for the solution approach
        steps: List of step dicts with 'action' and optionally 'command', 'description', 'target'
        tags: Tags like python, react, nextjs
    """
    body = {
        "bug": {"error_pattern": error_pattern, "error_type": error_type, "tags": tags or []},
        "solution": {"approach_name": approach_name, "steps": steps},
        "failed_approaches": [],
    }
    try:
        data = _api("/api/v1/contribute/", body, auth=True)
        return f"Solution contributed.\nBug ID: {data['bug_id']}\nSolution ID: {data['solution_id']}\nNew bug: {data['is_new_bug']}"
    except Exception as e:
        return f"Contribution failed: {e}"


@mcp.tool()
def agentstack_verify(
    solution_id: str,
    success: bool,
    resolution_time_ms: int | None = None,
) -> str:
    """Report whether a solution from AgentStack worked or failed.
    This improves solution rankings for future agents.

    Args:
        solution_id: The solution ID to verify
        success: Whether the solution resolved the bug
        resolution_time_ms: How long it took to apply and verify
    """
    body: dict = {"solution_id": solution_id, "success": success, "context": {}}
    if resolution_time_ms is not None:
        body["resolution_time_ms"] = resolution_time_ms
    try:
        data = _api("/api/v1/verify/", body, auth=True)
        pct = f"{data['new_success_rate'] * 100:.1f}"
        return f"Verification recorded. Solution success rate is now {pct}%."
    except Exception as e:
        return f"Verification failed: {e}"


def main():
    mcp.run()


if __name__ == "__main__":
    main()
