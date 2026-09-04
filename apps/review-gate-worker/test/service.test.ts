import { describe, expect, it } from "vitest";
import { evaluateReviewGateService } from "../src/service.ts";
import { handleWebhookRequest, parseAndValidateTrustedEnv, WorkerEnv } from "../src/index.ts";
import { PILOT_TRUSTED_CONFIG } from "../src/types.ts";
import { EvaluationGuard, InMemoryEvaluationGuard } from "../src/guard.ts";
import { createHmac, generateKeyPairSync } from "node:crypto";

const CURRENT_HEAD_SHA = "09297ea56133d10d5f40c429e78c7195a8aac61f";
const OLD_HEAD_SHA = "374b80f6e411ef9d89be3a7bbf656b50b7da5d8e";
const REPO = "Banhtalon/mindx-review-bot";

const mockPr = {
  number: 6,
  title: "chore: migrate agent workflow",
  body: "Some PR description without control issue link",
  state: "open",
  head: { sha: CURRENT_HEAD_SHA, ref: "chore/agent-workflow-migration" },
  base: { sha: "main-sha", ref: "main" },
};

const mockIssue7 = {
  number: 7,
  title: "[agent] Control Issue",
  state: "open",
  labels: [{ name: "ready-for-review" }],
  body: `
<!-- AGENT_CONTROL_BLOCK_V1 -->
state: ready-for-review
scope_revision: 3
fix_reentries: 0
owner_scope_reset: https://github.com/Banhtalon/mindx-review-bot/issues/7#issuecomment-5534707230
<!-- /AGENT_CONTROL_BLOCK_V1 -->
  `,
  user: { login: "Banhtalon", id: 105797112 },
};

const mockScopeResetComment = {
  id: 5534707230,
  user: { login: "Banhtalon", id: 105797112 },
  author_association: "OWNER",
  issue_url: "https://api.github.com/repos/Banhtalon/mindx-review-bot/issues/7",
  html_url: "https://github.com/Banhtalon/mindx-review-bot/issues/7#issuecomment-5534707230",
  body: `
<!-- OWNER_SCOPE_RESET_V1 -->
old_scope_revision: 2
new_scope_revision: 3
reason: Final Terra review found material trust-boundary weaknesses
material_scope_change: Redesign review authority with trusted GitHub App
owner_decision: APPROVED
approved_by: Banhtalon
<!-- /OWNER_SCOPE_RESET_V1 -->
  `,
  created_at: "2026-09-04T01:00:00Z",
};

interface CapturedCheckRun {
  name: string;
  head_sha: string;
  status: string;
  conclusion?: string;
  method?: string;
  url?: string;
  external_id?: string;
}

function createMockFetch(
  comments: unknown[] = [],
  capturedCheckRuns: CapturedCheckRun[] = [],
  existingCheckRun: unknown = null,
  issueOverride: unknown = null,
  commentsError: Error | null = null,
  commentOverrides: Map<string, unknown> = new Map()
) {
  return async (url: RequestInfo | URL, init?: RequestInit) => {
    const urlStr = String(url);

    if (urlStr.includes("/pulls/6")) {
      return new Response(JSON.stringify(mockPr), { status: 200 });
    }

    if (urlStr.includes("/issues/7/comments")) {
      return new Response(JSON.stringify([]), { status: 200 });
    }

    if (urlStr.includes("/issues/7")) {
      return new Response(JSON.stringify(issueOverride || mockIssue7), { status: 200 });
    }

    if (urlStr.includes("/issues/comments/")) {
      const match = /\/comments\/(\d+)/.exec(urlStr);
      if (match) {
        const cId = match[1];
        if (commentOverrides.has(cId)) {
          const val = commentOverrides.get(cId);
          if (val instanceof Error) throw val;
          return new Response(JSON.stringify(val), { status: 200 });
        }
      }
      return new Response(JSON.stringify(mockScopeResetComment), { status: 200 });
    }

    if (urlStr.includes("/issues/6/comments")) {
      if (commentsError) {
        throw commentsError;
      }
      return new Response(JSON.stringify(comments), { status: 200 });
    }

    if (urlStr.includes("/commits/") && urlStr.includes("/check-runs")) {
      if (existingCheckRun) {
        return new Response(JSON.stringify({ total_count: 1, check_runs: [existingCheckRun] }), { status: 200 });
      }
      return new Response(JSON.stringify({ total_count: 0, check_runs: [] }), { status: 200 });
    }

    if (urlStr.includes("/check-runs")) {
      const body = JSON.parse(String(init?.body));
      capturedCheckRuns.push({ ...body, method: init?.method, url: urlStr });
      const idMatch = /\/check-runs\/(\d+)/.exec(urlStr);
      const returnedId = idMatch ? Number(idMatch[1]) : 12345;
      return new Response(JSON.stringify({ id: returnedId, url: `https://api.github.com/repos/Banhtalon/mindx-review-bot/check-runs/${returnedId}` }), { status: 201 });
    }

    if (urlStr.includes("/access_tokens")) {
      return new Response(JSON.stringify({ token: "mock-installation-token" }), { status: 201 });
    }

    return new Response(JSON.stringify({ error: "Not Found" }), { status: 404 });
  };
}

