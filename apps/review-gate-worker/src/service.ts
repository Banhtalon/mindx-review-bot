import {
  createOrUpdateCheckRun,
  fetchAllIssueComments,
  fetchIssue,
  fetchIssueComment,
  fetchPullRequest,
} from "./github.ts";
import {
  extractOwnerAttestationsFromComments,
  validateReviewGate,
} from "./validator.ts";
import {
  GitHubCheckRunPayload,
  TRUSTED_CHECK_NAME,
  ValidationResult,
} from "./types.ts";

export interface EvaluateReviewGateServiceOptions {
  repo: string;
  prNumber: number;
  token: string;
  expectedControlIssue?: number;
  expectedScopeRevision?: number;
  checkRunId?: number;
  fetchFn?: typeof fetch;
}

export interface EvaluateReviewGateServiceResult {
  valid: boolean;
  headSha: string;
  validationResult: ValidationResult;
  checkRun: { id: number; url: string };
}

/**
 * Extracts comment ID from GitHub comment URL:
 * e.g. https://github.com/Banhtalon/mindx-review-bot/issues/7#issuecomment-5534707230 -> 5534707230
 */
export function extractCommentIdFromUrl(url: string): string | null {
  if (!url || typeof url !== "string") return null;
  const match = /#(?:issuecomment-|comment-)?(\d+)/i.exec(url);
  if (match) return match[1];
  const pathMatch = /\/comments\/(\d+)/i.exec(url);
  return pathMatch ? pathMatch[1] : null;
}

/**
 * Parses linked control issue number from PR body markdown.
 */
export function parseControlIssueFromPrBody(prBody: string): number | null {
  if (!prBody || typeof prBody !== "string") return null;
  const match = /(?:Authoritative control issue|Linked issue|Linked GitHub issue):\s*#?(\d+)/i.exec(prBody);
  return match ? parseInt(match[1], 10) : null;
}

/**
 * Full review-gate service evaluation:
 * - Re-fetches current PR head SHA directly from GitHub API
 * - Re-fetches control issue from GitHub API
 * - Re-fetches scope-reset comment if scope_revision > 1
 * - Fetches all PR top-level comments with pagination
 * - Evaluates validation rules
 * - Emits terra-review-gate check run on exact current head SHA
 */
export async function evaluateReviewGateService(
  options: EvaluateReviewGateServiceOptions
): Promise<EvaluateReviewGateServiceResult> {
  const { repo, prNumber, token, fetchFn = fetch } = options;

  // 1. Re-fetch PR metadata to get exact current head SHA (NEVER trust webhook/caller head SHA)
  const pr = await fetchPullRequest(repo, prNumber, token, fetchFn);
  const currentHeadSha = pr.head.sha;

  // 2. Identify linked control issue
  let controlIssueNum = options.expectedControlIssue;
  if (!controlIssueNum) {
    const fromBody = parseControlIssueFromPrBody(pr.body || "");
    if (fromBody) controlIssueNum = fromBody;
  }

  if (!controlIssueNum) {
    const failResult: ValidationResult = {
      valid: false,
      reason: "MISSING_CONTROL_ISSUE",
      details: "No authoritative control issue specified or linked in PR body.",
    };
    const checkRun = await createOrUpdateCheckRun(
      repo,
      createCheckRunPayload(currentHeadSha, failResult),
      token,
      options.checkRunId,
      fetchFn
    );
    return {
      valid: false,
      headSha: currentHeadSha,
      validationResult: failResult,
      checkRun,
    };
  }

  // 3. Fetch control issue
  let controlIssueData;
  try {
    controlIssueData = await fetchIssue(repo, controlIssueNum, token, fetchFn);
  } catch (err) {
    const failResult: ValidationResult = {
      valid: false,
      reason: "ISSUE_FETCH_FAILED",
      details: `Failed to fetch authoritative control issue #${controlIssueNum}: ${(err as Error).message}`,
    };
    const checkRun = await createOrUpdateCheckRun(
      repo,
      createCheckRunPayload(currentHeadSha, failResult),
      token,
      options.checkRunId,
      fetchFn
    );
    return {
      valid: false,
      headSha: currentHeadSha,
      validationResult: failResult,
      checkRun,
    };
  }

  // 4. Fetch scope-reset comment if referenced
  let scopeResetCommentData;
  const resetUrlMatch = /owner_scope_reset:\s*(https:\/\/[^\r\n]+)/i.exec(controlIssueData.body || "");
  if (resetUrlMatch) {
    const commentId = extractCommentIdFromUrl(resetUrlMatch[1]);
    if (commentId) {
      try {
        scopeResetCommentData = await fetchIssueComment(repo, commentId, token, fetchFn);
      } catch {
        scopeResetCommentData = null; // Will fail in validator if required
      }
    }
  }

  // 5. Fetch all top-level PR conversation comments
  const prComments = await fetchAllIssueComments(repo, prNumber, token, fetchFn);

  // 6. Extract owner-authorized attestations
  const attestations = extractOwnerAttestationsFromComments(prComments);

  // 7. Validate review gate
  const validationResult = validateReviewGate({
    attestations,
    expectedHeadSha: currentHeadSha,
    expectedPrNumber: prNumber,
    expectedControlIssue: controlIssueNum,
    expectedScopeRevision: options.expectedScopeRevision,
    controlIssueData,
    scopeResetCommentData,
  });

  // 8. Emit check run on exact current head SHA
  const checkRunPayload = createCheckRunPayload(currentHeadSha, validationResult);
  const checkRun = await createOrUpdateCheckRun(
    repo,
    checkRunPayload,
    token,
    options.checkRunId,
    fetchFn
  );

  return {
    valid: validationResult.valid,
    headSha: currentHeadSha,
    validationResult,
    checkRun,
  };
}

function createCheckRunPayload(headSha: string, result: ValidationResult): GitHubCheckRunPayload {
  if (result.valid) {
    return {
      name: TRUSTED_CHECK_NAME,
      head_sha: headSha,
      status: "completed",
      conclusion: "success",
      output: {
        title: "Terra Review Gate: Passed",
        summary: `### Terra Review Attestation Verified\n\n- **Verdict**: \`${result.attestation.verdict}\`\n- **Reviewer**: \`${result.attestation.reviewer_model}\`\n- **Head SHA**: \`${result.attestation.head_sha}\`\n- **PR Number**: #${result.attestation.pr_number}\n- **Control Issue**: #${result.attestation.control_issue}\n- **Scope Revision**: ${result.attestation.scope_revision}\n- **Findings**: P0: ${result.attestation.p0}, P1: ${result.attestation.p1}\n- **Material Findings Resolved**: ${result.attestation.material_findings_resolved}\n- **Reviewed At (UTC)**: ${result.attestation.reviewed_at_utc}`,
      },
    };
  }

  return {
    name: TRUSTED_CHECK_NAME,
    head_sha: headSha,
    status: "completed",
    conclusion: "failure",
    output: {
      title: "Terra Review Gate: Failed",
      summary: `### Review Gate Check Failed: [${result.reason}]\n\n${result.details}\n\n*Head SHA evaluated: \`${headSha}\`*`,
    },
  };
}
