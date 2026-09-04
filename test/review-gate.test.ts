import { describe, expect, it } from "vitest";
import { writeFileSync, unlinkSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawnSync } from "node:child_process";
import {
  parseTerraAttestationBlock,
  extractAttestationsFromText,
  parseAttestationsFromComments,
  validateTerraAttestation,
  parseControlBlock,
  validateControlIssue,
  fetchAllPagedItems,
  parseCanonicalNonNegativeInteger,
  isValidStrictUtcIsoTimestamp,
  areAttestationsIdentical,
  CANONICAL_WORKFLOW_STATES,
  REVIEWABLE_CONTROL_STATES,
  BOOTSTRAP_PR_NUMBER,
  BOOTSTRAP_CONTROL_ISSUE,
  BOOTSTRAP_SCOPE_REVISION,
} from "../.github/scripts/validate_terra_attestation.mjs";

const VALID_HEAD_SHA = "7074b025458d63e009da12e5e85f891852108004";
const STALE_HEAD_SHA = "2222222222222222222222222222222222222222";
const PR_NUMBER = 6;
const CONTROL_ISSUE = 7;
const SCOPE_REVISION = 4;
const VALID_TIMESTAMP = "2026-09-03T20:00:00Z";
const VALID_RESET_LINK = "https://github.com/Banhtalon/mindx-review-bot/issues/7#issuecomment-5526241968";

function createValidAttestation(overrides = {}) {
  return {
    malformed: false,
    reviewer_model: "terra-xhigh",
    head_sha: VALID_HEAD_SHA,
    pr_number: PR_NUMBER,
    control_issue: CONTROL_ISSUE,
    scope_revision: SCOPE_REVISION,
    verdict: "RECOMMEND_PASS",
    p0: 0,
    p1: 0,
    material_findings_resolved: true,
    reviewed_at_utc: VALID_TIMESTAMP,
    ...overrides,
  };
}

