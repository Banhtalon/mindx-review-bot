import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

import {
  buildCronDispatchRequest,
  dispatchCronJob,
} from "../scripts/cron_dispatch.mjs";

const WORKSPACE_ID = "00000000-0000-4000-8000-0000000000cc";
const JOB_ID = "00000000-0000-4000-8000-0000000000d1";
const ENVIRONMENT = {
  SUPABASE_URL: "https://synthetic.supabase.co",
  CRON_DISPATCH_SECRET: "synthetic-cron-secret",
  CRON_WORKSPACE_ID: WORKSPACE_ID,
  JOB_TYPE: "read_lms_pending",
};

describe("scheduled read-only dispatch contract", () => {
  it("builds a deterministic empty-payload Cron request", () => {
    const request = buildCronDispatchRequest({
      ...ENVIRONMENT,
      now: new Date("2026-08-21T15:07:03.000Z"),
    });

    expect(request.url).toBe("https://synthetic.supabase.co/functions/v1/dispatch-job");
    expect(request.headers).toEqual({
      "content-type": "application/json",
      "x-cron-dispatch-secret": "synthetic-cron-secret",
    });
    expect(JSON.parse(request.body)).toEqual({
      workspace_id: WORKSPACE_ID,
      type: "read_lms_pending",
      idempotency_key: `read_lms_pending:${WORKSPACE_ID}:202608211507:202608211637`,
      payload: {},
    });
  });

  it("uses a distinct time window for the scheduled LMS retry", () => {
    const firstWindow = JSON.parse(buildCronDispatchRequest({
      ...ENVIRONMENT,
      now: new Date("2026-08-21T15:07:00.000Z"),
    }).body).idempotency_key;
    const retryWindow = JSON.parse(buildCronDispatchRequest({
      ...ENVIRONMENT,
      now: new Date("2026-08-21T16:37:00.000Z"),
    }).body).idempotency_key;

    expect(firstWindow).toBe(
      `read_lms_pending:${WORKSPACE_ID}:202608211507:202608211637`,
    );
    expect(retryWindow).toBe(
      `read_lms_pending:${WORKSPACE_ID}:202608211637:202608221507`,
    );
    expect(retryWindow).not.toBe(firstWindow);
  });

  it("accepts only a safe job UUID and status from the dispatch response", async () => {
    const calls: Array<{ url: string; init: RequestInit }> = [];
    const result = await dispatchCronJob({
      environment: ENVIRONMENT,
      now: new Date("2026-08-21T22:33:00.000Z"),
      fetcher: async (url, init) => {
        calls.push({ url: String(url), init: init ?? {} });
        return new Response(JSON.stringify({ job_id: JOB_ID, status: "dispatched" }), {
          status: 202,
          headers: { "content-type": "application/json" },
        });
      },
    });

    expect(result).toEqual({ jobId: JOB_ID, status: "dispatched" });
    expect(calls).toHaveLength(1);
    expect(calls[0].init.body).not.toContain("synthetic-cron-secret");
    expect(calls[0].init.body).toContain('"payload":{}');
  });

  it("fails closed when a required Cron variable is missing", async () => {
    const environment = { ...ENVIRONMENT };
    delete (environment as Partial<typeof ENVIRONMENT>).CRON_DISPATCH_SECRET;

    await expect(dispatchCronJob({ environment })).rejects.toMatchObject({
      code: "CRON_CONFIG_INVALID",
    });
  });

  it("pins the three UTC schedules and read-only workflow permissions", () => {
    const workflow = readFileSync(
      new URL("../.github/workflows/cron-dispatch.yml", import.meta.url),
      "utf8",
    );

    expect(workflow).toContain('cron: "33 22 * * *"');
    expect(workflow).toContain('cron: "07 15 * * *"');
    expect(workflow).toContain('cron: "37 16 * * *"');
    expect(workflow).toMatch(/permissions:[\s\S]*contents:\s*read/);
    expect(workflow).toContain("cancel-in-progress: false");
    expect(workflow).toContain("CRON_DISPATCH_SECRET");
    expect(workflow).toContain("CRON_WORKSPACE_ID");
    expect(workflow).toContain("node scripts/cron_dispatch.mjs");
    expect(workflow).not.toMatch(/cleanup|generate|save|submit/i);
  });
});
