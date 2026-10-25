import type { components } from "./schema";

type Schemas = components["schemas"];

export type ChatRequest = Schemas["ChatRequest"];
export type ChatResponse = Schemas["ChatResponse"];
export type Citation = Schemas["Citation"];
export type ClaimView = Schemas["ClaimView"];
export type PendingApproval = Schemas["PendingApproval"];
export type Usage = Schemas["Usage"];
export type CountryInfo = Schemas["CountryInfo"];
export type DocumentView = Schemas["DocumentView"];
export type ApprovalRequest = Schemas["ApprovalRequest"];
export type ApproveResponse = Schemas["ApproveResponse"];
export type RejectResponse = Schemas["RejectResponse"];
