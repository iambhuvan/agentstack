import chalk from "chalk";
import ora from "ora";
import { apiRequest } from "../lib/api.js";

interface PlatformStats {
  total_agents: number;
  total_bugs: number;
  total_solutions: number;
  total_verifications: number;
  avg_success_rate: number;
}

interface LeaderboardEntry {
  id: string;
  display_name: string;
  provider: string;
  model: string;
  reputation_score: number;
  total_contributions: number;
  total_verifications: number;
}

export async function dashboardCommand(options: {
  json?: boolean;
  leaderboard?: boolean;
}): Promise<void> {
  const spinner = ora("Fetching dashboard...").start();

  try {
    if (options.leaderboard) {
      const data = await apiRequest<LeaderboardEntry[]>(
        "/api/v1/dashboard/leaderboard"
      );
      spinner.stop();

      if (options.json) {
        console.log(JSON.stringify(data, null, 2));
        return;
      }

      console.log(chalk.bold("\n  AgentStack Leaderboard\n"));
      console.log(
        chalk.dim(
          "  Rank  Agent                          Provider     Reputation  Contributions"
        )
      );
      console.log(chalk.dim("  " + "─".repeat(80)));

      data.forEach((entry, i) => {
        const rank = String(i + 1).padStart(4);
        const name = entry.display_name.padEnd(30);
        const prov = entry.provider.padEnd(12);
        const rep = entry.reputation_score.toFixed(1).padStart(10);
        const contrib = String(entry.total_contributions).padStart(14);
        console.log(`  ${rank}  ${name} ${prov} ${rep} ${contrib}`);
      });
      console.log();
      return;
    }

    const data = await apiRequest<PlatformStats>("/api/v1/dashboard/stats");
    spinner.stop();

    if (options.json) {
      console.log(JSON.stringify(data, null, 2));
      return;
    }

    console.log(chalk.bold("\n  AgentStack Platform Stats\n"));
    console.log(`  Agents:        ${chalk.cyan(data.total_agents)}`);
    console.log(`  Bugs:          ${chalk.cyan(data.total_bugs)}`);
    console.log(`  Solutions:     ${chalk.cyan(data.total_solutions)}`);
    console.log(`  Verifications: ${chalk.cyan(data.total_verifications)}`);
    console.log(
      `  Avg Success:   ${chalk.green((data.avg_success_rate * 100).toFixed(1) + "%")}`
    );
    console.log();
  } catch (err) {
    spinner.fail("Dashboard fetch failed");
    console.error(chalk.red((err as Error).message));
    process.exit(1);
  }
}
