import chalk from "chalk";
import ora from "ora";
import { apiRequest } from "../lib/api.js";

interface VerifyResponse {
  verification_id: string;
  solution_id: string;
  new_success_rate: number;
  message: string;
}

export async function verifyCommand(
  solutionId: string,
  options: { success?: boolean; failure?: boolean; time?: string; json?: boolean }
): Promise<void> {
  const isSuccess = options.success === true;
  const isFailure = options.failure === true;

  if (!isSuccess && !isFailure) {
    console.error(chalk.red("Specify --success or --failure"));
    process.exit(1);
  }

  const spinner = ora("Recording verification...").start();

  try {
    const body = {
      solution_id: solutionId,
      success: isSuccess,
      resolution_time_ms: options.time ? parseInt(options.time, 10) : null,
      context: {},
    };

    const data = await apiRequest<VerifyResponse>("/api/v1/verify/", {
      method: "POST",
      body,
      requireAuth: true,
    });

    spinner.succeed("Verification recorded!");

    if (options.json) {
      console.log(JSON.stringify(data, null, 2));
    } else {
      const rate = (data.new_success_rate * 100).toFixed(1);
      console.log(chalk.green(`  Solution ${data.solution_id}`));
      console.log(chalk.green(`  New success rate: ${rate}%`));
    }
  } catch (err) {
    spinner.fail("Verification failed");
    console.error(chalk.red((err as Error).message));
    process.exit(1);
  }
}
