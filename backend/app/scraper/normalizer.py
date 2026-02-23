"""Normalizer pipeline to convert raw scraped data into AgentStack schema.

Transforms Stack Overflow Q&A and GitHub Issues into structured
bug/solution records ready for database insertion.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from app.core.embeddings import generate_embedding, generate_embeddings_batch
from app.core.fingerprint import fingerprint

logger = logging.getLogger(__name__)

CODE_BLOCK_RE = re.compile(r"<code>(.*?)</code>", re.DOTALL)
PRE_BLOCK_RE = re.compile(r"<pre>(.*?)</pre>", re.DOTALL)
HTML_TAG_RE = re.compile(r"<[^>]+>")
MD_CODE_BLOCK_RE = re.compile(r"```[\w]*\n(.*?)```", re.DOTALL)


def _extract_code_blocks(html_or_md: str) -> list[str]:
    blocks = CODE_BLOCK_RE.findall(html_or_md)
    blocks.extend(PRE_BLOCK_RE.findall(html_or_md))
    blocks.extend(MD_CODE_BLOCK_RE.findall(html_or_md))
    return [HTML_TAG_RE.sub("", b).strip() for b in blocks if b.strip()]


def _strip_html(text: str) -> str:
    return HTML_TAG_RE.sub("", text).strip()


def _detect_error_type(text: str) -> str:
    patterns = [
        (r"TypeError", "TypeError"),
        (r"ReferenceError", "ReferenceError"),
        (r"SyntaxError", "SyntaxError"),
        (r"ImportError", "ImportError"),
        (r"ModuleNotFoundError", "ModuleNotFoundError"),
        (r"KeyError", "KeyError"),
        (r"ValueError", "ValueError"),
        (r"AttributeError", "AttributeError"),
        (r"FileNotFoundError", "FileNotFoundError"),
        (r"ConnectionError", "ConnectionError"),
        (r"TimeoutError", "TimeoutError"),
        (r"PermissionError", "PermissionError"),
        (r"ERESOLVE", "ERESOLVE"),
        (r"ENOENT", "ENOENT"),
        (r"EACCES", "EACCES"),
        (r"ERR_MODULE_NOT_FOUND", "ERR_MODULE_NOT_FOUND"),
        (r"NullPointerException", "NullPointerException"),
        (r"ClassNotFoundException", "ClassNotFoundException"),
        (r"segmentation fault", "SegmentationFault"),
        (r"compilation error", "CompilationError"),
        (r"build error", "BuildError"),
    ]
    text_lower = text.lower()
    for pattern, error_type in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return error_type

    if "error" in text_lower:
        return "GenericError"
    if "exception" in text_lower:
        return "GenericException"
    return "Unknown"


def normalize_so_question(raw: dict[str, Any], embedding: list[float] | None = None) -> dict[str, Any] | None:
    """Convert a raw Stack Overflow question + answers into AgentStack schema."""
    title = _strip_html(raw.get("title", ""))
    body = _strip_html(raw.get("body", ""))
    error_text = f"{title}\n{body}"

    error_type = _detect_error_type(error_text)
    normalized_error, shash = fingerprint(error_text)
    if embedding is None:
        embedding = generate_embedding(normalized_error)

    answers = raw.get("answers", [])
    accepted = [a for a in answers if a.get("is_accepted")]
    top_answers = accepted if accepted else sorted(answers, key=lambda a: a.get("score", 0), reverse=True)[:3]

    if not top_answers:
        return None

    solutions = []
    for answer in top_answers:
        answer_text = _strip_html(answer.get("body", ""))
        code_blocks = _extract_code_blocks(answer.get("body", ""))

        steps = []
        for block in code_blocks:
            if any(cmd in block for cmd in ["npm ", "pip ", "yarn ", "brew ", "apt ", "cargo "]):
                steps.append({"action": "exec", "command": block.strip()})
            elif "diff" in block or block.startswith("+") or block.startswith("-"):
                steps.append({"action": "patch", "diff": block.strip()})
            else:
                steps.append({"action": "code", "content": block.strip()})

        if not steps:
            steps.append({"action": "description", "description": answer_text[:500]})

        solutions.append({
            "approach_name": answer_text[:100].replace("\n", " "),
            "steps": steps,
            "score": answer.get("score", 0),
            "is_accepted": answer.get("is_accepted", False),
            "source": "human_sourced",
        })

    return {
        "structural_hash": shash,
        "embedding": embedding,
        "error_pattern": error_text[:2000],
        "error_type": error_type,
        "tags": raw.get("tags", []),
        "environment": {},
        "solutions": solutions,
        "source_url": raw.get("link", ""),
        "source_type": "stackoverflow",
    }


def normalize_gh_issue(raw: dict[str, Any]) -> dict[str, Any] | None:
    """Convert a raw GitHub issue + comments into AgentStack schema."""
    title = raw.get("title", "")
    body = raw.get("body", "") or ""
    error_text = f"{title}\n{body}"

    error_type = _detect_error_type(error_text)
    normalized_error, shash = fingerprint(error_text)
    embedding = generate_embedding(normalized_error)

    comments = raw.get("comments", [])
    if not comments:
        return None

    solutions = []
    for comment in comments[:3]:
        comment_body = comment.get("body", "")
        code_blocks = _extract_code_blocks(comment_body)

        steps = []
        for block in code_blocks:
            steps.append({"action": "code", "content": block.strip()})

        if not steps:
            plain = _strip_html(comment_body)
            if len(plain) > 20:
                steps.append({"action": "description", "description": plain[:500]})

        if steps:
            solutions.append({
                "approach_name": comment_body[:100].replace("\n", " "),
                "steps": steps,
                "source": "human_sourced",
            })

    if not solutions:
        return None

    repo = raw.get("repo", "")
    labels = raw.get("labels", [])
    tags = [repo.split("/")[-1]] + labels

    return {
        "structural_hash": shash,
        "embedding": embedding,
        "error_pattern": error_text[:2000],
        "error_type": error_type,
        "tags": tags,
        "environment": {},
        "solutions": solutions,
        "source_url": raw.get("html_url", ""),
        "source_type": "github_issues",
    }


def normalize_batch(
    raw_items: list[dict[str, Any]], source_type: str
) -> list[dict[str, Any]]:
    """Normalize a batch of raw items with batched embedding generation."""
    if source_type == "stackoverflow":
        return _normalize_so_batch(raw_items)

    normalizer = normalize_gh_issue
    results = []
    seen_hashes: set[str] = set()

    for item in raw_items:
        try:
            normalized = normalizer(item)
            if normalized and normalized["structural_hash"] not in seen_hashes:
                seen_hashes.add(normalized["structural_hash"])
                results.append(normalized)
        except Exception as e:
            logger.warning("Failed to normalize item: %s", e)

    logger.info("Normalized %d/%d items from %s", len(results), len(raw_items), source_type)
    return results


def _normalize_so_batch(raw_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize SO questions with batched embedding generation."""
    texts_for_embedding = []
    for item in raw_items:
        title = _strip_html(item.get("title", ""))
        body = _strip_html(item.get("body", ""))
        error_text = f"{title}\n{body}"
        normalized_error, _ = fingerprint(error_text)
        texts_for_embedding.append(normalized_error)

    logger.info("Generating embeddings for %d items in batch...", len(texts_for_embedding))
    embeddings = generate_embeddings_batch(texts_for_embedding)
    logger.info("Embeddings generated, normalizing items...")

    results = []
    seen_hashes: set[str] = set()

    for item, emb in zip(raw_items, embeddings):
        try:
            normalized = normalize_so_question(item, embedding=emb)
            if normalized and normalized["structural_hash"] not in seen_hashes:
                seen_hashes.add(normalized["structural_hash"])
                results.append(normalized)
        except Exception as e:
            logger.warning("Failed to normalize item: %s", e)

    logger.info("Normalized %d/%d items from stackoverflow", len(results), len(raw_items))
    return results
