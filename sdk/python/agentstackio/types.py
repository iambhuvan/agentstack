from dataclasses import dataclass, field
from typing import Literal, Optional


@dataclass
class EnvironmentContext:
    language: Optional[str] = None
    language_version: Optional[str] = None
    framework: Optional[str] = None
    framework_version: Optional[str] = None
    runtime: Optional[str] = None
    runtime_version: Optional[str] = None
    os: Optional[str] = None
    package_manager: Optional[str] = None
    agent_model: Optional[str] = None

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v is not None}


@dataclass
class SolutionStep:
    action: Literal["exec", "patch", "delete", "create", "description"]
    target: Optional[str] = None
    command: Optional[str] = None
    diff: Optional[str] = None
    content: Optional[str] = None
    description: Optional[str] = None

    def __post_init__(self):
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

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v is not None}


@dataclass
class FailedApproachCreate:
    approach_name: str
    command_or_action: Optional[str] = None
    failure_rate: float = 0.0
    common_followup_error: Optional[str] = None
    reason: Optional[str] = None

    def __post_init__(self):
        if self.failure_rate < 0.0 or self.failure_rate > 1.0:
            raise ValueError("`failure_rate` must be between 0.0 and 1.0")

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v is not None}


@dataclass
class BugInfo:
    id: str
    structural_hash: str
    error_pattern: str
    error_type: str
    environment: dict = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    solution_count: int = 0
    created_at: str = ""


@dataclass
class SolutionInfo:
    id: str
    bug_id: str
    contributed_by: str
    approach_name: str
    steps: list[dict] = field(default_factory=list)
    diff_patch: Optional[str] = None
    success_rate: float = 0.0
    total_attempts: int = 0
    success_count: int = 0
    failure_count: int = 0
    avg_resolution_ms: int = 0
    version_constraints: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    source: str = "agent_verified"
    created_at: str = ""
    last_verified: str = ""


@dataclass
class FailedApproachInfo:
    id: str
    bug_id: str
    approach_name: str
    command_or_action: Optional[str] = None
    failure_rate: float = 0.0
    common_followup_error: Optional[str] = None
    reason: Optional[str] = None


@dataclass
class SearchResult:
    bug: BugInfo
    solutions: list[SolutionInfo] = field(default_factory=list)
    failed_approaches: list[FailedApproachInfo] = field(default_factory=list)
    match_type: str = "exact_hash"
    similarity_score: Optional[float] = None


@dataclass
class SearchResponse:
    results: list[SearchResult] = field(default_factory=list)
    total_found: int = 0
    search_time_ms: int = 0


@dataclass
class ContributeResponse:
    bug_id: str = ""
    solution_id: str = ""
    is_new_bug: bool = False
    message: str = ""


@dataclass
class VerifyResponse:
    verification_id: str = ""
    solution_id: str = ""
    new_success_rate: float = 0.0
    message: str = ""
