import {
  AgentStackConfig,
  ContributeResponse,
  EnvironmentContext,
  SearchResponse,
  SolutionStep,
  VerifyResponse,
} from "./types.js";

const DEFAULT_BASE_URL = "http://localhost:8000";
const DEFAULT_TIMEOUT = 30_000;

export class AgentStackClient {
  private baseUrl: string;
  private apiKey: string | undefined;
  private agentModel: string | undefined;
  private agentProvider: string | undefined;
  private timeout: number;

  constructor(config: AgentStackConfig = {}) {
    this.baseUrl = (config.baseUrl || DEFAULT_BASE_URL).replace(/\/$/, "");
    this.apiKey = config.apiKey;
    this.agentModel = config.agentModel;
    this.agentProvider = config.agentProvider;
    this.timeout = config.timeout || DEFAULT_TIMEOUT;
  }

  async search(
    errorPattern: string,
    options: {
      errorType?: string;
      environment?: EnvironmentContext;
      maxResults?: number;
    } = {}
  ): Promise<SearchResponse> {
    return this.request<SearchResponse>("/api/v1/search/", {
      method: "POST",
      body: {
        error_pattern: errorPattern,
        error_type: options.errorType,
        environment: options.environment,
        agent_model: this.agentModel,
        agent_provider: this.agentProvider,
        max_results: options.maxResults || 10,
      },
    });
  }

  async contribute(
    bug: {
      errorPattern: string;
      errorType: string;
      environment?: EnvironmentContext;
      tags?: string[];
    },
    solution: {
      approachName: string;
      steps: SolutionStep[];
      diffPatch?: string;
      versionConstraints?: Record<string, string>;
      warnings?: string[];
    },
    failedApproaches: Array<{
      approachName: string;
      commandOrAction?: string;
      failureRate?: number;
      reason?: string;
    }> = []
  ): Promise<ContributeResponse> {
    return this.request<ContributeResponse>("/api/v1/contribute/", {
      method: "POST",
      auth: true,
      body: {
        bug: {
          error_pattern: bug.errorPattern,
          error_type: bug.errorType,
          environment: bug.environment,
          tags: bug.tags || [],
        },
        solution: {
          approach_name: solution.approachName,
          steps: solution.steps,
          diff_patch: solution.diffPatch,
          version_constraints: solution.versionConstraints || {},
          warnings: solution.warnings || [],
        },
        failed_approaches: failedApproaches.map((fa) => ({
          approach_name: fa.approachName,
          command_or_action: fa.commandOrAction,
          failure_rate: fa.failureRate || 0,
          reason: fa.reason,
        })),
      },
    });
  }

  async verify(
    solutionId: string,
    success: boolean,
    options: {
      context?: Record<string, unknown>;
      resolutionTimeMs?: number;
    } = {}
  ): Promise<VerifyResponse> {
    return this.request<VerifyResponse>("/api/v1/verify/", {
      method: "POST",
      auth: true,
      body: {
        solution_id: solutionId,
        success,
        context: options.context || {},
        resolution_time_ms: options.resolutionTimeMs,
      },
    });
  }

  private async request<T>(
    path: string,
    options: {
      method?: string;
      body?: unknown;
      auth?: boolean;
    } = {}
  ): Promise<T> {
    const { method = "GET", body, auth = false } = options;
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };

    if (auth) {
      if (!this.apiKey) {
        throw new Error("API key required. Pass apiKey in AgentStackConfig.");
      }
      headers["X-API-Key"] = this.apiKey;
    }

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeout);

    try {
      const res = await fetch(`${this.baseUrl}${path}`, {
        method,
        headers,
        body: body ? JSON.stringify(body) : undefined,
        signal: controller.signal,
      });

      if (!res.ok) {
        const errText = await res.text();
        throw new Error(`AgentStack API error ${res.status}: ${errText}`);
      }

      return (await res.json()) as T;
    } finally {
      clearTimeout(timer);
    }
  }
}
