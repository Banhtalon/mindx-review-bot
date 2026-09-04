import { createHmac, createSign, timingSafeEqual } from "node:crypto";
import {
  GitHubCheckRunPayload,
  GitHubIssue,
  GitHubIssueComment,
  GitHubPullRequest,
  TRUSTED_CHECK_NAME,
} from "./types.ts";

/**
 * Verifies the X-Hub-Signature-256 header using constant-time comparison.
 */
export function verifyWebhookSignature(
  payload: string | Buffer,
  signatureHeader: string | undefined | null,
  secret: string
): boolean {
  if (!signatureHeader || !secret) return false;
  if (!signatureHeader.startsWith("sha256=")) return false;

  const signature = signatureHeader.slice("sha256=".length);
  const hmac = createHmac("sha256", secret);
  hmac.update(payload);
  const digest = hmac.digest("hex");

  if (digest.length !== signature.length) return false;

  try {
    return timingSafeEqual(Buffer.from(digest, "utf-8"), Buffer.from(signature, "utf-8"));
  } catch {
    return false;
  }
}

/**
 * Generates an RS256 JWT for GitHub App authentication using built-in node:crypto.
 */
export function generateAppJwt(appId: string, privateKeyPem: string): string {
  const now = Math.floor(Date.now() / 1000);
  const payload = {
    iat: now - 60, // 60s in the past to compensate for clock drift
    exp: now + 600, // 10 minutes expiry
    iss: appId,
  };
  const header = {
    alg: "RS256",
    typ: "JWT",
  };

  const encodeBase64Url = (obj: unknown): string =>
    Buffer.from(JSON.stringify(obj))
      .toString("base64")
      .replace(/=/g, "")
      .replace(/\+/g, "-")
      .replace(/\//g, "_");

  const unsignedToken = `${encodeBase64Url(header)}.${encodeBase64Url(payload)}`;

  const sign = createSign("RSA-SHA256");
  sign.update(unsignedToken);
  const signature = sign
    .sign(privateKeyPem, "base64")
    .replace(/=/g, "")
    .replace(/\+/g, "-")
    .replace(/\//g, "_");

  return `${unsignedToken}.${signature}`;
}

/**
 * Requests an installation access token for a given installation ID.
 */
export async function getInstallationAccessToken(
  jwt: string,
  installationId: number | string,
  fetchFn: typeof fetch = fetch
): Promise<string> {
  const url = `https://api.github.com/app/installations/${installationId}/access_tokens`;
  const res = await fetchFn(url, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${jwt}`,
      Accept: "application/vnd.github+json",
      "User-Agent": "mindx-review-gate-worker",
    },
  });

  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Failed to obtain installation token (${res.status}): ${body}`);
  }

  const data = (await res.json()) as { token: string };
  return data.token;
}

/**
 * Fetches pull request metadata to re-fetch exact current head SHA.
 * Never trust webhook-provided head SHA.
 */
export async function fetchPullRequest(
  repo: string,
  prNumber: number,
  token: string,
  fetchFn: typeof fetch = fetch
): Promise<GitHubPullRequest> {
  const url = `https://api.github.com/repos/${repo}/pulls/${prNumber}`;
  const res = await fetchFn(url, {
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "application/vnd.github+json",
      "User-Agent": "mindx-review-gate-worker",
    },
  });

  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Failed to fetch PR #${prNumber} (${res.status}): ${body}`);
  }

  return (await res.json()) as GitHubPullRequest;
}

/**
 * Fetches issue data (for control issue).
 */
export async function fetchIssue(
  repo: string,
  issueNumber: number,
  token: string,
  fetchFn: typeof fetch = fetch
): Promise<GitHubIssue> {
  const url = `https://api.github.com/repos/${repo}/issues/${issueNumber}`;
  const res = await fetchFn(url, {
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "application/vnd.github+json",
      "User-Agent": "mindx-review-gate-worker",
    },
  });

  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Failed to fetch issue #${issueNumber} (${res.status}): ${body}`);
  }

  return (await res.json()) as GitHubIssue;
}

/**
 * Fetches a single issue comment by comment ID.
 */
