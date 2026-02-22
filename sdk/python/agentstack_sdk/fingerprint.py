import hashlib
import re

_PATH_PATTERN = re.compile(
    r"(/[a-zA-Z0-9_./-]+|[A-Z]:\\[a-zA-Z0-9_.\\ -]+|~/[a-zA-Z0-9_./-]+)"
)
_LINE_COL_PATTERN = re.compile(r"(line |ln |:)\d+(:\d+)?", re.IGNORECASE)
_MEMORY_ADDR_PATTERN = re.compile(r"0x[0-9a-fA-F]{4,16}")
_TIMESTAMP_PATTERN = re.compile(
    r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:?\d{2})?"
)
_UUID_PATTERN = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE
)
_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")
_STACK_FRAME_AT = re.compile(r"^\s+at .+$", re.MULTILINE)
_PYTHON_TRACEBACK_FILE = re.compile(r'File "[^"]+", line \d+', re.MULTILINE)
_VARIABLE_NAMES = re.compile(r"'[a-zA-Z_]\w*'")
_NUMERIC_LITERALS = re.compile(r"\b\d{3,}\b")


def normalize_error(raw_error: str) -> str:
    """Strip environment-specific noise from an error message."""
    text = raw_error.strip()
    text = _ANSI_ESCAPE.sub("", text)
    text = _TIMESTAMP_PATTERN.sub("<TIMESTAMP>", text)
    text = _UUID_PATTERN.sub("<UUID>", text)
    text = _MEMORY_ADDR_PATTERN.sub("<ADDR>", text)
    text = _PATH_PATTERN.sub("<PATH>", text)
    text = _LINE_COL_PATTERN.sub("<LOC>", text)
    text = _PYTHON_TRACEBACK_FILE.sub('File "<PATH>", <LOC>', text)
    text = _STACK_FRAME_AT.sub("  at <FRAME>", text)
    text = _VARIABLE_NAMES.sub("<VAR>", text)
    text = _NUMERIC_LITERALS.sub("<NUM>", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def structural_hash(normalized_error: str) -> str:
    """Produce a deterministic hash from a normalized error string."""
    return hashlib.sha256(normalized_error.encode("utf-8")).hexdigest()


def fingerprint(raw_error: str) -> tuple[str, str]:
    """Return (normalized_error, structural_hash) for a raw error string."""
    normed = normalize_error(raw_error)
    return normed, structural_hash(normed)
