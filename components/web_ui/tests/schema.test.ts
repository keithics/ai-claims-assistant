import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const root = join(__dirname, "..");

describe("generated API client types", () => {
  it("match what the committed OpenAPI schema generates", () => {
    const out = join(mkdtempSync(join(tmpdir(), "schema-")), "schema.d.ts");
    execFileSync(
      join(root, "node_modules", ".bin", "openapi-typescript"),
      [join(root, "..", "agent_app", "openapi.json"), "-o", out],
      { stdio: "pipe" },
    );
    expect(readFileSync(out, "utf-8")).toBe(
      readFileSync(join(root, "src", "api", "schema.d.ts"), "utf-8"),
    );
  });

  it("cover every endpoint the UI calls", () => {
    const schema = JSON.parse(
      readFileSync(join(root, "..", "agent_app", "openapi.json"), "utf-8"),
    ) as { paths: Record<string, unknown> };
    expect(Object.keys(schema.paths)).toEqual(
      expect.arrayContaining([
        "/chat",
        "/approve",
        "/reject",
        "/countries",
        "/documents/{doc_id}",
      ]),
    );
  });
});
