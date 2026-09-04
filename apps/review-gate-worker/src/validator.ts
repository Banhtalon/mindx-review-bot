import { isValidStrictUtcCalendarIsoTimestamp } from "./calendar.ts";
import {
  AgentControlBlock,
  CANONICAL_WORKFLOW_STATES,
  CanonicalWorkflowState,
  GitHubIssue,
  GitHubIssueComment,
  OwnerScopeResetApproval,
  REVIEWABLE_CONTROL_STATES,
  TerraAttestation,
  TRUSTED_OWNER_ID,
  TRUSTED_OWNER_LOGIN,
  ValidationResult,
} from "./types.ts";

/**
 * Validates and parses a canonical non-negative decimal integer.
 * Accepts only canonical non-negative decimal integers (e.g. 0, 1, 2).
 * Rejects negative numbers (-1), explicit signs (+1), floats (0.5, 1.0),
 * exponent notation (1e5), leading zeros (01), and whitespace.
 */
export function parseCanonicalNonNegativeInteger(val: unknown): number | null {
  if (typeof val === "number") {
    if (Number.isSafeInteger(val) && val >= 0 && Object.is(val, Math.abs(val))) {
      return val;
    }
    return null;
  }
  if (typeof val !== "string") {
    return null;
  }
  if (!/^(?:0|[1-9]\d*)$/.test(val)) {
    return null;
  }
  const parsed = Number(val);
  return Number.isSafeInteger(parsed) ? parsed : null;
}

/**
 * Parses Agent Control Block V1 from markdown text:
 * <!-- AGENT_CONTROL_BLOCK_V1 -->
 * state: <canonical-state>
 * scope_revision: <canonical-positive-integer>
 * fix_reentries: <0..2>
 * owner_scope_reset: <none-or-valid-approval-comment-url>
 * <!-- /AGENT_CONTROL_BLOCK_V1 -->
 */
