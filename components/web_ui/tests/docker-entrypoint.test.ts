import { spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const script = join(__dirname, "..", "docker-entrypoint.d", "40-config.sh");

function run(env: Record<string, string>) {
  const dir = mkdtempSync(join(tmpdir(), "html-"));
  const result = spawnSync("sh", [script], {
    env: { PATH: process.env.PATH ?? "", HTML_DIR: dir, ...env },
    encoding: "utf-8",
  });
  return { dir, result };
}

describe("container start-up config script", () => {
  it("writes config.json from API_BASE_URL", () => {
    const { dir, result } = run({ API_BASE_URL: "https://agent.example.com" });
    expect(result.status).toBe(0);
    expect(JSON.parse(readFileSync(join(dir, "config.json"), "utf-8"))).toEqual(
      {
        apiBaseUrl: "https://agent.example.com",
      },
    );
  });

  it("keeps the default config when API_BASE_URL is not set", () => {
    const { dir, result } = run({});
    expect(result.status).toBe(0);
    expect(() => readFileSync(join(dir, "config.json"))).toThrow();
  });

  it.each(["javascript:alert(1)", "agent.example.com", "ftp://x"])(
    "refuses %s",
    (value) => {
      const { result } = run({ API_BASE_URL: value });
      expect(result.status).not.toBe(0);
      expect(result.stderr).toContain("must start with http");
    },
  );
});