export async function fetchIssueComment(
  repo: string,
  commentId: number | string,
  token: string,
  fetchFn: typeof fetch = fetch
): Promise<GitHubIssueComment> {
  const url = `https://api.github.com/repos/${repo}/issues/comments/${commentId}`;
  const res = await fetchFn(url, {
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "application/vnd.github+json",
      "User-Agent": "mindx-review-gate-worker",
    },
  });

  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Failed to fetch comment #${commentId} (${res.status}): ${body}`);
  }

  return (await res.json()) as GitHubIssueComment;
}

export interface ExistingCheckRun {
  id: number;
  url: string;
  name: string;
  head_sha: string;
  status: string;
  conclusion?: string | null;
  external_id?: string | null;
}

/**
 * Deterministically fetches all paginated comments from PR conversation until exhausted.
 * Fails closed with error if maxPages (safety cap) is reached and there are still more comments.
 */
export async function fetchAllIssueComments(
  repo: string,
  issueNumber: number,
  token: string,
  fetchFn: typeof fetch = fetch,
  maxPages = 200
): Promise<GitHubIssueComment[]> {
  const allComments: GitHubIssueComment[] = [];
  let page = 1;
  const perPage = 100;

  while (true) {
    if (page > maxPages) {
      const err = new Error(`PAGINATION_LIMIT_EXCEEDED: Exceeded maximum allowed comment pages (${maxPages}) for issue #${issueNumber}`);
      (err as unknown as { code: string }).code = "PAGINATION_LIMIT_EXCEEDED";
      throw err;
    }

    const url = `https://api.github.com/repos/${repo}/issues/${issueNumber}/comments?per_page=${perPage}&page=${page}`;
    const res = await fetchFn(url, {
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/vnd.github+json",
        "User-Agent": "mindx-review-gate-worker",
      },
    });

    if (!res.ok) {
      const body = await res.text();
      throw new Error(`Failed to fetch comments for #${issueNumber} on page ${page} (${res.status}): ${body}`);
    }

    const items = (await res.json()) as GitHubIssueComment[];
    if (!Array.isArray(items) || items.length === 0) {
      break;
    }

    allComments.push(...items);
    if (items.length < perPage) {
      break;
    }
    page++;
  }

  return allComments;
}

/**
 * Searches for an existing check run by check name on exact current head SHA.
 * GET /repos/:owner/:repo/commits/:ref/check-runs?check_name=:name
 */
export async function findExistingCheckRun(
  repo: string,
  headSha: string,
  checkName: string,
  token: string,
  fetchFn: typeof fetch = fetch
): Promise<ExistingCheckRun | null> {
  const url = `https://api.github.com/repos/${repo}/commits/${headSha}/check-runs?check_name=${encodeURIComponent(checkName)}`;
  const res = await fetchFn(url, {
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "application/vnd.github+json",
      "User-Agent": "mindx-review-gate-worker",
    },
  });

  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Failed to query check runs for commit ${headSha} (${res.status}): ${body}`);
  }

  const data = (await res.json()) as {
    total_count: number;
    check_runs?: ExistingCheckRun[];
  };

  if (Array.isArray(data.check_runs) && data.check_runs.length > 0) {
    return data.check_runs[0];
  }

  return null;
}

/**
 * Creates or updates the terra-review-gate check run on exact current head SHA.
 */
export async function createOrUpdateCheckRun(
  repo: string,
  payload: GitHubCheckRunPayload,
  token: string,
  checkRunId?: number,
  fetchFn: typeof fetch = fetch
): Promise<{ id: number; url: string }> {
  if (payload.name !== TRUSTED_CHECK_NAME) {
    throw new Error(`Check run name must be exactly '${TRUSTED_CHECK_NAME}', got '${payload.name}'.`);
  }

  const url = checkRunId
    ? `https://api.github.com/repos/${repo}/check-runs/${checkRunId}`
    : `https://api.github.com/repos/${repo}/check-runs`;
  const method = checkRunId ? "PATCH" : "POST";

  const res = await fetchFn(url, {
    method,
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "application/vnd.github+json",
      "Content-Type": "application/json",
      "User-Agent": "mindx-review-gate-worker",
    },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Failed to ${method} check run (${res.status}): ${body}`);
  }

  return (await res.json()) as { id: number; url: string };
}
