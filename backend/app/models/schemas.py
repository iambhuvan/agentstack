from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


# ---------- Agent ----------

class AgentRegister(BaseModel):
    provider: Optional[str] = Field(default=None, examples=["anthropic"])
    model: Optional[str] = Field(default=None, examples=["claude-opus-4-6"])
    display_name: Optional[str] = Field(default=None, examples=["pikachu-01"])


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
    action: Literal["exec", "patch", "delete", "create", "description"] = Field(
        ..., examples=["exec", "patch", "delete", "create", "description"]
    )
    target: Optional[str] = None
    command: Optional[str] = None
    diff: Optional[str] = None
    content: Optional[str] = None
    description: Optional[str] = None

    @model_validator(mode="after")
    def validate_action_fields(self):
        if self.action == "exec" and not self.command:
            raise ValueError("`command` is required when action is `exec`")
        if self.action == "patch" and not (self.diff or self.target):
            raise ValueError("`diff` or `target` is required when action is `patch`")
        if self.action == "create" and not (self.target and self.content):
            raise ValueError("`target` and `content` are required when action is `create`")
        if self.action == "delete" and not self.target:
            raise ValueError("`target` is required when action is `delete`")
        if self.action == "description" and not self.description:
            raise ValueError("`description` is required when action is `description`")
        return self


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


class FailedApproachCreate(BaseModel):
    approach_name: str
    command_or_action: Optional[str] = None
    failure_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    common_followup_error: Optional[str] = None
    reason: Optional[str] = None

class ContributeRequest(BaseModel):
    bug: BugCreate
    solution: SolutionCreate
    failed_approaches: list[FailedApproachCreate] = Field(default_factory=list)


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
