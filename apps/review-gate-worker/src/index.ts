import { generateAppJwt, getInstallationAccessToken, verifyWebhookSignature } from "./github.ts";
import { evaluateReviewGateService } from "./service.ts";
import { PILOT_TRUSTED_CONFIG, TrustedMappingConfig } from "./types.ts";

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

/**
 * Serverless / Edge / Node HTTP request handler for the GitHub App webhook.
 */
export async function handleWebhookRequest(
  request: WebhookHandlerRequest,
  env: WorkerEnv,
  fetchFn: typeof fetch = fetch
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

  const event = request.headers["x-github-event"] || request.headers["X-GitHub-Event"];

  let payload: Record<string, unknown>;
  try {
    payload = JSON.parse(rawBody);
  } catch {
    return { status: 400, body: JSON.stringify({ error: "Invalid JSON body" }) };
  }

  const trustedConfig: TrustedMappingConfig = {
    repo: env.TRUSTED_REPO || PILOT_TRUSTED_CONFIG.repo,
    prNumber: env.TRUSTED_PR_NUMBER ? Number(env.TRUSTED_PR_NUMBER) : PILOT_TRUSTED_CONFIG.prNumber,
    controlIssue: env.TRUSTED_CONTROL_ISSUE ? Number(env.TRUSTED_CONTROL_ISSUE) : PILOT_TRUSTED_CONFIG.controlIssue,
    scopeRevision: env.TRUSTED_SCOPE_REVISION ? Number(env.TRUSTED_SCOPE_REVISION) : PILOT_TRUSTED_CONFIG.scopeRevision,
  };

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
    // Only process comments on pull requests
    if (!issue?.pull_request) {
      return { status: 200, body: JSON.stringify({ ignored: true, reason: "Comment is not on a pull request" }) };
    }
    prNumber = issue.number;
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
