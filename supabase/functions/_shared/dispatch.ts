export const ALLOWED_JOB_TYPES = ["sync_teaching", "read_lms_pending"] as const;
export type JobType = (typeof ALLOWED_JOB_TYPES)[number];

export type JobStatus =
  | "queued"
  | "dispatching"
  | "dispatched"
  | "running"
  | "succeeded"
  | "partial"
  | "dispatch_failed"
  | "failed"
  | "cancelled";

export type DispatchRequest = {
  authorization?: string;
  cronSecret?: string;
  workspaceId: string;
  type: string;
  idempotencyKey: string;
  payload: unknown;
};

export type DispatchConfig = {
  cronSecret: string;
  cronActorUserId: string;
  cronWorkspaceId: string;
};

export type AuthenticatedUser = {
  userId: string;
  accessToken?: string;
};

export type EnqueuedJob = {
  jobId: string;
  workspaceId: string;
  type: JobType;
  status: JobStatus;
  idempotencyKey: string;
  payload: Record<string, unknown>;
  created: boolean;
};

export type DispatchDependencies = {
  authenticateUser: (accessToken: string) => Promise<AuthenticatedUser | null>;
  authorizeOwner: (
    userId: string,
    workspaceId: string,
    accessToken?: string,
  ) => Promise<boolean>;
  enqueueJob: (input: {
    workspaceId: string;
    type: JobType;
    idempotencyKey: string;
    payload: Record<string, unknown>;
    requestedBy: string;
  }) => Promise<EnqueuedJob>;
  claimDispatch: (jobId: string) => Promise<{ claimed: boolean; status: JobStatus }>;
  finishDispatch: (
    jobId: string,
    status: "dispatched" | "dispatch_failed",
  ) => Promise<{ status: JobStatus }>;
  dispatchGitHub: (input: { jobId: string; jobType: JobType }) => Promise<{ status: number }>;
};

export type DispatchResponse = {
  status: number;
  body: {
    job_id?: string;
    status?: JobStatus;
    created?: boolean;
    error_code?: string;
  };
};

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const IDEMPOTENCY_KEY_PATTERN = /^[a-z0-9][a-z0-9._:-]{0,127}$/;
const FORBIDDEN_PAYLOAD_KEY = /(?:authorization|cookie|credential|password|secret|token|url)/i;
const URL_VALUE_PATTERN = /^https?:\/\//i;
const TERMINAL_STATUSES = new Set<JobStatus>([
  "dispatched",
  "running",
  "succeeded",
  "partial",
  "failed",
  "cancelled",
]);

function isUuid(value: string): boolean {
  return UUID_PATTERN.test(value);
}

function hasForbiddenPayload(value: unknown, depth = 0): boolean {
  if (depth > 4) return true;
  if (typeof value === "string") return URL_VALUE_PATTERN.test(value);
  if (Array.isArray(value)) return value.some((entry) => hasForbiddenPayload(entry, depth + 1));
  if (value === null || typeof value !== "object") return false;

  return Object.entries(value).some(([key, entry]) => {
    return FORBIDDEN_PAYLOAD_KEY.test(key) || hasForbiddenPayload(entry, depth + 1);
  });
}

function isPayloadRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function safeEqual(left: string, right: string): boolean {
  if (left.length !== right.length) return false;
  let difference = 0;
  for (let index = 0; index < left.length; index += 1) {
    difference |= left.charCodeAt(index) ^ right.charCodeAt(index);
  }
  return difference === 0;
}

function parseBearerToken(authorization: string | undefined): string | null {
  if (!authorization?.startsWith("Bearer ")) return null;
  const token = authorization.slice("Bearer ".length).trim();
  return token.length > 0 ? token : null;
}

function validateRequest(request: DispatchRequest):
  | { ok: true; type: JobType; payload: Record<string, unknown> }
  | { ok: false; response: DispatchResponse } {
  if (!isUuid(request.workspaceId)) {
    return { ok: false, response: { status: 400, body: { error_code: "INVALID_WORKSPACE_ID" } } };
  }
  if (!ALLOWED_JOB_TYPES.includes(request.type as JobType)) {
    return { ok: false, response: { status: 400, body: { error_code: "INVALID_JOB_TYPE" } } };
  }
  if (!IDEMPOTENCY_KEY_PATTERN.test(request.idempotencyKey)) {
    return { ok: false, response: { status: 400, body: { error_code: "INVALID_IDEMPOTENCY_KEY" } } };
  }
  if (!isPayloadRecord(request.payload) || hasForbiddenPayload(request.payload)) {
    return { ok: false, response: { status: 400, body: { error_code: "INVALID_JOB_PAYLOAD" } } };
  }
  try {
    if (JSON.stringify(request.payload).length > 4096) {
      return { ok: false, response: { status: 400, body: { error_code: "INVALID_JOB_PAYLOAD" } } };
    }
  } catch {
    return { ok: false, response: { status: 400, body: { error_code: "INVALID_JOB_PAYLOAD" } } };
  }
  return { ok: true, type: request.type as JobType, payload: request.payload };
}

