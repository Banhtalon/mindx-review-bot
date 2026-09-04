import { generateAppJwt, getInstallationAccessToken, verifyWebhookSignature } from "./github.ts";
import { InMemoryEvaluationGuard } from "./guard.ts";
import { evaluateReviewGateService } from "./service.ts";
import { EvaluationGuard, TrustedMappingConfig } from "./types.ts";
import { parseCanonicalNonNegativeInteger } from "./validator.ts";

export interface WorkerEnv {
  GITHUB_APP_ID: string;
  GITHUB_PRIVATE_KEY: string;
  GITHUB_WEBHOOK_SECRET: string;
  TRUSTED_REPO?: string;
  TRUSTED_PR_NUMBER?: string;
  TRUSTED_CONTROL_ISSUE?: string;
  TRUSTED_SCOPE_REVISION?: string;
}

export interface WebhookHandlerRequest {
  method: string;
  headers: Record<string, string | undefined>;
  text: () => Promise<string>;
}

export interface WebhookHandlerResponse {
  status: number;
  headers?: Record<string, string>;
  body: string;
}

const defaultGuard = new InMemoryEvaluationGuard();

/**
 * Validates and parses deployment trusted configuration from WorkerEnv.
 * Rejects non-canonical numbers, missing variables, or pilot requirement mismatches fail-closed.
 */
export function parseAndValidateTrustedEnv(env: WorkerEnv): {
  valid: true;
  config: TrustedMappingConfig;
} | {
  valid: false;
  reason: string;
  details: string;
} {
  if (!env.TRUSTED_REPO || typeof env.TRUSTED_REPO !== "string" || !env.TRUSTED_REPO.trim()) {
    return {
      valid: false,
      reason: "MISSING_TRUSTED_CONFIG",
      details: "TRUSTED_REPO environment variable is missing or empty.",
    };
  }
  if (env.TRUSTED_PR_NUMBER === undefined || env.TRUSTED_PR_NUMBER === null || env.TRUSTED_PR_NUMBER === "") {
    return {
      valid: false,
      reason: "MISSING_TRUSTED_CONFIG",
      details: "TRUSTED_PR_NUMBER environment variable is missing or empty.",
    };
  }
  if (env.TRUSTED_CONTROL_ISSUE === undefined || env.TRUSTED_CONTROL_ISSUE === null || env.TRUSTED_CONTROL_ISSUE === "") {
    return {
      valid: false,
      reason: "MISSING_TRUSTED_CONFIG",
      details: "TRUSTED_CONTROL_ISSUE environment variable is missing or empty.",
    };
  }
  if (env.TRUSTED_SCOPE_REVISION === undefined || env.TRUSTED_SCOPE_REVISION === null || env.TRUSTED_SCOPE_REVISION === "") {
    return {
      valid: false,
      reason: "MISSING_TRUSTED_CONFIG",
      details: "TRUSTED_SCOPE_REVISION environment variable is missing or empty.",
    };
  }

  const prNum = parseCanonicalNonNegativeInteger(env.TRUSTED_PR_NUMBER);
  if (prNum === null || prNum < 1) {
    return {
      valid: false,
      reason: "MALFORMED_TRUSTED_CONFIG",
      details: `TRUSTED_PR_NUMBER '${env.TRUSTED_PR_NUMBER}' is not a canonical positive integer.`,
    };
  }

  const issueNum = parseCanonicalNonNegativeInteger(env.TRUSTED_CONTROL_ISSUE);
  if (issueNum === null || issueNum < 1) {
    return {
      valid: false,
      reason: "MALFORMED_TRUSTED_CONFIG",
      details: `TRUSTED_CONTROL_ISSUE '${env.TRUSTED_CONTROL_ISSUE}' is not a canonical positive integer.`,
    };
  }

  const scopeRev = parseCanonicalNonNegativeInteger(env.TRUSTED_SCOPE_REVISION);
  if (scopeRev === null || scopeRev < 1) {
    return {
      valid: false,
      reason: "MALFORMED_TRUSTED_CONFIG",
      details: `TRUSTED_SCOPE_REVISION '${env.TRUSTED_SCOPE_REVISION}' is not a canonical positive integer.`,
    };
  }

  // For this pilot, must resolve exactly to:
  // Banhtalon/mindx-review-bot, PR 6, Issue 7, scope revision 3
  if (
    env.TRUSTED_REPO.trim().toLowerCase() !== "banhtalon/mindx-review-bot" ||
    prNum !== 6 ||
    issueNum !== 7 ||
    scopeRev !== 3
  ) {
    return {
      valid: false,
      reason: "TRUSTED_CONFIG_MISMATCH",
      details: `Trusted deployment configuration (${env.TRUSTED_REPO} PR #${prNum}, Issue #${issueNum}, rev ${scopeRev}) does not match pilot requirements (Banhtalon/mindx-review-bot, PR 6, Issue 7, rev 3).`,
    };
  }

  return {
    valid: true,
    config: {
      repo: env.TRUSTED_REPO.trim(),
      prNumber: prNum,
      controlIssue: issueNum,
      scopeRevision: scopeRev,
    },
  };
}

/**
 * Serverless / Edge / Node HTTP request handler for the GitHub App webhook.
 */
