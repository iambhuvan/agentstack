"use client";

import { useMemo, useState } from "react";

interface ExpandableQuestionTextProps {
  text: string;
  previewChars?: number;
  className?: string;
}

export default function ExpandableQuestionText({
  text,
  previewChars = 320,
  className = "",
}: ExpandableQuestionTextProps) {
  const [expanded, setExpanded] = useState(false);
  const cleanedText = text || "";
  const isLong = cleanedText.length > previewChars;

  const previewText = useMemo(() => {
    if (!isLong) return cleanedText;
    return `${cleanedText.slice(0, previewChars).trimEnd()}...`;
  }, [cleanedText, isLong, previewChars]);

  return (
    <div>
      <p
        className={`text-sm text-zinc-300 font-mono whitespace-pre-wrap break-words [overflow-wrap:anywhere] ${className}`.trim()}
      >
        {expanded || !isLong ? cleanedText : previewText}
      </p>
      {isLong && (
        <button
          type="button"
          onClick={() => setExpanded((prev) => !prev)}
          className="mt-2 text-xs text-zinc-400 hover:text-zinc-200 transition-colors"
        >
          {expanded ? "Show less" : "Show more"}
        </button>
      )}
    </div>
  );
}
