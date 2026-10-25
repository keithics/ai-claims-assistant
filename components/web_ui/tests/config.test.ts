import { describe, expect, it, vi } from "vitest";
import { DEFAULT_CONFIG, loadConfig, parseConfig } from "../src/api/config";

describe("parseConfig", () => {
  it("accepts an http(s) base URL and drops trailing slashes", () => {
    expect(parseConfig({ apiBaseUrl: "https://api.example.com//" })).toEqual({
      apiBaseUrl: "https://api.example.com",
    });
    expect(
      parseConfig({ apiBaseUrl: "http://localhost:8000" }).apiBaseUrl,
    ).toBe("http://localhost:8000");
  });

  it.each([
    null,
    "x",
    5,
    {},
    { apiBaseUrl: 5 },
    { apiBaseUrl: "ftp://x" },
    { apiBaseUrl: "/api" },
  ])("rejects %j", (value) => {
    expect(() => parseConfig(value)).toThrow();
  });

  it("has no place for secrets", () => {
    expect(
      Object.keys(
        parseConfig({ apiBaseUrl: "http://x.test", apiKey: "secret" }),
      ),
    ).toEqual(["apiBaseUrl"]);
  });
});

describe("loadConfig", () => {
  it("reads /config.json at runtime", async () => {
    const fetchImpl = vi.fn(async () =>
      Response.json({ apiBaseUrl: "https://api.test" }),
    );
    expect(await loadConfig(fetchImpl as unknown as typeof fetch)).toEqual({
      apiBaseUrl: "https://api.test",
    });
    expect(fetchImpl).toHaveBeenCalledWith("/config.json", {
      cache: "no-store",
    });
  });

  it("falls back to the default when the file is missing or invalid", async () => {
    const missing = vi.fn(async () => new Response("", { status: 404 }));
    const invalid = vi.fn(async () => Response.json({ apiBaseUrl: "nope" }));
    const broken = vi.fn(async () => {
      throw new Error("offline");
    });
    for (const fetchImpl of [missing, invalid, broken]) {
      expect(await loadConfig(fetchImpl as unknown as typeof fetch)).toEqual(
        DEFAULT_CONFIG,
      );
    }
  });
});
