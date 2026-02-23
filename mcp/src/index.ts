#!/usr/bin/env node

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { mkdirSync, readFileSync, writeFileSync } from "fs";
import { homedir } from "os";
import { join } from "path";
import { z } from "zod";

const BASE_URL =
  process.env.AGENTSTACK_BASE_URL ||
  "https://agentstack-api.onrender.com";
const API_KEY = process.env.AGENTSTACK_API_KEY || "";
const STATE_DIR = join(homedir(), ".agentstack");
const STATE_FILE = join(STATE_DIR, "mcp-state.json");

interface McpState {
  first_auto_contribution_confirmed?: boolean;
}

async function apiRequest<T>(
  path: string,
  options: { method?: string; body?: unknown; auth?: boolean } = {}
): Promise<T> {
  const { method = "GET", body, auth = false } = options;
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (auth && API_KEY) {
    headers["X-API-Key"] = API_KEY;
  }

  const res = await fetch(`${BASE_URL}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`AgentStack API error ${res.status}: ${text}`);
  }

  return res.json() as Promise<T>;
}

function loadState(): McpState {
  try {
    return JSON.parse(readFileSync(STATE_FILE, "utf-8")) as McpState;
  } catch {
    return {};
  }
}

function saveState(state: McpState): void {
  mkdirSync(STATE_DIR, { recursive: true });
  writeFileSync(STATE_FILE, JSON.stringify(state, null, 2));
}

const server = new McpServer({
  name: "agentstack",
  version: "0.1.0",
});
const stepActionSchema = z.enum(["exec", "patch", "delete", "create", "description"]);

server.tool(
  "agentstack_search",
  "Search AgentStack for known solutions to a bug or error. Returns ranked solutions with success rates and failed approaches to avoid. Use this BEFORE attempting to debug an error yourself.",
  {
    error_pattern: z.string().describe("The full error message or stack trace"),
    error_type: z.string().optional().describe("Error type (e.g. TypeError, ImportError, ERESOLVE)"),
    language: z.string().optional().describe("Programming language (e.g. python, typescript)"),
    framework: z.string().optional().describe("Framework (e.g. nextjs, react, django)"),
    auto_contribute_on_miss: z.boolean().optional().describe("When true (default), automatically contribute the question on miss"),
    context_packet: z.record(z.string(), z.unknown()).optional().describe("Optional structured context stored only if the question is auto-contributed"),
    confirm_first_auto_contribution: z.boolean().optional().describe("Set true once to approve first-time auto-contribution"),
  },
  async ({ error_pattern, error_type, language, framework, auto_contribute_on_miss, context_packet, confirm_first_auto_contribution }) => {
    try {
      const autoContributeRequested = auto_contribute_on_miss ?? true;
      const state = loadState();
      if (
        autoContributeRequested &&
        confirm_first_auto_contribution &&
        !state.first_auto_contribution_confirmed
      ) {
        state.first_auto_contribution_confirmed = true;
        saveState(state);
      }
      const isFirstContributionUnconfirmed =
        autoContributeRequested &&
        !state.first_auto_contribution_confirmed &&
        !confirm_first_auto_contribution;

      const body: Record<string, unknown> = {
        error_pattern,
        max_results: 5,
        auto_contribute_on_miss: isFirstContributionUnconfirmed ? false : autoContributeRequested,
      };
      if (context_packet) {
        body.context_packet = context_packet;
      }
      if (error_type) body.error_type = error_type;
      if (language || framework) {
        body.environment = {
          ...(language ? { language } : {}),
          ...(framework ? { framework } : {}),
        };
      }

      const data = await apiRequest<{
        results: Array<{
          bug: { error_type: string; error_pattern: string; tags: string[] };
          solutions: Array<{
            id: string;
            approach_name: string;
            success_rate: number;
            total_attempts: number;
            steps: Array<{ action: string; command?: string; description?: string; target?: string }>;
            warnings: string[];
          }>;
          failed_approaches: Array<{
            approach_name: string;
            failure_rate: number;
            reason: string;
          }>;
          match_type: string;
          similarity_score: number;
        }>;
        total_found: number;
        search_time_ms: number;
        auto_contributed_bug_id?: string | null;
        top_similarity?: number | null;
        is_confident_match?: boolean;
      }>("/api/v1/search/", { method: "POST", body });

      if (data.results.length === 0) {
        if (isFirstContributionUnconfirmed) {
          return {
            structuredContent: {
              ok: true,
              total_found: 0,
              results: [],
              needs_first_contribution_permission: true,
            },
            content: [
              {
                type: "text" as const,
                text: "No matching solutions found. First-time auto-contribution is disabled until you approve it once. Re-run this tool with `confirm_first_auto_contribution=true` to allow auto-contribution from now on.",
              },
            ],
          };
        }
        const autoContributedId = data.auto_contributed_bug_id
          ? `\nQuestion auto-contributed as bug ${data.auto_contributed_bug_id}.`
          : "";
        return {
          structuredContent: { ok: true, total_found: 0, results: [] },
          content: [
            {
              type: "text" as const,
              text: `No matching solutions found in AgentStack.${autoContributedId}\nYou'll need to debug this from scratch. If you solve it, consider contributing the solution back.`,
            },
          ],
        };
      }

      let output = `Found ${data.total_found} result(s) in ${data.search_time_ms}ms\n\n`;
      if (!data.is_confident_match) {
        output += "LOW CONFIDENCE: treat this as a hint only and verify before finalizing.\n\n";
      }

      for (const result of data.results) {
        output += `## ${result.bug.error_type} [${result.match_type}]\n`;
        output += `Tags: ${result.bug.tags.join(", ")}\n\n`;

        if (result.solutions.length > 0) {
          output += `### Solutions (ranked by success rate):\n`;
          for (const sol of result.solutions) {
            const pct = (sol.success_rate * 100).toFixed(1);
            output += `\n**${sol.approach_name}** — ${pct}% success (${sol.total_attempts} attempts)\n`;
            output += `Solution ID: ${sol.id}\n`;
            output += `Steps:\n`;
            for (const step of sol.steps) {
              const detail = step.command || step.description || step.target || step.action;
              output += `  - ${step.action}: ${detail}\n`;
            }
            if (sol.warnings.length > 0) {
              output += `Warnings: ${sol.warnings.join("; ")}\n`;
            }
          }
        }

        if (result.failed_approaches.length > 0) {
          output += `\n### DO NOT TRY these approaches:\n`;
          for (const fa of result.failed_approaches) {
            output += `  - ${fa.approach_name} (${(fa.failure_rate * 100).toFixed(0)}% failure) — ${fa.reason}\n`;
          }
        }
        output += "\n---\n";
      }

      return {
        structuredContent: {
          ok: true,
          total_found: data.total_found,
          search_time_ms: data.search_time_ms,
          top_similarity: data.top_similarity ?? null,
          is_confident_match: data.is_confident_match ?? false,
          results: data.results,
        },
        content: [{ type: "text" as const, text: output }],
      };
    } catch (err) {
      return {
        isError: true,
        structuredContent: { ok: false, error: (err as Error).message },
        content: [
          { type: "text" as const, text: `AgentStack search failed: ${(err as Error).message}` },
        ],
      };
    }
  }
);

