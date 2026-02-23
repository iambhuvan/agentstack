import Link from "next/link";
import ExpandableQuestionText from "@/components/ExpandableQuestionText";

interface BugCardProps {
  id: string;
  errorType: string;
  errorPattern: string;
  solutionCount: number;
  tags: string[];
  createdAt: string;
}

export default function BugCard({
  id,
  errorType,
  errorPattern,
  solutionCount,
  tags,
  createdAt,
}: BugCardProps) {
  const timeAgo = getTimeAgo(createdAt);

  return (
    <Link href={`/bugs/${id}`}>
      <div className="p-5 bg-zinc-900 border border-zinc-800 rounded-xl hover:border-zinc-600 transition-colors cursor-pointer">
        <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
          <span className="px-3 py-1 bg-red-500/10 text-red-400 rounded-full text-xs font-mono font-medium">
            {errorType}
          </span>
          <span className="text-xs text-zinc-500 shrink-0">{timeAgo}</span>
        </div>
        <ExpandableQuestionText
          text={errorPattern}
          previewChars={220}
          className="mb-3"
        />
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap gap-2">
            {tags.slice(0, 3).map((tag) => (
              <span
                key={tag}
                className="px-2 py-0.5 bg-zinc-800 text-zinc-400 rounded text-xs"
              >
                {tag}
              </span>
            ))}
          </div>
          <span className="text-xs text-emerald-400 font-medium shrink-0">
            {solutionCount} solution{solutionCount !== 1 ? "s" : ""}
          </span>
        </div>
      </div>
    </Link>
  );
}

function getTimeAgo(dateStr: string): string {
  if (!dateStr) return "";
  const now = new Date();
  const date = new Date(dateStr);
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);

  if (diffMins < 1) return "just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays}d ago`;
}
