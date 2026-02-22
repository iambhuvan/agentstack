import { createHash } from "crypto";

const PATH_RE =
  /(?:\/[a-zA-Z0-9_./-]+|[A-Z]:\\[a-zA-Z0-9_.\\ -]+|~\/[a-zA-Z0-9_./-]+)/g;
const LINE_COL_RE = /(?:line |ln |:)\d+(?::\d+)?/gi;
const MEM_ADDR_RE = /0x[0-9a-fA-F]{4,16}/g;
const TIMESTAMP_RE =
  /\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?/g;
const UUID_RE =
  /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi;
const ANSI_RE = /\x1b\[[0-9;]*[a-zA-Z]/g;
const STACK_FRAME_RE = /^\s+at .+$/gm;
const PY_TB_FILE_RE = /File "[^"]+", line \d+/gm;
const VAR_NAMES_RE = /'[a-zA-Z_]\w*'/g;
const NUMERIC_LITERALS_RE = /\b\d{3,}\b/g;

export function normalizeError(raw: string): string {
  let text = raw.trim();
  text = text.replace(ANSI_RE, "");
  text = text.replace(TIMESTAMP_RE, "<TIMESTAMP>");
  text = text.replace(UUID_RE, "<UUID>");
  text = text.replace(MEM_ADDR_RE, "<ADDR>");
  text = text.replace(PATH_RE, "<PATH>");
  text = text.replace(LINE_COL_RE, "<LOC>");
  text = text.replace(PY_TB_FILE_RE, 'File "<PATH>", <LOC>');
  text = text.replace(STACK_FRAME_RE, "  at <FRAME>");
  text = text.replace(VAR_NAMES_RE, "<VAR>");
  text = text.replace(NUMERIC_LITERALS_RE, "<NUM>");
  text = text.replace(/\s+/g, " ").trim();
  return text;
}

export function structuralHash(normalized: string): string {
  return createHash("sha256").update(normalized).digest("hex");
}

export function fingerprint(raw: string): {
  normalized: string;
  hash: string;
} {
  const normalized = normalizeError(raw);
  return { normalized, hash: structuralHash(normalized) };
}
