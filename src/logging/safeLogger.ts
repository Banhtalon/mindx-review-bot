const SAFE_ENUM_VALUES: Record<string, ReadonlySet<string>> = {
  status: new Set([
    "queued",
    "dispatching",
    "dispatched",
    "running",
    "succeeded",
    "partial",
    "dispatch_failed",
    "failed",
    "cancelled",
  ]),
  jobType: new Set(["sync_teaching", "read_lms_pending"]),
  job_type: new Set(["sync_teaching", "read_lms_pending"]),
  errorCode: new Set([
    "AUTH_EXPIRED",
    "AUTH_FAILED",
    "CAPTCHA_DETECTED",
    "DOMAIN_BLOCKED",
    "TEACHING_SELECTOR_CHANGED",
    "LMS_SELECTOR_CHANGED",
    "CLASS_IDENTITY_MISMATCH",
    "SESSION_IDENTITY_MISMATCH",
    "STUDENT_MAPPING_UNRESOLVABLE",
    "PRIVACY_GUARD_BLOCKED",
    "JOB_ALREADY_CLAIMED",
    "JOB_LEASE_EXPIRED",
    "GITHUB_DISPATCH_FAILED",
    "SUPABASE_UNAVAILABLE",
    "GEMINI_TIMEOUT",
    "GEMINI_SCHEMA_INVALID",
    "GENERATION_PARTIAL",
    "STORAGE_STATE_DECRYPT_FAILED",
    "QUOTA_GUARD_BLOCKED",
  ]),
  error_code: new Set([
    "AUTH_EXPIRED",
    "AUTH_FAILED",
    "CAPTCHA_DETECTED",
    "DOMAIN_BLOCKED",
    "TEACHING_SELECTOR_CHANGED",
    "LMS_SELECTOR_CHANGED",
    "CLASS_IDENTITY_MISMATCH",
    "SESSION_IDENTITY_MISMATCH",
    "STUDENT_MAPPING_UNRESOLVABLE",
    "PRIVACY_GUARD_BLOCKED",
    "JOB_ALREADY_CLAIMED",
    "JOB_LEASE_EXPIRED",
    "GITHUB_DISPATCH_FAILED",
    "SUPABASE_UNAVAILABLE",
    "GEMINI_TIMEOUT",
    "GEMINI_SCHEMA_INVALID",
    "GENERATION_PARTIAL",
    "STORAGE_STATE_DECRYPT_FAILED",
    "QUOTA_GUARD_BLOCKED",
  ]),
};

const NUMERIC_KEYS = new Set([
  "recordsRead",
  "records_read",
  "durationMs",
  "duration_ms",
  "attempt",
  "studentCount",
  "student_count",
  "classCount",
  "class_count",
  "browserMs",
  "browser_ms",
]);

const ID_KEYS = new Set(["jobId", "job_id"]);
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function sanitizeEntry(key: string, value: unknown): unknown {
  if (ID_KEYS.has(key) && typeof value === "string" && UUID_PATTERN.test(value)) {
    return value;
  }

  if (
    NUMERIC_KEYS.has(key) &&
    typeof value === "number" &&
    Number.isInteger(value) &&
    Number.isFinite(value) &&
    value >= 0
  ) {
    return value;
  }

  const allowedValues = SAFE_ENUM_VALUES[key];
  if (allowedValues && typeof value === "string" && allowedValues.has(value)) {
    return value;
  }

  return undefined;
}

export function sanitizeLogMetadata(metadata: Record<string, unknown>): Record<string, unknown> {
  const output: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(metadata)) {
    const sanitized = sanitizeEntry(key, value);
    if (sanitized !== undefined) output[key] = sanitized;
  }
  return output;
}
