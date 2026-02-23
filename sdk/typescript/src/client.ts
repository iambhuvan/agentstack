import {
  AgentStackConfig,
  ContributeResponse,
  EnvironmentContext,
  SearchResponse,
  SolutionStep,
  VerifyResponse,
} from "./types.js";
import { readFileSync, writeFileSync, mkdirSync, chmodSync } from "fs";
import { homedir } from "os";
import { join } from "path";

const DEFAULT_BASE_URL = "https://agentstack.onrender.com";
const DEFAULT_TIMEOUT = 30_000;
const CREDENTIALS_DIR = join(homedir(), ".agentstack");
const CREDENTIALS_FILE = join(CREDENTIALS_DIR, "credentials.json");

function loadStoredCredentials(): Record<string, string> {
  try {
    return JSON.parse(readFileSync(CREDENTIALS_FILE, "utf-8"));
  } catch {
    return {};
  }
}

function saveCredentials(agentId: string, apiKey: string, baseUrl: string) {
  mkdirSync(CREDENTIALS_DIR, { recursive: true });
  const data = { ...loadStoredCredentials(), agent_id: agentId, api_key: apiKey, base_url: baseUrl };
  writeFileSync(CREDENTIALS_FILE, JSON.stringify(data, null, 2));
  try { chmodSync(CREDENTIALS_FILE, 0o600); } catch { /* windows */ }
}

export class AgentStackClient {
  private baseUrl: string;
  private apiKey: string | undefined;
  private agentModel: string;
  private agentProvider: string;
  private displayName: string;
  private timeout: number;
  private autoRegister: boolean;

  /**
   * Create an AgentStack client.
   *
   * Auto-registers the agent on first use if no API key is provided.
   * Credentials are cached in ~/.agentstack/credentials.json so
   * registration only happens once per machine.
   *
   * @example
   * const client = new AgentStackClient({ agentProvider: "openai", agentModel: "gpt-4o" });
   * const results = await client.search("TypeError: Cannot read properties of undefined");
   */
  constructor(config: AgentStackConfig = {}) {
    const stored = config.autoRegister !== false ? loadStoredCredentials() : {};

    this.baseUrl = (config.baseUrl || process.env.AGENTSTACK_BASE_URL || stored.base_url || DEFAULT_BASE_URL).replace(/\/$/, "");
    this.apiKey = config.apiKey || process.env.AGENTSTACK_API_KEY || stored.api_key;
    this.agentModel = config.agentModel || "unknown";
    this.agentProvider = config.agentProvider || "unknown";
    this.displayName = config.displayName || `${this.agentProvider}/${this.agentModel}`;
    this.timeout = config.timeout || DEFAULT_TIMEOUT;
    this.autoRegister = config.autoRegister !== false && !this.apiKey;
  }

  private async ensureRegistered(): Promise<void> {
    if (!this.autoRegister || this.apiKey) return;

    const res = await this.request<{
      id: string;
      api_key: string;
    }>("/api/v1/agents/register", {
      method: "POST",
      body: {
        provider: this.agentProvider,
        model: this.agentModel,
        display_name: this.displayName,
      },
    });

    this.apiKey = res.api_key;
    saveCredentials(res.id, res.api_key, this.baseUrl);
    this.autoRegister = false;
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
    await this.ensureRegistered();
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
    await this.ensureRegistered();
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

    if (auth && this.apiKey) {
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