export function parseAgentControlBlock(
  text: string | undefined | null
): { valid: true; block: AgentControlBlock } | { valid: false; reason: string; details: string } {
  if (!text || typeof text !== "string") {
    return {
      valid: false,
      reason: "MISSING_AGENT_CONTROL_BLOCK",
      details: "Authoritative text is empty or not a string.",
    };
  }

  const startRegex = /<!--\s*AGENT_CONTROL_BLOCK_V1\s*-->/gi;
  const endRegex = /<!--\s*\/AGENT_CONTROL_BLOCK_V1\s*-->/gi;

  const startMatches = text.match(startRegex) || [];
  const endMatches = text.match(endRegex) || [];

  if (startMatches.length === 0 || endMatches.length === 0) {
    return {
      valid: false,
      reason: "MISSING_AGENT_CONTROL_BLOCK",
      details: "Authoritative issue is missing required AGENT_CONTROL_BLOCK_V1 markers.",
    };
  }

  if (startMatches.length > 1 || endMatches.length > 1) {
    return {
      valid: false,
      reason: "MULTIPLE_AGENT_CONTROL_BLOCKS",
      details: `Found multiple AGENT_CONTROL_BLOCK_V1 blocks (${startMatches.length} start, ${endMatches.length} end). Must have exactly one.`,
    };
  }

  const blockRegex = /<!--\s*AGENT_CONTROL_BLOCK_V1\s*-->([\s\S]*?)<!--\s*\/AGENT_CONTROL_BLOCK_V1\s*-->/i;
  const match = blockRegex.exec(text);
  if (!match) {
    return {
      valid: false,
      reason: "MISSING_AGENT_CONTROL_BLOCK",
      details: "Malformed AGENT_CONTROL_BLOCK_V1 block structure.",
    };
  }

  const content = match[1];
  const lines = content.split(/\r?\n/);
  const seenKeys = new Set<string>();
  const parsedMap: Record<string, string> = {};

  const allowedKeys = new Set(["state", "scope_revision", "fix_reentries", "owner_scope_reset"]);

  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#")) continue;

    const colonIdx = line.indexOf(":");
    if (colonIdx === -1) {
      return {
        valid: false,
        reason: "MALFORMED_CONTROL_BLOCK",
        details: `Line in AGENT_CONTROL_BLOCK_V1 does not contain key-value separator ':': '${line}'`,
      };
    }

    const key = line.slice(0, colonIdx).trim();
    const val = line.slice(colonIdx + 1).trim();

    if (seenKeys.has(key)) {
      return {
        valid: false,
        reason: "DUPLICATE_KEY_IN_CONTROL_BLOCK",
        details: `Duplicate key '${key}' in AGENT_CONTROL_BLOCK_V1.`,
      };
    }

    if (!allowedKeys.has(key)) {
      return {
        valid: false,
        reason: "UNKNOWN_KEY_IN_CONTROL_BLOCK",
        details: `Unknown key '${key}' in AGENT_CONTROL_BLOCK_V1.`,
      };
    }

    seenKeys.add(key);
    parsedMap[key] = val;
  }

  for (const reqKey of allowedKeys) {
    if (!seenKeys.has(reqKey) || !parsedMap[reqKey]) {
      return {
        valid: false,
        reason: "MISSING_FIELD_IN_CONTROL_BLOCK",
        details: `Missing required key '${reqKey}' in AGENT_CONTROL_BLOCK_V1.`,
      };
    }
  }

  const rawState = parsedMap["state"];
  if (!CANONICAL_WORKFLOW_STATES.includes(rawState as CanonicalWorkflowState)) {
    return {
      valid: false,
      reason: "INVALID_CONTROL_STATE",
      details: `State '${rawState}' in AGENT_CONTROL_BLOCK_V1 is not a canonical workflow state.`,
    };
  }

  const scopeRev = parseCanonicalNonNegativeInteger(parsedMap["scope_revision"]);
  if (scopeRev === null || scopeRev < 1) {
    return {
      valid: false,
      reason: "INVALID_CONTROL_BLOCK",
      details: `scope_revision '${parsedMap["scope_revision"]}' must be a canonical positive integer.`,
    };
  }

  const fixReentries = parseCanonicalNonNegativeInteger(parsedMap["fix_reentries"]);
  if (fixReentries === null || fixReentries < 0 || fixReentries > 2) {
    return {
      valid: false,
      reason: "INVALID_CONTROL_BLOCK",
      details: `fix_reentries '${parsedMap["fix_reentries"]}' must be a canonical integer in range 0..2.`,
    };
  }

  const resetVal = parsedMap["owner_scope_reset"];
  if (scopeRev > 1 && (!resetVal || resetVal.toLowerCase() === "none")) {
    return {
      valid: false,
      reason: "INVALID_CONTROL_BLOCK",
      details: `owner_scope_reset must be present and non-empty for scope_revision > 1 (got '${resetVal}').`,
    };
  }

  return {
    valid: true,
    block: {
      state: rawState as CanonicalWorkflowState,
      scope_revision: scopeRev,
      fix_reentries: fixReentries,
      owner_scope_reset: resetVal,
    },
  };
}

/**
 * Validates the authoritative control issue:
 * 1. Checks issue structure
 * 2. Parses unique AGENT_CONTROL_BLOCK_V1
 * 3. Enforces exactly one primary state label matching block state
 * 4. Checks expected scope revision
 * 5. Requires state to be reviewable (ready-for-review or ready-for-verify)
 */
