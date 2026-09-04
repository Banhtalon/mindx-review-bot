/* global console */

import { readFileSync } from "node:fs";
import { request as httpsRequest } from "node:https";
import process from "node:process";
import { URL } from "node:url";

export const CANONICAL_WORKFLOW_STATES = [
  "needs-plan",
  "ready-for-implementation",
  "implementing",
  "ready-for-review",
  "needs-fix",
  "ready-for-verify",
  "done",
  "blocked-owner",
  "blocked-external",
];

export const REVIEWABLE_CONTROL_STATES = [
  "ready-for-review",
  "ready-for-verify",
];

export const BOOTSTRAP_PR_NUMBER = 6;
export const BOOTSTRAP_CONTROL_ISSUE = 7;
export const BOOTSTRAP_SCOPE_REVISION = 2;

/**
 * Validates and parses a canonical non-negative decimal integer.
 * Accepts only canonical non-negative decimal integers (e.g. 0, 1, 2).
 * Rejects negative numbers (-1), explicit signs (+1), floats (0.5, 1.0),
 * exponent notation (1e5), leading zeros (01), and whitespace.
 */
export function parseCanonicalNonNegativeInteger(val) {
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
 * Validates that reviewed_at_utc is a strict ISO-8601 UTC timestamp ending in 'Z'.
 * Rejects date-only values, local timestamps without Z, and offsets like +07:00.
 */
export function isValidStrictUtcIsoTimestamp(val) {
  if (typeof val !== "string") return false;
  const trimmed = val.trim();
  const strictUtcRegex = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$/;
  if (!strictUtcRegex.test(trimmed)) {
    return false;
  }
  const timestamp = Date.parse(trimmed);
  return !isNaN(timestamp);
}

function findDuplicateKeysInJson(jsonString) {
  const keyRegex = /"([^"\\]*(?:\\.[^"\\]*)*)"\s*:/g;
  const seen = new Set();
  let match;
  while ((match = keyRegex.exec(jsonString)) !== null) {
    const key = match[1];
    if (seen.has(key)) {
      return key;
    }
    seen.add(key);
  }
  return null;
}

function hasNonCanonicalNumbersInJson(jsonString) {
  const numRegex = /"(?:p0|p1|pr_number|control_issue|scope_revision)"\s*:\s*([^\s,}]+)/g;
  let m;
  while ((m = numRegex.exec(jsonString)) !== null) {
    const rawVal = m[1].replace(/^["']|["']$/g, "");
    if (!/^(?:0|[1-9]\d*)$/.test(rawVal)) {
      return rawVal;
    }
  }
  return null;
}

/**
 * Compares whether two parsed attestation blocks are completely identical
 * across all normalized required fields.
 */
export function areAttestationsIdentical(a, b) {
  if (!a || !b || a.malformed || b.malformed) {
    return false;
  }
  const fields = [
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

/**
 * Parses a string content (either JSON or YAML-like key-value pairs)
 * into a structured attestation object.
 * Duplicate keys and non-canonical forms fail closed.
 */
export function parseTerraAttestationBlock(content) {
  if (!content || typeof content !== "string") {
    return { malformed: true, error: "Empty attestation content" };
  }

  const trimmed = content.trim();

  // Try JSON parsing first if wrapped in { ... }
  if (trimmed.startsWith("{") && trimmed.endsWith("}")) {
    const dupKey = findDuplicateKeysInJson(trimmed);
    if (dupKey) {
      return { malformed: true, error: `Duplicate key '${dupKey}' in JSON attestation block` };
    }
    const nonCanonical = hasNonCanonicalNumbersInJson(trimmed);
    if (nonCanonical !== null) {
      return {
        malformed: true,
        error: `Numeric field value '${nonCanonical}' is not a canonical non-negative decimal integer`,
      };
    }
    try {
      const parsed = JSON.parse(trimmed);
      return normalizeAttestation(parsed);
    } catch (err) {
      return { malformed: true, error: `Invalid JSON in attestation: ${err.message}` };
    }
  }

  // Parse YAML / key-value lines
  const seenKeys = new Set();
  const result = {};
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
      };
    }
    seenKeys.add(key);

    let val = trimmedLine.slice(colonIdx + 1).trim();

    // Remove quotes
    if (
      (val.startsWith('"') && val.endsWith('"')) ||
      (val.startsWith("'") && val.endsWith("'"))
    ) {
      val = val.slice(1, -1).trim();
    }

    // Coerce booleans / numbers
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

function normalizeAttestation(raw) {
  if (!raw || typeof raw !== "object") {
    return { malformed: true, error: "Attestation is not an object" };
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
        raw,
      };
    }
  }

  // Strict numeric checks
  const p0Num = parseCanonicalNonNegativeInteger(raw.p0);
  const p1Num = parseCanonicalNonNegativeInteger(raw.p1);
  const prNum = parseCanonicalNonNegativeInteger(raw.pr_number);
  const issueNum = parseCanonicalNonNegativeInteger(raw.control_issue);
  const scopeRev = parseCanonicalNonNegativeInteger(raw.scope_revision);

  if (p0Num === null || p1Num === null || prNum === null || issueNum === null || scopeRev === null) {
    return {
      malformed: true,
      error: "Numeric fields (p0, p1, pr_number, control_issue, scope_revision) must be canonical non-negative decimal integers",
      raw,
    };
  }

  const sha = String(raw.head_sha).trim().toLowerCase();
  if (!/^[0-9a-f]{40}$/i.test(sha)) {
    return {
      malformed: true,
      error: "head_sha must be a 40-character hexadecimal SHA",
      raw,
    };
  }

  const reviewedAt = typeof raw.reviewed_at_utc === "string" ? raw.reviewed_at_utc.trim() : "";
  if (!isValidStrictUtcIsoTimestamp(reviewedAt)) {
    return {
      malformed: true,
      error: `reviewed_at_utc must be a valid full ISO-8601 UTC timestamp ending in 'Z' (e.g. '2026-09-04T01:23:45Z'), got '${raw.reviewed_at_utc}'`,
      raw,
    };
  }

  const matResolved = raw.material_findings_resolved === true || raw.material_findings_resolved === "true";

  return {
    malformed: false,
    reviewer_model: String(raw.reviewer_model).trim().toLowerCase(),
    head_sha: sha,
    pr_number: prNum,
    control_issue: issueNum,
    scope_revision: scopeRev,
    verdict: String(raw.verdict).trim().toUpperCase(),
    p0: p0Num,
    p1: p1Num,
    material_findings_resolved: matResolved,
    reviewed_at_utc: reviewedAt,
    raw,
  };
}

/**
 * Extracts all attestation blocks from markdown text.
 */
export function extractAttestationsFromText(text) {
  if (!text || typeof text !== "string") return [];

  const attestations = [];

  // Match TERRA_REVIEW_ATTESTATION_V1 blocks: <!-- TERRA_REVIEW_ATTESTATION_V1 --> ... <!-- /TERRA_REVIEW_ATTESTATION_V1 -->
  const v1Regex = /<!--\s*TERRA_REVIEW_ATTESTATION_V1\s*-->([\s\S]*?)<!--\s*\/TERRA_REVIEW_ATTESTATION_V1\s*-->/gi;
  let match;
  while ((match = v1Regex.exec(text)) !== null) {
    attestations.push(parseTerraAttestationBlock(match[1]));
  }

  // Match fenced blocks with explicit language: ```terra-attestation, ```json:terra-attestation, ```yaml:terra-attestation
  const explicitRegex = /```(?:terra-attestation|json:terra-attestation|yaml:terra-attestation)[\r\n]+([\s\S]*?)```/gi;
  while ((match = explicitRegex.exec(text)) !== null) {
    attestations.push(parseTerraAttestationBlock(match[1]));
  }

  // Also match HTML comment blocks: <!-- terra-attestation ... -->
  const htmlCommentRegex = /<!--\s*terra-attestation\s*([\s\S]*?)-->/gi;
  while ((match = htmlCommentRegex.exec(text)) !== null) {
    attestations.push(parseTerraAttestationBlock(match[1]));
  }

  // Also match generic fenced code blocks if they contain "reviewer_model"
  if (attestations.length === 0) {
    const genericCodeFence = /```(?:json|yaml|text)?[\r\n]+([\s\S]*?)```/gi;
    while ((match = genericCodeFence.exec(text)) !== null) {
      if (match[1].includes("reviewer_model")) {
        attestations.push(parseTerraAttestationBlock(match[1]));
      }
    }
  }

  return attestations;
}

/**
 * Parses attestations from a list of GitHub comments/reviews in chronological order.
 * Multi-block comments fail closed unless all normalized fields are completely identical.
 * Later attestations override earlier ones according to latest-attestation precedence.
 */
export function parseAttestationsFromComments(comments) {
  if (!Array.isArray(comments) || comments.length === 0) {
    return [];
  }

  // Sort chronologically by created_at or submitted_at or id
  const sorted = [...comments].sort((a, b) => {
    const timeA = new Date(a.created_at || a.submitted_at || 0).getTime();
    const timeB = new Date(b.created_at || b.submitted_at || 0).getTime();
    if (timeA !== timeB) return timeA - timeB;
    return (Number(a.id) || 0) - (Number(b.id) || 0);
  });

  const parsedEntries = [];

  for (const comment of sorted) {
    const body = comment.body || "";
    const found = extractAttestationsFromText(body);
    if (found.length === 0) continue;

    if (found.length > 1) {
      // Multiple attestation blocks in the same comment must be 100% identical
      const first = found[0];
      const allIdentical = found.every((item) => areAttestationsIdentical(first, item));
      if (!allIdentical) {
        parsedEntries.push({
          conflicting: true,
          commentId: comment.id,
          error: "Multiple conflicting or non-identical attestation blocks found in the same comment",
        });
        continue;
      }
      // Deduplicate identical blocks
      parsedEntries.push({
        ...first,
        commentId: comment.id,
        createdAt: comment.created_at || comment.submitted_at,
      });
    } else {
      parsedEntries.push({
        ...found[0],
        commentId: comment.id,
        createdAt: comment.created_at || comment.submitted_at,
      });
    }
  }

  return parsedEntries;
}

/**
 * Parses Agent Control Block from issue/PR body markdown.
 */
export function parseControlBlock(text) {
  if (!text) return {};
  const blockMatch = /```text[\r\n]+([\s\S]*?)```/i.exec(text) || [null, text];
  const content = blockMatch[1] || text;
  const result = {};
  for (const line of content.split(/\r?\n/)) {
    const idx = line.indexOf(":");
    if (idx !== -1) {
      const k = line.slice(0, idx).trim();
      const v = line.slice(idx + 1).trim();
      if (k === "state" || k === "scope_revision" || k === "fix_reentries" || k === "owner_scope_reset") {
        result[k] = v;
      }
    }
  }
  return result;
}

/**
 * Validates the authoritative control issue:
 * 1. Must exist (fetch did not fail)
 * 2. Must contain valid, complete Agent Control Block:
 *    - state
 *    - scope_revision (canonical non-negative integer)
 *    - fix_reentries (canonical integer in 0..2)
 *    - owner_scope_reset (non-empty / non-none for scope_revision >= 2)
 * 3. Must match expected scope_revision (if provided)
 * 4. Must have exactly one primary workflow-state label
 * 5. Primary label must match Agent Control Block state
 * 6. State must be reviewable (ready-for-review or ready-for-verify)
 */
export function validateControlIssue(issueData, expectedScopeRevision) {
  if (!issueData || typeof issueData !== "object") {
    return {
      valid: false,
      reason: "ISSUE_FETCH_FAILED",
      details: "Authoritative control issue could not be fetched or is null/empty.",
    };
  }

  const controlBlock = parseControlBlock(issueData.body || "");
  const requiredFields = ["state", "scope_revision", "fix_reentries", "owner_scope_reset"];
  for (const field of requiredFields) {
    if (controlBlock[field] === undefined || controlBlock[field] === null || controlBlock[field].trim() === "") {
      return {
        valid: false,
        reason: "MISSING_AGENT_CONTROL_BLOCK",
        details: `Authoritative control issue Agent Control Block is missing required field '${field}'.`,
      };
    }
  }

  const issueScopeRev = parseCanonicalNonNegativeInteger(controlBlock.scope_revision);
  if (issueScopeRev === null) {
    return {
      valid: false,
      reason: "MISSING_AGENT_CONTROL_BLOCK",
      details: `Agent Control Block scope_revision '${controlBlock.scope_revision}' is not a valid canonical integer.`,
    };
  }

  if (expectedScopeRevision !== undefined && issueScopeRev !== Number(expectedScopeRevision)) {
    return {
      valid: false,
      reason: "WRONG_SCOPE_REVISION",
      details: `Authoritative control issue scope_revision (${issueScopeRev}) does not match expected (${expectedScopeRevision}).`,
    };
  }

  const fixReentries = parseCanonicalNonNegativeInteger(controlBlock.fix_reentries);
  if (fixReentries === null || fixReentries < 0 || fixReentries > 2) {
    return {
      valid: false,
      reason: "INVALID_CONTROL_BLOCK",
      details: `Agent Control Block fix_reentries '${controlBlock.fix_reentries}' must be a canonical integer in allowed range 0..2.`,
    };
  }

  const resetVal = controlBlock.owner_scope_reset.trim();
  if (issueScopeRev >= 2) {
    if (!resetVal || resetVal.toLowerCase() === "none") {
      return {
        valid: false,
        reason: "INVALID_CONTROL_BLOCK",
        details: `Agent Control Block owner_scope_reset must be present and non-empty for scope_revision >= 2 (got '${resetVal}').`,
      };
    }
  }

  const rawLabels = issueData.labels || [];
  const labelNames = rawLabels
    .map((l) => (typeof l === "string" ? l : l && l.name))
    .filter(Boolean);
  const primaryLabels = labelNames.filter((name) => CANONICAL_WORKFLOW_STATES.includes(name));

  if (primaryLabels.length === 0) {
    return {
      valid: false,
      reason: "ZERO_PRIMARY_STATE_LABELS",
      details: `Authoritative control issue #${issueData.number || ""} has zero canonical primary workflow-state labels.`,
    };
  }

  if (primaryLabels.length > 1) {
    return {
      valid: false,
      reason: "MULTIPLE_PRIMARY_STATE_LABELS",
      details: `Authoritative control issue #${issueData.number || ""} has multiple primary workflow-state labels: ${primaryLabels.join(", ")}.`,
    };
  }

  const primaryLabel = primaryLabels[0];
  if (primaryLabel !== controlBlock.state) {
    return {
      valid: false,
      reason: "LABEL_STATE_MISMATCH",
      details: `Authoritative issue primary label '${primaryLabel}' does not match Agent Control Block state '${controlBlock.state}'.`,
    };
  }

  if (!REVIEWABLE_CONTROL_STATES.includes(controlBlock.state)) {
    return {
      valid: false,
      reason: "INVALID_CONTROL_STATE",
      details: `Control issue state '${controlBlock.state}' is not reviewable (must be 'ready-for-review' or 'ready-for-verify').`,
    };
  }

  return {
    valid: true,
    reason: "OK",
    controlBlock,
    primaryLabel,
    scopeRevision: issueScopeRev,
    fixReentries,
    state: controlBlock.state,
  };
}

/**
 * Core deterministic validator function.
 */
export function validateTerraAttestation({
  attestations,
  expectedHeadSha,
  expectedPrNumber,
  expectedControlIssue,
  expectedScopeRevision,
  controlIssueData,
}) {
  // Validate control issue if provided
  if (controlIssueData !== undefined) {
    const issueResult = validateControlIssue(controlIssueData, expectedScopeRevision);
    if (!issueResult.valid) {
      return issueResult;
    }
    if (expectedScopeRevision === undefined) {
      expectedScopeRevision = issueResult.scopeRevision;
    }
  }

  if (!attestations || !Array.isArray(attestations) || attestations.length === 0) {
    return {
      valid: false,
      reason: "NO_ATTESTATION_FOUND",
      details: "No Terra attestation block found in PR comments or reviews.",
    };
  }

  // Later-attestation precedence: inspect the most recent attestation entry
  const latest = attestations[attestations.length - 1];

  if (latest.conflicting) {
    return {
      valid: false,
      reason: "CONFLICTING_ATTESTATIONS",
      details: latest.error || "Conflicting attestations found in the latest review comment.",
    };
  }

  if (latest.malformed) {
    return {
      valid: false,
      reason: "MALFORMED_ATTESTATION",
      details: latest.error || "Attestation block is malformed or missing required fields.",
    };
  }

  // Model check
  if (latest.reviewer_model !== "terra-xhigh") {
    return {
      valid: false,
      reason: "INVALID_REVIEWER_MODEL",
      details: `Expected reviewer_model 'terra-xhigh', got '${latest.reviewer_model}'.`,
    };
  }

  // Exact head SHA check
  const normalizedExpectedHead = String(expectedHeadSha || "").trim().toLowerCase();
  if (!normalizedExpectedHead || latest.head_sha !== normalizedExpectedHead) {
    return {
      valid: false,
      reason: "STALE_HEAD_SHA",
      details: `Attestation head_sha '${latest.head_sha}' does not match current PR head_sha '${normalizedExpectedHead}'.`,
    };
  }

  // PR number check
  if (expectedPrNumber !== undefined && latest.pr_number !== Number(expectedPrNumber)) {
    return {
      valid: false,
      reason: "WRONG_PR_NUMBER",
      details: `Attestation pr_number '${latest.pr_number}' does not match expected PR #${expectedPrNumber}.`,
    };
  }

  // Control issue check
  if (expectedControlIssue !== undefined && latest.control_issue !== Number(expectedControlIssue)) {
    return {
      valid: false,
      reason: "WRONG_CONTROL_ISSUE",
      details: `Attestation control_issue '${latest.control_issue}' does not match expected issue #${expectedControlIssue}.`,
    };
  }

  // Scope revision check
  if (expectedScopeRevision !== undefined && latest.scope_revision !== Number(expectedScopeRevision)) {
    return {
      valid: false,
      reason: "WRONG_SCOPE_REVISION",
      details: `Attestation scope_revision '${latest.scope_revision}' does not match expected scope revision ${expectedScopeRevision}.`,
    };
  }

  // Verdict check
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

  // Strict P0 check: exact 0 required
  if (latest.p0 !== 0) {
    return {
      valid: false,
      reason: "UNRESOLVED_P0_FINDINGS",
      details: `Attestation reports ${latest.p0} unresolved P0 finding(s). Must be exactly 0.`,
    };
  }

  // Strict P1 check: exact 0 required
  if (latest.p1 !== 0) {
    return {
      valid: false,
      reason: "UNRESOLVED_P1_FINDINGS",
      details: `Attestation reports ${latest.p1} unresolved P1 finding(s). Must be exactly 0.`,
    };
  }

  // Material findings resolved check
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
  };
}

// GitHub API helper
function githubApiGet(url, token) {
  return new Promise((resolve, reject) => {
    const parsedUrl = new URL(url);
    const options = {
      hostname: parsedUrl.hostname,
      path: parsedUrl.pathname + parsedUrl.search,
      method: "GET",
      headers: {
        "User-Agent": "mindx-review-gate",
        Accept: "application/vnd.github+json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    };

    const req = httpsRequest(options, (res) => {
      let data = "";
      res.on("data", (chunk) => (data += chunk));
      res.on("end", () => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          try {
            resolve(JSON.parse(data));
          } catch (e) {
            reject(new Error(`Failed to parse JSON response: ${e.message}`));
          }
        } else {
          reject(new Error(`GitHub API error ${res.statusCode}: ${data}`));
        }
      });
    });

    req.on("error", reject);
    req.end();
  });
}

/**
 * Deterministically fetches all paginated items from a GitHub REST endpoint
 * until there are no further pages or returned page length < perPage.
 */
export async function fetchAllPagedItems(baseUrl, token, getFn = githubApiGet) {
  const allItems = [];
  let page = 1;
  const perPage = 100;
  while (true) {
    const separator = baseUrl.includes("?") ? "&" : "?";
    const pageUrl = `${baseUrl}${separator}per_page=${perPage}&page=${page}`;
    const items = await getFn(pageUrl, token);
    if (!Array.isArray(items) || items.length === 0) {
      break;
    }
    allItems.push(...items);
    if (items.length < perPage) {
      break;
    }
    page++;
  }
  return allItems;
}

function parseCliArgs() {
  const args = process.argv.slice(2);
  const parsed = {};
  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (arg.startsWith("--")) {
      const key = arg.slice(2);
      const next = args[i + 1];
      if (next && !next.startsWith("--")) {
        parsed[key] = next;
        i++;
      } else {
        parsed[key] = true;
      }
    }
  }
  return parsed;
}

