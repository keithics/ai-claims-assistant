import createClient from "openapi-fetch";
import type { paths } from "./schema";
import type {
  ApprovalRequest,
  ApproveResponse,
  ChatRequest,
  ChatResponse,
  CountryInfo,
  DocumentView,
  RejectResponse,
} from "./types";

export class ApiError extends Error {
  readonly status: number;
  readonly code: string | null;

  constructor(status: number, code: string | null, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

export interface Api {
  countries(): Promise<CountryInfo[]>;
  chat(body: ChatRequest): Promise<ChatResponse>;
  approve(body: ApprovalRequest): Promise<ApproveResponse>;
  reject(body: ApprovalRequest): Promise<RejectResponse>;
  document(docId: string): Promise<DocumentView>;
}

export function describeError(status: number, body: unknown): ApiError {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return new ApiError(status, null, detail);
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => (item as { msg?: string }).msg)
      .filter((msg): msg is string => typeof msg === "string");
    return new ApiError(
      status,
      "invalid_request",
      messages.join("; ") || "invalid request",
    );
  }
  if (detail && typeof detail === "object") {
    const { code, message } = detail as { code?: string; message?: string };
    return new ApiError(
      status,
      code ?? null,
      message ?? `request failed (${status})`,
    );
  }
  return new ApiError(status, null, `request failed (${status})`);
}

export function createApi(
  baseUrl: string,
  fetchImpl: typeof fetch = fetch,
): Api {
  const client = createClient<paths>({
    baseUrl,
    fetch: (request) => fetchImpl(request),
  });

  async function unwrap<T>(
    result: Promise<{ data?: T; error?: unknown; response: Response }>,
  ): Promise<T> {
    let outcome;
    try {
      outcome = await result;
    } catch {
      throw new ApiError(0, "network", "the service could not be reached");
    }
    if (outcome.data === undefined)
      throw describeError(outcome.response.status, outcome.error);
    return outcome.data;
  }

  return {
    countries: () => unwrap(client.GET("/countries")),
    chat: (body) => unwrap(client.POST("/chat", { body })),
    approve: (body) => unwrap(client.POST("/approve", { body })),
    reject: (body) => unwrap(client.POST("/reject", { body })),
    document: (docId) =>
      unwrap(
        client.GET("/documents/{doc_id}", {
          params: { path: { doc_id: docId } },
        }),
      ),
  };
}