export function validateControlIssue(
  issueData: unknown,
  expectedScopeRevision?: number
): {
  valid: true;
  block: AgentControlBlock;
  primaryLabel: string;
} | {
  valid: false;
  reason: string;
  details: string;
} {
  if (!issueData || typeof issueData !== "object") {
    return {
      valid: false,
      reason: "ISSUE_FETCH_FAILED",
      details: "Authoritative control issue could not be fetched or is null/empty.",
    };
  }

  const issue = issueData as GitHubIssue;
  const parseResult = parseAgentControlBlock(issue.body);
  if (!parseResult.valid) {
    return parseResult;
  }

  const block = parseResult.block;

  if (expectedScopeRevision !== undefined && block.scope_revision !== expectedScopeRevision) {
    return {
      valid: false,
      reason: "WRONG_SCOPE_REVISION",
      details: `Authoritative control issue scope_revision (${block.scope_revision}) does not match expected (${expectedScopeRevision}).`,
    };
  }

  const rawLabels = issue.labels || [];
  const labelNames = rawLabels
    .map((l) => (typeof l === "string" ? l : l && l.name))
    .filter(Boolean);
  const primaryLabels = labelNames.filter((name) =>
    CANONICAL_WORKFLOW_STATES.includes(name as CanonicalWorkflowState)
  );

  if (primaryLabels.length === 0) {
    return {
      valid: false,
      reason: "ZERO_PRIMARY_STATE_LABELS",
      details: `Authoritative control issue #${issue.number || ""} has zero canonical primary workflow-state labels.`,
    };
  }

  if (primaryLabels.length > 1) {
    return {
      valid: false,
      reason: "MULTIPLE_PRIMARY_STATE_LABELS",
      details: `Authoritative control issue #${issue.number || ""} has multiple primary workflow-state labels: ${primaryLabels.join(", ")}.`,
    };
  }

  const primaryLabel = primaryLabels[0];
  if (primaryLabel !== block.state) {
    return {
      valid: false,
      reason: "LABEL_STATE_MISMATCH",
      details: `Authoritative issue primary label '${primaryLabel}' does not match Agent Control Block state '${block.state}'.`,
    };
  }

  if (!REVIEWABLE_CONTROL_STATES.includes(block.state as (typeof REVIEWABLE_CONTROL_STATES)[number])) {
    return {
      valid: false,
      reason: "INVALID_CONTROL_STATE",
      details: `Control issue state '${block.state}' is not reviewable (must be 'ready-for-review' or 'ready-for-verify').`,
    };
  }

  return {
    valid: true,
    block,
    primaryLabel,
  };
}

/**
 * Validates and parses Owner scope-reset approval record:
 * <!-- OWNER_SCOPE_RESET_V1 -->
 * old_scope_revision: <n>
 * new_scope_revision: <n+1>
 * reason: <non-empty>
 * material_scope_change: <non-empty>
 * owner_decision: APPROVED
 * approved_by: Banhtalon
 * <!-- /OWNER_SCOPE_RESET_V1 -->
 */