function dependencyError(error: unknown): DispatchResponse {
  const code =
    typeof error === "object" && error !== null && "code" in error && typeof error.code === "string"
      ? error.code
      : "SUPABASE_UNAVAILABLE";
  const status = code === "IDEMPOTENCY_KEY_REUSED" ? 409 : code === "JOB_NOT_FOUND" ? 404 : 500;
  return { status, body: { error_code: code } };
}

function responseForClaim(
  job: EnqueuedJob,
  claim: { claimed: boolean; status: JobStatus },
): DispatchResponse {
  return {
    status: TERMINAL_STATUSES.has(claim.status) ? 200 : 202,
    body: { job_id: job.jobId, status: claim.status, created: job.created },
  };
}

export async function handleDispatch(
  request: DispatchRequest,
  dependencies: DispatchDependencies,
  config: DispatchConfig,
): Promise<DispatchResponse> {
  const hasJwt = request.authorization !== undefined;
  const hasCronSecret = request.cronSecret !== undefined;
  if (hasJwt === hasCronSecret) {
    return { status: 401, body: { error_code: "AUTH_REQUIRED" } };
  }

  let requestedBy: string;
  if (hasJwt) {
    const token = parseBearerToken(request.authorization);
    if (token === null) return { status: 401, body: { error_code: "AUTH_REQUIRED" } };
    const user = await dependencies.authenticateUser(token);
    if (user === null || !isUuid(user.userId)) {
      return { status: 401, body: { error_code: "AUTH_FAILED" } };
    }
    if (!(await dependencies.authorizeOwner(user.userId, request.workspaceId, user.accessToken))) {
      return { status: 403, body: { error_code: "OWNER_REQUIRED" } };
    }
    requestedBy = user.userId;
  } else {
    if (!safeEqual(request.cronSecret ?? "", config.cronSecret)) {
      return { status: 403, body: { error_code: "CRON_FORBIDDEN" } };
    }
    if (
      request.workspaceId !== config.cronWorkspaceId ||
      !isUuid(config.cronActorUserId)
    ) {
      return { status: 403, body: { error_code: "CRON_WORKSPACE_FORBIDDEN" } };
    }
    requestedBy = config.cronActorUserId;
  }

  const validation = validateRequest(request);
  if (!validation.ok) return validation.response;

  let job: EnqueuedJob;
  try {
    job = await dependencies.enqueueJob({
      workspaceId: request.workspaceId,
      type: validation.type,
      idempotencyKey: request.idempotencyKey,
      payload: validation.payload,
      requestedBy,
    });
  } catch (error) {
    return dependencyError(error);
  }

  let claim: { claimed: boolean; status: JobStatus };
  try {
    claim = await dependencies.claimDispatch(job.jobId);
  } catch (error) {
    return dependencyError(error);
  }
  if (!claim.claimed) return responseForClaim(job, claim);

  try {
    const githubResponse = await dependencies.dispatchGitHub({
      jobId: job.jobId,
      jobType: job.type,
    });
    if (githubResponse.status < 200 || githubResponse.status >= 300) {
      await dependencies.finishDispatch(job.jobId, "dispatch_failed");
      return {
        status: 502,
        body: {
          job_id: job.jobId,
          status: "dispatch_failed",
          error_code: "GITHUB_DISPATCH_FAILED",
        },
      };
    }
    const finished = await dependencies.finishDispatch(job.jobId, "dispatched");
    return {
      status: 202,
      body: { job_id: job.jobId, status: finished.status, created: job.created },
    };
  } catch {
    await dependencies.finishDispatch(job.jobId, "dispatch_failed");
    return {
      status: 502,
      body: {
        job_id: job.jobId,
        status: "dispatch_failed",
        error_code: "GITHUB_DISPATCH_FAILED",
      },
    };
  }
}
