import chalk from "chalk";
import ora from "ora";
import { apiRequest } from "../lib/api.js";

interface SearchResult {
  bug: {
    id: string;
    error_type: string;
    error_pattern: string;
    solution_count: number;
    tags: string[];
  };
  solutions: Array<{
    id: string;
    approach_name: string;
    success_rate: number;
    total_attempts: number;
    steps: Array<{ action: string; target?: string; command?: string; description?: string }>;
    warnings: string[];
  }>;
  failed_approaches: Array<{
    approach_name: string;
    failure_rate: number;
    reason: string;
  }>;
  match_type: string;
  similarity_score: number;
}

interface SearchResponse {
  results: SearchResult[];
  total_found: number;
  search_time_ms: number;
  auto_contributed_bug_id?: string | null;
}

export async function searchCommand(
  error: string,
  options: {
    type?: string;
    json?: boolean;
    model?: string;
    provider?: string;
    autoContribute?: boolean;
    context?: string;
  }
): Promise<void> {
  const spinner = ora("Searching AgentStack...").start();

  try {
    const body: Record<string, unknown> = {
      error_pattern: error,
    };
    if (options.type) body.error_type = options.type;
    if (options.model) body.agent_model = options.model;
    if (options.provider) body.agent_provider = options.provider;
    if (options.autoContribute) {
      body.auto_contribute_on_miss = true;
      if (options.context) {
        try {
          body.context_packet = JSON.parse(options.context);
        } catch {
          spinner.fail("Search failed");
          console.error(chalk.red("`--context` must be valid JSON."));
          process.exit(1);
        }
      }
    }

    const data = await apiRequest<SearchResponse>("/api/v1/search/", {
      method: "POST",
      body,
    });

    spinner.stop();

    if (options.json) {
      console.log(JSON.stringify(data, null, 2));
      return;
    }

    if (data.results.length === 0) {
      console.log(chalk.yellow("No matching solutions found."));
      if (data.auto_contributed_bug_id) {
        console.log(
          chalk.cyan(`Question auto-contributed as bug ${data.auto_contributed_bug_id}.`)
        );
      }
      console.log(chalk.dim(`Search took ${data.search_time_ms}ms`));
      return;
    }

    console.log(
      chalk.green(`Found ${data.total_found} result(s) in ${data.search_time_ms}ms\n`)
    );

    for (const result of data.results) {
      console.log(
        chalk.bold(`Bug: ${result.bug.error_type}`) +
          chalk.dim(` [${result.match_type}, score: ${result.similarity_score?.toFixed(3) ?? "1.000"}]`)
      );
      console.log(chalk.dim(result.bug.error_pattern.slice(0, 120)));
      console.log();

      if (result.solutions.length > 0) {
        console.log(chalk.cyan("  Solutions:"));
        for (const sol of result.solutions) {
          const rate = (sol.success_rate * 100).toFixed(1);
          const color = sol.success_rate > 0.8 ? chalk.green : sol.success_rate > 0.5 ? chalk.yellow : chalk.red;
          console.log(
            `    ${color(`${rate}%`)} ${sol.approach_name} ${chalk.dim(`(${sol.total_attempts} attempts)`)}`
          );
          for (const step of sol.steps) {
            const desc = step.command || step.description || step.target || step.action;
            console.log(chalk.dim(`      -> ${step.action}: ${desc}`));
          }
          if (sol.warnings.length > 0) {
            console.log(chalk.yellow(`      warnings: ${sol.warnings.join(", ")}`));
          }
        }
      }

      if (result.failed_approaches.length > 0) {
        console.log(chalk.red("\n  Failed Approaches (skip these):"));
        for (const fa of result.failed_approaches) {
          console.log(
            chalk.red(`    X ${fa.approach_name}`) +
              chalk.dim(` (${(fa.failure_rate * 100).toFixed(0)}% fail) — ${fa.reason}`)
          );
        }
      }

      console.log();
    }
  } catch (err) {
    spinner.fail("Search failed");
    console.error(chalk.red((err as Error).message));
    process.exit(1);
  }
}
