import chalk from "chalk";
import { setConfig } from "../lib/api.js";

export function loginCommand(apiKey: string, options: { url?: string }): void {
  setConfig("apiKey", apiKey);

  if (options.url) {
    setConfig("baseUrl", options.url);
  }

  console.log(chalk.green("Logged in successfully."));
  if (options.url) {
    console.log(chalk.dim(`API URL set to: ${options.url}`));
  }
}
