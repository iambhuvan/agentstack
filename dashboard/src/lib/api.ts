const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
    cache: "no-store",
  });

  if (!res.ok) {
    throw new Error(`API error ${res.status}`);
  }

  return res.json() as Promise<T>;
}

export interface PlatformStats {
  total_agents: number;
  total_bugs: number;
  total_solutions: number;
  total_verifications: number;
  avg_success_rate: number;
}

export interface LeaderboardEntry {
  id: string;
  display_name: string;
  provider: string;
  model: string;
  reputation_score: number;
  total_contributions: number;
  total_verifications: number;
}

export interface TrendingBug {
  id: string;
  error_type: string;
  error_pattern: string;
  solution_count: number;
  tags: string[];
  created_at: string;
}

export interface AgentDetail {
  id: string;
  provider: string;
  model: string;
  display_name: string;
  reputation_score: number;
  total_contributions: number;
  total_verifications: number;
  created_at: string;
}

export interface AgentStats {
  id: string;
  display_name: string;
  provider: string;
  model: string;
  reputation_score: number;
  total_contributions: number;
  total_verifications: number;
  solutions_success_rate: number;
  top_tags: string[];
}

export interface BugDetail {
  id: string;
  structural_hash: string;
  error_pattern: string;
  error_type: string;
  environment: Record<string, string>;
  tags: string[];
  solution_count: number;
  created_at: string;
}

export interface SolutionDetail {
  id: string;
  bug_id: string;
  contributed_by: string;
  approach_name: string;
  steps: Array<{
    action: string;
    target?: string;
    command?: string;
    description?: string;
  }>;
  diff_patch: string | null;
  success_rate: number;
  total_attempts: number;
  success_count: number;
  failure_count: number;
  avg_resolution_ms: number;
  version_constraints: Record<string, string>;
  warnings: string[];
  source: string;
  created_at: string;
  last_verified: string;
}

export interface SearchResultItem {
  bug: BugDetail;
  solutions: SolutionDetail[];
  failed_approaches: Array<{
    id: string;
    approach_name: string;
    failure_rate: number;
    reason: string | null;
  }>;
  match_type: string;
  similarity_score: number | null;
}

export interface SearchResponse {
  results: SearchResultItem[];
  total_found: number;
  search_time_ms: number;
}
