# Supabase Edge key environment Compatibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `dispatch-job` use Supabase's hosted built-in API-key environment variables while preserving local development fallback behavior.

**Architecture:** Extract environment parsing into a pure shared module. Hosted functions resolve the `default` key from JSON maps; local functions can use the existing singular variables. The Edge Function entrypoint consumes the parsed configuration and keeps all dispatch behavior unchanged.

**Tech Stack:** TypeScript, Deno Edge Function, Vitest, Supabase CLI.

## Global Constraints

- MVP 1 is read-only for Teaching and LMS.
- Do not create LMS Save or Submit actions.
- Do not log credentials, cookies, tokens, or PII.
- Keep Supabase secret keys out of frontend code and repository files.
- Every behavior follows RED → GREEN → REFACTOR → VERIFY.

---

### Task 1: Add failing environment-resolution tests

**Files:**
- Create: `test/edge-environment.test.ts`

**Interfaces:**
- The test will import `loadDispatchEnvironment` and `type EnvironmentReader` from `supabase/functions/_shared/environment.ts`.
- The function will accept an environment reader and return the existing `DispatchAdapterConfig` plus cron configuration.

- [ ] **Step 1: Write the failing tests**

Cover these exact behaviors:

```ts
it("reads the default hosted publishable and secret keys from JSON maps", () => {
  const config = loadDispatchEnvironment(environment({
    SUPABASE_URL: "https://synthetic.supabase.invalid/",
    SUPABASE_PUBLISHABLE_KEYS: JSON.stringify({ default: "hosted-publishable" }),
    SUPABASE_SECRET_KEYS: JSON.stringify({ default: "hosted-secret" }),
    GITHUB_REPOSITORY: "synthetic-owner/synthetic-repo",
    GITHUB_WORKFLOW_ID: "spike0-dispatch-probe.yml",
    GITHUB_DISPATCH_TOKEN: "synthetic-github-token",
    CRON_DISPATCH_SECRET: "synthetic-cron-secret",
    CRON_ACTOR_USER_ID: "00000000-0000-0000-0000-0000000000c1",
    CRON_WORKSPACE_ID: "00000000-0000-0000-0000-0000000000cc",
  }));

  expect(config.publishableKey).toBe("hosted-publishable");
  expect(config.serviceKey).toBe("hosted-secret");
  expect(config.supabaseUrl).toBe("https://synthetic.supabase.invalid");
});

it("falls back to singular local keys", () => {
  const config = loadDispatchEnvironment(environment({
    SUPABASE_URL: "http://127.0.0.1:55021",
    SUPABASE_PUBLISHABLE_KEY: "local-publishable",
    SUPABASE_SECRET_KEY: "local-secret",
    GITHUB_REPOSITORY: "synthetic-owner/synthetic-repo",
    GITHUB_WORKFLOW_ID: "spike0-dispatch-probe.yml",
    GITHUB_DISPATCH_TOKEN: "synthetic-github-token",
    CRON_DISPATCH_SECRET: "synthetic-cron-secret",
    CRON_ACTOR_USER_ID: "00000000-0000-0000-0000-0000000000c1",
    CRON_WORKSPACE_ID: "00000000-0000-0000-0000-0000000000cc",
  }));

  expect(config.publishableKey).toBe("local-publishable");
  expect(config.serviceKey).toBe("local-secret");
});

it("fails closed when a hosted key map has no default key", () => {
  expect(() => loadDispatchEnvironment(environment({
    SUPABASE_URL: "https://synthetic.supabase.invalid",
    SUPABASE_PUBLISHABLE_KEYS: "{}",
    SUPABASE_SECRET_KEYS: JSON.stringify({ default: "hosted-secret" }),
    GITHUB_REPOSITORY: "synthetic-owner/synthetic-repo",
    GITHUB_WORKFLOW_ID: "spike0-dispatch-probe.yml",
    GITHUB_DISPATCH_TOKEN: "synthetic-github-token",
    CRON_DISPATCH_SECRET: "synthetic-cron-secret",
    CRON_ACTOR_USER_ID: "00000000-0000-0000-0000-0000000000c1",
    CRON_WORKSPACE_ID: "00000000-0000-0000-0000-0000000000cc",
  }))).toThrow("DISPATCH_FUNCTION_MISCONFIGURED");
});
```

- [ ] **Step 2: Run the focused test to verify RED**

Run: `npx vitest run test/edge-environment.test.ts`

Expected: FAIL because `supabase/functions/_shared/environment.ts` does not exist yet.

### Task 2: Implement the environment parser

**Files:**
- Create: `supabase/functions/_shared/environment.ts`
- Modify: `supabase/functions/dispatch-job/index.ts:5-42`

**Interfaces:**
- `EnvironmentReader` exposes `get(name: string): string | undefined`.
- `loadDispatchEnvironment(environment: EnvironmentReader): DispatchEnvironment` returns `DispatchAdapterConfig` fields plus `cronSecret`, `cronActorUserId`, and `cronWorkspaceId`.

- [ ] **Step 1: Implement hosted JSON resolution and local fallback**

Use `JSON.parse` only for the plural hosted variables. Accept a value only when the parsed value is a non-array object whose `default` property is a non-empty string. If the plural variable is present but malformed or missing `default`, throw `DISPATCH_FUNCTION_MISCONFIGURED` instead of silently falling back.

- [ ] **Step 2: Replace entrypoint-local environment parsing**

Pass `Deno.env` to `loadDispatchEnvironment`, then use its returned adapter and cron configs to create the existing handler. Do not change request handling or dispatch adapters.

- [ ] **Step 3: Run the focused test to verify GREEN**

Run: `npx vitest run test/edge-environment.test.ts`

Expected: PASS.

### Task 3: Refactor and verify the complete project

**Files:**
- Modify: `.env.example` only if its comments need to document hosted plural variables and local singular fallback.

- [ ] **Step 1: Run all web checks**

Run:

```powershell
npm run lint
npm run typecheck
npm run test
npm run build
npm run verify:no-secrets
npm run verify:no-live-write
```

Expected: every command exits with status 0 and no secret values appear in output.

- [ ] **Step 2: Run Supabase RLS checks**

Run: `npm run test:rls`

Expected: all SQL tests pass.

- [ ] **Step 3: Review the diff**

Run: `git diff --check` and `git diff --stat`.

Confirm only environment parsing, tests, and necessary documentation changed.