export function parseOwnerScopeResetApproval(
  commentData: unknown,
  expectedOldRev: number,
  expectedNewRev: number
): { valid: true; approval: OwnerScopeResetApproval } | { valid: false; reason: string; details: string } {
  if (!commentData || typeof commentData !== "object") {
    return {
      valid: false,
      reason: "MISSING_SCOPE_RESET_RECORD",
      details: "Scope-reset approval comment could not be fetched or is null.",
    };
  }

  const comment = commentData as GitHubIssueComment;

  // Provenance verification: Must be authored by Banhtalon (id: 105797112)
  if (comment.user?.login !== TRUSTED_OWNER_LOGIN || Number(comment.user?.id) !== TRUSTED_OWNER_ID) {
    return {
      valid: false,
      reason: "UNAUTHORIZED_SCOPE_RESET_AUTHOR",
      details: `Scope-reset comment author '${comment.user?.login}' (id: ${comment.user?.id}) is not the authorized owner (${TRUSTED_OWNER_LOGIN} / ${TRUSTED_OWNER_ID}).`,
    };
  }

  if (comment.author_association && comment.author_association !== "OWNER") {
    return {
      valid: false,
      reason: "UNAUTHORIZED_SCOPE_RESET_AUTHOR",
      details: `Scope-reset comment author association is '${comment.author_association}', expected 'OWNER'.`,
    };
  }

  const text = comment.body || "";
  const startMatches = text.match(/<!--\s*OWNER_SCOPE_RESET_V1\s*-->/gi) || [];
  const endMatches = text.match(/<!--\s*\/OWNER_SCOPE_RESET_V1\s*-->/gi) || [];

  if (startMatches.length === 0 || endMatches.length === 0) {
    return {
      valid: false,
      reason: "MISSING_OWNER_SCOPE_RESET_BLOCK",
      details: "Scope-reset comment is missing required OWNER_SCOPE_RESET_V1 markers.",
    };
  }

  if (startMatches.length > 1 || endMatches.length > 1) {
    return {
      valid: false,
      reason: "MULTIPLE_OWNER_SCOPE_RESET_BLOCKS",
      details: `Found multiple OWNER_SCOPE_RESET_V1 blocks (${startMatches.length} start, ${endMatches.length} end).`,
    };
  }

  const blockRegex = /<!--\s*OWNER_SCOPE_RESET_V1\s*-->([\s\S]*?)<!--\s*\/OWNER_SCOPE_RESET_V1\s*-->/i;
  const match = blockRegex.exec(text);
  if (!match) {
    return {
      valid: false,
      reason: "MISSING_OWNER_SCOPE_RESET_BLOCK",
      details: "Malformed OWNER_SCOPE_RESET_V1 block structure.",
    };
  }

  const allowedKeys = new Set([
    "old_scope_revision",
    "new_scope_revision",
    "reason",
    "material_scope_change",
    "owner_decision",
    "approved_by",
  ]);

  const lines = match[1].split(/\r?\n/);
  const seenKeys = new Set<string>();
  const parsedMap: Record<string, string> = {};

  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#")) continue;

    const colonIdx = line.indexOf(":");
    if (colonIdx === -1) {
      return {
        valid: false,
        reason: "MALFORMED_SCOPE_RESET",
        details: `Line does not contain separator ':': '${line}'`,
      };
    }

    const key = line.slice(0, colonIdx).trim();
    const val = line.slice(colonIdx + 1).trim();

    if (seenKeys.has(key)) {
      return {
        valid: false,
        reason: "DUPLICATE_KEY_IN_SCOPE_RESET",
        details: `Duplicate key '${key}' in OWNER_SCOPE_RESET_V1.`,
      };
    }

    if (!allowedKeys.has(key)) {
      return {
        valid: false,
        reason: "UNKNOWN_KEY_IN_SCOPE_RESET",
        details: `Unknown key '${key}' in OWNER_SCOPE_RESET_V1.`,
      };
    }

    seenKeys.add(key);
    parsedMap[key] = val;
  }

  for (const reqKey of allowedKeys) {
    if (!seenKeys.has(reqKey) || !parsedMap[reqKey]) {
      return {
        valid: false,
        reason: "MISSING_FIELD_IN_SCOPE_RESET",
        details: `Missing required key '${reqKey}' in OWNER_SCOPE_RESET_V1.`,
      };
    }
  }

  const oldRev = parseCanonicalNonNegativeInteger(parsedMap["old_scope_revision"]);
  const newRev = parseCanonicalNonNegativeInteger(parsedMap["new_scope_revision"]);

  if (oldRev === null || newRev === null) {
    return {
      valid: false,
      reason: "MALFORMED_SCOPE_RESET",
      details: "Scope revision numbers in OWNER_SCOPE_RESET_V1 must be canonical integers.",
    };
  }

  if (oldRev !== expectedOldRev || newRev !== expectedNewRev) {
    return {
      valid: false,
      reason: "SCOPE_RESET_REVISION_MISMATCH",
      details: `Scope reset revisions (${oldRev} -> ${newRev}) do not match expected (${expectedOldRev} -> ${expectedNewRev}).`,
    };
  }

  if (parsedMap["owner_decision"] !== "APPROVED") {
    return {
      valid: false,
      reason: "SCOPE_RESET_NOT_APPROVED",
      details: `owner_decision is '${parsedMap["owner_decision"]}', must be 'APPROVED'.`,
    };
  }

  if (parsedMap["approved_by"] !== TRUSTED_OWNER_LOGIN) {
    return {
      valid: false,
      reason: "SCOPE_RESET_WRONG_APPROVER",
      details: `approved_by is '${parsedMap["approved_by"]}', must be '${TRUSTED_OWNER_LOGIN}'.`,
    };
  }

  return {
    valid: true,
    approval: {
      old_scope_revision: oldRev,
      new_scope_revision: newRev,
      reason: parsedMap["reason"],
      material_scope_change: parsedMap["material_scope_change"],
      owner_decision: "APPROVED",
      approved_by: "Banhtalon",
    },
  };
}

