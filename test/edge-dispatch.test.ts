import { describe, expect, it, vi } from "vitest";
import {
  createDispatchDependencies,
  type DispatchAdapterConfig,
  type Fetcher,
} from "../supabase/functions/_shared/edgeAdapters";
import { createDispatchHttpHandler } from "../supabase/functions/_shared/http";

const USER_ID = "00000000-0000-0000-0000-0000000000c1";
const WORKSPACE_ID = "00000000-0000-0000-0000-0000000000cc";
const JOB_ID = "00000000-0000-0000-0000-0000000000d1";

const CONFIG: DispatchAdapterConfig = {
  supabaseUrl: "https://synthetic.supabase.invalid",
  publishableKey: "synthetic-publishable-key",
  serviceKey: "synthetic-service-key",
  githubToken: "synthetic-github-token",
  githubRepository: "synthetic-owner/synthetic-repo",
  githubWorkflowId: "spike0-dispatch-probe.yml",
  githubRef: "main",
};

function response(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function request(): Request {
  return new Request("http://edge.local/dispatch-job", {
    method: "POST",
    headers: {
      Authorization: "Bearer synthetic-access-token",
      "content-type": "application/json",
    },
    body: JSON.stringify({
      workspace_id: WORKSPACE_ID,
      type: "sync_teaching",
      idempotency_key: "synthetic-dispatch-001",
      payload: {},
    }),
  });
}

function fakeFetch(githubStatus = 204): {
  fetcher: Fetcher;
  calls: Array<{ url: string; init?: RequestInit }>;
} {
  const calls: Array<{ url: string; init?: RequestInit }> = [];
  const fetcher: Fetcher = vi.fn(async (input, init) => {
    const url = String(input);
    calls.push({ url, init });
    if (url.endsWith("/auth/v1/user")) return response({ id: USER_ID });
    if (url.includes("/rest/v1/workspace_members")) return response([{ role: "owner" }]);
    if (url.endsWith("/rest/v1/rpc/enqueue_automation_job")) {
      return response([{
        job_id: JOB_ID,
        workspace_id: WORKSPACE_ID,
        job_type: "sync_teaching",
        status: "queued",
        idempotency_key: "synthetic-dispatch-001",
        payload_json: {},
        requested_by: USER_ID,
        created: true,
      }]);
    }
    if (url.endsWith("/rest/v1/rpc/claim_automation_job_dispatch")) {
      return response([{ claimed: true, status: "dispatching" }]);
    }
    if (url.endsWith("/rest/v1/rpc/finish_automation_job_dispatch")) {
      return response([{ status: githubStatus === 204 ? "dispatched" : "dispatch_failed" }]);
    }
    if (url.includes("api.github.com/repos/")) return new Response(null, { status: githubStatus });
    throw new Error(`unexpected URL: ${url}`);
  });
  return { fetcher, calls };
}

describe("dispatch Edge Function adapters", () => {
  it("rejects non-POST requests and malformed JSON", async () => {
    const { fetcher } = fakeFetch();
    const dependencies = createDispatchDependencies(CONFIG, fetcher);
    const handler = createDispatchHttpHandler(dependencies, {
      cronSecret: "synthetic-cron-secret",
      cronActorUserId: USER_ID,
      cronWorkspaceId: WORKSPACE_ID,
    });

    const methodResponse = await handler(new Request("http://edge.local", { method: "GET" }));
    const jsonResponse = await handler(new Request("http://edge.local", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: "not-json",
    }));

    expect(methodResponse.status).toBe(405);
    expect(await jsonResponse.json()).toEqual({ error_code: "INVALID_JSON" });
  });

  it("authenticates the user, calls RPCs, and dispatches GitHub", async () => {
    const { fetcher, calls } = fakeFetch();
    const dependencies = createDispatchDependencies(CONFIG, fetcher);
    const handler = createDispatchHttpHandler(dependencies, {
      cronSecret: "synthetic-cron-secret",
      cronActorUserId: USER_ID,
      cronWorkspaceId: WORKSPACE_ID,
    });

    const result = await handler(request());

    expect(result.status).toBe(202);
    expect(await result.json()).toEqual({
      job_id: JOB_ID,
      status: "dispatched",
      created: true,
    });
    const githubCall = calls.find((call) => call.url.includes("api.github.com/repos/"));
    expect(githubCall?.init?.headers).toMatchObject({
      Authorization: "Bearer synthetic-github-token",
    });
    expect(JSON.stringify(githubCall?.init)).not.toContain("synthetic-access-token");
  });

  it("returns 502 and marks the job failed when GitHub rejects dispatch", async () => {
    const { fetcher } = fakeFetch(500);
    const dependencies = createDispatchDependencies(CONFIG, fetcher);
    const handler = createDispatchHttpHandler(dependencies, {
      cronSecret: "synthetic-cron-secret",
      cronActorUserId: USER_ID,
      cronWorkspaceId: WORKSPACE_ID,
    });

    const result = await handler(request());

    expect(result.status).toBe(502);
    expect(await result.json()).toEqual({
      job_id: JOB_ID,
      status: "dispatch_failed",
      error_code: "GITHUB_DISPATCH_FAILED",
    });
  });
});
