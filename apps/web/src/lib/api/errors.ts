import type { ErrorCode } from "@saveclock/contracts";
import { z } from "zod";

/**
 * Every code the API can send, so an unknown one is recognised at runtime. `satisfies` makes a code
 * added to the Python `ErrorCode` enum (and regenerated into the contracts) a compile error here until
 * it is listed deliberately.
 */
const ERROR_CODES = {
  validation_error: true,
  bad_request: true,
  forbidden: true,
  not_found: true,
  conflict: true,
  plan_version_conflict: true,
  lock_conflict: true,
  payload_too_large: true,
  unsupported_media: true,
  file_rejected: true,
  insufficient_storage: true,
  pixabay_not_configured: true,
  stock_unavailable: true,
  clip_unavailable: true,
  verification_failed: true,
  upstream_unavailable: true,
  internal_error: true,
} satisfies Record<ErrorCode, true>;

function isErrorCode(value: string): value is ErrorCode {
  return Object.hasOwn(ERROR_CODES, value);
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
