import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const WORKFLOW_PATH = new URL(
  "../.github/workflows/spike0-dispatch-probe.yml",
  import.meta.url,
);

function workflowText(): string {
  return readFileSync(WORKFLOW_PATH, "utf8");
}

describe("synthetic GitHub dispatch workflow contract", () => {
  it("accepts only the allowed manual-dispatch inputs", () => {
    const workflow = workflowText();

    expect(workflow).toMatch(/workflow_dispatch:/);
    expect(workflow).toMatch(/job_id:\s*[\s\S]*?required:\s*true[\s\S]*?type:\s*string/);
    expect(workflow).toMatch(/job_type:\s*[\s\S]*?required:\s*true[\s\S]*?type:\s*choice/);
    expect(workflow).toMatch(/options:\s*\n\s*-\s*sync_teaching\s*\n\s*-\s*read_lms_pending/);
  });

  it("keeps the original validation job read-only and deduplicated", () => {
    const workflow = workflowText();
    const jobs = workflow.split("jobs:", 2)[1] ?? "";
    const validate = jobs.split("\n  runtime:", 1)[0];

    expect(workflow).toMatch(/contents:\s*read/);
    expect(workflow).toMatch(/cancel-in-progress:\s*false/);
    expect(workflow).toMatch(/group:\s*mindx-spike0-\$\{\{\s*inputs\.job_id\s*\}\}/);
    expect(validate).toMatch(/timeout-minutes:\s*15/);
    expect(validate).not.toMatch(/\b(?:save|submit)\b/i);
    expect(validate).not.toMatch(/uses:\s*[^\n]+/);
  });

  it("validates a UUID job id and rejects unapproved job types in the shell", () => {
    const workflow = workflowText();

    expect(workflow).toMatch(/JOB_ID:\s*\$\{\{\s*inputs\.job_id\s*\}\}/);
    expect(workflow).toMatch(/JOB_TYPE:\s*\$\{\{\s*inputs\.job_type\s*\}\}/);
    expect(workflow).toMatch(/fullmatch\(uuid_pattern/);
    expect(workflow).toMatch(/r"\[0-9a-f\]\{8\}/);
    expect(workflow).toMatch(/sync_teaching/);
    expect(workflow).toMatch(/read_lms_pending/);
    expect(workflow).toMatch(/sys\.exit/);
  });

  it("adds a fixed-job runtime behind repository, main, attempt, and approval guards", () => {
    const workflow = workflowText();
    const runtime = workflow.split("\n  runtime:", 2)[1] ?? "";

    expect(workflow).toMatch(/run-name:.*\$\{\{\s*inputs\.job_id\s*\}\}/);
    expect(runtime).toMatch(/timeout-minutes:\s*20/);
    expect(runtime).toMatch(/github\.repository\s*==\s*'Banhtalon\/mindx-review-bot'/);
    expect(runtime).toMatch(/github\.ref\s*==\s*'refs\/heads\/main'/);
    expect(runtime).toMatch(/github\.run_attempt\s*==\s*1/);
    expect(runtime).toMatch(/MINDX_API_CHAIN_PILOT_APPROVAL_SHA\s*==\s*github\.sha/);
    expect(runtime).toMatch(/spike0-dispatch-probe\.yml/);
    expect([...runtime.matchAll(/uses:\s*([^\s#]+)/g)].map((match) => match[1])).toEqual(
      expect.arrayContaining([expect.stringMatching(/@(?:[0-9a-f]{40})$/)]),
    );
  });
});
