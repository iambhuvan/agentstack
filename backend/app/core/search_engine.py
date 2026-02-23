import time
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.core.embeddings import generate_embedding
from app.core.fingerprint import fingerprint
from app.core.ranker import rank_solutions
from app.models.database import Agent, Bug, FailedApproach, Solution

settings = get_settings()


class SearchEngine:
    """Hierarchical search: exact hash (same model -> same provider -> any) then semantic."""

    def __init__(self, db: Session):
        self.db = db

    def search(
        self,
        error_pattern: str,
        error_type: str | None = None,
        agent_provider: str | None = None,
        agent_model: str | None = None,
        environment: dict | None = None,
        max_results: int = 10,
    ) -> list[dict]:
        start = time.time()
        normalized, shash = fingerprint(error_pattern)

        results = self._exact_hash_search(shash, agent_model, agent_provider)

        if not results:
            embedding = generate_embedding(normalized)
            results = self._semantic_search(embedding, error_type, max_results)

        for r in results:
            r["solutions"] = rank_solutions(
                r["solutions"], agent_provider, agent_model, environment
            )[:max_results]

        elapsed_ms = int((time.time() - start) * 1000)
        for r in results:
            r["search_time_ms"] = elapsed_ms

        return results[:max_results]

    def _exact_hash_search(
        self,
        structural_hash: str,
        agent_model: str | None,
        agent_provider: str | None,
    ) -> list[dict]:
        bugs = (
            self.db.execute(
                select(Bug)
                .where(Bug.structural_hash == structural_hash)
                .options(
                    joinedload(Bug.solutions).joinedload(Solution.contributor),
                    joinedload(Bug.failed_approaches),
                )
            )
            .unique()
            .scalars()
            .all()
        )

        if not bugs:
            return []

        results = []
        for bug in bugs:
            if not bug.solutions:
                continue
            lvl1 = [s for s in bug.solutions if agent_model and s.contributor and s.contributor.model == agent_model]
            lvl2 = [s for s in bug.solutions if agent_provider and s.contributor and s.contributor.provider == agent_provider]
            lvl3 = list(bug.solutions)

            if lvl1:
                solutions = lvl1
            elif lvl2:
                solutions = lvl2
            else:
                solutions = lvl3

            results.append({
                "bug": bug,
                "solutions": solutions,
                "failed_approaches": list(bug.failed_approaches),
                "match_type": "exact_hash",
                "similarity_score": 1.0,
            })

        return results

    def _semantic_search(
        self,
        embedding: list[float],
        error_type: str | None,
        max_results: int,
    ) -> list[dict]:
        embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

        type_filter = ""
        params: dict = {
            "threshold": settings.search_similarity_threshold,
            "limit": max_results,
        }
        if error_type:
            type_filter = "AND b.error_type = :error_type"
            params["error_type"] = error_type

        safe_embedding = embedding_str.replace("'", "")
        query = text(f"""
            SELECT b.id, 1 - (b.embedding <=> '{safe_embedding}'::vector) AS similarity
            FROM bugs b
            WHERE b.embedding IS NOT NULL
            AND b.solution_count > 0
            {type_filter}
            AND 1 - (b.embedding <=> '{safe_embedding}'::vector) > :threshold
            ORDER BY similarity DESC
            LIMIT :limit
        """)

        rows = self.db.execute(query, params).fetchall()

        if not rows:
            return []

        bug_ids = [row[0] for row in rows]
        similarity_map = {row[0]: row[1] for row in rows}

        bugs = (
            self.db.execute(
                select(Bug)
                .where(Bug.id.in_(bug_ids))
                .options(
                    joinedload(Bug.solutions).joinedload(Solution.contributor),
                    joinedload(Bug.failed_approaches),
                )
            )
            .unique()
            .scalars()
            .all()
        )

        results = []
        for bug in bugs:
            results.append({
                "bug": bug,
                "solutions": list(bug.solutions),
                "failed_approaches": list(bug.failed_approaches),
                "match_type": "semantic_similar",
                "similarity_score": float(similarity_map.get(bug.id, 0)),
            })

        results.sort(key=lambda r: r["similarity_score"], reverse=True)
        if results:
            top_similarity = float(results[0]["similarity_score"])
            if top_similarity < settings.search_semantic_confidence_threshold:
                return []
        return results
