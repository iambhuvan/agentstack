from __future__ import annotations

from datetime import datetime, timezone
import sys
from types import SimpleNamespace
import types
from uuid import uuid4

if "pgvector.sqlalchemy" not in sys.modules:
    from sqlalchemy.types import UserDefinedType

    pgvector_module = types.ModuleType("pgvector")
    pgvector_sqlalchemy = types.ModuleType("pgvector.sqlalchemy")

    class Vector(UserDefinedType):  # pragma: no cover - compatibility shim for local test envs
        def __init__(self, *args, **kwargs):
            pass

        def get_col_spec(self, **_kw):
            return "VECTOR"

    pgvector_sqlalchemy.Vector = Vector
    pgvector_module.sqlalchemy = pgvector_sqlalchemy
    sys.modules["pgvector"] = pgvector_module
    sys.modules["pgvector.sqlalchemy"] = pgvector_sqlalchemy

from app.api.routes import search as search_route
from app.core.search_engine import SearchEngine
from app.models.schemas import SearchRequest


class _ScalarOneOrNoneResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _BugListResult:
    def __init__(self, bugs):
        self._bugs = bugs

    def unique(self):
        return self

    def scalars(self):
        return self

    def all(self):
        return self._bugs


class _FakeRouteDB:
    def __init__(self, existing_bug=None):
        self.existing_bug = existing_bug
        self.added = []
        self.commits = 0

    def execute(self, _query):
        return _ScalarOneOrNoneResult(self.existing_bug)

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.commits += 1

    def refresh(self, obj):
        if not getattr(obj, "id", None):
            obj.id = uuid4()


class _FakeExactSearchDB:
    def __init__(self, bugs):
        self.bugs = bugs

    def execute(self, _query):
        return _BugListResult(self.bugs)


def _make_solution(total_attempts: int):
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=uuid4(),
        bug_id=uuid4(),
        contributed_by=uuid4(),
        approach_name="Fix",
        steps=[{"action": "description", "description": "Try this fix"}],
        diff_patch=None,
        success_rate=0.6,
        total_attempts=total_attempts,
        success_count=1 if total_attempts else 0,
        failure_count=0 if total_attempts else 1,
        avg_resolution_ms=500,
        version_constraints={},
        warnings=[],
        source="agent_verified",
        created_at=now,
        last_verified=now,
        contributor=SimpleNamespace(model="m", provider="p"),
    )


def _make_bug_with_context():
    return SimpleNamespace(
        id=uuid4(),
        structural_hash="hash",
        error_pattern="TypeError: nope",
        error_type="TypeError",
        environment={"language": "python", "context_packet": {"trace_id": "abc"}},
        tags=["python"],
        solution_count=1,
        created_at=datetime.now(timezone.utc),
    )


def test_auto_contribute_on_miss_creates_bug(monkeypatch):
    class _FakeSearchEngine:
        def __init__(self, _db):
            pass

        def search(self, **_kwargs):
            return []

    monkeypatch.setattr(search_route, "SearchEngine", _FakeSearchEngine)
    monkeypatch.setattr(search_route, "fingerprint", lambda _x: ("norm", "h1"))
    monkeypatch.setattr(search_route, "generate_embedding", lambda _x: [0.1, 0.2])

    db = _FakeRouteDB(existing_bug=None)
    payload = SearchRequest(
        error_pattern="WeirdError: boom",
        auto_contribute_on_miss=True,
        context_packet={"session": "qa"},
    )

    response = search_route.search_bugs(payload, db)

    assert response.total_found == 0
    assert response.auto_contributed_bug_id is not None
    assert len(db.added) == 1
    assert db.added[0].environment["context_packet"] == {"session": "qa"}


def test_auto_contribute_on_miss_dedupes_existing_bug(monkeypatch):
    class _FakeSearchEngine:
        def __init__(self, _db):
            pass

        def search(self, **_kwargs):
            return []

    monkeypatch.setattr(search_route, "SearchEngine", _FakeSearchEngine)
    monkeypatch.setattr(search_route, "fingerprint", lambda _x: ("norm", "h1"))

    existing_bug = SimpleNamespace(id=uuid4())
    db = _FakeRouteDB(existing_bug=existing_bug)
    payload = SearchRequest(
        error_pattern="WeirdError: boom",
        auto_contribute_on_miss=True,
    )

    response = search_route.search_bugs(payload, db)

    assert response.auto_contributed_bug_id == existing_bug.id
    assert len(db.added) == 0


def test_search_response_strips_context_packet_and_flags_low_confidence(monkeypatch):
    solution = _make_solution(total_attempts=0)
    bug = _make_bug_with_context()
    raw_results = [{
        "bug": bug,
        "solutions": [solution],
        "failed_approaches": [],
        "match_type": "semantic_similar",
        "similarity_score": 0.81,
    }]

    class _FakeSearchEngine:
        def __init__(self, _db):
            pass

        def search(self, **_kwargs):
            return raw_results

    monkeypatch.setattr(search_route, "SearchEngine", _FakeSearchEngine)
    db = _FakeRouteDB(existing_bug=None)

    payload = SearchRequest(error_pattern="TypeError: nope")
    response = search_route.search_bugs(payload, db)

    assert response.results[0].bug.environment == {"language": "python"}
    assert response.top_similarity == 0.81
    assert response.is_confident_match is False


def test_semantic_match_with_verified_attempts_is_confident(monkeypatch):
    solution = _make_solution(total_attempts=2)
    bug = _make_bug_with_context()
    raw_results = [{
        "bug": bug,
        "solutions": [solution],
        "failed_approaches": [],
        "match_type": "semantic_similar",
        "similarity_score": 0.9,
    }]

    class _FakeSearchEngine:
        def __init__(self, _db):
            pass

        def search(self, **_kwargs):
            return raw_results

    monkeypatch.setattr(search_route, "SearchEngine", _FakeSearchEngine)
    db = _FakeRouteDB(existing_bug=None)

    payload = SearchRequest(error_pattern="TypeError: nope")
    response = search_route.search_bugs(payload, db)

    assert response.is_confident_match is True


def test_exact_hash_search_skips_unsolved_bugs():
    solved_bug = SimpleNamespace(
        id=uuid4(),
        solutions=[_make_solution(total_attempts=3)],
        failed_approaches=[],
    )
    unsolved_bug = SimpleNamespace(
        id=uuid4(),
        solutions=[],
        failed_approaches=[],
    )
    engine = SearchEngine(_FakeExactSearchDB([unsolved_bug, solved_bug]))

    results = engine._exact_hash_search("h1", None, None)

    assert len(results) == 1
    assert results[0]["bug"].id == solved_bug.id
