interface SolutionStep {
  action: string;
  target?: string;
  command?: string;
  description?: string;
  diff?: string;
}

interface Solution {
  id: string;
  approach_name: string;
  success_rate: number;
  total_attempts: number;
  success_count: number;
  failure_count: number;
  avg_resolution_ms: number;
  steps: SolutionStep[];
  warnings: string[];
  source: string;
  last_verified: string;
}

interface FailedApproach {
  approach_name: string;
  failure_rate: number;
  reason: string | null;
}

interface SolutionThreadProps {
  solutions: Solution[];
  failedApproaches: FailedApproach[];
}

export default function SolutionThread({
  solutions,
  failedApproaches,
}: SolutionThreadProps) {
  return (
    <div className="space-y-4">
      {solutions.map((sol, i) => {
        const pct = (sol.success_rate * 100).toFixed(1);
        const rateColor =
          sol.success_rate > 0.8
            ? "text-emerald-400"
            : sol.success_rate > 0.5
            ? "text-yellow-400"
            : "text-red-400";
        const barColor =
          sol.success_rate > 0.8
            ? "bg-emerald-500"
            : sol.success_rate > 0.5
            ? "bg-yellow-500"
            : "bg-red-500";

        return (
          <div
            key={sol.id}
            className="p-5 bg-zinc-900 border border-zinc-800 rounded-xl"
          >
            <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
              <div className="flex items-center gap-3 min-w-0">
                <span className="text-xs text-zinc-500 font-mono">
                  #{i + 1}
                </span>
                <h3 className="text-white font-medium break-words [overflow-wrap:anywhere]">
                  {sol.approach_name}
                </h3>
              </div>
              <div className="flex items-center gap-4 shrink-0">
                <span className={`text-sm font-bold ${rateColor}`}>
                  {pct}%
                </span>
                <span className="text-xs text-zinc-500">
                  {sol.total_attempts} attempts
                </span>
              </div>
            </div>

            <div className="w-full bg-zinc-800 rounded-full h-1.5 mb-4">
              <div
                className={`h-1.5 rounded-full ${barColor}`}
                style={{ width: `${Math.max(Number(pct), 2)}%` }}
              />
            </div>

            <div className="space-y-2 mb-4">
              {sol.steps.map((step, j) => (
                <div
                  key={j}
                  className="flex items-start gap-3 p-3 bg-zinc-950 rounded-lg font-mono text-sm min-w-0"
                >
                  <span className="text-emerald-400 shrink-0">
                    {step.action}
                  </span>
                  <span className="text-zinc-300 flex-1 min-w-0 whitespace-pre-wrap break-words [overflow-wrap:anywhere]">
                    {step.command || step.target || step.description || ""}
                  </span>
                </div>
              ))}
            </div>

            {sol.warnings.length > 0 && (
              <div className="p-3 bg-yellow-500/5 border border-yellow-500/20 rounded-lg">
                <p className="text-xs text-yellow-400">
                  {sol.warnings.join(" | ")}
                </p>
              </div>
            )}

            <div className="flex flex-wrap items-center gap-4 mt-3 text-xs text-zinc-500">
              <span>
                {sol.avg_resolution_ms > 0 ? `~${sol.avg_resolution_ms}ms` : ""}
              </span>
              <span className="break-words [overflow-wrap:anywhere]">
                {sol.source}
              </span>
            </div>
          </div>
        );
      })}

      {failedApproaches.length > 0 && (
        <div className="p-5 bg-red-500/5 border border-red-500/20 rounded-xl">
          <h3 className="text-red-400 font-medium mb-3">
            Failed Approaches (skip these)
          </h3>
          <div className="space-y-2">
            {failedApproaches.map((fa, i) => (
              <div key={i} className="flex flex-wrap items-start justify-between gap-2">
                <span className="text-sm text-red-300 font-mono break-words [overflow-wrap:anywhere]">
                  {fa.approach_name}
                </span>
                <div className="flex items-center gap-3 min-w-0">
                  <span className="text-xs text-red-400">
                    {(fa.failure_rate * 100).toFixed(0)}% fail
                  </span>
                  {fa.reason && (
                    <span className="text-xs text-zinc-500 break-words [overflow-wrap:anywhere]">
                      {fa.reason}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
