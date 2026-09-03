/* global console */

import { readFileSync } from "node:fs";
import { request as httpsRequest } from "node:https";
import process from "node:process";
import { URL } from "node:url";

/**
 * Parses a string content (either JSON or YAML-like key-value pairs)
 * into a structured attestation object.
 */
export function parseTerraAttestationBlock(content) {
  if (!content || typeof content !== "string") {
    return { malformed: true, error: "Empty attestation content" };
  }

  const trimmed = content.trim();

  // Try JSON parsing first if wrapped in { ... }
  if (trimmed.startsWith("{") && trimmed.endsWith("}")) {
    try {
      const parsed = JSON.parse(trimmed);
      return normalizeAttestation(parsed);
    } catch (err) {
      return { malformed: true, error: `Invalid JSON in attestation: ${err.message}` };
    }
  }

  // Parse YAML / key-value lines
  const result = {};
  const lines = trimmed.split(/\r?\n/);
  for (const line of lines) {
    const trimmedLine = line.trim();
    if (!trimmedLine || trimmedLine.startsWith("#")) continue;
    const colonIdx = trimmedLine.indexOf(":");
    if (colonIdx === -1) continue;

    const key = trimmedLine.slice(0, colonIdx).trim();
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
    } else if (key !== "head_sha" && /^-?\d+$/.test(val)) {
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

  // Type checks
  const p0Num = typeof raw.p0 === "number" ? raw.p0 : parseInt(raw.p0, 10);
  const p1Num = typeof raw.p1 === "number" ? raw.p1 : parseInt(raw.p1, 10);
  const prNum = typeof raw.pr_number === "number" ? raw.pr_number : parseInt(raw.pr_number, 10);
  const issueNum = typeof raw.control_issue === "number" ? raw.control_issue : parseInt(raw.control_issue, 10);
  const scopeRev = typeof raw.scope_revision === "number" ? raw.scope_revision : parseInt(raw.scope_revision, 10);

  if (isNaN(p0Num) || isNaN(p1Num) || isNaN(prNum) || isNaN(issueNum) || isNaN(scopeRev)) {
    return {
      malformed: true,
      error: "Numeric fields (p0, p1, pr_number, control_issue, scope_revision) must be valid integers",
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

  if (raw.reviewed_at_utc && isNaN(Date.parse(String(raw.reviewed_at_utc)))) {
    return {
      malformed: true,
      error: "reviewed_at_utc must be a valid ISO-8601 date string",
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
    reviewed_at_utc: raw.reviewed_at_utc ? String(raw.reviewed_at_utc) : undefined,
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
 * Handles duplicate/conflicting attestations within a comment and enforces later-attestation precedence.
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
    return (a.id || 0) - (b.id || 0);
  });

  const parsedEntries = [];

  for (const comment of sorted) {
    const body = comment.body || "";
    const found = extractAttestationsFromText(body);
    if (found.length === 0) continue;

    // Check for conflicting attestations in the same comment
    if (found.length > 1) {
      const distinctVerdicts = new Set(found.map((f) => (f.malformed ? "MALFORMED" : f.verdict)));
      const distinctSHAs = new Set(found.map((f) => (f.malformed ? "MALFORMED" : f.head_sha)));
      if (distinctVerdicts.size > 1 || distinctSHAs.size > 1) {
        parsedEntries.push({
          conflicting: true,
          commentId: comment.id,
          error: "Multiple conflicting attestation blocks found in the same comment",
        });
        continue;
      }
      // Deduplicate identical blocks
      parsedEntries.push({
        ...found[0],
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
 * Core deterministic validator function.
 */
export function validateTerraAttestation({
  attestations,
  expectedHeadSha,
  expectedPrNumber,
  expectedControlIssue,
  expectedScopeRevision,
}) {
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

  // P0 check
  if (latest.p0 > 0) {
    return {
      valid: false,
      reason: "UNRESOLVED_P0_FINDINGS",
      details: `Attestation reports ${latest.p0} unresolved P0 finding(s). Must be 0.`,
    };
  }

  // P1 check
  if (latest.p1 > 0) {
    return {
      valid: false,
      reason: "UNRESOLVED_P1_FINDINGS",
      details: `Attestation reports ${latest.p1} unresolved P1 finding(s). Must be 0.`,
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

// Parse control block from issue/PR body text
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
      if (k === "state" || k === "scope_revision" || k === "fix_reentries") {
        result[k] = v;
      }
    }
  }
  return result;
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

    const result = validateTerraAttestation({
      attestations,
      expectedHeadSha: args["head-sha"] || process.env.HEAD_SHA,
      expectedPrNumber: args.pr ? Number(args.pr) : process.env.PR_NUMBER ? Number(process.env.PR_NUMBER) : undefined,
      expectedControlIssue: args["control-issue"]
        ? Number(args["control-issue"])
        : process.env.CONTROL_ISSUE
        ? Number(process.env.CONTROL_ISSUE)
        : undefined,
      expectedScopeRevision: args["scope-revision"]
        ? Number(args["scope-revision"])
        : process.env.SCOPE_REVISION
        ? Number(process.env.SCOPE_REVISION)
        : undefined,
    });

    if (result.valid) {
      console.log(`[PASS] Terra attestation verified: ${JSON.stringify(result.attestation)}`);
      process.exit(0);
    } else {
      console.error(`[FAIL] Review gate check failed: ${result.reason} - ${result.details}`);
      process.exit(1);
    }
  }

  // GitHub Actions API mode
  const token = process.env.GITHUB_TOKEN;
  const repo = process.env.GITHUB_REPOSITORY || process.env.REPOSITORY || args.repo;
  const prNumber = args.pr || process.env.PR_NUMBER;
  let headSha = args["head-sha"] || process.env.HEAD_SHA;
  let controlIssue = args["control-issue"] || process.env.CONTROL_ISSUE;
  let scopeRevision = args["scope-revision"] || process.env.SCOPE_REVISION;

  if (!repo || !prNumber) {
    console.error("[ERROR] Missing required environment/args: GITHUB_REPOSITORY and PR_NUMBER are required.");
    process.exit(1);
  }

  try {
    // 1. Fetch PR details
    const pr = await githubApiGet(`https://api.github.com/repos/${repo}/pulls/${prNumber}`, token);
    headSha = headSha || pr.head.sha;

    // Extract control issue and scope_revision from PR body if not provided
    if (!controlIssue) {
      const issueMatch = /(?:Authoritative control issue|Linked issue|Linked GitHub issue):\s*#?(\d+)/i.exec(pr.body || "");
      if (issueMatch) {
        controlIssue = issueMatch[1];
      }
    }

    if (controlIssue && !scopeRevision) {
      try {
        const issue = await githubApiGet(`https://api.github.com/repos/${repo}/issues/${controlIssue}`, token);
        const cb = parseControlBlock(issue.body);
        if (cb.scope_revision) {
          scopeRevision = cb.scope_revision;
        }
      } catch (err) {
        console.warn(`[WARN] Could not fetch linked control issue #${controlIssue}: ${err.message}`);
      }
    }

    // Fallback: parse scope_revision from PR body
    if (!scopeRevision) {
      const scopeMatch = /scope_revision:\s*(\d+)/i.exec(pr.body || "");
      if (scopeMatch) {
        scopeRevision = scopeMatch[1];
      }
    }

    // 2. Fetch issue comments & PR reviews
    const comments = await githubApiGet(`https://api.github.com/repos/${repo}/issues/${prNumber}/comments?per_page=100`, token);
    const reviews = await githubApiGet(`https://api.github.com/repos/${repo}/pulls/${prNumber}/reviews?per_page=100`, token);

    const allItems = [...(comments || []), ...(reviews || [])];
    const attestations = parseAttestationsFromComments(allItems);

    console.log(`[INFO] Evaluating ${attestations.length} attestation candidate(s) for PR #${prNumber} at head ${headSha}...`);

    const result = validateTerraAttestation({
      attestations,
      expectedHeadSha: headSha,
      expectedPrNumber: Number(prNumber),
      expectedControlIssue: controlIssue ? Number(controlIssue) : undefined,
      expectedScopeRevision: scopeRevision ? Number(scopeRevision) : undefined,
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
