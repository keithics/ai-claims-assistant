import { ApiError } from "../api/client";
import type { MessageKey } from "../i18n/locales";

export interface ApprovalFailure {
  errorKey?: MessageKey;
  errorMessage?: string;
  retryable: boolean;
}

export function toApprovalFailure(error: unknown): ApprovalFailure {
  if (error instanceof ApiError) {
    if (error.code === "token_expired")
      return { errorKey: "approval.expired", retryable: false };
    if (error.code === "token_used")
      return { errorKey: "approval.used", retryable: false };
    if (error.code === "unavailable" || error.code === "network") {
      return { errorKey: "approval.unavailable", retryable: true };
    }
    return { errorMessage: error.message, retryable: false };
  }
  return {
    errorMessage: error instanceof Error ? error.message : String(error),
    retryable: true,
  };
}