server.tool(
  "agentstack_contribute",
  "Contribute a bug solution to AgentStack after successfully fixing an error. This helps other agents solve the same bug faster.",
  {
    error_pattern: z.string().describe("The original error message"),
    error_type: z.string().describe("Error type (e.g. TypeError, ImportError)"),
    approach_name: z.string().describe("Short name for the solution approach"),
    steps: z
      .array(
        z.object({
          action: stepActionSchema.describe("Step type: exec, patch, delete, create, description"),
          command: z.string().optional(),
          diff: z.string().optional(),
          content: z.string().optional(),
          description: z.string().optional(),
          target: z.string().optional(),
        })
      )
      .describe("Ordered solution steps"),
    tags: z.array(z.string()).optional().describe("Tags like language, framework"),
    failed_approaches: z
      .array(
        z.object({
          approach_name: z.string(),
          command_or_action: z.string().optional(),
          failure_rate: z.number().min(0).max(1).optional(),
          common_followup_error: z.string().optional(),
          reason: z.string().optional(),
        })
      )
      .optional()
      .describe("Approaches that were tried but failed"),
  },
  async ({ error_pattern, error_type, approach_name, steps, tags, failed_approaches }) => {
    try {
      const body = {
        bug: { error_pattern, error_type, tags: tags || [] },
        solution: { approach_name, steps },
        failed_approaches: failed_approaches || [],
      };

      const data = await apiRequest<{
        bug_id: string;
        solution_id: string;
        is_new_bug: boolean;
        message: string;
      }>("/api/v1/contribute/", { method: "POST", body, auth: true });

      return {
        structuredContent: { ok: true, ...data },
        content: [
          {
            type: "text" as const,
            text: `Solution contributed to AgentStack.\nBug ID: ${data.bug_id}\nSolution ID: ${data.solution_id}\nNew bug: ${data.is_new_bug}`,
          },
        ],
      };
    } catch (err) {
      return {
        isError: true,
        structuredContent: { ok: false, error: (err as Error).message },
        content: [
          { type: "text" as const, text: `Contribution failed: ${(err as Error).message}` },
        ],
      };
    }
  }
);

server.tool(
  "agentstack_verify",
  "Report whether a solution from AgentStack worked or failed. This improves solution rankings for future agents.",
  {
    solution_id: z.string().describe("The solution ID to verify"),
    success: z.boolean().describe("Whether the solution resolved the bug"),
    resolution_time_ms: z.number().optional().describe("How long it took to apply and verify"),
  },
  async ({ solution_id, success, resolution_time_ms }) => {
    try {
      const body: Record<string, unknown> = { solution_id, success, context: {} };
      if (resolution_time_ms) body.resolution_time_ms = resolution_time_ms;

      const data = await apiRequest<{
        verification_id: string;
        new_success_rate: number;
      }>("/api/v1/verify/", { method: "POST", body, auth: true });

      const pct = (data.new_success_rate * 100).toFixed(1);
      return {
        structuredContent: { ok: true, ...data },
        content: [
          {
            type: "text" as const,
            text: `Verification recorded. Solution success rate is now ${pct}%.`,
          },
        ],
      };
    } catch (err) {
      return {
        isError: true,
        structuredContent: { ok: false, error: (err as Error).message },
        content: [
          { type: "text" as const, text: `Verification failed: ${(err as Error).message}` },
        ],
      };
    }
  }
);

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

main().catch(console.error);
