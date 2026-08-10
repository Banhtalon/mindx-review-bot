import type {
  DispatchDependencies,
  EnqueuedJob,
  JobStatus,
  JobType,
} from "./dispatch";

export type Fetcher = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;

export type DispatchAdapterConfig = {
  supabaseUrl: string;
  publishableKey: string;
  serviceKey: string;
  githubToken: string;
  githubRepository: string;
  githubWorkflowId: string;
  githubRef: string;
};

const JOB_STATUSES = new Set<JobStatus>([
  "queued",
  "dispatching",
  "dispatched",
  "running",
  "succeeded",
  "partial",
  "dispatch_failed",
  "failed",
  "cancelled",
]);
const JOB_TYPES = new Set<JobType>(["sync_teaching", "read_lms_pending"]);

export class AdapterError extends Error {
  constructor(public readonly code: string) {
    super(code);
    this.name = "AdapterError";
  }
}

function jsonHeaders(apiKey: string, authorization: string): HeadersInit {
  return {
    Accept: "application/json",
    "Content-Type": "application/json",
    apikey: apiKey,
    Authorization: authorization,
  };
}

async function readJson(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    throw new AdapterError("SUPABASE_UNAVAILABLE");
  }
}

function firstRow(value: unknown): Record<string, unknown> {
  const row = Array.isArray(value) ? value[0] : value;
  if (row === null || typeof row !== "object" || Array.isArray(row)) {
    throw new AdapterError("SUPABASE_UNAVAILABLE");
  }
  return row as Record<string, unknown>;
}

function requiredString(row: Record<string, unknown>, key: string): string {
  const value = row[key];
  if (typeof value !== "string" || value.length === 0) {
    throw new AdapterError("SUPABASE_UNAVAILABLE");
  }
  return value;
}

function jobStatus(value: unknown): JobStatus {
  if (typeof value !== "string" || !JOB_STATUSES.has(value as JobStatus)) {
    throw new AdapterError("SUPABASE_UNAVAILABLE");
  }
  return value as JobStatus;
}

function jobType(value: unknown): JobType {
  if (typeof value !== "string" || !JOB_TYPES.has(value as JobType)) {
    throw new AdapterError("SUPABASE_UNAVAILABLE");
  }
  return value as JobType;
}

async function callRpc(
  config: DispatchAdapterConfig,
  fetcher: Fetcher,
  name: string,
  args: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  let response: Response;
  try {
    response = await fetcher(`${config.supabaseUrl}/rest/v1/rpc/${name}`, {
      method: "POST",
      headers: jsonHeaders(config.serviceKey, `Bearer ${config.serviceKey}`),
      body: JSON.stringify(args),
    });
  } catch {
    throw new AdapterError("SUPABASE_UNAVAILABLE");
  }
  if (!response.ok) throw new AdapterError("SUPABASE_UNAVAILABLE");
  return firstRow(await readJson(response));
}

export function createDispatchDependencies(
  config: DispatchAdapterConfig,
  fetcher: Fetcher = fetch,
): DispatchDependencies {
  return {
    authenticateUser: async (accessToken) => {
      let response: Response;
      try {
        response = await fetcher(`${config.supabaseUrl}/auth/v1/user`, {
          headers: {
            Accept: "application/json",
            apikey: config.publishableKey,
            Authorization: `Bearer ${accessToken}`,
          },
        });
      } catch {
        throw new AdapterError("SUPABASE_UNAVAILABLE");
      }
      if (response.status === 401 || response.status === 403) return null;
      if (!response.ok) throw new AdapterError("SUPABASE_UNAVAILABLE");
      const body = firstRow(await readJson(response));
      const userId = requiredString(body, "id");
      return { userId, accessToken };
    },

    authorizeOwner: async (userId, workspaceId, accessToken) => {
      if (accessToken === undefined) return false;
      const params = new URLSearchParams({
        workspace_id: `eq.${workspaceId}`,
        user_id: `eq.${userId}`,
        select: "role",
        limit: "1",
      });
      let response: Response;
      try {
        response = await fetcher(
          `${config.supabaseUrl}/rest/v1/workspace_members?${params.toString()}`,
          {
            headers: {
              Accept: "application/json",
              apikey: config.publishableKey,
              Authorization: `Bearer ${accessToken}`,
            },
          },
        );
      } catch {
        throw new AdapterError("SUPABASE_UNAVAILABLE");
      }
      if (response.status === 401 || response.status === 403) return false;
      if (!response.ok) throw new AdapterError("SUPABASE_UNAVAILABLE");
      const body = await readJson(response);
      if (!Array.isArray(body) || body.length !== 1) return false;
      const row = body[0];
      return row !== null && typeof row === "object" && !Array.isArray(row)
        && (row as Record<string, unknown>).role === "owner";
    },

    enqueueJob: async ({ workspaceId, type, idempotencyKey, payload, requestedBy }) => {
      const row = await callRpc(config, fetcher, "enqueue_automation_job", {
        target_workspace_id: workspaceId,
        target_type: type,
        target_idempotency_key: idempotencyKey,
        target_payload: payload,
        target_requested_by: requestedBy,
      });
      const payloadJson = row.payload_json;
      if (payloadJson === null || typeof payloadJson !== "object" || Array.isArray(payloadJson)) {
        throw new AdapterError("SUPABASE_UNAVAILABLE");
      }
      const created = row.created;
      if (typeof created !== "boolean") throw new AdapterError("SUPABASE_UNAVAILABLE");
      return {
        jobId: requiredString(row, "job_id"),
        workspaceId: requiredString(row, "workspace_id"),
        type: jobType(row.job_type),
        status: jobStatus(row.status),
        idempotencyKey: requiredString(row, "idempotency_key"),
        payload: payloadJson as Record<string, unknown>,
        created,
      } satisfies EnqueuedJob;
    },

    claimDispatch: async (jobId) => {
      const row = await callRpc(config, fetcher, "claim_automation_job_dispatch", {
        target_job_id: jobId,
      });
      if (typeof row.claimed !== "boolean") throw new AdapterError("SUPABASE_UNAVAILABLE");
      return { claimed: row.claimed, status: jobStatus(row.status) };
    },

    finishDispatch: async (jobId, status) => {
      const row = await callRpc(config, fetcher, "finish_automation_job_dispatch", {
        target_job_id: jobId,
        target_status: status,
      });
      return { status: jobStatus(row.status) };
    },

    dispatchGitHub: async ({ jobId, jobType }) => {
      const url = `https://api.github.com/repos/${config.githubRepository}/actions/workflows/${encodeURIComponent(config.githubWorkflowId)}/dispatches`;
      let response: Response;
      try {
        response = await fetcher(url, {
          method: "POST",
          headers: {
            Accept: "application/vnd.github+json",
            Authorization: `Bearer ${config.githubToken}`,
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            ref: config.githubRef,
            inputs: { job_id: jobId, job_type: jobType },
          }),
        });
      } catch {
        throw new AdapterError("GITHUB_DISPATCH_FAILED");
      }
      return { status: response.status };
    },
  };
}
