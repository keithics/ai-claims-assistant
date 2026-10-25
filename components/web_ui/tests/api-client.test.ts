import { describe, expect, it, vi } from "vitest";
import { ApiError, createApi, describeError } from "../src/api/client";
import { reply } from "./helpers";

function fakeFetch(
  handler: (request: Request) => Response | Promise<Response>,
) {
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) =>
    handler(new Request(input, init)),
  ) as unknown as typeof fetch & ReturnType<typeof vi.fn>;
}

describe("createApi", () => {
  it("posts chat requests to the configured base URL and returns typed data", async () => {
    let seen: Request | undefined;
    const fetchImpl = fakeFetch((request) => {
      seen = request;
      return Response.json(reply());
    });
    const api = createApi("https://api.test", fetchImpl);
    const body = {
      message: "hello",
      country: "ph",
      language: "en",
      conversation_id: null,
      history: [],
    };
    const result = await api.chat(body);
    expect(result.answer).toContain("30 days");
    expect(seen?.url).toBe("https://api.test/chat");
    expect(seen?.method).toBe("POST");
    expect(await seen?.json()).toEqual(body);
  });

  it("reads countries and documents", async () => {
    const urls: string[] = [];
    const fetchImpl = fakeFetch((request) => {
      urls.push(new URL(request.url).pathname);
      return Response.json(urls.length === 1 ? [] : { doc_id: "ph-x" });
    });
    const api = createApi("https://api.test", fetchImpl);
    await api.countries();
    await api.document("ph-x");
    expect(urls).toEqual(["/countries", "/documents/ph-x"]);
  });

  it("turns structured errors into ApiError with the server's code", async () => {
    const fetchImpl = fakeFetch(() =>
      Response.json(
        { detail: { code: "token_expired", message: "expired" } },
        { status: 410 },
      ),
    );
    const api = createApi("https://api.test", fetchImpl);
    await expect(
      api.approve({ claim_id: "PH-5001", token: "x".repeat(12) }),
    ).rejects.toMatchObject({
      status: 410,
      code: "token_expired",
      message: "expired",
    });
  });

  it("reports a network failure as ApiError with code network", async () => {
    const fetchImpl = fakeFetch(() => {
      throw new TypeError("Failed to fetch");
    });
    const api = createApi("https://api.test", fetchImpl);
    await expect(api.countries()).rejects.toMatchObject({
      status: 0,
      code: "network",
    });
  });
});

describe("describeError", () => {
  it("handles string, list and object details and missing bodies", () => {
    expect(describeError(422, { detail: "unknown country" })).toMatchObject({
      status: 422,
      message: "unknown country",
      code: null,
    });
    expect(
      describeError(422, { detail: [{ msg: "too short" }, { msg: "bad" }] })
        .message,
    ).toBe("too short; bad");
    expect(
      describeError(409, { detail: { code: "token_used", message: "used" } })
        .code,
    ).toBe("token_used");
    expect(describeError(500, undefined).message).toBe("request failed (500)");
    expect(describeError(500, { detail: {} })).toBeInstanceOf(ApiError);
  });
});
