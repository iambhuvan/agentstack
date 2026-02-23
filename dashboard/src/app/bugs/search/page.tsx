import SearchBar from "@/components/SearchBar";
import ExpandableQuestionText from "@/components/ExpandableQuestionText";
import SolutionThread from "@/components/SolutionThread";
import {
  apiFetch,
  SearchResponse,
  SearchResultItem,
} from "@/lib/api";

interface PageProps {
  searchParams: Promise<{ q?: string }>;
}

async function searchBugs(query: string): Promise<SearchResponse | null> {
  if (!query.trim()) return null;
  try {
    return await apiFetch<SearchResponse>("/api/v1/search/", {
      method: "POST",
      body: JSON.stringify({ error_pattern: query }),
    });
  } catch {
    return null;
  }
}

export default async function SearchPage({ searchParams }: PageProps) {
  const { q } = await searchParams;
  const query = q || "";
  const data = query ? await searchBugs(query) : null;

  return (
    <div className="max-w-4xl mx-auto px-6 py-12">
      <div className="mb-10">
        <SearchBar initialQuery={query} />
      </div>

      {!query && (
        <div className="text-center py-20">
          <p className="text-zinc-500 text-sm">
            Paste an error message above to find solutions.
          </p>
        </div>
      )}

      {query && !data && (
        <div className="text-center py-20">
          <p className="text-zinc-400 font-medium mb-1">Search failed</p>
          <p className="text-zinc-500 text-sm">
            Could not reach the API. Make sure the backend is running.
          </p>
        </div>
      )}

      {data && data.results.length === 0 && (
        <div className="text-center py-20">
          <p className="text-zinc-400 font-medium mb-1">No results found</p>
          <p className="text-zinc-500 text-sm">
            No matching bugs for that error pattern. Try a different query or
            contribute a solution.
          </p>
        </div>
      )}

      {data && data.results.length > 0 && (
        <>
          <div className="flex items-center justify-between mb-6">
            <p className="text-sm text-zinc-400">
              <span className="text-white font-medium">{data.total_found}</span>{" "}
              result{data.total_found !== 1 ? "s" : ""} in{" "}
              <span className="text-zinc-300">{data.search_time_ms}ms</span>
            </p>
          </div>

          <div className="space-y-6">
            {data.results.map((result) => (
              <SearchResultCard key={result.bug.id} result={result} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function SearchResultCard({ result }: { result: SearchResultItem }) {
  const { bug, solutions, failed_approaches, match_type, similarity_score } =
    result;

  return (
    <div className="border border-zinc-800 rounded-xl min-w-0">
      <div className="p-5 bg-zinc-900">
        <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
          <div className="flex flex-wrap items-center gap-3 min-w-0">
            <span className="px-3 py-1 bg-red-500/10 text-red-400 rounded-full text-xs font-mono font-medium">
              {bug.error_type}
            </span>
            <MatchBadge type={match_type} score={similarity_score} />
          </div>
          <span className="text-xs text-emerald-400 font-medium shrink-0">
            {bug.solution_count} solution{bug.solution_count !== 1 ? "s" : ""}
          </span>
        </div>

        <ExpandableQuestionText
          text={bug.error_pattern}
          previewChars={280}
          className="mb-3"
        />

        <div className="flex flex-wrap items-center gap-2">
          {bug.tags.slice(0, 5).map((tag) => (
            <span
              key={tag}
              className="px-2 py-0.5 bg-zinc-800 text-zinc-400 rounded text-xs"
            >
              {tag}
            </span>
          ))}
        </div>
      </div>

      {solutions.length > 0 && (
        <div className="p-5 border-t border-zinc-800">
          <h3 className="text-sm font-medium text-zinc-400 mb-3">
            Top Solutions
          </h3>
          <SolutionThread
            solutions={solutions.slice(0, 3)}
            failedApproaches={failed_approaches}
          />
        </div>
      )}

      <div className="px-5 py-3 bg-zinc-950 border-t border-zinc-800 flex justify-end">
        <a
          href={`/bugs/${bug.id}`}
          className="text-xs text-emerald-400 hover:text-emerald-300 transition-colors"
        >
          View all solutions &rarr;
        </a>
      </div>
    </div>
  );
}

function MatchBadge({
  type,
  score,
}: {
  type: string;
  score: number | null;
}) {
  if (type === "exact_hash") {
    return (
      <span className="px-2 py-0.5 bg-emerald-500/10 text-emerald-400 rounded text-xs font-medium">
        Exact match
      </span>
    );
  }

  const pct = score ? (score * 100).toFixed(0) : "?";
  return (
    <span className="px-2 py-0.5 bg-cyan-500/10 text-cyan-400 rounded text-xs font-medium">
      {pct}% similar
    </span>
  );
}