/**
 * Validates whether a comment author is the authorized repository Owner.
 */
export function isAuthorizedOwnerComment(comment: GitHubIssueComment): boolean {
  if (!comment || typeof comment !== "object") return false;
  if (comment.user?.login !== TRUSTED_OWNER_LOGIN) return false;
  if (Number(comment.user?.id) !== TRUSTED_OWNER_ID) return false;
  if (comment.author_association && comment.author_association !== "OWNER") return false;
  return true;
}

/**
 * Compares whether two parsed attestation blocks are completely identical
 * across all normalized required fields.
 */
export function areAttestationsIdentical(a: TerraAttestation, b: TerraAttestation): boolean {
  if (!a || !b || a.malformed || b.malformed) {
    return false;
  }
  const fields: (keyof TerraAttestation)[] = [
    "reviewer_model",
    "head_sha",
    "pr_number",
    "control_issue",
    "scope_revision",
    "verdict",
    "p0",
    "p1",
    "material_findings_resolved",
    "reviewed_at_utc",
  ];
  for (const field of fields) {
    if (a[field] !== b[field]) {
      return false;
    }
  }
  return true;
}

function findDuplicateKeysInJson(jsonString: string): string | null {
  const keyRegex = /"([^"\\]*(?:\\.[^"\\]*)*)"\s*:/g;
  const seen = new Set<string>();
  let match: RegExpExecArray | null;
  while ((match = keyRegex.exec(jsonString)) !== null) {
    const key = match[1];
    if (seen.has(key)) {
      return key;
    }
    seen.add(key);
  }
  return null;
}

function hasNonCanonicalNumbersInJson(jsonString: string): string | null {
  const numRegex = /"(?:p0|p1|pr_number|control_issue|scope_revision)"\s*:\s*([^\s,}]+)/g;
  let m: RegExpExecArray | null;
  while ((m = numRegex.exec(jsonString)) !== null) {
    const rawVal = m[1].replace(/^["']|["']$/g, "");
    if (!/^(?:0|[1-9]\d*)$/.test(rawVal)) {
      return rawVal;
    }
  }
  return null;
}

/**
 * Parses a TERRA_REVIEW_ATTESTATION_V1 block (JSON or YAML).
 */
export function parseTerraAttestationBlock(content: string): TerraAttestation {
  if (!content || typeof content !== "string") {
    return {
      malformed: true,
      error: "Empty attestation content",
    } as TerraAttestation;
  }

  const trimmed = content.trim();

  // Try JSON first
  if (trimmed.startsWith("{") && trimmed.endsWith("}")) {
    const dupKey = findDuplicateKeysInJson(trimmed);
    if (dupKey) {
      return {
        malformed: true,
        error: `Duplicate key '${dupKey}' in JSON attestation block`,
      } as TerraAttestation;
    }
    const nonCanonical = hasNonCanonicalNumbersInJson(trimmed);
    if (nonCanonical !== null) {
      return {
        malformed: true,
        error: `Numeric field value '${nonCanonical}' is not a canonical non-negative decimal integer`,
      } as TerraAttestation;
    }
    try {
      const parsed = JSON.parse(trimmed);
      return normalizeAttestation(parsed);
    } catch (err) {
      return {
        malformed: true,
        error: `Invalid JSON in attestation: ${(err as Error).message}`,
      } as TerraAttestation;
    }
  }

  // Parse YAML / key-value lines
  const seenKeys = new Set<string>();
  const result: Record<string, unknown> = {};
  const lines = trimmed.split(/\r?\n/);
  for (const line of lines) {
    const trimmedLine = line.trim();
    if (!trimmedLine || trimmedLine.startsWith("#")) continue;
    const colonIdx = trimmedLine.indexOf(":");
    if (colonIdx === -1) continue;

    const key = trimmedLine.slice(0, colonIdx).trim();
    if (seenKeys.has(key)) {
      return {
        malformed: true,
        error: `Duplicate key '${key}' in attestation block`,
      } as TerraAttestation;
    }
    seenKeys.add(key);

    let val = trimmedLine.slice(colonIdx + 1).trim();

    if (
      (val.startsWith('"') && val.endsWith('"')) ||
      (val.startsWith("'") && val.endsWith("'"))
    ) {
      val = val.slice(1, -1).trim();
    }

    if (val.toLowerCase() === "true") {
      result[key] = true;
    } else if (val.toLowerCase() === "false") {
      result[key] = false;
    } else if (key !== "head_sha" && /^(?:0|[1-9]\d*)$/.test(val)) {
      result[key] = parseInt(val, 10);
    } else {
      result[key] = val;
    }
  }

  return normalizeAttestation(result);
}

function normalizeAttestation(raw: Record<string, unknown>): TerraAttestation {
  if (!raw || typeof raw !== "object") {
    return { malformed: true, error: "Attestation is not an object" } as TerraAttestation;
  }

  const requiredKeys = [
    "reviewer_model",
    "head_sha",
    "pr_number",
    "control_issue",
    "scope_revision",
    "verdict",
    "p0",
    "p1",
    "material_findings_resolved",
    "reviewed_at_utc",
  ];

  for (const key of requiredKeys) {
    if (raw[key] === undefined || raw[key] === null || raw[key] === "") {
      return {
        malformed: true,
        error: `Missing required field '${key}'`,
      } as TerraAttestation;
    }
  }

  const p0Num = parseCanonicalNonNegativeInteger(raw.p0);
  const p1Num = parseCanonicalNonNegativeInteger(raw.p1);
  const prNum = parseCanonicalNonNegativeInteger(raw.pr_number);
  const issueNum = parseCanonicalNonNegativeInteger(raw.control_issue);
  const scopeRev = parseCanonicalNonNegativeInteger(raw.scope_revision);

  if (p0Num === null || p1Num === null || prNum === null || issueNum === null || scopeRev === null) {
    return {
      malformed: true,
      error: "Numeric fields (p0, p1, pr_number, control_issue, scope_revision) must be canonical non-negative decimal integers",
    } as TerraAttestation;
  }

  const sha = String(raw.head_sha).trim().toLowerCase();
  if (!/^[0-9a-f]{40}$/i.test(sha)) {
    return {
      malformed: true,
      error: "head_sha must be a 40-character hexadecimal SHA",
    } as TerraAttestation;
  }

  const reviewedAt = typeof raw.reviewed_at_utc === "string" ? raw.reviewed_at_utc.trim() : "";
  if (!isValidStrictUtcCalendarIsoTimestamp(reviewedAt)) {
    return {
      malformed: true,
      error: `reviewed_at_utc must be a valid full ISO-8601 UTC timestamp ending in 'Z' (got '${raw.reviewed_at_utc}')`,
    } as TerraAttestation;
  }

  const matResolved = raw.material_findings_resolved === true || raw.material_findings_resolved === "true";

  return {
    malformed: false,
    reviewer_model: String(raw.reviewer_model).trim().toLowerCase() as "terra-xhigh",
    head_sha: sha,
    pr_number: prNum,
    control_issue: issueNum,
    scope_revision: scopeRev,
    verdict: String(raw.verdict).trim().toUpperCase() as "RECOMMEND_PASS" | "NEEDS_FIX" | "BLOCKED",
    p0: p0Num,
    p1: p1Num,
    material_findings_resolved: matResolved,
    reviewed_at_utc: reviewedAt,
  };
}

/**
 * Extracts attestation blocks from comment text:
 * Targets <!-- TERRA_REVIEW_ATTESTATION_V1 --> ... <!-- /TERRA_REVIEW_ATTESTATION_V1 -->
 * Also accepts fenced blocks with explicit marker: ```terra-attestation, ```json:terra-attestation, ```yaml:terra-attestation
 */
export function extractAttestationsFromCommentText(text: string): TerraAttestation[] {
  if (!text || typeof text !== "string") return [];

  const attestations: TerraAttestation[] = [];

  // V1 HTML comment markers
  const v1Regex = /<!--\s*TERRA_REVIEW_ATTESTATION_V1\s*-->([\s\S]*?)<!--\s*\/TERRA_REVIEW_ATTESTATION_V1\s*-->/gi;
  let match: RegExpExecArray | null;
  while ((match = v1Regex.exec(text)) !== null) {
    attestations.push(parseTerraAttestationBlock(match[1]));
  }

  // Fenced blocks with explicit tag
  if (attestations.length === 0) {
    const explicitRegex = /```(?:terra-attestation|json:terra-attestation|yaml:terra-attestation)[\r\n]+([\s\S]*?)```/gi;
    while ((match = explicitRegex.exec(text)) !== null) {
      attestations.push(parseTerraAttestationBlock(match[1]));
    }
  }

  return attestations;
}

/**
 * Parses and filters attestations from PR top-level comments:
 * 1. Provenance filtering: Keeps ONLY comments authored by Banhtalon (id: 105797112, association: OWNER).
 * 2. Sorts comments chronologically by created_at / id.
 * 3. Extracts V1 attestation blocks.
 * 4. Rejects multiple non-identical blocks in a single comment as conflicting.
 */
export function extractOwnerAttestationsFromComments(
  comments: GitHubIssueComment[]
): TerraAttestation[] {
  if (!Array.isArray(comments) || comments.length === 0) {
    return [];
  }

  // Filter strictly to authorized owner comments
  const authorizedComments = comments.filter(isAuthorizedOwnerComment);

  // Sort chronologically
  const sorted = [...authorizedComments].sort((a, b) => {
    const timeA = new Date(a.created_at || 0).getTime();
    const timeB = new Date(b.created_at || 0).getTime();
    if (timeA !== timeB) return timeA - timeB;
    return (Number(a.id) || 0) - (Number(b.id) || 0);
  });

  const parsedEntries: TerraAttestation[] = [];

  for (const comment of sorted) {
    const found = extractAttestationsFromCommentText(comment.body || "");
    if (found.length === 0) continue;

    if (found.length > 1) {
      const first = found[0];
      const allIdentical = found.every((item) => areAttestationsIdentical(first, item));
      if (!allIdentical) {
        parsedEntries.push({
          conflicting: true,
          commentId: comment.id,
          createdAt: comment.created_at,
          error: "Multiple conflicting or non-identical attestation blocks found in the same comment",
        } as TerraAttestation);
        continue;
      }
      parsedEntries.push({
        ...first,
        commentId: comment.id,
        createdAt: comment.created_at,
      });
    } else {
      parsedEntries.push({
        ...found[0],
        commentId: comment.id,
        createdAt: comment.created_at,
      });
    }
  }

  return parsedEntries;
}

/**
 * Evaluates review gate conditions deterministically:
 * - Validates control issue
 * - Validates scope reset approval (if revision > 1)
 * - Evaluates latest authorized Terra attestation
 */
export function validateReviewGate({
  attestations,
  expectedHeadSha,
  expectedPrNumber,
  expectedControlIssue,
  expectedScopeRevision,
  controlIssueData,
  scopeResetCommentData,
}: {
  attestations: TerraAttestation[];
  expectedHeadSha: string;
  expectedPrNumber: number;
  expectedControlIssue?: number;
  expectedScopeRevision?: number;
  controlIssueData?: unknown;
  scopeResetCommentData?: unknown;
}): ValidationResult {
  let controlBlock: AgentControlBlock | undefined;
  let scopeResetApproval: OwnerScopeResetApproval | undefined;

  // 1. Validate control issue
  if (controlIssueData !== undefined) {
    const issueResult = validateControlIssue(controlIssueData, expectedScopeRevision);
    if (!issueResult.valid) {
      return issueResult;
    }
    controlBlock = issueResult.block;
    if (expectedScopeRevision === undefined) {
      expectedScopeRevision = controlBlock.scope_revision;
    }

    // 2. Validate scope-reset approval comment if scope_revision > 1
    if (controlBlock.scope_revision > 1) {
      const scopeResetResult = parseOwnerScopeResetApproval(
        scopeResetCommentData,
        controlBlock.scope_revision - 1,
        controlBlock.scope_revision
      );
      if (!scopeResetResult.valid) {
        return scopeResetResult;
      }
      scopeResetApproval = scopeResetResult.approval;
    }
  }

  // 3. Attestation checks
  if (!attestations || !Array.isArray(attestations) || attestations.length === 0) {
    return {
      valid: false,
      reason: "NO_ATTESTATION_FOUND",
      details: "No authorized Terra attestation found in top-level PR comments.",
    };
  }

  // Latest-attestation precedence
  const latest = attestations[attestations.length - 1];

  if (latest.conflicting) {
    return {
      valid: false,
      reason: "CONFLICTING_ATTESTATIONS",
      details: latest.error || "Conflicting attestations found in the latest comment.",
    };
  }

  if (latest.malformed) {
    return {
      valid: false,
      reason: "MALFORMED_ATTESTATION",
      details: latest.error || "Attestation block is malformed or missing required fields.",
    };
  }

  if (latest.reviewer_model !== "terra-xhigh") {
    return {
      valid: false,
      reason: "INVALID_REVIEWER_MODEL",
      details: `Expected reviewer_model 'terra-xhigh', got '${latest.reviewer_model}'.`,
    };
  }

  const normalizedExpectedHead = String(expectedHeadSha || "").trim().toLowerCase();
  if (!normalizedExpectedHead || latest.head_sha !== normalizedExpectedHead) {
    return {
      valid: false,
      reason: "STALE_HEAD_SHA",
      details: `Attestation head_sha '${latest.head_sha}' does not match current PR head_sha '${normalizedExpectedHead}'.`,
    };
  }

  if (expectedPrNumber !== undefined && latest.pr_number !== Number(expectedPrNumber)) {
    return {
      valid: false,
      reason: "WRONG_PR_NUMBER",
      details: `Attestation pr_number '${latest.pr_number}' does not match expected PR #${expectedPrNumber}.`,
    };
  }

  if (expectedControlIssue !== undefined && latest.control_issue !== Number(expectedControlIssue)) {
    return {
      valid: false,
      reason: "WRONG_CONTROL_ISSUE",
      details: `Attestation control_issue '${latest.control_issue}' does not match expected issue #${expectedControlIssue}.`,
    };
  }

  if (expectedScopeRevision !== undefined && latest.scope_revision !== Number(expectedScopeRevision)) {
    return {
      valid: false,
      reason: "WRONG_SCOPE_REVISION",
      details: `Attestation scope_revision '${latest.scope_revision}' does not match expected scope revision ${expectedScopeRevision}.`,
    };
  }

  if (latest.verdict === "NEEDS_FIX") {
    return {
      valid: false,
      reason: "VERDICT_NEEDS_FIX",
      details: "Terra verdict is NEEDS_FIX.",
    };
  }

  if (latest.verdict === "BLOCKED") {
    return {
      valid: false,
      reason: "VERDICT_BLOCKED",
      details: "Terra verdict is BLOCKED.",
    };
  }

  if (latest.verdict !== "RECOMMEND_PASS") {
    return {
      valid: false,
      reason: "INVALID_VERDICT",
      details: `Attestation verdict '${latest.verdict}' is not RECOMMEND_PASS.`,
    };
  }

  if (latest.p0 !== 0) {
    return {
      valid: false,
      reason: "UNRESOLVED_P0_FINDINGS",
      details: `Attestation reports ${latest.p0} unresolved P0 finding(s). Must be exactly 0.`,
    };
  }

  if (latest.p1 !== 0) {
    return {
      valid: false,
      reason: "UNRESOLVED_P1_FINDINGS",
      details: `Attestation reports ${latest.p1} unresolved P1 finding(s). Must be exactly 0.`,
    };
  }

  if (latest.material_findings_resolved !== true) {
    return {
      valid: false,
      reason: "MATERIAL_FINDINGS_NOT_RESOLVED",
      details: "material_findings_resolved must be true.",
    };
  }

  return {
    valid: true,
    reason: "OK",
    attestation: latest,
    controlBlock: controlBlock!,
    scopeResetApproval,
  };
}
