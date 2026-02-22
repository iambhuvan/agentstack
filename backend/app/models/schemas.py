from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ---------- Agent ----------

class AgentRegister(BaseModel):
    provider: str = Field(..., examples=["anthropic"])
    model: str = Field(..., examples=["claude-opus-4-6"])
    display_name: str = Field(..., examples=["Claude Opus 4.6"])


class AgentResponse(BaseModel):
    id: UUID
    provider: str
    model: str
    display_name: str
    reputation_score: float
    total_contributions: int
    total_verifications: int
    created_at: datetime
    api_key: Optional[str] = Field(None, description="Only returned on registration")

    model_config = {"from_attributes": True}


class AgentStats(BaseModel):
    id: UUID
    display_name: str
    provider: str
    model: str
    reputation_score: float
    total_contributions: int
    total_verifications: int
    solutions_success_rate: float
    top_tags: list[str]

    model_config = {"from_attributes": True}


# ---------- Environment ----------

class EnvironmentContext(BaseModel):
    language: Optional[str] = None
    language_version: Optional[str] = None
    framework: Optional[str] = None
    framework_version: Optional[str] = None
    runtime: Optional[str] = None
    runtime_version: Optional[str] = None
    os: Optional[str] = None
    package_manager: Optional[str] = None
    agent_model: Optional[str] = None


# ---------- Bug ----------

class BugCreate(BaseModel):
    error_pattern: str = Field(..., description="The raw error message or pattern")
    error_type: str = Field(..., examples=["TypeError", "ERESOLVE", "ImportError"])
    environment: Optional[EnvironmentContext] = None
    tags: list[str] = Field(default_factory=list)


class BugResponse(BaseModel):
    id: UUID
    structural_hash: str
    error_pattern: str
    error_type: str
    environment: dict
    tags: list
    solution_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------- Solution ----------

class SolutionStep(BaseModel):
    action: str = Field(..., examples=["exec", "patch", "delete", "create"])
    target: Optional[str] = None
    command: Optional[str] = None
    diff: Optional[str] = None
    content: Optional[str] = None
    description: Optional[str] = None


class SolutionCreate(BaseModel):
    approach_name: str
    steps: list[SolutionStep]
    diff_patch: Optional[str] = None
    version_constraints: dict = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class SolutionResponse(BaseModel):
    id: UUID
    bug_id: UUID
    contributed_by: UUID
    approach_name: str
    steps: list
    diff_patch: Optional[str]
    success_rate: float
    total_attempts: int
    success_count: int
    failure_count: int
    avg_resolution_ms: int
    version_constraints: dict
    warnings: list
    source: str
    created_at: datetime
    last_verified: datetime

    model_config = {"from_attributes": True}


# ---------- Failed Approach ----------

class FailedApproachResponse(BaseModel):
    id: UUID
    bug_id: UUID
    approach_name: str
    command_or_action: Optional[str]
    failure_rate: float
    common_followup_error: Optional[str]
    reason: Optional[str]

    model_config = {"from_attributes": True}


# ---------- Contribute ----------

class ContributeRequest(BaseModel):
    bug: BugCreate
    solution: SolutionCreate
    failed_approaches: list[dict] = Field(default_factory=list)


class ContributeResponse(BaseModel):
    bug_id: UUID
    solution_id: UUID
    is_new_bug: bool
    message: str


# ---------- Search ----------

class SearchRequest(BaseModel):
    error_pattern: str
    error_type: Optional[str] = None
    environment: Optional[EnvironmentContext] = None
    agent_model: Optional[str] = None
    agent_provider: Optional[str] = None
    max_results: int = Field(default=10, le=50)


class SearchResult(BaseModel):
    bug: BugResponse
    solutions: list[SolutionResponse]
    failed_approaches: list[FailedApproachResponse]
    match_type: str = Field(..., description="exact_hash | semantic_similar")
    similarity_score: Optional[float] = None


class SearchResponse(BaseModel):
    results: list[SearchResult]
    total_found: int
    search_time_ms: int


# ---------- Verify ----------

class VerifyRequest(BaseModel):
    solution_id: UUID
    success: bool
    context: dict = Field(default_factory=dict)
    resolution_time_ms: Optional[int] = None


class VerifyResponse(BaseModel):
    verification_id: UUID
    solution_id: UUID
    new_success_rate: float
    message: str
