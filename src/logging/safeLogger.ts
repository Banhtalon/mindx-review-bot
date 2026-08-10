const SAFE_KEYS = new Set([
  "jobId",
  "job_id",
  "jobType",
  "job_type",
  "status",
  "recordsRead",
  "records_read",
  "errorCode",
  "error_code",
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

function sanitizeValue(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(sanitizeValue);
  if (!value || typeof value !== "object") return value;

  const output: Record<string, unknown> = {};
  for (const [key, nestedValue] of Object.entries(value)) {
    if (SAFE_KEYS.has(key)) output[key] = sanitizeValue(nestedValue);
  }
  return output;
}

export function sanitizeLogMetadata(metadata: Record<string, unknown>): Record<string, unknown> {
  return sanitizeValue(metadata) as Record<string, unknown>;
}
