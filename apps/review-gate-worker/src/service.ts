import {
  createOrUpdateCheckRun,
  fetchAllIssueComments,
  fetchIssue,
  fetchIssueComment,
  fetchPullRequest,
  findExistingCheckRun,
} from "./github.ts";
import {
  extractOwnerAttestationsFromComments,
  parseCanonicalNonNegativeInteger,
  validateReviewGate,
} from "./validator.ts";
import {
  GitHubCheckRunPayload,
  PILOT_TRUSTED_CONFIG,
  TRUSTED_CHECK_NAME,
  TrustedMappingConfig,
  ValidationResult,
} from "./types.ts";

export interface EvaluateReviewGateServiceOptions {
  repo: string;
  prNumber: number;
  token: string;
  trustedConfig?: TrustedMappingConfig;
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
 * Validates trusted mapping configuration.
 */
export function validateTrustedConfig(
  config: unknown
): { valid: true; config: TrustedMappingConfig } | { valid: false; reason: string; details: string } {
  if (!config || typeof config !== "object") {
    return {
      valid: false,
      reason: "MISSING_TRUSTED_CONFIG",
      details: "Trusted mapping configuration is missing or not an object.",
    };
  }

  const c = config as Record<string, unknown>;
  if (typeof c.repo !== "string" || !c.repo.trim()) {
    return {
      valid: false,
      reason: "MALFORMED_TRUSTED_CONFIG",
      details: "trustedConfig.repo must be a non-empty string.",
    };
  }

  const prNum = parseCanonicalNonNegativeInteger(c.prNumber);
  if (prNum === null || prNum < 1) {
    return {
      valid: false,
      reason: "MALFORMED_TRUSTED_CONFIG",
      details: "trustedConfig.prNumber must be a positive integer.",
    };
  }

  const issueNum = parseCanonicalNonNegativeInteger(c.controlIssue);
  if (issueNum === null || issueNum < 1) {
    return {
      valid: false,
      reason: "MALFORMED_TRUSTED_CONFIG",
      details: "trustedConfig.controlIssue must be a positive integer.",
    };
  }

  const scopeRev = parseCanonicalNonNegativeInteger(c.scopeRevision);
  if (scopeRev === null || scopeRev < 1) {
    return {
      valid: false,
      reason: "MALFORMED_TRUSTED_CONFIG",
      details: "trustedConfig.scopeRevision must be a positive integer.",
    };
  }

  return {
    valid: true,
    config: {
      repo: c.repo.trim(),
      prNumber: prNum,
      controlIssue: issueNum,
      scopeRevision: scopeRev,
    },
  };
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
 * Emits or updates the terra-review-gate check run on exact current head SHA.
 * Finds existing check run on headSha to update (PATCH) for idempotency,
 * or creates a new one (POST) with external_id if none exists.
 */
export async function emitReviewGateCheckRun(
  repo: string,
  prNumber: number,
  headSha: string,
  result: ValidationResult,
  token: string,
  explicitCheckRunId?: number,
  fetchFn: typeof fetch = fetch
): Promise<{ id: number; url: string }> {
  let checkRunId = explicitCheckRunId;
  if (!checkRunId) {
    try {
      const existing = await findExistingCheckRun(repo, headSha, TRUSTED_CHECK_NAME, token, fetchFn);
      if (existing) {
        checkRunId = existing.id;
      }
    } catch {
      // If query fails, fall through to create
    }
  }

  const checkRunPayload: GitHubCheckRunPayload = {
    ...createCheckRunPayload(headSha, result),
    external_id: `${TRUSTED_CHECK_NAME}:${prNumber}`,
  };

  return createOrUpdateCheckRun(repo, checkRunPayload, token, checkRunId, fetchFn);
}

/**
 * Full review-gate service evaluation:
 * - Re-fetches current PR head SHA directly from GitHub API (never trusts webhook SHA)
 * - Enforces non-PR-controlled trusted deployment configuration
 * - Re-fetches control issue from GitHub API
 * - Re-fetches scope-reset comment if scope_revision > 1
 * - Fetches all PR top-level comments with exhaustive pagination
 * - Evaluates validation rules
 * - Emits or updates terra-review-gate check run on exact current head SHA
 */
export async function evaluateReviewGateService(
  options: EvaluateReviewGateServiceOptions
): Promise<EvaluateReviewGateServiceResult> {
  const { repo, prNumber, token, fetchFn = fetch } = options;

  // 1. Re-fetch PR metadata to get exact current head SHA (NEVER trust webhook/caller head SHA)
  const pr = await fetchPullRequest(repo, prNumber, token, fetchFn);
  const currentHeadSha = pr.head.sha;

  // 2. Validate trusted configuration (never derive control issue or scope revision from PR body)
  const rawConfig = options.trustedConfig !== undefined ? options.trustedConfig : PILOT_TRUSTED_CONFIG;
  const configValidation = validateTrustedConfig(rawConfig);
  if (!configValidation.valid) {
    const failResult: ValidationResult = {
      valid: false,
      reason: configValidation.reason,
      details: configValidation.details,
    };
    const checkRun = await emitReviewGateCheckRun(
      repo,
      prNumber,
      currentHeadSha,
      failResult,
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

  const trustedConfig = configValidation.config;

  // Verify incoming repo and prNumber match trustedConfig
  if (
    repo.toLowerCase() !== trustedConfig.repo.toLowerCase() ||
    prNumber !== trustedConfig.prNumber
  ) {
    const failResult: ValidationResult = {
      valid: false,
      reason: "TRUSTED_CONFIG_MISMATCH",
      details: `Incoming PR (${repo} #${prNumber}) does not match trusted deployment configuration (${trustedConfig.repo} #${trustedConfig.prNumber}).`,
    };
    const checkRun = await emitReviewGateCheckRun(
      repo,
      prNumber,
      currentHeadSha,
      failResult,
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

  const controlIssueNum = trustedConfig.controlIssue;
  const expectedScopeRevision = trustedConfig.scopeRevision;

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
    const checkRun = await emitReviewGateCheckRun(
      repo,
      prNumber,
      currentHeadSha,
      failResult,
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

  // 5. Fetch all top-level PR conversation comments with exhaustive pagination
  let prComments;
  try {
    prComments = await fetchAllIssueComments(repo, prNumber, token, fetchFn);
  } catch (err: unknown) {
    const errorObj = err as { code?: string; message?: string };
    if (
      errorObj.code === "PAGINATION_LIMIT_EXCEEDED" ||
      (errorObj.message && errorObj.message.includes("PAGINATION_LIMIT_EXCEEDED"))
    ) {
      const failResult: ValidationResult = {
        valid: false,
        reason: "PAGINATION_LIMIT_EXCEEDED",
        details: errorObj.message || "Exceeded maximum allowed comment pagination pages.",
      };
      const checkRun = await emitReviewGateCheckRun(
        repo,
        prNumber,
        currentHeadSha,
        failResult,
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
    throw err;
  }

  // 6. Extract owner-authorized attestations
  const attestations = extractOwnerAttestationsFromComments(prComments);

  // 7. Validate review gate
  const validationResult = validateReviewGate({
    attestations,
    expectedHeadSha: currentHeadSha,
    expectedPrNumber: prNumber,
    expectedControlIssue: controlIssueNum,
    expectedScopeRevision,
    expectedRepo: repo,
    controlIssueData,
    scopeResetCommentData,
  });

  // 8. Emit or update check run on exact current head SHA
  const checkRun = await emitReviewGateCheckRun(
    repo,
    prNumber,
    currentHeadSha,
    validationResult,
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

export function createCheckRunPayload(headSha: string, result: ValidationResult): GitHubCheckRunPayload {
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
