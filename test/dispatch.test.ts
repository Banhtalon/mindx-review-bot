import { describe, expect, it, vi } from "vitest";
import {
  handleDispatch,
  type DispatchDependencies,
  type DispatchRequest,
} from "../supabase/functions/_shared/dispatch";

const USER_ID = "00000000-0000-0000-0000-0000000000c1";
const WORKSPACE_ID = "00000000-0000-0000-0000-0000000000cc";
const JOB_ID = "00000000-0000-0000-0000-0000000000d1";
const CONFIG = {
  cronSecret: "synthetic-cron-secret",
  cronActorUserId: USER_ID,
  cronWorkspaceId: WORKSPACE_ID,
};

function request(overrides: Partial<DispatchRequest> = {}): DispatchRequest {
  return {
    authorization: "Bearer synthetic-access-token",
    workspaceId: WORKSPACE_ID,
    type: "sync_teaching",
    idempotencyKey: "synthetic-dispatch-001",
    payload: {},
    ...overrides,
  };
}

function dependencyHarness(
  overrides: Partial<DispatchDependencies> = {},
): DispatchDependencies {
  return {
    authenticateUser: vi.fn().mockResolvedValue({ userId: USER_ID }),
    authorizeOwner: vi.fn().mockResolvedValue(true),
    enqueueJob: vi.fn().mockResolvedValue({
      jobId: JOB_ID,
      workspaceId: WORKSPACE_ID,
      type: "sync_teaching",
      status: "queued",
      idempotencyKey: "synthetic-dispatch-001",
      payload: {},
      created: true,
    }),
    claimDispatch: vi.fn().mockResolvedValue({ claimed: true, status: "dispatching" }),
    finishDispatch: vi.fn().mockResolvedValue({ status: "dispatched" }),
    dispatchGitHub: vi.fn().mockResolvedValue({ status: 204 }),
    ...overrides,
  };
}

describe("dispatch idempotency state machine", () => {
  it("rejects a request without JWT or Cron authentication", async () => {
    const result = await handleDispatch(
      request({ authorization: undefined }),
      dependencyHarness(),
      CONFIG,
    );

    expect(result).toEqual({ status: 401, body: { error_code: "AUTH_REQUIRED" } });
  });

  it("rejects an invalid Cron secret", async () => {
    const result = await handleDispatch(
      request({ authorization: undefined, cronSecret: "wrong" }),
      dependencyHarness(),
      CONFIG,
    );

    expect(result).toEqual({ status: 403, body: { error_code: "CRON_FORBIDDEN" } });
  });

  it("requires an owner for manual dispatch", async () => {
    const dependencies = dependencyHarness({
      authorizeOwner: vi.fn().mockResolvedValue(false),
    });

    const result = await handleDispatch(request(), dependencies, CONFIG);

    expect(result).toEqual({ status: 403, body: { error_code: "OWNER_REQUIRED" } });
  });

  it("rejects unsupported job types and secret-bearing payload keys", async () => {
    const dependencies = dependencyHarness();

    const invalidType = await handleDispatch(
      request({ type: "unsupported" }),
      dependencies,
      CONFIG,
    );
    const invalidPayload = await handleDispatch(
      request({ payload: { password: "synthetic" } }),
      dependencies,
      CONFIG,
    );

    expect(invalidType).toEqual({ status: 400, body: { error_code: "INVALID_JOB_TYPE" } });
    expect(invalidPayload).toEqual({
      status: 400,
      body: { error_code: "INVALID_JOB_PAYLOAD" },
    });
  });

  it("dispatches a newly claimed job and marks it dispatched", async () => {
    const dependencies = dependencyHarness();

    const result = await handleDispatch(request(), dependencies, CONFIG);

    expect(result).toEqual({
      status: 202,
      body: { job_id: JOB_ID, status: "dispatched", created: true },
    });
    expect(dependencies.claimDispatch).toHaveBeenCalledWith(JOB_ID);
    expect(dependencies.dispatchGitHub).toHaveBeenCalledWith({
      jobId: JOB_ID,
      jobType: "sync_teaching",
    });
    expect(dependencies.finishDispatch).toHaveBeenCalledWith(JOB_ID, "dispatched");
  });

  it("returns an existing dispatched job without dispatching twice", async () => {
    const dependencies = dependencyHarness({
      enqueueJob: vi.fn().mockResolvedValue({
        jobId: JOB_ID,
        workspaceId: WORKSPACE_ID,
        type: "sync_teaching",
        status: "dispatched",
        idempotencyKey: "synthetic-dispatch-001",
        payload: {},
        created: false,
      }),
      claimDispatch: vi.fn().mockResolvedValue({ claimed: false, status: "dispatched" }),
    });

    const result = await handleDispatch(request(), dependencies, CONFIG);

    expect(result).toEqual({
      status: 200,
      body: { job_id: JOB_ID, status: "dispatched", created: false },
    });
    expect(dependencies.dispatchGitHub).not.toHaveBeenCalled();
  });

  it("returns conflict when an idempotency key has different payload", async () => {
    const dependencies = dependencyHarness({
      enqueueJob: vi.fn().mockRejectedValue({ code: "IDEMPOTENCY_KEY_REUSED" }),
    });

    const result = await handleDispatch(request(), dependencies, CONFIG);

    expect(result).toEqual({
      status: 409,
      body: { error_code: "IDEMPOTENCY_KEY_REUSED" },
    });
  });

  it("does not call GitHub when another request owns the dispatch claim", async () => {
    const dependencies = dependencyHarness({
      claimDispatch: vi.fn().mockResolvedValue({ claimed: false, status: "dispatching" }),
    });

    const result = await handleDispatch(request(), dependencies, CONFIG);

    expect(result).toEqual({
      status: 202,
      body: { job_id: JOB_ID, status: "dispatching", created: true },
    });
    expect(dependencies.dispatchGitHub).not.toHaveBeenCalled();
  });

  it("marks dispatch_failed and returns a safe error when GitHub rejects the request", async () => {
    const dependencies = dependencyHarness({
      dispatchGitHub: vi.fn().mockResolvedValue({ status: 500 }),
    });

    const result = await handleDispatch(request(), dependencies, CONFIG);

    expect(result).toEqual({
      status: 502,
      body: { job_id: JOB_ID, status: "dispatch_failed", error_code: "GITHUB_DISPATCH_FAILED" },
    });
    expect(dependencies.finishDispatch).toHaveBeenCalledWith(JOB_ID, "dispatch_failed");
  });
});