describe("Terra Attestation Validator", () => {
  describe("Strict numeric parsing (p0, p1, etc.)", () => {
    it("parses canonical non-negative integers correctly", () => {
      expect(parseCanonicalNonNegativeInteger(0)).toBe(0);
      expect(parseCanonicalNonNegativeInteger("0")).toBe(0);
      expect(parseCanonicalNonNegativeInteger(1)).toBe(1);
      expect(parseCanonicalNonNegativeInteger("1")).toBe(1);
      expect(parseCanonicalNonNegativeInteger(42)).toBe(42);
      expect(parseCanonicalNonNegativeInteger("42")).toBe(42);
    });

    it("rejects non-canonical or negative or fractional integers", () => {
      expect(parseCanonicalNonNegativeInteger(-1)).toBeNull();
      expect(parseCanonicalNonNegativeInteger("-1")).toBeNull();
      expect(parseCanonicalNonNegativeInteger("+1")).toBeNull();
      expect(parseCanonicalNonNegativeInteger(0.5)).toBeNull();
      expect(parseCanonicalNonNegativeInteger("0.5")).toBeNull();
      expect(parseCanonicalNonNegativeInteger("1.0")).toBeNull();
      expect(parseCanonicalNonNegativeInteger("01")).toBeNull();
      expect(parseCanonicalNonNegativeInteger(" 0 ")).toBeNull();
      expect(parseCanonicalNonNegativeInteger("1e5")).toBeNull();
      expect(parseCanonicalNonNegativeInteger(NaN)).toBeNull();
      expect(parseCanonicalNonNegativeInteger(Infinity)).toBeNull();
      expect(parseCanonicalNonNegativeInteger(null)).toBeNull();
      expect(parseCanonicalNonNegativeInteger(undefined)).toBeNull();
    });

    it("flags negative p0 or p1 in YAML block as malformed", () => {
      const text = `
\`\`\`terra-attestation
reviewer_model: terra-xhigh
head_sha: ${VALID_HEAD_SHA}
pr_number: ${PR_NUMBER}
control_issue: ${CONTROL_ISSUE}
scope_revision: ${SCOPE_REVISION}
verdict: RECOMMEND_PASS
p0: -1
p1: 0
material_findings_resolved: true
reviewed_at_utc: ${VALID_TIMESTAMP}
\`\`\`
      `;
      const found = extractAttestationsFromText(text);
      expect(found[0].malformed).toBe(true);
      expect(found[0].error).toContain("canonical non-negative decimal integer");
    });

    it("flags fractional p0 or p1 in YAML block as malformed", () => {
      const text = `
\`\`\`terra-attestation
reviewer_model: terra-xhigh
head_sha: ${VALID_HEAD_SHA}
pr_number: ${PR_NUMBER}
control_issue: ${CONTROL_ISSUE}
scope_revision: ${SCOPE_REVISION}
verdict: RECOMMEND_PASS
p0: 0.5
p1: 0
material_findings_resolved: true
reviewed_at_utc: ${VALID_TIMESTAMP}
\`\`\`
      `;
      const found = extractAttestationsFromText(text);
      expect(found[0].malformed).toBe(true);
      expect(found[0].error).toContain("canonical non-negative decimal integer");
    });

    it("flags decimal 1.0 in YAML block as malformed", () => {
      const text = `
\`\`\`terra-attestation
reviewer_model: terra-xhigh
head_sha: ${VALID_HEAD_SHA}
pr_number: ${PR_NUMBER}
control_issue: ${CONTROL_ISSUE}
scope_revision: ${SCOPE_REVISION}
verdict: RECOMMEND_PASS
p0: 0
p1: 1.0
material_findings_resolved: true
reviewed_at_utc: ${VALID_TIMESTAMP}
\`\`\`
      `;
      const found = extractAttestationsFromText(text);
      expect(found[0].malformed).toBe(true);
    });

    it("flags fractional or negative numbers in JSON attestation as malformed", () => {
      const text1 = `
\`\`\`json:terra-attestation
{
  "reviewer_model": "terra-xhigh",
  "head_sha": "${VALID_HEAD_SHA}",
  "pr_number": ${PR_NUMBER},
  "control_issue": ${CONTROL_ISSUE},
  "scope_revision": ${SCOPE_REVISION},
  "verdict": "RECOMMEND_PASS",
  "p0": -1,
  "p1": 0,
  "material_findings_resolved": true,
  "reviewed_at_utc": "${VALID_TIMESTAMP}"
}
\`\`\`
      `;
      expect(extractAttestationsFromText(text1)[0].malformed).toBe(true);

      const text2 = `
\`\`\`json:terra-attestation
{
  "reviewer_model": "terra-xhigh",
  "head_sha": "${VALID_HEAD_SHA}",
  "pr_number": ${PR_NUMBER},
  "control_issue": ${CONTROL_ISSUE},
  "scope_revision": ${SCOPE_REVISION},
  "verdict": "RECOMMEND_PASS",
  "p0": 0.5,
  "p1": 0,
  "material_findings_resolved": true,
  "reviewed_at_utc": "${VALID_TIMESTAMP}"
}
\`\`\`
      `;
      expect(extractAttestationsFromText(text2)[0].malformed).toBe(true);

      const text3 = `
\`\`\`json:terra-attestation
{
  "reviewer_model": "terra-xhigh",
  "head_sha": "${VALID_HEAD_SHA}",
  "pr_number": ${PR_NUMBER},
  "control_issue": ${CONTROL_ISSUE},
  "scope_revision": ${SCOPE_REVISION},
  "verdict": "RECOMMEND_PASS",
  "p0": 1.0,
  "p1": 0,
  "material_findings_resolved": true,
  "reviewed_at_utc": "${VALID_TIMESTAMP}"
}
\`\`\`
      `;
      expect(extractAttestationsFromText(text3)[0].malformed).toBe(true);
    });
  });

  describe("Strict UTC timestamp parsing (reviewed_at_utc)", () => {
    it("validates strict UTC ISO-8601 timestamps", () => {
      expect(isValidStrictUtcIsoTimestamp("2026-09-04T01:23:45Z")).toBe(true);
      expect(isValidStrictUtcIsoTimestamp("2026-09-04T01:23:45.678Z")).toBe(true);
      expect(isValidStrictUtcIsoTimestamp("2024-02-29T12:00:00Z")).toBe(true); // leap year
    });

    it("rejects impossible calendar dates (non-leap year Feb 29, April 31)", () => {
      expect(isValidStrictUtcIsoTimestamp("2026-02-29T00:00:00Z")).toBe(false); // 2026 not leap
      expect(isValidStrictUtcIsoTimestamp("2026-04-31T00:00:00Z")).toBe(false); // April has 30 days
      expect(isValidStrictUtcIsoTimestamp("2026-13-01T00:00:00Z")).toBe(false); // month 13
      expect(isValidStrictUtcIsoTimestamp("2026-09-04T24:00:00Z")).toBe(false); // hour 24
    });

    it("rejects date-only, local timestamps without Z, or timezone offsets", () => {
      expect(isValidStrictUtcIsoTimestamp("2026-09-04")).toBe(false);
      expect(isValidStrictUtcIsoTimestamp("2026-09-04T01:23:45")).toBe(false);
      expect(isValidStrictUtcIsoTimestamp("2026-09-04T01:23:45+07:00")).toBe(false);
      expect(isValidStrictUtcIsoTimestamp("2026-09-04T01:23:45-05:00")).toBe(false);
      expect(isValidStrictUtcIsoTimestamp("invalid-date")).toBe(false);
      expect(isValidStrictUtcIsoTimestamp("")).toBe(false);
    });

    it("rejects attestation with date-only reviewed_at_utc", () => {
      const text = `
\`\`\`terra-attestation
reviewer_model: terra-xhigh
head_sha: ${VALID_HEAD_SHA}
pr_number: ${PR_NUMBER}
control_issue: ${CONTROL_ISSUE}
scope_revision: ${SCOPE_REVISION}
verdict: RECOMMEND_PASS
p0: 0
p1: 0
material_findings_resolved: true
reviewed_at_utc: 2026-09-04
\`\`\`
      `;
      const found = extractAttestationsFromText(text);
      expect(found[0].malformed).toBe(true);
      expect(found[0].error).toContain("valid full ISO-8601 UTC timestamp ending in 'Z'");
    });

    it("rejects attestation with timezone offset in reviewed_at_utc", () => {
      const text = `
\`\`\`terra-attestation
reviewer_model: terra-xhigh
head_sha: ${VALID_HEAD_SHA}
pr_number: ${PR_NUMBER}
control_issue: ${CONTROL_ISSUE}
scope_revision: ${SCOPE_REVISION}
verdict: RECOMMEND_PASS
p0: 0
p1: 0
material_findings_resolved: true
reviewed_at_utc: 2026-09-04T08:00:00+07:00
\`\`\`
      `;
      const found = extractAttestationsFromText(text);
      expect(found[0].malformed).toBe(true);
      expect(found[0].error).toContain("valid full ISO-8601 UTC timestamp ending in 'Z'");
    });
  });

  describe("Parsing attestation blocks", () => {
    it("parses YAML/key-value attestation block", () => {
      const text = `
\`\`\`terra-attestation
reviewer_model: terra-xhigh
head_sha: ${VALID_HEAD_SHA}
pr_number: ${PR_NUMBER}
control_issue: ${CONTROL_ISSUE}
scope_revision: ${SCOPE_REVISION}
verdict: RECOMMEND_PASS
p0: 0
p1: 0
material_findings_resolved: true
reviewed_at_utc: ${VALID_TIMESTAMP}
\`\`\`
      `;
      const found = extractAttestationsFromText(text);
      expect(found).toHaveLength(1);
      expect(found[0].malformed).toBe(false);
      expect(found[0].reviewer_model).toBe("terra-xhigh");
      expect(found[0].head_sha).toBe(VALID_HEAD_SHA);
      expect(found[0].verdict).toBe("RECOMMEND_PASS");
      expect(found[0].p0).toBe(0);
      expect(found[0].p1).toBe(0);
      expect(found[0].material_findings_resolved).toBe(true);
      expect(found[0].reviewed_at_utc).toBe(VALID_TIMESTAMP);
    });

    it("parses JSON attestation block", () => {
      const text = `
\`\`\`json:terra-attestation
{
  "reviewer_model": "terra-xhigh",
  "head_sha": "${VALID_HEAD_SHA}",
  "pr_number": ${PR_NUMBER},
  "control_issue": ${CONTROL_ISSUE},
  "scope_revision": ${SCOPE_REVISION},
  "verdict": "RECOMMEND_PASS",
  "p0": 0,
  "p1": 0,
  "material_findings_resolved": true,
  "reviewed_at_utc": "${VALID_TIMESTAMP}"
}
\`\`\`
      `;
      const found = extractAttestationsFromText(text);
      expect(found).toHaveLength(1);
      expect(found[0].malformed).toBe(false);
      expect(found[0].verdict).toBe("RECOMMEND_PASS");
      expect(found[0].reviewed_at_utc).toBe(VALID_TIMESTAMP);
    });

    it("parses HTML comment attestation block", () => {
      const text = `
<!-- terra-attestation
reviewer_model: terra-xhigh
head_sha: ${VALID_HEAD_SHA}
pr_number: ${PR_NUMBER}
control_issue: ${CONTROL_ISSUE}
scope_revision: ${SCOPE_REVISION}
verdict: RECOMMEND_PASS
p0: 0
p1: 0
material_findings_resolved: true
reviewed_at_utc: ${VALID_TIMESTAMP}
-->
      `;
      const found = extractAttestationsFromText(text);
      expect(found).toHaveLength(1);
      expect(found[0].malformed).toBe(false);
      expect(found[0].verdict).toBe("RECOMMEND_PASS");
      expect(found[0].reviewed_at_utc).toBe(VALID_TIMESTAMP);
    });

    it("parses TERRA_REVIEW_ATTESTATION_V1 block", () => {
      const text = `
<!-- TERRA_REVIEW_ATTESTATION_V1 -->
reviewer_model: terra-xhigh
control_issue: ${CONTROL_ISSUE}
scope_revision: ${SCOPE_REVISION}
pr_number: ${PR_NUMBER}
head_sha: ${VALID_HEAD_SHA}
verdict: RECOMMEND_PASS
p0: 0
p1: 0
material_findings_resolved: true
reviewed_at_utc: ${VALID_TIMESTAMP}
<!-- /TERRA_REVIEW_ATTESTATION_V1 -->
      `;
      const found = extractAttestationsFromText(text);
      expect(found).toHaveLength(1);
      expect(found[0].malformed).toBe(false);
      expect(found[0].reviewed_at_utc).toBe(VALID_TIMESTAMP);
      expect(found[0].verdict).toBe("RECOMMEND_PASS");
    });

    it("flags malformed SHA (non-hex or wrong length) as malformed", () => {
      const text = `
\`\`\`terra-attestation
reviewer_model: terra-xhigh
head_sha: not-a-valid-40-char-sha
pr_number: ${PR_NUMBER}
control_issue: ${CONTROL_ISSUE}
scope_revision: ${SCOPE_REVISION}
verdict: RECOMMEND_PASS
p0: 0
p1: 0
material_findings_resolved: true
reviewed_at_utc: ${VALID_TIMESTAMP}
\`\`\`
      `;
      const found = extractAttestationsFromText(text);
      expect(found).toHaveLength(1);
      expect(found[0].malformed).toBe(true);
      expect(found[0].error).toContain("40-character hexadecimal SHA");
    });

    it("flags missing reviewed_at_utc as malformed", () => {
      const text = `
\`\`\`terra-attestation
reviewer_model: terra-xhigh
head_sha: ${VALID_HEAD_SHA}
pr_number: ${PR_NUMBER}
control_issue: ${CONTROL_ISSUE}
scope_revision: ${SCOPE_REVISION}
verdict: RECOMMEND_PASS
p0: 0
p1: 0
material_findings_resolved: true
\`\`\`
      `;
      const found = extractAttestationsFromText(text);
      expect(found).toHaveLength(1);
      expect(found[0].malformed).toBe(true);
      expect(found[0].error).toContain("reviewed_at_utc");
    });

    it("flags duplicate verdict key in YAML block as malformed (no last-write-wins)", () => {
      const text = `
\`\`\`terra-attestation
reviewer_model: terra-xhigh
head_sha: ${VALID_HEAD_SHA}
pr_number: ${PR_NUMBER}
control_issue: ${CONTROL_ISSUE}
scope_revision: ${SCOPE_REVISION}
verdict: NEEDS_FIX
verdict: RECOMMEND_PASS
p0: 0
p1: 0
material_findings_resolved: true
reviewed_at_utc: ${VALID_TIMESTAMP}
\`\`\`
      `;
      const found = extractAttestationsFromText(text);
      expect(found).toHaveLength(1);
      expect(found[0].malformed).toBe(true);
      expect(found[0].error).toContain("Duplicate key 'verdict'");
    });

    it("flags duplicate head_sha key in YAML block as malformed (no last-write-wins)", () => {
      const text = `
\`\`\`terra-attestation
reviewer_model: terra-xhigh
head_sha: ${STALE_HEAD_SHA}
head_sha: ${VALID_HEAD_SHA}
pr_number: ${PR_NUMBER}
control_issue: ${CONTROL_ISSUE}
scope_revision: ${SCOPE_REVISION}
verdict: RECOMMEND_PASS
p0: 0
p1: 0
material_findings_resolved: true
reviewed_at_utc: ${VALID_TIMESTAMP}
\`\`\`
      `;
      const found = extractAttestationsFromText(text);
      expect(found).toHaveLength(1);
      expect(found[0].malformed).toBe(true);
      expect(found[0].error).toContain("Duplicate key 'head_sha'");
    });

    it("flags duplicate keys in JSON block as malformed", () => {
      const text = `
\`\`\`json:terra-attestation
{
  "reviewer_model": "terra-xhigh",
  "head_sha": "${VALID_HEAD_SHA}",
  "pr_number": ${PR_NUMBER},
  "control_issue": ${CONTROL_ISSUE},
  "scope_revision": ${SCOPE_REVISION},
  "verdict": "NEEDS_FIX",
  "verdict": "RECOMMEND_PASS",
  "p0": 0,
  "p1": 0,
  "material_findings_resolved": true,
  "reviewed_at_utc": "${VALID_TIMESTAMP}"
}
\`\`\`
      `;
      const found = extractAttestationsFromText(text);
      expect(found).toHaveLength(1);
      expect(found[0].malformed).toBe(true);
      expect(found[0].error).toContain("Duplicate key 'verdict'");
    });

    it("flags broken JSON as malformed", () => {
      const text = "```json:terra-attestation\n{ broken json \n```";
      const found = extractAttestationsFromText(text);
      expect(found).toHaveLength(1);
      expect(found[0].malformed).toBe(true);
    });

    it("handles direct parseTerraAttestationBlock calls", () => {
      const parsed = parseTerraAttestationBlock(`
reviewer_model: terra-xhigh
head_sha: ${VALID_HEAD_SHA}
pr_number: ${PR_NUMBER}
control_issue: ${CONTROL_ISSUE}
scope_revision: ${SCOPE_REVISION}
verdict: RECOMMEND_PASS
p0: 0
p1: 0
material_findings_resolved: true
reviewed_at_utc: ${VALID_TIMESTAMP}
      `);
      expect(parsed.malformed).toBe(false);
      expect(parsed.reviewer_model).toBe("terra-xhigh");
      expect(parsed.reviewed_at_utc).toBe(VALID_TIMESTAMP);
    });

    it("parses control blocks from issue/PR markdown", () => {
      const markdown = `
## Agent Control Block
\`\`\`text
state: implementing
scope_revision: 2
fix_reentries: 0
owner_scope_reset: https://github.com/example/approval
\`\`\`
      `;
      const control = parseControlBlock(markdown);
      expect(control.state).toBe("implementing");
      expect(control.scope_revision).toBe("2");
      expect(control.fix_reentries).toBe("0");
      expect(control.owner_scope_reset).toBe("https://github.com/example/approval");
    });
  });

  describe("Authoritative Control Issue Validation", () => {
    it("exports canonical workflow states and reviewable control states constants", () => {
      expect(CANONICAL_WORKFLOW_STATES).toContain("implementing");
      expect(CANONICAL_WORKFLOW_STATES).toContain("ready-for-review");
      expect(REVIEWABLE_CONTROL_STATES).toEqual(["ready-for-review", "ready-for-verify"]);
      expect(BOOTSTRAP_PR_NUMBER).toBe(6);
      expect(BOOTSTRAP_CONTROL_ISSUE).toBe(7);
      expect(BOOTSTRAP_SCOPE_REVISION).toBe(4);
    });

    it("fails closed on linked issue fetch failure (null/empty input)", () => {
      const result = validateControlIssue(null, SCOPE_REVISION);
      expect(result.valid).toBe(false);
      expect(result.reason).toBe("ISSUE_FETCH_FAILED");
    });

    it("fails closed on missing Agent Control Block in issue body", () => {
      const issue = {
        number: CONTROL_ISSUE,
        body: "Just an issue with no Agent Control Block",
        labels: [{ name: "ready-for-review" }],
      };
      const result = validateControlIssue(issue, SCOPE_REVISION);
      expect(result.valid).toBe(false);
      expect(result.reason).toBe("MISSING_AGENT_CONTROL_BLOCK");
    });

    it("fails closed on missing required fields in control block", () => {
      // Missing fix_reentries and owner_scope_reset
      const issue1 = {
        number: CONTROL_ISSUE,
        body: "```text\nstate: ready-for-review\nscope_revision: 2\n```",
        labels: [{ name: "ready-for-review" }],
      };
      const result1 = validateControlIssue(issue1, SCOPE_REVISION);
      expect(result1.valid).toBe(false);
      expect(result1.reason).toBe("MISSING_AGENT_CONTROL_BLOCK");
      expect(result1.details).toContain("fix_reentries");

      // Missing owner_scope_reset
      const issue2 = {
        number: CONTROL_ISSUE,
        body: "```text\nstate: ready-for-review\nscope_revision: 2\nfix_reentries: 0\n```",
        labels: [{ name: "ready-for-review" }],
      };
      const result2 = validateControlIssue(issue2, SCOPE_REVISION);
      expect(result2.valid).toBe(false);
      expect(result2.reason).toBe("MISSING_AGENT_CONTROL_BLOCK");
      expect(result2.details).toContain("owner_scope_reset");
    });

    it("fails closed when fix_reentries is outside allowed range 0..2", () => {
      const issue = {
        number: CONTROL_ISSUE,
        body: `\`\`\`text\nstate: ready-for-review\nscope_revision: ${SCOPE_REVISION}\nfix_reentries: 3\nowner_scope_reset: ${VALID_RESET_LINK}\n\`\`\``,
        labels: [{ name: "ready-for-review" }],
      };
      const result = validateControlIssue(issue, SCOPE_REVISION);
      expect(result.valid).toBe(false);
      expect(result.reason).toBe("INVALID_CONTROL_BLOCK");
      expect(result.details).toContain("allowed range 0..2");
    });

    it("fails closed when owner_scope_reset is none or empty for scope_revision >= 2", () => {
      const issueNone = {
        number: CONTROL_ISSUE,
        body: `\`\`\`text\nstate: ready-for-review\nscope_revision: ${SCOPE_REVISION}\nfix_reentries: 0\nowner_scope_reset: none\n\`\`\``,
        labels: [{ name: "ready-for-review" }],
      };
      const resultNone = validateControlIssue(issueNone, SCOPE_REVISION);
      expect(resultNone.valid).toBe(false);
      expect(resultNone.reason).toBe("INVALID_CONTROL_BLOCK");
      expect(resultNone.details).toContain("owner_scope_reset must be present and non-empty");
    });

    it("fails closed when scope_revision does not match expected", () => {
      const issue = {
        number: CONTROL_ISSUE,
        body: `\`\`\`text\nstate: ready-for-review\nscope_revision: 1\nfix_reentries: 0\nowner_scope_reset: none\n\`\`\``,
        labels: [{ name: "ready-for-review" }],
      };
      const result = validateControlIssue(issue, 2);
      expect(result.valid).toBe(false);
      expect(result.reason).toBe("WRONG_SCOPE_REVISION");
    });

    it("fails closed on zero primary state labels", () => {
      const issue = {
        number: CONTROL_ISSUE,
        body: `\`\`\`text\nstate: ready-for-review\nscope_revision: ${SCOPE_REVISION}\nfix_reentries: 0\nowner_scope_reset: ${VALID_RESET_LINK}\n\`\`\``,
        labels: [{ name: "bug" }, { name: "documentation" }],
      };
      const result = validateControlIssue(issue, SCOPE_REVISION);
      expect(result.valid).toBe(false);
      expect(result.reason).toBe("ZERO_PRIMARY_STATE_LABELS");
    });

    it("fails closed on multiple primary state labels", () => {
      const issue = {
        number: CONTROL_ISSUE,
        body: `\`\`\`text\nstate: ready-for-review\nscope_revision: ${SCOPE_REVISION}\nfix_reentries: 0\nowner_scope_reset: ${VALID_RESET_LINK}\n\`\`\``,
        labels: [{ name: "ready-for-review" }, { name: "needs-fix" }],
      };
      const result = validateControlIssue(issue, SCOPE_REVISION);
      expect(result.valid).toBe(false);
      expect(result.reason).toBe("MULTIPLE_PRIMARY_STATE_LABELS");
    });

    it("fails closed on label/state mismatch", () => {
      const issue = {
        number: CONTROL_ISSUE,
        body: `\`\`\`text\nstate: implementing\nscope_revision: ${SCOPE_REVISION}\nfix_reentries: 1\nowner_scope_reset: ${VALID_RESET_LINK}\n\`\`\``,
        labels: [{ name: "ready-for-review" }],
      };
      const result = validateControlIssue(issue, SCOPE_REVISION);
      expect(result.valid).toBe(false);
      expect(result.reason).toBe("LABEL_STATE_MISMATCH");
    });

    it("rejects implementing state (not reviewable)", () => {
      const issue = {
        number: CONTROL_ISSUE,
        body: `\`\`\`text\nstate: implementing\nscope_revision: ${SCOPE_REVISION}\nfix_reentries: 2\nowner_scope_reset: ${VALID_RESET_LINK}\n\`\`\``,
        labels: [{ name: "implementing" }],
      };
      const result = validateControlIssue(issue, SCOPE_REVISION);
      expect(result.valid).toBe(false);
      expect(result.reason).toBe("INVALID_CONTROL_STATE");
      expect(result.details).toContain("not reviewable");
    });

    it("rejects needs-fix state (not reviewable)", () => {
      const issue = {
        number: CONTROL_ISSUE,
        body: `\`\`\`text\nstate: needs-fix\nscope_revision: ${SCOPE_REVISION}\nfix_reentries: 1\nowner_scope_reset: ${VALID_RESET_LINK}\n\`\`\``,
        labels: [{ name: "needs-fix" }],
      };
      const result = validateControlIssue(issue, SCOPE_REVISION);
      expect(result.valid).toBe(false);
      expect(result.reason).toBe("INVALID_CONTROL_STATE");
    });

    it("rejects blocked-owner state (not reviewable)", () => {
      const issue = {
        number: CONTROL_ISSUE,
        body: `\`\`\`text\nstate: blocked-owner\nscope_revision: ${SCOPE_REVISION}\nfix_reentries: 2\nowner_scope_reset: ${VALID_RESET_LINK}\n\`\`\``,
        labels: [{ name: "blocked-owner" }],
      };
      const result = validateControlIssue(issue, SCOPE_REVISION);
      expect(result.valid).toBe(false);
      expect(result.reason).toBe("INVALID_CONTROL_STATE");
    });

    it("rejects blocked-external state (not reviewable)", () => {
      const issue = {
        number: CONTROL_ISSUE,
        body: `\`\`\`text\nstate: blocked-external\nscope_revision: ${SCOPE_REVISION}\nfix_reentries: 0\nowner_scope_reset: ${VALID_RESET_LINK}\n\`\`\``,
        labels: [{ name: "blocked-external" }],
      };
      const result = validateControlIssue(issue, SCOPE_REVISION);
      expect(result.valid).toBe(false);
      expect(result.reason).toBe("INVALID_CONTROL_STATE");
    });

    it("accepts ready-for-review state with complete control block and matching label", () => {
      const issue = {
        number: CONTROL_ISSUE,
        body: `\`\`\`text\nstate: ready-for-review\nscope_revision: ${SCOPE_REVISION}\nfix_reentries: 0\nowner_scope_reset: ${VALID_RESET_LINK}\n\`\`\``,
        labels: [{ name: "ready-for-review" }],
      };
      const result = validateControlIssue(issue, SCOPE_REVISION);
      expect(result.valid).toBe(true);
      expect(result.reason).toBe("OK");
      expect(result.state).toBe("ready-for-review");
      expect(result.primaryLabel).toBe("ready-for-review");
      expect(result.fixReentries).toBe(0);
    });

    it("accepts ready-for-verify state with complete control block and matching label", () => {
      const issue = {
        number: CONTROL_ISSUE,
        body: `\`\`\`text\nstate: ready-for-verify\nscope_revision: ${SCOPE_REVISION}\nfix_reentries: 1\nowner_scope_reset: ${VALID_RESET_LINK}\n\`\`\``,
        labels: [{ name: "ready-for-verify" }],
      };
      const result = validateControlIssue(issue, SCOPE_REVISION);
      expect(result.valid).toBe(true);
      expect(result.reason).toBe("OK");
      expect(result.state).toBe("ready-for-verify");
      expect(result.primaryLabel).toBe("ready-for-verify");
      expect(result.fixReentries).toBe(1);
    });
  });

  describe("Validation scenarios", () => {
    it("accepts a valid attestation", () => {
      const result = validateTerraAttestation({
        attestations: [createValidAttestation()],
        expectedHeadSha: VALID_HEAD_SHA,
        expectedPrNumber: PR_NUMBER,
        expectedControlIssue: CONTROL_ISSUE,
        expectedScopeRevision: SCOPE_REVISION,
      });

      expect(result.valid).toBe(true);
      expect(result.reason).toBe("OK");
    });

    it("rejects a stale attestation (head_sha mismatch)", () => {
      const result = validateTerraAttestation({
        attestations: [createValidAttestation({ head_sha: STALE_HEAD_SHA })],
        expectedHeadSha: VALID_HEAD_SHA,
        expectedPrNumber: PR_NUMBER,
        expectedControlIssue: CONTROL_ISSUE,
        expectedScopeRevision: SCOPE_REVISION,
      });

      expect(result.valid).toBe(false);
      expect(result.reason).toBe("STALE_HEAD_SHA");
    });

    it("rejects a malformed attestation missing required fields", () => {
      const result = validateTerraAttestation({
        attestations: [{ malformed: true, error: "Missing required field 'verdict'" }],
        expectedHeadSha: VALID_HEAD_SHA,
        expectedPrNumber: PR_NUMBER,
        expectedControlIssue: CONTROL_ISSUE,
        expectedScopeRevision: SCOPE_REVISION,
      });

      expect(result.valid).toBe(false);
      expect(result.reason).toBe("MALFORMED_ATTESTATION");
    });

    it("rejects when p0 !== 0", () => {
      const result = validateTerraAttestation({
        attestations: [createValidAttestation({ p0: 1 })],
        expectedHeadSha: VALID_HEAD_SHA,
        expectedPrNumber: PR_NUMBER,
        expectedControlIssue: CONTROL_ISSUE,
        expectedScopeRevision: SCOPE_REVISION,
      });

      expect(result.valid).toBe(false);
      expect(result.reason).toBe("UNRESOLVED_P0_FINDINGS");
    });

    it("rejects when p1 !== 0", () => {
      const result = validateTerraAttestation({
        attestations: [createValidAttestation({ p1: 2 })],
        expectedHeadSha: VALID_HEAD_SHA,
        expectedPrNumber: PR_NUMBER,
        expectedControlIssue: CONTROL_ISSUE,
        expectedScopeRevision: SCOPE_REVISION,
      });

      expect(result.valid).toBe(false);
      expect(result.reason).toBe("UNRESOLVED_P1_FINDINGS");
    });

    it("rejects when verdict is NEEDS_FIX", () => {
      const result = validateTerraAttestation({
        attestations: [createValidAttestation({ verdict: "NEEDS_FIX" })],
        expectedHeadSha: VALID_HEAD_SHA,
        expectedPrNumber: PR_NUMBER,
        expectedControlIssue: CONTROL_ISSUE,
        expectedScopeRevision: SCOPE_REVISION,
      });

      expect(result.valid).toBe(false);
      expect(result.reason).toBe("VERDICT_NEEDS_FIX");
    });

    it("rejects when verdict is BLOCKED", () => {
      const result = validateTerraAttestation({
        attestations: [createValidAttestation({ verdict: "BLOCKED" })],
        expectedHeadSha: VALID_HEAD_SHA,
        expectedPrNumber: PR_NUMBER,
        expectedControlIssue: CONTROL_ISSUE,
        expectedScopeRevision: SCOPE_REVISION,
      });

      expect(result.valid).toBe(false);
      expect(result.reason).toBe("VERDICT_BLOCKED");
    });

    it("rejects when PR number does not match", () => {
      const result = validateTerraAttestation({
        attestations: [createValidAttestation({ pr_number: 999 })],
        expectedHeadSha: VALID_HEAD_SHA,
        expectedPrNumber: PR_NUMBER,
        expectedControlIssue: CONTROL_ISSUE,
        expectedScopeRevision: SCOPE_REVISION,
      });

      expect(result.valid).toBe(false);
      expect(result.reason).toBe("WRONG_PR_NUMBER");
    });

    it("rejects when control issue does not match", () => {
      const result = validateTerraAttestation({
        attestations: [createValidAttestation({ control_issue: 999 })],
        expectedHeadSha: VALID_HEAD_SHA,
        expectedPrNumber: PR_NUMBER,
        expectedControlIssue: CONTROL_ISSUE,
        expectedScopeRevision: SCOPE_REVISION,
      });

      expect(result.valid).toBe(false);
      expect(result.reason).toBe("WRONG_CONTROL_ISSUE");
    });

    it("rejects when scope revision does not match", () => {
      const result = validateTerraAttestation({
        attestations: [createValidAttestation({ scope_revision: 1 })],
        expectedHeadSha: VALID_HEAD_SHA,
        expectedPrNumber: PR_NUMBER,
        expectedControlIssue: CONTROL_ISSUE,
        expectedScopeRevision: SCOPE_REVISION,
      });

      expect(result.valid).toBe(false);
      expect(result.reason).toBe("WRONG_SCOPE_REVISION");
    });

    it("rejects when material_findings_resolved is false", () => {
      const result = validateTerraAttestation({
        attestations: [createValidAttestation({ material_findings_resolved: false })],
        expectedHeadSha: VALID_HEAD_SHA,
        expectedPrNumber: PR_NUMBER,
        expectedControlIssue: CONTROL_ISSUE,
        expectedScopeRevision: SCOPE_REVISION,
      });

      expect(result.valid).toBe(false);
      expect(result.reason).toBe("MATERIAL_FINDINGS_NOT_RESOLVED");
    });

    it("rejects when reviewer model is not terra-xhigh", () => {
      const result = validateTerraAttestation({
        attestations: [createValidAttestation({ reviewer_model: "gemini-3.8-flash" })],
        expectedHeadSha: VALID_HEAD_SHA,
        expectedPrNumber: PR_NUMBER,
        expectedControlIssue: CONTROL_ISSUE,
        expectedScopeRevision: SCOPE_REVISION,
      });

      expect(result.valid).toBe(false);
      expect(result.reason).toBe("INVALID_REVIEWER_MODEL");
    });

    it("fails closed when no attestation exists", () => {
      const result = validateTerraAttestation({
        attestations: [],
        expectedHeadSha: VALID_HEAD_SHA,
        expectedPrNumber: PR_NUMBER,
        expectedControlIssue: CONTROL_ISSUE,
        expectedScopeRevision: SCOPE_REVISION,
      });

      expect(result.valid).toBe(false);
      expect(result.reason).toBe("NO_ATTESTATION_FOUND");
    });

    it("validates controlIssueData integrated in validateTerraAttestation", () => {
      const issueImplementing = {
        number: CONTROL_ISSUE,
        body: `\`\`\`text\nstate: implementing\nscope_revision: ${SCOPE_REVISION}\nfix_reentries: 2\nowner_scope_reset: ${VALID_RESET_LINK}\n\`\`\``,
        labels: [{ name: "implementing" }],
      };

      const failResult = validateTerraAttestation({
        attestations: [createValidAttestation()],
        expectedHeadSha: VALID_HEAD_SHA,
        expectedPrNumber: PR_NUMBER,
        expectedControlIssue: CONTROL_ISSUE,
        expectedScopeRevision: SCOPE_REVISION,
        controlIssueData: issueImplementing,
      });
      expect(failResult.valid).toBe(false);
      expect(failResult.reason).toBe("INVALID_CONTROL_STATE");

      const issueReady = {
        number: CONTROL_ISSUE,
        body: `\`\`\`text\nstate: ready-for-review\nscope_revision: ${SCOPE_REVISION}\nfix_reentries: 1\nowner_scope_reset: ${VALID_RESET_LINK}\n\`\`\``,
        labels: [{ name: "ready-for-review" }],
      };

      const passResult = validateTerraAttestation({
        attestations: [createValidAttestation()],
        expectedHeadSha: VALID_HEAD_SHA,
        expectedPrNumber: PR_NUMBER,
        expectedControlIssue: CONTROL_ISSUE,
        expectedScopeRevision: SCOPE_REVISION,
        controlIssueData: issueReady,
      });
      expect(passResult.valid).toBe(true);
      expect(passResult.reason).toBe("OK");
    });
  });

  describe("Multi-block attestation conflict detection", () => {
    it("identifies identical attestations and detects differences correctly", () => {
      const a = createValidAttestation();
      const b = createValidAttestation();
      expect(areAttestationsIdentical(a, b)).toBe(true);

      expect(areAttestationsIdentical(a, { ...b, p0: 1 })).toBe(false);
      expect(areAttestationsIdentical(a, { ...b, p1: 1 })).toBe(false);
      expect(areAttestationsIdentical(a, { ...b, verdict: "NEEDS_FIX" })).toBe(false);
      expect(areAttestationsIdentical(a, { ...b, head_sha: STALE_HEAD_SHA })).toBe(false);
      expect(areAttestationsIdentical(a, { ...b, scope_revision: 1 })).toBe(false);
      expect(areAttestationsIdentical(a, { ...b, reviewed_at_utc: "2026-09-04T00:00:00Z" })).toBe(false);
    });

    it("deduplicates multiple completely identical attestations in a single comment", () => {
      const comments = [
        {
          id: 1,
          created_at: "2026-09-03T12:00:00Z",
          body: `
\`\`\`terra-attestation
reviewer_model: terra-xhigh
head_sha: ${VALID_HEAD_SHA}
pr_number: ${PR_NUMBER}
control_issue: ${CONTROL_ISSUE}
scope_revision: ${SCOPE_REVISION}
verdict: RECOMMEND_PASS
p0: 0
p1: 0
material_findings_resolved: true
reviewed_at_utc: ${VALID_TIMESTAMP}
\`\`\`
\`\`\`terra-attestation
reviewer_model: terra-xhigh
head_sha: ${VALID_HEAD_SHA}
pr_number: ${PR_NUMBER}
control_issue: ${CONTROL_ISSUE}
scope_revision: ${SCOPE_REVISION}
verdict: RECOMMEND_PASS
p0: 0
p1: 0
material_findings_resolved: true
reviewed_at_utc: ${VALID_TIMESTAMP}
\`\`\`
          `,
        },
      ];

      const attestations = parseAttestationsFromComments(comments);
      expect(attestations).toHaveLength(1);
      const result = validateTerraAttestation({
        attestations,
        expectedHeadSha: VALID_HEAD_SHA,
        expectedPrNumber: PR_NUMBER,
        expectedControlIssue: CONTROL_ISSUE,
        expectedScopeRevision: SCOPE_REVISION,
      });
      expect(result.valid).toBe(true);
    });

    it("rejects multi-block comment when an older pass block is combined with later p0: 1", () => {
      const comments = [
        {
          id: 1,
          created_at: "2026-09-03T12:00:00Z",
          body: `
\`\`\`terra-attestation
reviewer_model: terra-xhigh
head_sha: ${VALID_HEAD_SHA}
pr_number: ${PR_NUMBER}
control_issue: ${CONTROL_ISSUE}
scope_revision: ${SCOPE_REVISION}
verdict: RECOMMEND_PASS
p0: 0
p1: 0
material_findings_resolved: true
reviewed_at_utc: ${VALID_TIMESTAMP}
\`\`\`
\`\`\`terra-attestation
reviewer_model: terra-xhigh
head_sha: ${VALID_HEAD_SHA}
pr_number: ${PR_NUMBER}
control_issue: ${CONTROL_ISSUE}
scope_revision: ${SCOPE_REVISION}
verdict: RECOMMEND_PASS
p0: 1
p1: 0
material_findings_resolved: true
reviewed_at_utc: ${VALID_TIMESTAMP}
\`\`\`
          `,
        },
      ];

      const attestations = parseAttestationsFromComments(comments);
      const result = validateTerraAttestation({
        attestations,
        expectedHeadSha: VALID_HEAD_SHA,
        expectedPrNumber: PR_NUMBER,
        expectedControlIssue: CONTROL_ISSUE,
        expectedScopeRevision: SCOPE_REVISION,
      });
      expect(result.valid).toBe(false);
      expect(result.reason).toBe("CONFLICTING_ATTESTATIONS");
    });

    it("rejects conflicting verdicts within the same comment", () => {
      const comments = [
        {
          id: 1,
          created_at: "2026-09-03T12:00:00Z",
          body: `
\`\`\`terra-attestation
reviewer_model: terra-xhigh
head_sha: ${VALID_HEAD_SHA}
pr_number: ${PR_NUMBER}
control_issue: ${CONTROL_ISSUE}
scope_revision: ${SCOPE_REVISION}
verdict: RECOMMEND_PASS
p0: 0
p1: 0
material_findings_resolved: true
reviewed_at_utc: ${VALID_TIMESTAMP}
\`\`\`
\`\`\`terra-attestation
reviewer_model: terra-xhigh
head_sha: ${VALID_HEAD_SHA}
pr_number: ${PR_NUMBER}
control_issue: ${CONTROL_ISSUE}
scope_revision: ${SCOPE_REVISION}
verdict: NEEDS_FIX
p0: 1
p1: 0
material_findings_resolved: false
reviewed_at_utc: ${VALID_TIMESTAMP}
\`\`\`
          `,
        },
      ];

      const attestations = parseAttestationsFromComments(comments);
      const result = validateTerraAttestation({
        attestations,
        expectedHeadSha: VALID_HEAD_SHA,
        expectedPrNumber: PR_NUMBER,
        expectedControlIssue: CONTROL_ISSUE,
        expectedScopeRevision: SCOPE_REVISION,
      });
      expect(result.valid).toBe(false);
      expect(result.reason).toBe("CONFLICTING_ATTESTATIONS");
    });
  });

  describe("Pagination and later-attestation precedence", () => {
    it("fetches all pages deterministically across multiple pages", async () => {
      const mockApi = async (url: string) => {
        const page = new URL(url).searchParams.get("page");
        if (page === "1") {
          return Array.from({ length: 100 }, (_, i) => ({ id: i + 1, body: `Comment ${i + 1}` }));
        }
        if (page === "2") {
          return Array.from({ length: 5 }, (_, i) => ({ id: i + 101, body: `Comment ${i + 101}` }));
        }
        return [];
      };

      const all = await fetchAllPagedItems("https://api.github.com/repos/example/issues/1/comments", "fake-token", mockApi);
      expect(all).toHaveLength(105);
      expect(all[0].id).toBe(1);
      expect(all[104].id).toBe(105);
    });

    it("simulates later failing attestation on page 2 overriding earlier pass on page 1", async () => {
      const page1Comments = [
        {
          id: 1,
          created_at: "2026-09-03T10:00:00Z",
          body: `
\`\`\`terra-attestation
reviewer_model: terra-xhigh
head_sha: ${VALID_HEAD_SHA}
pr_number: ${PR_NUMBER}
control_issue: ${CONTROL_ISSUE}
scope_revision: ${SCOPE_REVISION}
verdict: RECOMMEND_PASS
p0: 0
p1: 0
material_findings_resolved: true
reviewed_at_utc: ${VALID_TIMESTAMP}
\`\`\`
          `,
        },
        // Pad to 100 items
        ...Array.from({ length: 99 }, (_, i) => ({
          id: i + 2,
          created_at: `2026-09-03T10:0${i % 10}:00Z`,
          body: `Discussion comment ${i + 2}`,
        })),
      ];

      const page2Comments = [
        {
          id: 101,
          created_at: "2026-09-03T12:00:00Z", // later timestamp
          body: `
\`\`\`terra-attestation
reviewer_model: terra-xhigh
head_sha: ${VALID_HEAD_SHA}
pr_number: ${PR_NUMBER}
control_issue: ${CONTROL_ISSUE}
scope_revision: ${SCOPE_REVISION}
verdict: NEEDS_FIX
p0: 1
p1: 0
material_findings_resolved: false
reviewed_at_utc: "2026-09-03T21:00:00Z"
\`\`\`
          `,
        },
      ];

      const mockGet = async (url: string) => {
        const page = new URL(url).searchParams.get("page");
        if (page === "1") return page1Comments;
        if (page === "2") return page2Comments;
        return [];
      };

      const allItems = await fetchAllPagedItems("https://api.github.com/comments", "fake", mockGet);
      expect(allItems).toHaveLength(101);

      const attestations = parseAttestationsFromComments(allItems);
      expect(attestations).toHaveLength(2);

      const result = validateTerraAttestation({
        attestations,
        expectedHeadSha: VALID_HEAD_SHA,
        expectedPrNumber: PR_NUMBER,
        expectedControlIssue: CONTROL_ISSUE,
        expectedScopeRevision: SCOPE_REVISION,
      });

      expect(result.valid).toBe(false);
      expect(result.reason).toBe("VERDICT_NEEDS_FIX");
    });
  });

  describe("CLI execution", () => {
    it("succeeds with exit code 0 on valid attestation file and valid control issue", () => {
      const tmpFile = join(tmpdir(), `terra-valid-${Date.now()}.md`);
      const tmpIssue = join(tmpdir(), `control-issue-valid-${Date.now()}.json`);
      const content = `
\`\`\`terra-attestation
reviewer_model: terra-xhigh
head_sha: ${VALID_HEAD_SHA}
pr_number: ${PR_NUMBER}
control_issue: ${CONTROL_ISSUE}
scope_revision: ${SCOPE_REVISION}
verdict: RECOMMEND_PASS
p0: 0
p1: 0
material_findings_resolved: true
reviewed_at_utc: ${VALID_TIMESTAMP}
\`\`\`
      `;
      const issueData = {
        number: CONTROL_ISSUE,
        body: `\`\`\`text\nstate: ready-for-review\nscope_revision: ${SCOPE_REVISION}\nfix_reentries: 0\nowner_scope_reset: ${VALID_RESET_LINK}\n\`\`\``,
        labels: [{ name: "ready-for-review" }],
      };
      writeFileSync(tmpFile, content, "utf8");
      writeFileSync(tmpIssue, JSON.stringify(issueData), "utf8");

      try {
        const proc = spawnSync(
          process.execPath,
          [
            ".github/scripts/validate_terra_attestation.mjs",
            "--file",
            tmpFile,
            "--head-sha",
            VALID_HEAD_SHA,
            "--pr",
            String(PR_NUMBER),
            "--control-issue",
            String(CONTROL_ISSUE),
            "--scope-revision",
            String(SCOPE_REVISION),
            "--control-issue-file",
            tmpIssue,
          ],
          { encoding: "utf8" }
        );

        expect(proc.status).toBe(0);
        expect(proc.stdout).toContain("[PASS]");
      } finally {
        unlinkSync(tmpFile);
        unlinkSync(tmpIssue);
      }
    });

    it("fails with exit code 1 when PR #6 bootstrap has mismatched control issue or scope revision", () => {
      const tmpFile = join(tmpdir(), `terra-bootstrap-mismatch-${Date.now()}.md`);
      const content = `
\`\`\`terra-attestation
reviewer_model: terra-xhigh
head_sha: ${VALID_HEAD_SHA}
pr_number: 6
control_issue: 8
scope_revision: 2
verdict: RECOMMEND_PASS
p0: 0
p1: 0
material_findings_resolved: true
reviewed_at_utc: ${VALID_TIMESTAMP}
\`\`\`
      `;
      writeFileSync(tmpFile, content, "utf8");

      try {
        const proc = spawnSync(
          process.execPath,
          [
            ".github/scripts/validate_terra_attestation.mjs",
            "--file",
            tmpFile,
            "--pr",
            "6",
            "--control-issue",
            "8",
          ],
          { encoding: "utf8" }
        );

        expect(proc.status).toBe(1);
        expect(proc.stderr).toContain("PR #6 bootstrap must bind to control issue #7");
      } finally {
        unlinkSync(tmpFile);
      }
    });

    it("fails with exit code 1 when control issue fetch fails", () => {
      const tmpFile = join(tmpdir(), `terra-fetch-fail-${Date.now()}.md`);
      const content = `
\`\`\`terra-attestation
reviewer_model: terra-xhigh
head_sha: ${VALID_HEAD_SHA}
pr_number: ${PR_NUMBER}
control_issue: ${CONTROL_ISSUE}
scope_revision: ${SCOPE_REVISION}
verdict: RECOMMEND_PASS
p0: 0
p1: 0
material_findings_resolved: true
reviewed_at_utc: ${VALID_TIMESTAMP}
\`\`\`
      `;
      writeFileSync(tmpFile, content, "utf8");

      try {
        const proc = spawnSync(
          process.execPath,
          [
            ".github/scripts/validate_terra_attestation.mjs",
            "--file",
            tmpFile,
            "--control-issue-fetch-fail",
          ],
          { encoding: "utf8" }
        );

        expect(proc.status).toBe(1);
        expect(proc.stderr).toContain("ISSUE_FETCH_FAILED");
      } finally {
        unlinkSync(tmpFile);
      }
    });

    it("fails with exit code 1 when control issue is in implementing state", () => {
      const tmpFile = join(tmpdir(), `terra-impl-state-${Date.now()}.md`);
      const tmpIssue = join(tmpdir(), `control-issue-impl-${Date.now()}.json`);
      const content = `
\`\`\`terra-attestation
reviewer_model: terra-xhigh
head_sha: ${VALID_HEAD_SHA}
pr_number: ${PR_NUMBER}
control_issue: ${CONTROL_ISSUE}
scope_revision: ${SCOPE_REVISION}
verdict: RECOMMEND_PASS
p0: 0
p1: 0
material_findings_resolved: true
reviewed_at_utc: ${VALID_TIMESTAMP}
\`\`\`
      `;
      const issueData = {
        number: CONTROL_ISSUE,
        body: `\`\`\`text\nstate: implementing\nscope_revision: ${SCOPE_REVISION}\nfix_reentries: 2\nowner_scope_reset: ${VALID_RESET_LINK}\n\`\`\``,
        labels: [{ name: "implementing" }],
      };
      writeFileSync(tmpFile, content, "utf8");
      writeFileSync(tmpIssue, JSON.stringify(issueData), "utf8");

      try {
        const proc = spawnSync(
          process.execPath,
          [
            ".github/scripts/validate_terra_attestation.mjs",
            "--file",
            tmpFile,
            "--head-sha",
            VALID_HEAD_SHA,
            "--pr",
            String(PR_NUMBER),
            "--control-issue",
            String(CONTROL_ISSUE),
            "--scope-revision",
            String(SCOPE_REVISION),
            "--control-issue-file",
            tmpIssue,
          ],
          { encoding: "utf8" }
        );

        expect(proc.status).toBe(1);
        expect(proc.stderr).toContain("INVALID_CONTROL_STATE");
      } finally {
        unlinkSync(tmpFile);
        unlinkSync(tmpIssue);
      }
    });

    it("fails with exit code 1 on stale attestation file", () => {
      const tmpFile = join(tmpdir(), `terra-stale-${Date.now()}.md`);
      const content = `
\`\`\`terra-attestation
reviewer_model: terra-xhigh
head_sha: ${STALE_HEAD_SHA}
pr_number: ${PR_NUMBER}
control_issue: ${CONTROL_ISSUE}
scope_revision: ${SCOPE_REVISION}
verdict: RECOMMEND_PASS
p0: 0
p1: 0
material_findings_resolved: true
reviewed_at_utc: ${VALID_TIMESTAMP}
\`\`\`
      `;
      writeFileSync(tmpFile, content, "utf8");

      try {
        const proc = spawnSync(
          process.execPath,
          [
            ".github/scripts/validate_terra_attestation.mjs",
            "--file",
            tmpFile,
            "--head-sha",
            VALID_HEAD_SHA,
            "--pr",
            String(PR_NUMBER),
            "--control-issue",
            String(CONTROL_ISSUE),
            "--scope-revision",
            String(SCOPE_REVISION),
          ],
          { encoding: "utf8" }
        );

        expect(proc.status).toBe(1);
        expect(proc.stderr).toContain("STALE_HEAD_SHA");
      } finally {
        unlinkSync(tmpFile);
      }
    });
  });
});
