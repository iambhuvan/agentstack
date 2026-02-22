export interface EnvironmentContext {
  language?: string;
  language_version?: string;
  framework?: string;
  framework_version?: string;
  runtime?: string;
  runtime_version?: string;
  os?: string;
  package_manager?: string;
  agent_model?: string;
}

export interface SolutionStep {
  action: string;
  target?: string;
  command?: string;
  diff?: string;
  content?: string;
  description?: string;
}

export interface BugInfo {
  id: string;
  structural_hash: string;
  error_pattern: string;
  error_type: string;
  environment: Record<string, unknown>;
  tags: string[];
  solution_count: number;
  created_at: string;
}

export interface SolutionInfo {
  id: string;
  bug_id: string;
  contributed_by: string;
  approach_name: string;
  steps: SolutionStep[];
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

export interface FailedApproachInfo {
  id: string;
  bug_id: string;
  approach_name: string;
  command_or_action: string | null;
  failure_rate: number;
  common_followup_error: string | null;
  reason: string | null;
}

export interface SearchResult {
  bug: BugInfo;
  solutions: SolutionInfo[];
  failed_approaches: FailedApproachInfo[];
  match_type: "exact_hash" | "semantic_similar";
  similarity_score: number | null;
}

export interface SearchResponse {
  results: SearchResult[];
  total_found: number;
  search_time_ms: number;
}

export interface ContributeResponse {
  bug_id: string;
  solution_id: string;
  is_new_bug: boolean;
  message: string;
}

export interface VerifyResponse {
  verification_id: string;
  solution_id: string;
  new_success_rate: number;
  message: string;
}

export interface AgentStackConfig {
  baseUrl?: string;
  apiKey?: string;
  agentModel?: string;
  agentProvider?: string;
  timeout?: number;
}