export async function handleWebhookRequest(
  request: WebhookHandlerRequest,
  env: WorkerEnv,
  fetchFn: typeof fetch = fetch,
  guard: EvaluationGuard = defaultGuard
): Promise<WebhookHandlerResponse> {
  if (request.method !== "POST") {
    return { status: 405, body: JSON.stringify({ error: "Method Not Allowed" }) };
  }

  const rawBody = await request.text();
  const signature =
    request.headers["x-hub-signature-256"] || request.headers["X-Hub-Signature-256"];

  if (!env.GITHUB_WEBHOOK_SECRET) {
    return { status: 500, body: JSON.stringify({ error: "Server missing GITHUB_WEBHOOK_SECRET" }) };
  }

  const isValidSignature = verifyWebhookSignature(rawBody, signature, env.GITHUB_WEBHOOK_SECRET);
  if (!isValidSignature) {
    return { status: 401, body: JSON.stringify({ error: "Invalid webhook signature" }) };
  }

  // Validate non-PR-controlled trusted configuration
  const configValidation = parseAndValidateTrustedEnv(env);
  if (!configValidation.valid) {
    return {
      status: 500,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        error: configValidation.reason,
        details: configValidation.details,
      }),
    };
  }

  const trustedConfig = configValidation.config;

  const event = request.headers["x-github-event"] || request.headers["X-GitHub-Event"];

  let payload: Record<string, unknown>;
  try {
    payload = JSON.parse(rawBody);
  } catch {
    return { status: 400, body: JSON.stringify({ error: "Invalid JSON body" }) };
  }

  let prNumber: number | undefined;
  let repoFullName: string | undefined;
  let installationId: number | undefined;

  if (payload.repository && typeof payload.repository === "object") {
    repoFullName = (payload.repository as { full_name?: string }).full_name;
  }

  if (payload.installation && typeof payload.installation === "object") {
    installationId = (payload.installation as { id?: number }).id;
  }

  if (event === "pull_request") {
    const action = payload.action as string;
    const relevantActions = ["opened", "reopened", "synchronize", "ready_for_review"];
    if (!relevantActions.includes(action)) {
      return { status: 200, body: JSON.stringify({ ignored: true, reason: `Action '${action}' not relevant` }) };
    }
    const pr = payload.pull_request as { number?: number };
    prNumber = pr?.number;
  } else if (event === "issue_comment") {
    const action = payload.action as string;
    const relevantActions = ["created", "edited", "deleted"];
    if (!relevantActions.includes(action)) {
      return { status: 200, body: JSON.stringify({ ignored: true, reason: `Action '${action}' not relevant` }) };
    }
    const issue = payload.issue as { number?: number; pull_request?: unknown };
    if (issue?.pull_request) {
      prNumber = issue.number;
    } else if (issue?.number === trustedConfig.controlIssue) {
      // Recompute PR #6 review gate when comments on authoritative control issue #7 are mutated or deleted
      prNumber = trustedConfig.prNumber;
    } else {
      return {
        status: 200,
        body: JSON.stringify({
          ignored: true,
          reason: `Comment is neither on PR #${trustedConfig.prNumber} nor control issue #${trustedConfig.controlIssue}`,
        }),
      };
    }
  } else if (event === "issues") {
    const action = payload.action as string;
    const relevantActions = ["edited", "labeled", "unlabeled", "opened", "reopened", "closed"];
    if (!relevantActions.includes(action)) {
      return { status: 200, body: JSON.stringify({ ignored: true, reason: `Action '${action}' not relevant` }) };
    }
    const issue = payload.issue as { number?: number };
    if (issue?.number !== trustedConfig.controlIssue) {
      return {
        status: 200,
        body: JSON.stringify({
          ignored: true,
          reason: `Issue #${issue?.number} is not control issue #${trustedConfig.controlIssue}`,
        }),
      };
    }
    // Map control issue update to PR review gate re-evaluation
    prNumber = trustedConfig.prNumber;
  } else {
    return { status: 200, body: JSON.stringify({ ignored: true, reason: `Event '${event}' not handled` }) };
  }

  if (!prNumber || !repoFullName || !installationId) {
    return {
      status: 400,
      body: JSON.stringify({
        error: "Missing required fields in payload (prNumber, repoFullName, or installationId)",
      }),
    };
  }

  try {
    const jwt = generateAppJwt(env.GITHUB_APP_ID, env.GITHUB_PRIVATE_KEY);
    const token = await getInstallationAccessToken(jwt, installationId, fetchFn);

    const result = await evaluateReviewGateService({
      repo: repoFullName,
      prNumber,
      token,
      trustedConfig,
      expectedAppId: Number(env.GITHUB_APP_ID),
      guard,
      fetchFn,
    });

    return {
      status: 200,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        success: true,
        valid: result.valid,
        headSha: result.headSha,
        reason: result.validationResult.reason,
        checkRunId: result.checkRun.id,
      }),
    };
  } catch (err) {
    return {
      status: 500,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        error: "Failed to evaluate review gate",
        details: (err as Error).message,
      }),
    };
  }
}

export default {
  fetch: (request: Request, env: WorkerEnv) => {
    const reqAdapter: WebhookHandlerRequest = {
      method: request.method,
      headers: Object.fromEntries(request.headers.entries()),
      text: () => request.text(),
    };
    return handleWebhookRequest(reqAdapter, env).then(
      (res) =>
        new Response(res.body, {
          status: res.status,
          headers: res.headers,
        })
    );
  },
};
