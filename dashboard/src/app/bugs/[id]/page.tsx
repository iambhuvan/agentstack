import SolutionThread from "@/components/SolutionThread";
import ExpandableQuestionText from "@/components/ExpandableQuestionText";
import { apiFetch, SearchResponse } from "@/lib/api";

interface PageProps {
  params: Promise<{ id: string }>;
}

async function getBugDetail(id: string) {
  try {
    const bug = await apiFetch<{
      id: string;
      structural_hash: string;
      error_pattern: string;
      error_type: string;
      environment: Record<string, string>;
      tags: string[];
      solution_count: number;
      created_at: string;
    }>(`/api/v1/bugs/${id}`);

    const searchRes = await apiFetch<SearchResponse>("/api/v1/search/", {
      method: "POST",
      body: JSON.stringify({
        error_pattern: bug.error_pattern,
        error_type: bug.error_type,
      }),
    });

    const match = searchRes.results.find((r) => r.bug.id === id);
    return {
      bug,
      solutions: match?.solutions || [],
      failedApproaches: match?.failed_approaches || [],
    };
  } catch {
    return null;
  }
}

export default async function BugPage({ params }: PageProps) {
  const { id } = await params;
  const data = await getBugDetail(id);

  if (!data) {
    return (
      <div className="max-w-4xl mx-auto px-6 py-16 text-center">
        <h1 className="text-2xl font-bold text-zinc-400">Bug not found</h1>
      </div>
    );
  }

  const { bug, solutions, failedApproaches } = data;

  return (
    <div className="max-w-4xl mx-auto px-6 py-16">
      <div className="mb-8">
        <div className="flex flex-wrap items-center gap-3 mb-3">
          <span className="px-3 py-1 bg-red-500/10 text-red-400 rounded-full text-xs font-mono font-medium">
            {bug.error_type}
          </span>
          <span className="text-xs text-zinc-500 font-mono break-all">
            {bug.structural_hash.slice(0, 12)}...
          </span>
        </div>
        <div className="bg-zinc-900 p-4 rounded-lg border border-zinc-800">
          <ExpandableQuestionText text={bug.error_pattern} previewChars={700} />
        </div>
        <div className="flex flex-wrap items-center gap-4 mt-3">
          <div className="flex flex-wrap gap-2">
            {bug.tags.map((tag) => (
              <span
                key={tag}
                className="px-2 py-0.5 bg-zinc-800 text-zinc-400 rounded text-xs"
              >
                {tag}
              </span>
            ))}
          </div>
          {Object.keys(bug.environment).length > 0 && (
            <div className="flex flex-wrap gap-2">
              {Object.entries(bug.environment).map(([k, v]) => (
                <span
                  key={k}
                  className="text-xs text-zinc-500 break-words [overflow-wrap:anywhere]"
                >
                  {k}: {v}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>

      <h2 className="text-lg font-bold mb-4">
        Solutions ({solutions.length})
      </h2>
      <SolutionThread
        solutions={solutions}
        failedApproaches={failedApproaches}
      />
    </div>
  );
}
