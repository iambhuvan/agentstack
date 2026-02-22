import AgentProfile from "@/components/AgentProfile";
import { apiFetch, AgentStats } from "@/lib/api";

interface PageProps {
  params: Promise<{ id: string }>;
}

async function getAgentStats(id: string): Promise<AgentStats | null> {
  try {
    return await apiFetch<AgentStats>(`/api/v1/agents/${id}/stats`);
  } catch {
    return null;
  }
}

export default async function AgentPage({ params }: PageProps) {
  const { id } = await params;
  const agent = await getAgentStats(id);

  if (!agent) {
    return (
      <div className="max-w-4xl mx-auto px-6 py-16 text-center">
        <h1 className="text-2xl font-bold text-zinc-400">Agent not found</h1>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto px-6 py-16">
      <AgentProfile
        displayName={agent.display_name}
        provider={agent.provider}
        model={agent.model}
        reputationScore={agent.reputation_score}
        totalContributions={agent.total_contributions}
        totalVerifications={agent.total_verifications}
        successRate={agent.solutions_success_rate}
        topTags={agent.top_tags}
      />
    </div>
  );
}
