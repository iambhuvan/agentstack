import Conf from "conf";

const config = new Conf({ projectName: "agentstack" });

export function getBaseUrl(): string {
  return (config.get("baseUrl") as string) || "http://localhost:8000";
}

export function getApiKey(): string {
  const key = config.get("apiKey") as string;
  if (!key) {
    throw new Error(
      "Not logged in. Run `agentstack login` to set your API key."
    );
  }
  return key;
}

export function setConfig(key: string, value: string): void {
  config.set(key, value);
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  requireAuth?: boolean;
}

export async function apiRequest<T>(
  path: string,
  options: RequestOptions = {}
): Promise<T> {
  const { method = "GET", body, requireAuth = false } = options;
  const baseUrl = getBaseUrl();

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };

  if (requireAuth) {
    headers["X-API-Key"] = getApiKey();
  }

  const res = await fetch(`${baseUrl}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  if (!res.ok) {
    const errBody = await res.text();
    throw new Error(`API error ${res.status}: ${errBody}`);
  }

  return res.json() as Promise<T>;
}
