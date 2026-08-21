import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const CI_WORKFLOW_PATH = new URL("../.github/workflows/ci.yml", import.meta.url);
const RUNNER_WORKFLOW_PATH = new URL("../.github/workflows/browser-runner.yml", import.meta.url);
const ENV_EXAMPLE_PATH = new URL("../.env.example", import.meta.url);

function workflowText(path: URL): string {
  return readFileSync(path, "utf8");
}

function actionRefs(workflow: string): string[] {
  return [...workflow.matchAll(/uses:\s+([^\s#]+)/g)].map((match) => match[1]);
}

describe("phase 1 CI workflow contract", () => {
  it("runs for push and pull requests with read-only contents permission", () => {
    const workflow = workflowText(CI_WORKFLOW_PATH);

    expect(workflow).toMatch(/\bon:\s*[\s\S]*?\bpull_request:\s*/);
    expect(workflow).toMatch(/\bon:\s*[\s\S]*?\bpush:\s*/);
    expect(workflow).toMatch(/permissions:\s*[\s\S]*?contents:\s*read/);
  });

  it("reuses the repository's pinned checkout and uv action SHAs", () => {
    const ciWorkflow = workflowText(CI_WORKFLOW_PATH);
    const runnerWorkflow = workflowText(RUNNER_WORKFLOW_PATH);
    const ciRefs = actionRefs(ciWorkflow);
    const runnerRefs = actionRefs(runnerWorkflow);

    const checkoutRef = runnerRefs.find((ref) => ref.startsWith("actions/checkout@"));
    const uvRef = runnerRefs.find((ref) => ref.startsWith("astral-sh/setup-uv@"));

    expect(checkoutRef).toBeDefined();
    expect(uvRef).toBeDefined();
    expect(ciRefs).toContain(checkoutRef);
    expect(ciRefs).toContain(uvRef);
    expect(ciRefs.every((ref) => /@[0-9a-f]{40}$/.test(ref))).toBe(true);
  });

  it("runs the web, privacy, and locked Python gates without artifacts or secrets", () => {
    const workflow = workflowText(CI_WORKFLOW_PATH);

    expect(workflow).toMatch(/\bnpm ci\b/);
    expect(workflow).toMatch(/\bnpm run lint\b/);
    expect(workflow).toMatch(/\bnpm run typecheck\b/);
    expect(workflow).toMatch(/\bnpm run test\b/);
    expect(workflow).toMatch(/\bnpm run build\b/);
    expect(workflow).toMatch(/\bnpm run verify:no-secrets\b/);
    expect(workflow).toMatch(/\bnpm run verify:no-live-write\b/);
    expect(workflow).toMatch(/\buv sync --locked --project apps\/browser-runner\b/);
    expect(workflow).toMatch(/working-directory:\s*apps\/browser-runner[\s\S]*?uv run ruff check \./);
    expect(workflow).toMatch(/working-directory:\s*apps\/browser-runner[\s\S]*?uv run mypy src/);
    expect(workflow).toMatch(/working-directory:\s*apps\/browser-runner[\s\S]*?uv run pytest/);
    expect(workflow).toMatch(/\bnpx supabase db reset\b/);
    expect(workflow).toMatch(/\bnpm run test:rls\b/);
    expect(workflow).not.toMatch(/upload-artifact/);
    expect(workflow).not.toMatch(/secrets\./);
  });

  it("defaults Edge dispatch to the read-only browser runner workflow", () => {
    const environment = workflowText(ENV_EXAMPLE_PATH);

    expect(environment).toContain("GITHUB_WORKFLOW_ID=browser-runner.yml");
  });
});
