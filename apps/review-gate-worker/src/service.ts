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
  parseOwnerScopeResetApproval,
  validateControlIssue,
  validateOwnerScopeResetUrl,
  validateReviewGate,
} from "./validator.ts";
import {
  EvaluationGuard,
  GitHubCheckRunPayload,
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
  expectedAppId?: number;
  guard?: EvaluationGuard;
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
 * Missing, non-object, empty repo, or non-canonical positive integers fail closed.
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
 * Queries existing check run on headSha to update (PATCH), or creates a new one (POST).
 * Lookup errors fail closed.
 */
export async function emitReviewGateCheckRun(
  repo: string,
  prNumber: number,
  headSha: string,
  result: ValidationResult,
  token: string,
  explicitCheckRunId?: number,
  expectedAppIdOrFetchFn?: number | typeof fetch,
  fetchFn?: typeof fetch
): Promise<{ id: number; url: string }> {
  let expectedAppId: number | undefined;
  let actualFetch: typeof fetch = fetch;

  if (typeof expectedAppIdOrFetchFn === "function") {
    actualFetch = expectedAppIdOrFetchFn;
  } else {
    expectedAppId = expectedAppIdOrFetchFn;
    if (typeof fetchFn === "function") {
      actualFetch = fetchFn;
    }
  }

  let checkRunId = explicitCheckRunId;
  if (!checkRunId) {
    const existing = await findExistingCheckRun(repo, headSha, TRUSTED_CHECK_NAME, token, expectedAppId, actualFetch);
    if (existing) {
      checkRunId = existing.id;
    }
  }

  const checkRunPayload: GitHubCheckRunPayload = {
    ...createCheckRunPayload(headSha, result),
    external_id: `${TRUSTED_CHECK_NAME}:${prNumber}`,
  };

  return createOrUpdateCheckRun(repo, checkRunPayload, token, checkRunId, actualFetch);
}

/**
 * Full review-gate service evaluation:
 * - Re-fetches current PR head SHA directly from GitHub API (never trusts webhook SHA).
 * - Enforces non-PR-controlled trusted deployment configuration (no production fallback).
 * - Immediately moves/recreates check run to `in_progress` on exact head SHA.
 * - Any subsequent read, parse, validation, or API error updates the check run to `failure`.
 * - Binds scope-reset authority exclusively to the parsed AGENT_CONTROL_BLOCK_V1.
 * - Validates scope-reset comment location metadata and comment ID.
 * - Checks monotonic evaluation version guard to prevent stale out-of-order success writes.
 */
export async function evaluateReviewGateService(
  options: EvaluateReviewGateServiceOptions
): Promise<EvaluateReviewGateServiceResult> {
  const { repo, prNumber, token, fetchFn = fetch } = options;

  // 1. Re-fetch PR metadata to get exact current head SHA (NEVER trust webhook/caller head SHA)
  const pr = await fetchPullRequest(repo, prNumber, token, fetchFn);
  const currentHeadSha = pr.head.sha;

  // 2. Acquire evaluation version claim to detect stale concurrent runs
  const claim = options.guard ? await options.guard.acquireVersion(repo, prNumber) : null;
  const versionTag = claim ? `:v${claim.version}` : "";
  const externalId = `${TRUSTED_CHECK_NAME}:${prNumber}${versionTag}`;

  // 3. Lookup existing check run on headSha
  let checkRunId = options.checkRunId;
  if (!checkRunId) {
    const existing = await findExistingCheckRun(repo, currentHeadSha, TRUSTED_CHECK_NAME, token, options.expectedAppId, fetchFn);
    if (existing) {
      checkRunId = existing.id;
    }
  }

  // 4. Immediately transition check run to in_progress (ensures no prior green check remains authoritative)
  const inProgressPayload: GitHubCheckRunPayload = {
    name: TRUSTED_CHECK_NAME,
    head_sha: currentHeadSha,
    status: "in_progress",
    output: {
      title: "Terra Review Gate: Evaluating",
      summary: `Review gate evaluation in progress for PR #${prNumber}...`,
    },
    external_id: externalId,
  };

  const initialCheckRun = await createOrUpdateCheckRun(
    repo,
    inProgressPayload,
    token,
    checkRunId,
    fetchFn
  );
  checkRunId = initialCheckRun.id;

  // Helper to finalize check run with concurrency guard
  const finalizeCheckRun = async (valResult: ValidationResult): Promise<EvaluateReviewGateServiceResult> => {
    // Check if this evaluation was superseded while in-flight
    if (claim && options.guard) {
      const isLatest = await options.guard.isLatestVersion(claim);
      if (!isLatest) {
        // Stale evaluation: abort without writing success or overwriting newer state
        return {
          valid: false,
          headSha: currentHeadSha,
          validationResult: {
            valid: false,
            reason: "STALE_EVALUATION_ABORTED",
            details: `Evaluation version ${claim.version} was superseded by a newer evaluation for ${repo} #${prNumber}.`,
          },
          checkRun: { id: checkRunId!, url: initialCheckRun.url },
        };
      }
    }

    const payload: GitHubCheckRunPayload = {
      ...createCheckRunPayload(currentHeadSha, valResult),
      external_id: externalId,
    };

    const finalizedCheck = await createOrUpdateCheckRun(
      repo,
      payload,
      token,
      checkRunId,
      fetchFn
    );

    return {
      valid: valResult.valid,
      headSha: currentHeadSha,
      validationResult: valResult,
      checkRun: finalizedCheck,
    };
  };

  // 5. Wrap all subsequent reads and validations in try/catch to fail closed
  try {
    // Validate trusted configuration (mandatory; no PR-source fallback)
    const configValidation = validateTrustedConfig(options.trustedConfig);
    if (!configValidation.valid) {
      return await finalizeCheckRun({
        valid: false,
        reason: configValidation.reason,
        details: configValidation.details,
      });
    }

    const trustedConfig = configValidation.config;

    // Verify incoming repo and prNumber match trustedConfig
    if (
      repo.toLowerCase() !== trustedConfig.repo.toLowerCase() ||
      prNumber !== trustedConfig.prNumber
    ) {
      return await finalizeCheckRun({
        valid: false,
        reason: "TRUSTED_CONFIG_MISMATCH",
        details: `Incoming PR (${repo} #${prNumber}) does not match trusted deployment configuration (${trustedConfig.repo} #${trustedConfig.prNumber}).`,
      });
    }

    const controlIssueNum = trustedConfig.controlIssue;
    const expectedScopeRevision = trustedConfig.scopeRevision;

    // Fetch control issue
    const controlIssueData = await fetchIssue(repo, controlIssueNum, token, fetchFn);

    // Validate control issue (including state === 'open')
    const issueResult = validateControlIssue(controlIssueData, expectedScopeRevision, repo);
    if (!issueResult.valid) {
      return await finalizeCheckRun(issueResult);
    }
    const controlBlock = issueResult.block;

    // Fetch and validate scope-reset comment if scope_revision > 1
    let scopeResetCommentData: unknown = undefined;
    if (controlBlock.scope_revision > 1) {
      const resetUrlValidation = validateOwnerScopeResetUrl(controlBlock.owner_scope_reset, repo, controlIssueNum);
      if (!resetUrlValidation.valid) {
        return await finalizeCheckRun({
          valid: false,
          reason: resetUrlValidation.reason,
          details: resetUrlValidation.details,
        });
      }

      const commentId = resetUrlValidation.commentId;
      try {
        scopeResetCommentData = await fetchIssueComment(repo, commentId, token, fetchFn);
      } catch (err) {
        return await finalizeCheckRun({
          valid: false,
          reason: "SCOPE_RESET_FETCH_FAILED",
          details: `Failed to fetch scope-reset approval comment #${commentId}: ${(err as Error).message}`,
        });
      }

      const scopeResetResult = parseOwnerScopeResetApproval(
        scopeResetCommentData,
        controlBlock.scope_revision - 1,
        controlBlock.scope_revision,
        repo,
        controlIssueNum,
        commentId
      );
      if (!scopeResetResult.valid) {
        return await finalizeCheckRun(scopeResetResult);
      }
    }

    // Fetch all top-level PR comments with exhaustive pagination
    const prComments = await fetchAllIssueComments(repo, prNumber, token, fetchFn);

    // Extract owner-authorized attestations
    const attestations = extractOwnerAttestationsFromComments(prComments);

    // Validate review gate
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

    return await finalizeCheckRun(validationResult);
  } catch (err: unknown) {
    const errorObj = err as { code?: string; message?: string };
    const failResult: ValidationResult = {
      valid: false,
      reason: errorObj.code || "EVALUATION_ERROR",
      details: errorObj.message || String(err),
    };

    return await finalizeCheckRun(failResult);
  }
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