/**
 * Main execution routine for CLI.
 */
async function main() {
  const args = parseCliArgs();

  // If input file is given, run file mode (used in offline testing)
  if (args.file) {
    const fileContent = readFileSync(args.file, "utf8");
    let attestations;
    try {
      const json = JSON.parse(fileContent);
      attestations = Array.isArray(json)
        ? parseAttestationsFromComments(json)
        : [normalizeAttestation(json)];
    } catch {
      attestations = extractAttestationsFromText(fileContent);
    }

    if (args["control-issue-fetch-fail"]) {
      console.error("[FAIL] review-gate failed closed: [ISSUE_FETCH_FAILED] Authoritative control issue could not be fetched.");
      process.exit(1);
    }

    let controlIssueData;
    if (args["control-issue-file"]) {
      try {
        controlIssueData = JSON.parse(readFileSync(args["control-issue-file"], "utf8"));
      } catch (err) {
        console.error(`[FAIL] review-gate failed closed: Failed to read control issue file: ${err.message}`);
        process.exit(1);
      }
    }

    const prNumber = args.pr ? Number(args.pr) : process.env.PR_NUMBER ? Number(process.env.PR_NUMBER) : undefined;
    let expectedControlIssue = args["control-issue"]
      ? Number(args["control-issue"])
      : process.env.CONTROL_ISSUE
      ? Number(process.env.CONTROL_ISSUE)
      : undefined;
    let expectedScopeRevision = args["scope-revision"]
      ? Number(args["scope-revision"])
      : process.env.SCOPE_REVISION
      ? Number(process.env.SCOPE_REVISION)
      : undefined;

    // Immutable bootstrap binding for PR #6
    if (prNumber === BOOTSTRAP_PR_NUMBER) {
      if (expectedControlIssue !== undefined && expectedControlIssue !== BOOTSTRAP_CONTROL_ISSUE) {
        console.error(`[FAIL] review-gate failed closed: PR #${BOOTSTRAP_PR_NUMBER} bootstrap must bind to control issue #${BOOTSTRAP_CONTROL_ISSUE}, got #${expectedControlIssue}`);
        process.exit(1);
      }
      if (expectedScopeRevision !== undefined && expectedScopeRevision !== BOOTSTRAP_SCOPE_REVISION) {
        console.error(`[FAIL] review-gate failed closed: PR #${BOOTSTRAP_PR_NUMBER} bootstrap must bind to scope revision ${BOOTSTRAP_SCOPE_REVISION}, got ${expectedScopeRevision}`);
        process.exit(1);
      }
      expectedControlIssue = BOOTSTRAP_CONTROL_ISSUE;
      expectedScopeRevision = BOOTSTRAP_SCOPE_REVISION;
    }

    const result = validateTerraAttestation({
      attestations,
      expectedHeadSha: args["head-sha"] || process.env.HEAD_SHA,
      expectedPrNumber: prNumber,
      expectedControlIssue,
      expectedScopeRevision,
      controlIssueData,
    });

    if (result.valid) {
      console.log(`[PASS] Terra attestation verified: ${JSON.stringify(result.attestation)}`);
      process.exit(0);
    } else {
      console.error(`[FAIL] Review gate check failed: [${result.reason}] ${result.details}`);
      process.exit(1);
    }
  }

  // GitHub Actions API mode
  const token = process.env.GITHUB_TOKEN;
  const repo = process.env.GITHUB_REPOSITORY || process.env.REPOSITORY || args.repo;
  const rawPrNumber = args.pr || process.env.PR_NUMBER;
  const prNumber = rawPrNumber ? Number(rawPrNumber) : undefined;
  let headSha = args["head-sha"] || process.env.HEAD_SHA;
  let controlIssue = args["control-issue"] || process.env.CONTROL_ISSUE;
  let scopeRevision = args["scope-revision"] || process.env.SCOPE_REVISION;

  if (!repo || !prNumber) {
    console.error("[ERROR] Missing required environment/args: GITHUB_REPOSITORY and PR_NUMBER are required.");
    process.exit(1);
  }

  // Immutable bootstrap binding for PR #6
  if (prNumber === BOOTSTRAP_PR_NUMBER) {
    if (controlIssue && Number(controlIssue) !== BOOTSTRAP_CONTROL_ISSUE) {
      console.error(`[FAIL] review-gate failed closed: PR #${BOOTSTRAP_PR_NUMBER} bootstrap must bind to control issue #${BOOTSTRAP_CONTROL_ISSUE}, got #${controlIssue}`);
      process.exit(1);
    }
    if (scopeRevision && Number(scopeRevision) !== BOOTSTRAP_SCOPE_REVISION) {
      console.error(`[FAIL] review-gate failed closed: PR #${BOOTSTRAP_PR_NUMBER} bootstrap must bind to scope revision ${BOOTSTRAP_SCOPE_REVISION}, got ${scopeRevision}`);
      process.exit(1);
    }
    controlIssue = BOOTSTRAP_CONTROL_ISSUE;
    scopeRevision = BOOTSTRAP_SCOPE_REVISION;
  }

  try {
    // 1. Fetch PR details
    const pr = await githubApiGet(`https://api.github.com/repos/${repo}/pulls/${prNumber}`, token);
    headSha = headSha || pr.head.sha;

    if (!controlIssue) {
      const issueMatch = /(?:Authoritative control issue|Linked issue|Linked GitHub issue):\s*#?(\d+)/i.exec(pr.body || "");
      if (issueMatch) {
        controlIssue = issueMatch[1];
      }
    }

    if (!controlIssue) {
      console.error("[FAIL] review-gate failed closed: No linked authoritative control issue found.");
      process.exit(1);
    }

    // 2. Fetch linked authoritative control issue from GitHub API (fail closed, NO FALLBACK)
    let issueData;
    try {
      issueData = await githubApiGet(`https://api.github.com/repos/${repo}/issues/${controlIssue}`, token);
    } catch (err) {
      console.error(`[FAIL] review-gate failed closed: [ISSUE_FETCH_FAILED] Failed to fetch linked control issue #${controlIssue}: ${err.message}`);
      process.exit(1);
    }

    // 3. Validate control issue state, complete control block, and labels
    const issueValidation = validateControlIssue(
      issueData,
      scopeRevision ? Number(scopeRevision) : undefined
    );

    if (!issueValidation.valid) {
      console.error(`[FAIL] review-gate failed closed: [${issueValidation.reason}] ${issueValidation.details}`);
      process.exit(1);
    }

    scopeRevision = issueValidation.scopeRevision;

    // 4. Fetch all pages of issue comments & PR reviews
    const commentsUrl = `https://api.github.com/repos/${repo}/issues/${prNumber}/comments`;
    const reviewsUrl = `https://api.github.com/repos/${repo}/pulls/${prNumber}/reviews`;

    const comments = await fetchAllPagedItems(commentsUrl, token);
    const reviews = await fetchAllPagedItems(reviewsUrl, token);

    const allItems = [...comments, ...reviews];
    const attestations = parseAttestationsFromComments(allItems);

    console.log(`[INFO] Evaluating ${attestations.length} attestation candidate(s) across ${allItems.length} comment/review items for PR #${prNumber} at head ${headSha} (control issue #${controlIssue}, state: ${issueValidation.state}, scope_rev: ${scopeRevision})...`);

    const result = validateTerraAttestation({
      attestations,
      expectedHeadSha: headSha,
      expectedPrNumber: Number(prNumber),
      expectedControlIssue: Number(controlIssue),
      expectedScopeRevision: Number(scopeRevision),
    });

    if (result.valid) {
      console.log(`[PASS] Valid Terra attestation confirmed for head ${headSha} on PR #${prNumber}!`);
      process.exit(0);
    } else {
      console.error(`[FAIL] review-gate failed closed: [${result.reason}] ${result.details}`);
      process.exit(1);
    }
  } catch (err) {
    console.error(`[ERROR] Review gate execution encountered an error: ${err.message}`);
    process.exit(1);
  }
}

if (process.argv[1] && process.argv[1].endsWith("validate_terra_attestation.mjs")) {
  main().catch((err) => {
    console.error("[FATAL]", err);
    process.exit(1);
  });
}
