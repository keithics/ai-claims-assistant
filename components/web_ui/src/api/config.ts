export interface AppConfig {
  apiBaseUrl: string;
}

export const DEFAULT_CONFIG: AppConfig = {
  apiBaseUrl: "http://localhost:8000",
};

export function parseConfig(raw: unknown): AppConfig {
  if (typeof raw !== "object" || raw === null) {
    throw new Error("config.json must be an object");
  }
  const url = (raw as Record<string, unknown>).apiBaseUrl;
  if (typeof url !== "string" || !/^https?:\/\/[^\s/]+/.test(url)) {
    throw new Error("config.json apiBaseUrl must be an http(s) URL");
  }
  return { apiBaseUrl: url.replace(/\/+$/, "") };
}

export async function loadConfig(
  fetchImpl: typeof fetch = fetch,
): Promise<AppConfig> {
  try {
    const response = await fetchImpl("/config.json", { cache: "no-store" });
    if (!response.ok) return DEFAULT_CONFIG;
    return parseConfig(await response.json());
  } catch {
    return DEFAULT_CONFIG;
  }
}
