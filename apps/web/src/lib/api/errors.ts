import type { ErrorCode } from "@saveclock/contracts";
import { z } from "zod";

/**
 * What to do about each API error code. `satisfies Record<ErrorCode, ...>` makes a code added to
 * the Python `ErrorCode` enum (and regenerated into the contracts) a compile error here until it
 * is given a deliberate entry. In Phase 1 every code lands on a read-only GET, so Retry is safe.
 */
export type ErrorAdvice = { retry: boolean };
const RETRY: ErrorAdvice = { retry: true };

export const ERROR_ADVICE = {
  validation_error: RETRY,
  bad_request: RETRY,
  forbidden: RETRY,
  not_found: RETRY,
  conflict: RETRY,
  plan_version_conflict: RETRY,
  lock_conflict: RETRY,
  payload_too_large: RETRY,
  unsupported_media: RETRY,
  file_rejected: RETRY,
  insufficient_storage: RETRY,
  pixabay_not_configured: RETRY,
  stock_unavailable: RETRY,
  clip_unavailable: RETRY,
  verification_failed: RETRY,
  upstream_unavailable: RETRY,
  internal_error: RETRY,
} satisfies Record<ErrorCode, ErrorAdvice>;

function isErrorCode(value: string): value is ErrorCode {
  return Object.hasOwn(ERROR_ADVICE, value);
}

const envelopeSchema = z.object({
  error: z.object({
    code: z.string(),
    message: z.string(),
    details: z.record(z.string(), z.unknown()).nullish(),
    request_id: z.string(),
    doc_url: z.string().nullish(),
  }),
});

/** The one error type the UI sees. `status` is 0 when the server could not be reached at all. */
export class ApiError extends Error {
  readonly code: ErrorCode;
  readonly requestId: string | null;
  readonly status: number;
  readonly details: Record<string, unknown> | null;
  /** True when the body was the API's own error envelope (not a proxy page or an empty body). */
  readonly enveloped: boolean;

  constructor(init: {
    code: ErrorCode;
    message: string;
    status: number;
    requestId?: string | null;
    details?: Record<string, unknown> | null;
    enveloped?: boolean;
  }) {
    super(init.message);
    this.name = "ApiError";
    this.code = init.code;
    this.status = init.status;
    this.requestId = init.requestId ?? null;
    this.details = init.details ?? null;
    this.enveloped = init.enveloped ?? false;
  }

  get advice(): ErrorAdvice {
    return ERROR_ADVICE[this.code];
  }
}

/** Parse an error body (already JSON-decoded or not) into an `ApiError`; never throws strings. */
export function toApiError(body: unknown, status: number): ApiError {
  const parsed = envelopeSchema.safeParse(body);
  if (parsed.success) {
    const { code, message, details, request_id: requestId } = parsed.data.error;
    return new ApiError({
      code: isErrorCode(code) ? code : "internal_error",
      message,
      status,
      requestId,
      details: details ?? null,
      enveloped: true,
    });
  }
  // Not our envelope (a proxy's HTML 502, an empty body): the server layer is unavailable.
  return new ApiError({ code: "upstream_unavailable", message: `HTTP ${status}`, status });
}

export function networkError(cause: unknown): ApiError {
  const message = cause instanceof Error ? cause.message : "network error";
  return new ApiError({ code: "upstream_unavailable", message, status: 0 });
}
