import chalk from "chalk";
import ora from "ora";
import { apiRequest } from "../lib/api.js";

interface ContributeArgs {
  errorPattern: string;
  errorType: string;
  approachName: string;
  steps: string;
  tags?: string;
  diff?: string;
  json?: boolean;
}

interface ContributeResponse {
  bug_id: string;
  solution_id: string;
  is_new_bug: boolean;
  message: string;
}

export async function contributeCommand(opts: ContributeArgs): Promise<void> {
  const spinner = ora("Contributing solution...").start();

  try {
    let parsedSteps: unknown[];
    try {
      parsedSteps = JSON.parse(opts.steps);
    } catch {
      spinner.fail("Invalid steps JSON");
      console.error(
        chalk.red("Steps must be valid JSON. Example: ") +
          chalk.dim('[{"action": "exec", "command": "npm install"}]')
      );
      process.exit(1);
    }

    const body = {
      bug: {
        error_pattern: opts.errorPattern,
        error_type: opts.errorType,
        tags: opts.tags ? opts.tags.split(",").map((t) => t.trim()) : [],
      },
      solution: {
        approach_name: opts.approachName,
        steps: parsedSteps,
        diff_patch: opts.diff || null,
      },
      failed_approaches: [],
    };

    const data = await apiRequest<ContributeResponse>("/api/v1/contribute/", {
      method: "POST",
      body,
      requireAuth: true,
    });

    spinner.succeed("Solution contributed!");

    if (opts.json) {
      console.log(JSON.stringify(data, null, 2));
    } else {
      console.log(chalk.green(`  Bug ID:      ${data.bug_id}`));
      console.log(chalk.green(`  Solution ID: ${data.solution_id}`));
      console.log(chalk.dim(`  New bug: ${data.is_new_bug}`));
    }
  } catch (err) {
    spinner.fail("Contribution failed");
    console.error(chalk.red((err as Error).message));
    process.exit(1);
  }
}
