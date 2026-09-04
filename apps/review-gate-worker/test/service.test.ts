import { describe, expect, it } from "vitest";
import { evaluateReviewGateService } from "../src/service.ts";
import { handleWebhookRequest, WorkerEnv } from "../src/index.ts";
import { createHmac, generateKeyPairSync } from "node:crypto";

const CURRENT_HEAD_SHA = "09297ea56133d10d5f40c429e78c7195a8aac61f";
const OLD_HEAD_SHA = "374b80f6e411ef9d89be3a7bbf656b50b7da5d8e";
const REPO = "Banhtalon/mindx-review-bot";

const mockPr = {
  number: 6,
  title: "chore: migrate agent workflow",
  body: "Authoritative control issue: #7",
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

function createMockFetch(comments: unknown[] = [], capturedCheckRuns: unknown[] = []) {
  return async (url: RequestInfo | URL, init?: RequestInit) => {
    const urlStr = String(url);

    if (urlStr.includes("/pulls/6")) {
      return new Response(JSON.stringify(mockPr), { status: 200 });
    }

    if (urlStr.includes("/issues/7/comments")) {
      return new Response(JSON.stringify([]), { status: 200 });
    }

    if (urlStr.includes("/issues/7")) {
      return new Response(JSON.stringify(mockIssue7), { status: 200 });
    }

    if (urlStr.includes("/issues/comments/5534707230")) {
      return new Response(JSON.stringify(mockScopeResetComment), { status: 200 });
    }

    if (urlStr.includes("/issues/6/comments")) {
      return new Response(JSON.stringify(comments), { status: 200 });
    }

    if (urlStr.includes("/check-runs")) {
      const body = JSON.parse(String(init?.body));
      capturedCheckRuns.push(body);
      return new Response(JSON.stringify({ id: 12345, url: "https://api.github.com/check-runs/12345" }), { status: 201 });
    }

    if (urlStr.includes("/access_tokens")) {
      return new Response(JSON.stringify({ token: "mock-installation-token" }), { status: 201 });
    }

    return new Response(JSON.stringify({ error: "Not Found" }), { status: 404 });
  };
}

describe("Review Gate Service & Webhook", () => {
  it("passes review gate and emits successful check run on exact current head SHA", async () => {
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

    const capturedCheckRuns: { name: string; head_sha: string; conclusion: string }[] = [];
    const mockFetch = createMockFetch([validOwnerComment], capturedCheckRuns);

    const result = await evaluateReviewGateService({
      repo: REPO,
      prNumber: 6,
      token: "mock-token",
      fetchFn: mockFetch as unknown as typeof fetch,
    });

    expect(result.valid).toBe(true);
    expect(result.headSha).toBe(CURRENT_HEAD_SHA);
    expect(capturedCheckRuns).toHaveLength(1);
    expect(capturedCheckRuns[0].name).toBe("terra-review-gate");
    expect(capturedCheckRuns[0].head_sha).toBe(CURRENT_HEAD_SHA);
    expect(capturedCheckRuns[0].conclusion).toBe("success");
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

    const capturedCheckRuns: { name: string; head_sha: string; conclusion: string }[] = [];
    const mockFetch = createMockFetch([staleOwnerComment], capturedCheckRuns);

    const result = await evaluateReviewGateService({
      repo: REPO,
      prNumber: 6,
      token: "mock-token",
      fetchFn: mockFetch as unknown as typeof fetch,
    });

    expect(result.valid).toBe(false);
    expect(result.validationResult.reason).toBe("STALE_HEAD_SHA");
    expect(capturedCheckRuns).toHaveLength(1);
    // Check run must still be posted to the CURRENT head SHA, reporting failure
    expect(capturedCheckRuns[0].head_sha).toBe(CURRENT_HEAD_SHA);
    expect(capturedCheckRuns[0].conclusion).toBe("failure");
  });

  it("fails closed when no attestation exists", async () => {
    const capturedCheckRuns: { name: string; head_sha: string; conclusion: string }[] = [];
    const mockFetch = createMockFetch([], capturedCheckRuns);

    const result = await evaluateReviewGateService({
      repo: REPO,
      prNumber: 6,
      token: "mock-token",
      fetchFn: mockFetch as unknown as typeof fetch,
    });

    expect(result.valid).toBe(false);
    expect(result.validationResult.reason).toBe("NO_ATTESTATION_FOUND");
    expect(capturedCheckRuns).toHaveLength(1);
    expect(capturedCheckRuns[0].conclusion).toBe("failure");
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

      const capturedCheckRuns: unknown[] = [];
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
  });
});
