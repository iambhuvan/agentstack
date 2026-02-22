interface AgentProfileProps {
  displayName: string;
  provider: string;
  model: string;
  reputationScore: number;
  totalContributions: number;
  totalVerifications: number;
  successRate: number;
  topTags: string[];
}

const PROVIDER_COLORS: Record<string, string> = {
  anthropic: "bg-orange-500/10 text-orange-400 border-orange-500/20",
  openai: "bg-green-500/10 text-green-400 border-green-500/20",
  google: "bg-blue-500/10 text-blue-400 border-blue-500/20",
  meta: "bg-purple-500/10 text-purple-400 border-purple-500/20",
  mistral: "bg-cyan-500/10 text-cyan-400 border-cyan-500/20",
};

export default function AgentProfile({
  displayName,
  provider,
  model,
  reputationScore,
  totalContributions,
  totalVerifications,
  successRate,
  topTags,
}: AgentProfileProps) {
  const colorClass =
    PROVIDER_COLORS[provider.toLowerCase()] ||
    "bg-zinc-500/10 text-zinc-400 border-zinc-500/20";

  return (
    <div className="p-6 bg-zinc-900 border border-zinc-800 rounded-xl">
      <div className="flex items-center gap-4 mb-6">
        <div
          className={`w-14 h-14 rounded-full flex items-center justify-center text-xl font-bold border ${colorClass}`}
        >
          {displayName.charAt(0).toUpperCase()}
        </div>
        <div>
          <h2 className="text-xl font-bold text-white">{displayName}</h2>
          <p className="text-sm text-zinc-400">
            {provider} / {model}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 mb-6">
        <StatBox label="Reputation" value={reputationScore.toFixed(1)} />
        <StatBox
          label="Success Rate"
          value={`${(successRate * 100).toFixed(1)}%`}
        />
        <StatBox label="Contributions" value={String(totalContributions)} />
        <StatBox label="Verifications" value={String(totalVerifications)} />
      </div>

      {topTags.length > 0 && (
        <div>
          <h4 className="text-xs text-zinc-500 uppercase tracking-wider mb-2">
            Domains
          </h4>
          <div className="flex flex-wrap gap-2">
            {topTags.map((tag) => (
              <span
                key={tag}
                className="px-2 py-1 bg-zinc-800 text-zinc-300 rounded text-xs"
              >
                {tag}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function StatBox({ label, value }: { label: string; value: string }) {
  return (
    <div className="p-3 bg-zinc-950 rounded-lg text-center">
      <p className="text-lg font-bold text-white">{value}</p>
      <p className="text-xs text-zinc-500">{label}</p>
    </div>
  );
}
