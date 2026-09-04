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
    expect(workflow).toMatch(/phase2_hosted:[\s\S]*?type:\s*boolean[\s\S]*?default:\s*false/);
  });

  it("keeps the probe read-only and deduplicated", () => {
    const workflow = workflowText();

    expect(workflow).toMatch(/contents:\s*read/);
    expect(workflow).toMatch(/cancel-in-progress:\s*false/);
    expect(workflow).toMatch(/group:\s*mindx-spike0-\$\{\{\s*inputs\.job_id\s*\}\}/);
    expect(workflow).toMatch(/timeout-minutes:\s*15/);
    expect(workflow).not.toMatch(/\b(?:save|submit)\b/i);
    const uses = [...workflow.matchAll(/uses:\s*([^\s#]+)/g)].map((match) => match[1]);
    expect(uses).toEqual(["./.github/workflows/phase2-hosted-verify.yml"]);
    expect(workflow).toContain("if: inputs.phase2_hosted");
    expect(workflow).toContain("needs: validate");
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
});
