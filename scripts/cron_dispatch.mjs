/* global URL, console, process */

import { pathToFileURL } from "node:url";

const ALLOWED_JOB_TYPES = new Set(["sync_teaching", "read_lms_pending"]);
const ALLOWED_STATUSES = new Set([
  "queued",
  "dispatched",
  "running",
  "succeeded",
  "partial",
  "failed",
  "cancelled",
]);
const WORKSPACE_TIME_ZONE = "Asia/Ho_Chi_Minh";
const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export class CronDispatchError extends Error {
  constructor(code) {
    super(code);
    this.code = code;
  }
}

function required(environment, name) {
  const value = environment[name]?.trim();
  if (!value) throw new CronDispatchError("CRON_CONFIG_INVALID");
  return value;
}

function dispatchEnabled(environment) {
  const value = environment.CRON_DISPATCH_ENABLED;
  if (value === undefined || value === "" || value === "false") return false;
  if (value === "true") return true;
  throw new CronDispatchError("CRON_CONFIG_INVALID");
}

function validateUuid(value) {
  if (!UUID_PATTERN.test(value)) throw new CronDispatchError("CRON_CONFIG_INVALID");
  return value.toLowerCase();
}

function validateSupabaseUrl(value) {
  let parsed;
  try {
    parsed = new URL(value);
  } catch {
    throw new CronDispatchError("CRON_CONFIG_INVALID");
  }
  if (
    parsed.protocol !== "https:" ||
    parsed.hostname === null ||
    !parsed.hostname.endsWith(".supabase.co") ||
    parsed.username ||
    parsed.password ||
    parsed.port ||
    (parsed.pathname !== "" && parsed.pathname !== "/") ||
    parsed.search ||
    parsed.hash
  ) {
    throw new CronDispatchError("CRON_CONFIG_INVALID");
  }
  return parsed.origin;
}

function localDate(value) {
  if (!(value instanceof Date) || Number.isNaN(value.getTime())) {
    throw new CronDispatchError("CRON_CONFIG_INVALID");
  }
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: WORKSPACE_TIME_ZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(value);
  const part = (type) => parts.find((entry) => entry.type === type)?.value;
  const year = part("year");
  const month = part("month");
  const day = part("day");
  if (!year || !month || !day) throw new CronDispatchError("CRON_CONFIG_INVALID");
  return `${year}-${month}-${day}`;
}

function compactUtc(value) {
  return value.toISOString().slice(0, 16).replace(/\D/g, "");
}

function scheduledUtcDay(value, hour, minute) {
  return new Date(Date.UTC(
    value.getUTCFullYear(),
    value.getUTCMonth(),
    value.getUTCDate(),
    hour,
    minute,
  ));
}

function lmsWindow(value) {
  const firstWindowStart = scheduledUtcDay(value, 15, 7);
  const retryWindowStart = scheduledUtcDay(value, 16, 37);
  if (value < firstWindowStart) {
    const previousDay = new Date(firstWindowStart.getTime() - 86400000);
    return [scheduledUtcDay(previousDay, 16, 37), firstWindowStart];
  }
  if (value < retryWindowStart) return [firstWindowStart, retryWindowStart];

  const nextDay = new Date(retryWindowStart.getTime() + 86400000);
  return [retryWindowStart, scheduledUtcDay(nextDay, 15, 7)];
}

function idempotencyKey(type, workspace, now) {
  if (type === "sync_teaching") return `sync_teaching:${workspace}:${localDate(now)}`;
  const [windowStart, windowEnd] = lmsWindow(now);
  return `read_lms_pending:${workspace}:${compactUtc(windowStart)}:${compactUtc(windowEnd)}`;
}

export function buildCronDispatchRequest({
  SUPABASE_URL: supabaseUrl,
  CRON_DISPATCH_SECRET: cronSecret,
  CRON_WORKSPACE_ID: workspaceId,
  JOB_TYPE: jobType,
  now = new Date(),
}) {
  const url = validateSupabaseUrl(required({ SUPABASE_URL: supabaseUrl }, "SUPABASE_URL"));
  const secret = required({ CRON_DISPATCH_SECRET: cronSecret }, "CRON_DISPATCH_SECRET");
  const workspace = validateUuid(required({ CRON_WORKSPACE_ID: workspaceId }, "CRON_WORKSPACE_ID"));
  const type = required({ JOB_TYPE: jobType }, "JOB_TYPE");
  if (!ALLOWED_JOB_TYPES.has(type)) throw new CronDispatchError("CRON_CONFIG_INVALID");

  return {
    url: `${url}/functions/v1/dispatch-job`,
    headers: {
      "content-type": "application/json",
      "x-cron-dispatch-secret": secret,
    },
    body: JSON.stringify({
      workspace_id: workspace,
      type,
      idempotency_key: idempotencyKey(type, workspace, now),
      payload: {},
    }),
  };
}

export async function dispatchCronJob({
  environment = process.env,
  fetcher = globalThis.fetch,
  now = new Date(),
} = {}) {
  if (!dispatchEnabled(environment)) return { status: "disabled" };
  if (typeof fetcher !== "function") throw new CronDispatchError("CRON_DISPATCH_FAILED");
  const request = buildCronDispatchRequest({ ...environment, now });
  let response;
  try {
    response = await fetcher(request.url, {
      method: "POST",
      headers: request.headers,
      body: request.body,
    });
  } catch {
    throw new CronDispatchError("CRON_DISPATCH_FAILED");
  }

  if (!response.ok) throw new CronDispatchError("CRON_DISPATCH_FAILED");

  let body;
  try {
    body = await response.json();
  } catch {
    throw new CronDispatchError("CRON_DISPATCH_FAILED");
  }
  const jobId = body?.job_id;
  const status = body?.status;
  if (
    typeof jobId !== "string" ||
    !UUID_PATTERN.test(jobId) ||
    typeof status !== "string" ||
    !ALLOWED_STATUSES.has(status)
  ) {
    throw new CronDispatchError("CRON_DISPATCH_FAILED");
  }
  return { jobId: jobId.toLowerCase(), status };
}

function isMainModule() {
  return process.argv[1] !== undefined && import.meta.url === pathToFileURL(process.argv[1]).href;
}

if (isMainModule()) {
  try {
    const result = await dispatchCronJob();
    console.log(JSON.stringify(result));
  } catch (error) {
    const code = error instanceof CronDispatchError ? error.code : "CRON_DISPATCH_FAILED";
    console.error(JSON.stringify({ status: "failed", error_code: code }));
    process.exitCode = 1;
  }
}