describe("Review Gate Service & Webhook", () => {
  it("passes review gate and emits in_progress then successful check run on exact current head SHA", async () => {
    const validOwnerComment = {
      id: 999,
      user: { login: "Banhtalon", id: 105797112 },
      author_association: "OWNER",
      body: `
<!-- TERRA_REVIEW_ATTESTATION_V1 -->
reviewer_model: terra-xhigh
head_sha: ${CURRENT_HEAD_SHA}
pr_number: 6
control_issue: 7
scope_revision: 3
verdict: RECOMMEND_PASS
p0: 0
p1: 0
material_findings_resolved: true
reviewed_at_utc: 2026-09-04T02:00:00Z
<!-- /TERRA_REVIEW_ATTESTATION_V1 -->
      `,
      created_at: "2026-09-04T02:00:00Z",
    };

    const capturedCheckRuns: CapturedCheckRun[] = [];
    const mockFetch = createMockFetch([validOwnerComment], capturedCheckRuns);

    const result = await evaluateReviewGateService({
      repo: REPO,
      prNumber: 6,
      token: "mock-token",
      trustedConfig: PILOT_TRUSTED_CONFIG,
      fetchFn: mockFetch as unknown as typeof fetch,
    });

    expect(result.valid).toBe(true);
    expect(result.headSha).toBe(CURRENT_HEAD_SHA);
    // Finding 4: Must first move check run to in_progress, then completed success
    expect(capturedCheckRuns).toHaveLength(2);
    expect(capturedCheckRuns[0].status).toBe("in_progress");
    expect(capturedCheckRuns[0].head_sha).toBe(CURRENT_HEAD_SHA);
    expect(capturedCheckRuns[1].status).toBe("completed");
    expect(capturedCheckRuns[1].conclusion).toBe("success");
  });

  it("fails closed without fallback when trustedConfig is omitted (Finding 1)", async () => {
    const capturedCheckRuns: CapturedCheckRun[] = [];
    const mockFetch = createMockFetch([], capturedCheckRuns);

    const result = await evaluateReviewGateService({
      repo: REPO,
      prNumber: 6,
      token: "mock-token",
      // trustedConfig omitted!
      fetchFn: mockFetch as unknown as typeof fetch,
    });

    expect(result.valid).toBe(false);
    expect(result.validationResult.reason).toBe("MISSING_TRUSTED_CONFIG");
    expect(capturedCheckRuns).toHaveLength(2);
    expect(capturedCheckRuns[0].status).toBe("in_progress");
    expect(capturedCheckRuns[1].status).toBe("completed");
    expect(capturedCheckRuns[1].conclusion).toBe("failure");
  });

  it("fails closed when attestation is for an older head SHA (stale head)", async () => {
    const staleOwnerComment = {
      id: 999,
      user: { login: "Banhtalon", id: 105797112 },
      author_association: "OWNER",
      body: `
<!-- TERRA_REVIEW_ATTESTATION_V1 -->
reviewer_model: terra-xhigh
head_sha: ${OLD_HEAD_SHA}
pr_number: 6
control_issue: 7
scope_revision: 3
verdict: RECOMMEND_PASS
p0: 0
p1: 0
material_findings_resolved: true
reviewed_at_utc: 2026-09-04T02:00:00Z
<!-- /TERRA_REVIEW_ATTESTATION_V1 -->
      `,
      created_at: "2026-09-04T02:00:00Z",
    };

    const capturedCheckRuns: CapturedCheckRun[] = [];
    const mockFetch = createMockFetch([staleOwnerComment], capturedCheckRuns);

    const result = await evaluateReviewGateService({
      repo: REPO,
      prNumber: 6,
      token: "mock-token",
      trustedConfig: PILOT_TRUSTED_CONFIG,
      fetchFn: mockFetch as unknown as typeof fetch,
    });

    expect(result.valid).toBe(false);
    expect(result.validationResult.reason).toBe("STALE_HEAD_SHA");
    expect(capturedCheckRuns).toHaveLength(2);
    expect(capturedCheckRuns[0].status).toBe("in_progress");
    expect(capturedCheckRuns[1].conclusion).toBe("failure");
  });

  it("fails closed when no attestation exists", async () => {
    const capturedCheckRuns: CapturedCheckRun[] = [];
    const mockFetch = createMockFetch([], capturedCheckRuns);

    const result = await evaluateReviewGateService({
      repo: REPO,
      prNumber: 6,
      token: "mock-token",
      trustedConfig: PILOT_TRUSTED_CONFIG,
      fetchFn: mockFetch as unknown as typeof fetch,
    });

    expect(result.valid).toBe(false);
    expect(result.validationResult.reason).toBe("NO_ATTESTATION_FOUND");
    expect(capturedCheckRuns).toHaveLength(2);
    expect(capturedCheckRuns[0].status).toBe("in_progress");
    expect(capturedCheckRuns[1].conclusion).toBe("failure");
  });

  it("fails closed when trustedConfig is mismatched with incoming PR", async () => {
    const capturedCheckRuns: CapturedCheckRun[] = [];
    const mockFetch = createMockFetch([], capturedCheckRuns);

    const result = await evaluateReviewGateService({
      repo: "Banhtalon/other-repo",
      prNumber: 6,
      token: "mock-token",
      trustedConfig: PILOT_TRUSTED_CONFIG,
      fetchFn: mockFetch as unknown as typeof fetch,
    });

    expect(result.valid).toBe(false);
    expect(result.validationResult.reason).toBe("TRUSTED_CONFIG_MISMATCH");
    expect(capturedCheckRuns).toHaveLength(2);
    expect(capturedCheckRuns[1].conclusion).toBe("failure");
  });

  it("fails closed when trustedConfig is malformed", async () => {
    const capturedCheckRuns: CapturedCheckRun[] = [];
    const mockFetch = createMockFetch([], capturedCheckRuns);

    const result = await evaluateReviewGateService({
      repo: REPO,
      prNumber: 6,
      token: "mock-token",
      trustedConfig: { repo: "", prNumber: 0, controlIssue: 0, scopeRevision: 0 },
      fetchFn: mockFetch as unknown as typeof fetch,
    });

    expect(result.valid).toBe(false);
    expect(result.validationResult.reason).toBe("MALFORMED_TRUSTED_CONFIG");
    expect(capturedCheckRuns).toHaveLength(2);
    expect(capturedCheckRuns[1].conclusion).toBe("failure");
  });

  it("fails closed when control issue is closed (Finding 7)", async () => {
    const closedIssue7 = {
      ...mockIssue7,
      state: "closed",
    };

    const capturedCheckRuns: CapturedCheckRun[] = [];
    const mockFetch = createMockFetch([], capturedCheckRuns, null, closedIssue7);

    const result = await evaluateReviewGateService({
      repo: REPO,
      prNumber: 6,
      token: "mock-token",
      trustedConfig: PILOT_TRUSTED_CONFIG,
      fetchFn: mockFetch as unknown as typeof fetch,
    });

    expect(result.valid).toBe(false);
    expect(result.validationResult.reason).toBe("CONTROL_ISSUE_CLOSED");
    expect(capturedCheckRuns).toHaveLength(2);
    expect(capturedCheckRuns[1].conclusion).toBe("failure");
  });

  it("binds scope-reset authority exclusively to parsed control block (Finding 2)", async () => {
    // Distraction in issue body text outside the block
    const issueWithDistraction = {
      ...mockIssue7,
      body: `
Distraction text with fake link:
owner_scope_reset: https://github.com/Banhtalon/mindx-review-bot/issues/7#issuecomment-1111111111

<!-- AGENT_CONTROL_BLOCK_V1 -->
state: ready-for-review
scope_revision: 3
fix_reentries: 0
owner_scope_reset: https://github.com/Banhtalon/mindx-review-bot/issues/7#issuecomment-5534707230
<!-- /AGENT_CONTROL_BLOCK_V1 -->
      `,
    };

    const validOwnerComment = {
      id: 999,
      user: { login: "Banhtalon", id: 105797112 },
      author_association: "OWNER",
      body: `
<!-- TERRA_REVIEW_ATTESTATION_V1 -->
reviewer_model: terra-xhigh
head_sha: ${CURRENT_HEAD_SHA}
pr_number: 6
control_issue: 7
scope_revision: 3
verdict: RECOMMEND_PASS
p0: 0
p1: 0
material_findings_resolved: true
reviewed_at_utc: 2026-09-04T02:00:00Z
<!-- /TERRA_REVIEW_ATTESTATION_V1 -->
      `,
      created_at: "2026-09-04T02:00:00Z",
    };

    const capturedCheckRuns: CapturedCheckRun[] = [];
    const mockFetch = createMockFetch([validOwnerComment], capturedCheckRuns, null, issueWithDistraction);

    const result = await evaluateReviewGateService({
      repo: REPO,
      prNumber: 6,
      token: "mock-token",
      trustedConfig: PILOT_TRUSTED_CONFIG,
      fetchFn: mockFetch as unknown as typeof fetch,
    });

    // Validates that it correctly used 5534707230 from AGENT_CONTROL_BLOCK_V1 rather than 1111111111
    expect(result.valid).toBe(true);
    expect(capturedCheckRuns[1].conclusion).toBe("success");
  });

  it("reuses and updates (PATCH) existing check run on same head SHA", async () => {
    const existingCheckRun = {
      id: 88888,
      url: "https://api.github.com/repos/Banhtalon/mindx-review-bot/check-runs/88888",
      name: "terra-review-gate",
      head_sha: CURRENT_HEAD_SHA,
      status: "completed",
      conclusion: "failure",
    };

    const capturedCheckRuns: CapturedCheckRun[] = [];
    const mockFetch = createMockFetch([], capturedCheckRuns, existingCheckRun);

    const result = await evaluateReviewGateService({
      repo: REPO,
      prNumber: 6,
      token: "mock-token",
      trustedConfig: PILOT_TRUSTED_CONFIG,
      fetchFn: mockFetch as unknown as typeof fetch,
    });

    expect(result.valid).toBe(false);
    expect(capturedCheckRuns).toHaveLength(2);
    expect(capturedCheckRuns[0].method).toBe("PATCH");
    expect(capturedCheckRuns[0].url).toContain("/check-runs/88888");
    expect(capturedCheckRuns[1].method).toBe("PATCH");
    expect(capturedCheckRuns[1].url).toContain("/check-runs/88888");
  });

  it("handles PAGINATION_LIMIT_EXCEEDED by emitting failure check run", async () => {
    const pagErr = new Error("PAGINATION_LIMIT_EXCEEDED: Exceeded max pages");
    (pagErr as unknown as { code: string }).code = "PAGINATION_LIMIT_EXCEEDED";

    const capturedCheckRuns: CapturedCheckRun[] = [];
    const mockFetch = createMockFetch([], capturedCheckRuns, null, null, pagErr);

    const result = await evaluateReviewGateService({
      repo: REPO,
      prNumber: 6,
      token: "mock-token",
      trustedConfig: PILOT_TRUSTED_CONFIG,
      fetchFn: mockFetch as unknown as typeof fetch,
    });

    expect(result.valid).toBe(false);
    expect(result.validationResult.reason).toBe("PAGINATION_LIMIT_EXCEEDED");
    expect(capturedCheckRuns).toHaveLength(2);
    expect(capturedCheckRuns[0].status).toBe("in_progress");
    expect(capturedCheckRuns[1].conclusion).toBe("failure");
  });

  it("prevent stale out-of-order success overwrite using evaluation guard (Finding 5)", async () => {
    const guard = new InMemoryEvaluationGuard();

    const passComment = {
      id: 999,
      user: { login: "Banhtalon", id: 105797112 },
      author_association: "OWNER",
      body: `
<!-- TERRA_REVIEW_ATTESTATION_V1 -->
reviewer_model: terra-xhigh
head_sha: ${CURRENT_HEAD_SHA}
pr_number: 6
control_issue: 7
scope_revision: 3
verdict: RECOMMEND_PASS
p0: 0
p1: 0
material_findings_resolved: true
reviewed_at_utc: 2026-09-04T02:00:00Z
<!-- /TERRA_REVIEW_ATTESTATION_V1 -->
      `,
      created_at: "2026-09-04T02:00:00Z",
    };

    const failComment = {
      id: 1000,
      user: { login: "Banhtalon", id: 105797112 },
      author_association: "OWNER",
      body: `
<!-- TERRA_REVIEW_ATTESTATION_V1 -->
reviewer_model: terra-xhigh
head_sha: ${CURRENT_HEAD_SHA}
pr_number: 6
control_issue: 7
scope_revision: 3
verdict: NEEDS_FIX
p0: 1
p1: 0
material_findings_resolved: false
reviewed_at_utc: 2026-09-04T02:05:00Z
<!-- /TERRA_REVIEW_ATTESTATION_V1 -->
      `,
      created_at: "2026-09-04T02:05:00Z",
    };

    const capturedCheckRuns: CapturedCheckRun[] = [];

    // Simulate concurrent runs:
    // Run 1 starts with passComment (acquires version 1)
    // Run 2 starts with failComment (acquires version 2)
    // Run 2 completes first
    // Run 1 finishes later
    const fetchRun1 = createMockFetch([passComment], capturedCheckRuns);
    const fetchRun2 = createMockFetch([failComment], capturedCheckRuns);

    // Simulate Run 2 completing first
    const result2 = await evaluateReviewGateService({
      repo: REPO,
      prNumber: 6,
      token: "mock-token",
      trustedConfig: PILOT_TRUSTED_CONFIG,
      guard,
      fetchFn: fetchRun2 as unknown as typeof fetch,
    });
    expect(result2.valid).toBe(false);
    expect(result2.validationResult.reason).toBe("VERDICT_NEEDS_FIX");

    const runsCountAfterRun2 = capturedCheckRuns.length;
    const lastCheckAfterRun2 = capturedCheckRuns[runsCountAfterRun2 - 1];
    expect(lastCheckAfterRun2.conclusion).toBe("failure");

    // Now Run 1 finishes. Since guard acquired a newer version (2), Run 1 claim is stale!
    // We simulate a claim acquired earlier
    const staleClaim = {
      repo: REPO,
      prNumber: 6,
      version: 1,
      token: "old-token",
      createdAt: Date.now() - 1000,
    };
    expect(await guard.isLatestVersion(staleClaim)).toBe(false);

    // If Run 1 runs with its earlier claim, it detects stale and aborts
    const mockGuardWithStaleClaim: EvaluationGuard = {
      acquireVersion: async () => staleClaim,
      isLatestVersion: async (c) => guard.isLatestVersion(c),
    };

    const result1 = await evaluateReviewGateService({
      repo: REPO,
      prNumber: 6,
      token: "mock-token",
      trustedConfig: PILOT_TRUSTED_CONFIG,
      guard: mockGuardWithStaleClaim,
      fetchFn: fetchRun1 as unknown as typeof fetch,
    });

    expect(result1.valid).toBe(false);
    expect(result1.validationResult.reason).toBe("STALE_EVALUATION_ABORTED");

    // Confirm that Run 1 DID NOT overwrite the failure with success
    const finalRuns = capturedCheckRuns;
    const lastCheckRun = finalRuns[finalRuns.length - 1];
    expect(lastCheckRun.conclusion).not.toBe("success");
  });

  describe("Webhook Handler End-to-End", () => {
    const { privateKey } = generateKeyPairSync("rsa", {
      modulusLength: 2048,
      publicKeyEncoding: { type: "spki", format: "pem" },
      privateKeyEncoding: { type: "pkcs8", format: "pem" },
    });

    const env: WorkerEnv = {
      GITHUB_APP_ID: "12345",
      GITHUB_PRIVATE_KEY: privateKey,
      GITHUB_WEBHOOK_SECRET: "my-webhook-secret",
      TRUSTED_REPO: REPO,
      TRUSTED_PR_NUMBER: "6",
      TRUSTED_CONTROL_ISSUE: "7",
      TRUSTED_SCOPE_REVISION: "3",
    };

    it("rejects webhook request with invalid signature (401)", async () => {
      const res = await handleWebhookRequest(
        {
          method: "POST",
          headers: {
            "x-hub-signature-256": "sha256=invalid-signature",
            "x-github-event": "pull_request",
          },
          text: async () => JSON.stringify({ action: "opened" }),
        },
        env
      );

      expect(res.status).toBe(401);
      expect(JSON.parse(res.body).error).toContain("Invalid webhook signature");
    });

    it("rejects missing or malformed trusted deployment environment variables", async () => {
      expect(parseAndValidateTrustedEnv({ ...env, TRUSTED_REPO: "" }).valid).toBe(false);
      expect(parseAndValidateTrustedEnv({ ...env, TRUSTED_PR_NUMBER: "6.0" }).valid).toBe(false);
      expect(parseAndValidateTrustedEnv({ ...env, TRUSTED_PR_NUMBER: "+6" }).valid).toBe(false);
      expect(parseAndValidateTrustedEnv({ ...env, TRUSTED_PR_NUMBER: " 6 " }).valid).toBe(false);
      expect(parseAndValidateTrustedEnv({ ...env, TRUSTED_CONTROL_ISSUE: "invalid" }).valid).toBe(false);
      expect(parseAndValidateTrustedEnv({ ...env, TRUSTED_SCOPE_REVISION: "-1" }).valid).toBe(false);
      expect(parseAndValidateTrustedEnv({ ...env, TRUSTED_REPO: "Wrong/repo" }).valid).toBe(false);
    });

    it("ignores non-relevant events (200 ignored)", async () => {
      const payload = JSON.stringify({ action: "labeled", pull_request: { number: 6 } });
      const hmac = createHmac("sha256", env.GITHUB_WEBHOOK_SECRET).update(payload).digest("hex");

      const res = await handleWebhookRequest(
        {
          method: "POST",
          headers: {
            "x-hub-signature-256": `sha256=${hmac}`,
            "x-github-event": "pull_request",
          },
          text: async () => payload,
        },
        env
      );

      expect(res.status).toBe(200);
      expect(JSON.parse(res.body).ignored).toBe(true);
    });

    it("processes pull_request synchronize event with valid signature", async () => {
      const payload = JSON.stringify({
        action: "synchronize",
        pull_request: { number: 6 },
        repository: { full_name: REPO },
        installation: { id: 777 },
      });
      const hmac = createHmac("sha256", env.GITHUB_WEBHOOK_SECRET).update(payload).digest("hex");

      const capturedCheckRuns: CapturedCheckRun[] = [];
      const mockFetch = createMockFetch([], capturedCheckRuns);

      const res = await handleWebhookRequest(
        {
          method: "POST",
          headers: {
            "x-hub-signature-256": `sha256=${hmac}`,
            "x-github-event": "pull_request",
          },
          text: async () => payload,
        },
        env,
        mockFetch as unknown as typeof fetch
      );

      expect(res.status).toBe(200);
      const body = JSON.parse(res.body);
      expect(body.success).toBe(true);
      expect(body.headSha).toBe(CURRENT_HEAD_SHA);
      expect(body.valid).toBe(false); // No attestation yet
      expect(body.reason).toBe("NO_ATTESTATION_FOUND");
    });

    it("handles issues event on control issue #7 and updates check run to failure when state changed to needs-fix", async () => {
      const issue7NeedsFix = {
        number: 7,
        title: "[agent] Control Issue",
        state: "open",
        labels: [{ name: "needs-fix" }],
        body: `
<!-- AGENT_CONTROL_BLOCK_V1 -->
state: needs-fix
scope_revision: 3
fix_reentries: 1
owner_scope_reset: https://github.com/Banhtalon/mindx-review-bot/issues/7#issuecomment-5534707230
<!-- /AGENT_CONTROL_BLOCK_V1 -->
        `,
        user: { login: "Banhtalon", id: 105797112 },
      };

      const payload = JSON.stringify({
        action: "labeled",
        issue: { number: 7 },
        repository: { full_name: REPO },
        installation: { id: 777 },
      });
      const hmac = createHmac("sha256", env.GITHUB_WEBHOOK_SECRET).update(payload).digest("hex");

      const existingCheckRun = {
        id: 77777,
        url: "https://api.github.com/repos/Banhtalon/mindx-review-bot/check-runs/77777",
        name: "terra-review-gate",
        head_sha: CURRENT_HEAD_SHA,
        status: "completed",
        conclusion: "success",
      };

      const capturedCheckRuns: CapturedCheckRun[] = [];
      const mockFetch = createMockFetch([], capturedCheckRuns, existingCheckRun, issue7NeedsFix);

      const res = await handleWebhookRequest(
        {
          method: "POST",
          headers: {
            "x-hub-signature-256": `sha256=${hmac}`,
            "x-github-event": "issues",
          },
          text: async () => payload,
        },
        env,
        mockFetch as unknown as typeof fetch
      );

      expect(res.status).toBe(200);
      const body = JSON.parse(res.body);
      expect(body.success).toBe(true);
      expect(body.valid).toBe(false);
      expect(body.reason).toBe("INVALID_CONTROL_STATE");
      expect(capturedCheckRuns).toHaveLength(2);
      expect(capturedCheckRuns[0].status).toBe("in_progress");
      expect(capturedCheckRuns[1].conclusion).toBe("failure");
    });

    it("handles issue_comment event on control issue #7 and recomputes PR #6 (Finding 3)", async () => {
      const payload = JSON.stringify({
        action: "created",
        issue: { number: 7 }, // Comment created on control issue #7
        repository: { full_name: REPO },
        installation: { id: 777 },
      });
      const hmac = createHmac("sha256", env.GITHUB_WEBHOOK_SECRET).update(payload).digest("hex");

      const capturedCheckRuns: CapturedCheckRun[] = [];
      const mockFetch = createMockFetch([], capturedCheckRuns);

      const res = await handleWebhookRequest(
        {
          method: "POST",
          headers: {
            "x-hub-signature-256": `sha256=${hmac}`,
            "x-github-event": "issue_comment",
          },
          text: async () => payload,
        },
        env,
        mockFetch as unknown as typeof fetch
      );

      expect(res.status).toBe(200);
      const body = JSON.parse(res.body);
      expect(body.success).toBe(true);
      expect(body.headSha).toBe(CURRENT_HEAD_SHA);
      // Recomputed PR #6 review gate
      expect(capturedCheckRuns).toHaveLength(2);
      expect(capturedCheckRuns[0].status).toBe("in_progress");
      expect(capturedCheckRuns[1].conclusion).toBe("failure"); // No attestation on PR #6
    });
  });
});
