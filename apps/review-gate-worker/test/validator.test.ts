import { describe, expect, it } from "vitest";
import {
  extractAttestationsFromCommentText,
  extractOwnerAttestationsFromComments,
  isAuthorizedOwnerComment,
  parseAgentControlBlock,
  parseCanonicalNonNegativeInteger,
  parseOwnerScopeResetApproval,
  validateControlIssue,
  validateReviewGate,
} from "../src/validator.ts";
import { GitHubIssue, GitHubIssueComment, TerraAttestation } from "../src/types.ts";

const VALID_HEAD_SHA = "7074b025458d63e009da12e5e85f891852108004";
const STALE_HEAD_SHA = "2222222222222222222222222222222222222222";
const PR_NUMBER = 6;
const CONTROL_ISSUE = 7;
const SCOPE_REVISION = 3;
const VALID_TIMESTAMP = "2026-09-04T02:00:00Z";
const VALID_RESET_LINK = "https://github.com/Banhtalon/mindx-review-bot/issues/7#issuecomment-5534707230";

function createValidAttestation(overrides: Partial<TerraAttestation> = {}): TerraAttestation {
  return {
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

function createValidControlBlockMarkdown(overrides: Record<string, string> = {}): string {
  const values = {
    state: "ready-for-review",
    scope_revision: "3",
    fix_reentries: "0",
    owner_scope_reset: VALID_RESET_LINK,
    ...overrides,
  };
  return `
<!-- AGENT_CONTROL_BLOCK_V1 -->
state: ${values.state}
scope_revision: ${values.scope_revision}
fix_reentries: ${values.fix_reentries}
owner_scope_reset: ${values.owner_scope_reset}
<!-- /AGENT_CONTROL_BLOCK_V1 -->
`;
}

function createValidScopeResetComment(overrides: Record<string, unknown> = {}): GitHubIssueComment {
  return {
    id: 5534707230,
    user: {
      login: "Banhtalon",
      id: 105797112,
    },
    author_association: "OWNER",
    body: `
<!-- OWNER_SCOPE_RESET_V1 -->
old_scope_revision: 2
new_scope_revision: 3
reason: Redesign review authority
material_scope_change: Trusted GitHub App review-gate worker
owner_decision: APPROVED
approved_by: Banhtalon
<!-- /OWNER_SCOPE_RESET_V1 -->
`,
    created_at: "2026-09-04T01:00:00Z",
    ...overrides,
  };
}

describe("Review Gate Validator (Scope Revision 3)", () => {
  describe("Numeric Parsing", () => {
    it("accepts canonical non-negative decimal integers", () => {
      expect(parseCanonicalNonNegativeInteger(0)).toBe(0);
      expect(parseCanonicalNonNegativeInteger("0")).toBe(0);
      expect(parseCanonicalNonNegativeInteger(3)).toBe(3);
      expect(parseCanonicalNonNegativeInteger("3")).toBe(3);
      expect(parseCanonicalNonNegativeInteger(42)).toBe(42);
    });

    it("rejects non-canonical numbers", () => {
      expect(parseCanonicalNonNegativeInteger(-1)).toBeNull();
      expect(parseCanonicalNonNegativeInteger("+1")).toBeNull();
      expect(parseCanonicalNonNegativeInteger(0.5)).toBeNull();
      expect(parseCanonicalNonNegativeInteger("1.0")).toBeNull();
      expect(parseCanonicalNonNegativeInteger("01")).toBeNull();
      expect(parseCanonicalNonNegativeInteger(" 1 ")).toBeNull();
      expect(parseCanonicalNonNegativeInteger("1e5")).toBeNull();
      expect(parseCanonicalNonNegativeInteger(NaN)).toBeNull();
      expect(parseCanonicalNonNegativeInteger(Infinity)).toBeNull();
      expect(parseCanonicalNonNegativeInteger(null)).toBeNull();
      expect(parseCanonicalNonNegativeInteger(undefined)).toBeNull();
    });
  });

  describe("Agent Control Block V1 Parsing", () => {
    it("parses valid AGENT_CONTROL_BLOCK_V1", () => {
      const text = createValidControlBlockMarkdown();
      const res = parseAgentControlBlock(text);
      expect(res.valid).toBe(true);
      if (res.valid) {
        expect(res.block.state).toBe("ready-for-review");
        expect(res.block.scope_revision).toBe(3);
        expect(res.block.fix_reentries).toBe(0);
        expect(res.block.owner_scope_reset).toBe(VALID_RESET_LINK);
      }
    });

    it("fails when AGENT_CONTROL_BLOCK_V1 markers are missing", () => {
      const res = parseAgentControlBlock("Some text without control block");
      expect(res.valid).toBe(false);
      if (!res.valid) {
        expect(res.reason).toBe("MISSING_AGENT_CONTROL_BLOCK");
      }
    });

    it("fails when multiple AGENT_CONTROL_BLOCK_V1 blocks exist", () => {
      const text = `
<!-- AGENT_CONTROL_BLOCK_V1 -->
state: ready-for-review
scope_revision: 3
fix_reentries: 0
owner_scope_reset: ${VALID_RESET_LINK}
<!-- /AGENT_CONTROL_BLOCK_V1 -->

<!-- AGENT_CONTROL_BLOCK_V1 -->
state: ready-for-verify
scope_revision: 3
fix_reentries: 0
owner_scope_reset: ${VALID_RESET_LINK}
<!-- /AGENT_CONTROL_BLOCK_V1 -->
      `;
      const res = parseAgentControlBlock(text);
      expect(res.valid).toBe(false);
      if (!res.valid) {
        expect(res.reason).toBe("MULTIPLE_AGENT_CONTROL_BLOCKS");
      }
    });

    it("fails when duplicate keys exist in AGENT_CONTROL_BLOCK_V1", () => {
      const text = `
<!-- AGENT_CONTROL_BLOCK_V1 -->
state: ready-for-review
state: ready-for-verify
scope_revision: 3
fix_reentries: 0
owner_scope_reset: ${VALID_RESET_LINK}
<!-- /AGENT_CONTROL_BLOCK_V1 -->
      `;
      const res = parseAgentControlBlock(text);
      expect(res.valid).toBe(false);
      if (!res.valid) {
        expect(res.reason).toBe("DUPLICATE_KEY_IN_CONTROL_BLOCK");
      }
    });

    it("fails when unknown keys exist in AGENT_CONTROL_BLOCK_V1", () => {
      const text = `
<!-- AGENT_CONTROL_BLOCK_V1 -->
state: ready-for-review
scope_revision: 3
fix_reentries: 0
owner_scope_reset: ${VALID_RESET_LINK}
unexpected_key: foo
<!-- /AGENT_CONTROL_BLOCK_V1 -->
      `;
      const res = parseAgentControlBlock(text);
      expect(res.valid).toBe(false);
      if (!res.valid) {
        expect(res.reason).toBe("UNKNOWN_KEY_IN_CONTROL_BLOCK");
      }
    });

    it("fails when required keys are missing in AGENT_CONTROL_BLOCK_V1", () => {
      const text = `
<!-- AGENT_CONTROL_BLOCK_V1 -->
state: ready-for-review
scope_revision: 3
fix_reentries: 0
<!-- /AGENT_CONTROL_BLOCK_V1 -->
      `;
      const res = parseAgentControlBlock(text);
      expect(res.valid).toBe(false);
      if (!res.valid) {
        expect(res.reason).toBe("MISSING_FIELD_IN_CONTROL_BLOCK");
      }
    });

    it("fails when fix_reentries is out of range 0..2", () => {
      const text = createValidControlBlockMarkdown({ fix_reentries: "3" });
      const res = parseAgentControlBlock(text);
      expect(res.valid).toBe(false);
      if (!res.valid) {
        expect(res.reason).toBe("INVALID_CONTROL_BLOCK");
      }
    });

    it("fails when scope_revision > 1 has owner_scope_reset set to 'none'", () => {
      const text = createValidControlBlockMarkdown({ owner_scope_reset: "none" });
      const res = parseAgentControlBlock(text);
      expect(res.valid).toBe(false);
      if (!res.valid) {
        expect(res.reason).toBe("INVALID_CONTROL_BLOCK");
      }
    });
  });

  describe("Control Issue Validation", () => {
    it("validates control issue with matching state label", () => {
      const issue: GitHubIssue = {
        number: 7,
        title: "Control Issue",
        body: createValidControlBlockMarkdown(),
        state: "open",
        labels: ["ready-for-review"],
        user: { login: "Banhtalon", id: 105797112 },
      };
      const res = validateControlIssue(issue, 3);
      expect(res.valid).toBe(true);
      if (res.valid) {
        expect(res.block.state).toBe("ready-for-review");
        expect(res.primaryLabel).toBe("ready-for-review");
      }
    });

    it("fails when primary workflow state label is missing", () => {
      const issue: GitHubIssue = {
        number: 7,
        title: "Control Issue",
        body: createValidControlBlockMarkdown(),
        state: "open",
        labels: ["enhancement"],
        user: { login: "Banhtalon", id: 105797112 },
      };
      const res = validateControlIssue(issue, 3);
      expect(res.valid).toBe(false);
      if (!res.valid) {
        expect(res.reason).toBe("ZERO_PRIMARY_STATE_LABELS");
      }
    });

    it("fails when multiple primary workflow state labels exist", () => {
      const issue: GitHubIssue = {
        number: 7,
        title: "Control Issue",
        body: createValidControlBlockMarkdown(),
        state: "open",
        labels: ["ready-for-review", "ready-for-verify"],
        user: { login: "Banhtalon", id: 105797112 },
      };
      const res = validateControlIssue(issue, 3);
      expect(res.valid).toBe(false);
      if (!res.valid) {
        expect(res.reason).toBe("MULTIPLE_PRIMARY_STATE_LABELS");
      }
    });

    it("fails when primary label does not match block state", () => {
      const issue: GitHubIssue = {
        number: 7,
        title: "Control Issue",
        body: createValidControlBlockMarkdown({ state: "ready-for-review" }),
        state: "open",
        labels: ["ready-for-verify"],
        user: { login: "Banhtalon", id: 105797112 },
      };
      const res = validateControlIssue(issue, 3);
      expect(res.valid).toBe(false);
      if (!res.valid) {
        expect(res.reason).toBe("LABEL_STATE_MISMATCH");
      }
    });

    it("fails when control issue state is not reviewable (e.g. implementing)", () => {
      const issue: GitHubIssue = {
        number: 7,
        title: "Control Issue",
        body: createValidControlBlockMarkdown({ state: "implementing" }),
        state: "open",
        labels: ["implementing"],
        user: { login: "Banhtalon", id: 105797112 },
      };
      const res = validateControlIssue(issue, 3);
      expect(res.valid).toBe(false);
      if (!res.valid) {
        expect(res.reason).toBe("INVALID_CONTROL_STATE");
      }
    });

    it("fails when scope revision does not match expected", () => {
      const issue: GitHubIssue = {
        number: 7,
        title: "Control Issue",
        body: createValidControlBlockMarkdown({ scope_revision: "2" }),
        state: "open",
        labels: ["ready-for-review"],
        user: { login: "Banhtalon", id: 105797112 },
      };
      const res = validateControlIssue(issue, 3);
      expect(res.valid).toBe(false);
      if (!res.valid) {
        expect(res.reason).toBe("WRONG_SCOPE_REVISION");
      }
    });
  });

  describe("Owner Scope Reset Approval V1", () => {
    it("validates authentic Owner scope reset comment", () => {
      const comment = createValidScopeResetComment();
      const res = parseOwnerScopeResetApproval(comment, 2, 3);
      expect(res.valid).toBe(true);
      if (res.valid) {
        expect(res.approval.old_scope_revision).toBe(2);
        expect(res.approval.new_scope_revision).toBe(3);
        expect(res.approval.owner_decision).toBe("APPROVED");
        expect(res.approval.approved_by).toBe("Banhtalon");
      }
    });

    it("rejects scope reset authored by unauthorized user", () => {
      const comment = createValidScopeResetComment({
        user: { login: "attacker", id: 99999 },
      });
      const res = parseOwnerScopeResetApproval(comment, 2, 3);
      expect(res.valid).toBe(false);
      if (!res.valid) {
        expect(res.reason).toBe("UNAUTHORIZED_SCOPE_RESET_AUTHOR");
      }
    });

    it("rejects scope reset with wrong user ID despite matching login", () => {
      const comment = createValidScopeResetComment({
        user: { login: "Banhtalon", id: 99999 },
      });
      const res = parseOwnerScopeResetApproval(comment, 2, 3);
      expect(res.valid).toBe(false);
      if (!res.valid) {
        expect(res.reason).toBe("UNAUTHORIZED_SCOPE_RESET_AUTHOR");
      }
    });

    it("rejects scope reset with non-OWNER association", () => {
      const comment = createValidScopeResetComment({
        author_association: "CONTRIBUTOR",
      });
      const res = parseOwnerScopeResetApproval(comment, 2, 3);
      expect(res.valid).toBe(false);
      if (!res.valid) {
        expect(res.reason).toBe("UNAUTHORIZED_SCOPE_RESET_AUTHOR");
      }
    });

    it("rejects scope reset when revisions do not match transition", () => {
      const comment = createValidScopeResetComment();
      const res = parseOwnerScopeResetApproval(comment, 1, 2);
      expect(res.valid).toBe(false);
      if (!res.valid) {
        expect(res.reason).toBe("SCOPE_RESET_REVISION_MISMATCH");
      }
    });

    it("rejects scope reset when owner_decision is not APPROVED", () => {
      const comment = createValidScopeResetComment({
        body: `
<!-- OWNER_SCOPE_RESET_V1 -->
old_scope_revision: 2
new_scope_revision: 3
reason: test
material_scope_change: test
owner_decision: REJECTED
approved_by: Banhtalon
<!-- /OWNER_SCOPE_RESET_V1 -->
        `,
      });
      const res = parseOwnerScopeResetApproval(comment, 2, 3);
      expect(res.valid).toBe(false);
      if (!res.valid) {
        expect(res.reason).toBe("SCOPE_RESET_NOT_APPROVED");
      }
    });
  });

  describe("Attestation Provenance Filtering", () => {
    it("recognizes authorized Owner comments", () => {
      const comment: GitHubIssueComment = {
        id: 1,
        user: { login: "Banhtalon", id: 105797112 },
        author_association: "OWNER",
        body: "Hello",
        created_at: "2026-09-04T00:00:00Z",
      };
      expect(isAuthorizedOwnerComment(comment)).toBe(true);
    });

    it("rejects non-owner commenters", () => {
      const comment1: GitHubIssueComment = {
        id: 2,
        user: { login: "random-user", id: 12345 },
        author_association: "NONE",
        body: "Hello",
        created_at: "2026-09-04T00:00:00Z",
      };
      expect(isAuthorizedOwnerComment(comment1)).toBe(false);

      const comment2: GitHubIssueComment = {
        id: 3,
        user: { login: "Banhtalon", id: 99999 },
        author_association: "OWNER",
        body: "Hello",
        created_at: "2026-09-04T00:00:00Z",
      };
      expect(isAuthorizedOwnerComment(comment2)).toBe(false);
    });

    it("ignores attestation blocks from non-owners", () => {
      const comments: GitHubIssueComment[] = [
        {
          id: 1,
          user: { login: "random-contributor", id: 99999 },
          author_association: "CONTRIBUTOR",
          body: `
<!-- TERRA_REVIEW_ATTESTATION_V1 -->
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
<!-- /TERRA_REVIEW_ATTESTATION_V1 -->
          `,
          created_at: "2026-09-04T01:00:00Z",
        },
      ];

      const found = extractOwnerAttestationsFromComments(comments);
      expect(found).toHaveLength(0);
    });

    it("later authorized comment overrides earlier authorized comment", () => {
      const comments: GitHubIssueComment[] = [
        {
          id: 1,
          user: { login: "Banhtalon", id: 105797112 },
          author_association: "OWNER",
          body: `
<!-- TERRA_REVIEW_ATTESTATION_V1 -->
reviewer_model: terra-xhigh
head_sha: ${VALID_HEAD_SHA}
pr_number: ${PR_NUMBER}
control_issue: ${CONTROL_ISSUE}
scope_revision: ${SCOPE_REVISION}
verdict: RECOMMEND_PASS
p0: 0
p1: 0
material_findings_resolved: true
reviewed_at_utc: 2026-09-04T01:00:00Z
<!-- /TERRA_REVIEW_ATTESTATION_V1 -->
          `,
          created_at: "2026-09-04T01:00:00Z",
        },
        {
          id: 2,
          user: { login: "Banhtalon", id: 105797112 },
          author_association: "OWNER",
          body: `
<!-- TERRA_REVIEW_ATTESTATION_V1 -->
reviewer_model: terra-xhigh
head_sha: ${VALID_HEAD_SHA}
pr_number: ${PR_NUMBER}
control_issue: ${CONTROL_ISSUE}
scope_revision: ${SCOPE_REVISION}
verdict: NEEDS_FIX
p0: 1
p1: 0
material_findings_resolved: false
reviewed_at_utc: 2026-09-04T02:00:00Z
<!-- /TERRA_REVIEW_ATTESTATION_V1 -->
          `,
          created_at: "2026-09-04T02:00:00Z",
        },
      ];

      const found = extractOwnerAttestationsFromComments(comments);
      expect(found).toHaveLength(2);
      expect(found[1].verdict).toBe("NEEDS_FIX");
    });

    it("untrusted later comment cannot override older authorized pass", () => {
      const comments: GitHubIssueComment[] = [
        {
          id: 1,
          user: { login: "Banhtalon", id: 105797112 },
          author_association: "OWNER",
          body: `
<!-- TERRA_REVIEW_ATTESTATION_V1 -->
reviewer_model: terra-xhigh
head_sha: ${VALID_HEAD_SHA}
pr_number: ${PR_NUMBER}
control_issue: ${CONTROL_ISSUE}
scope_revision: ${SCOPE_REVISION}
verdict: RECOMMEND_PASS
p0: 0
p1: 0
material_findings_resolved: true
reviewed_at_utc: 2026-09-04T01:00:00Z
<!-- /TERRA_REVIEW_ATTESTATION_V1 -->
          `,
          created_at: "2026-09-04T01:00:00Z",
        },
        {
          id: 2,
          user: { login: "attacker", id: 55555 },
          author_association: "NONE",
          body: `
<!-- TERRA_REVIEW_ATTESTATION_V1 -->
reviewer_model: terra-xhigh
head_sha: ${VALID_HEAD_SHA}
pr_number: ${PR_NUMBER}
control_issue: ${CONTROL_ISSUE}
scope_revision: ${SCOPE_REVISION}
verdict: BLOCKED
p0: 5
p1: 5
material_findings_resolved: false
reviewed_at_utc: 2026-09-04T02:00:00Z
<!-- /TERRA_REVIEW_ATTESTATION_V1 -->
          `,
          created_at: "2026-09-04T02:00:00Z",
        },
      ];

      const found = extractOwnerAttestationsFromComments(comments);
      expect(found).toHaveLength(1);
      expect(found[0].verdict).toBe("RECOMMEND_PASS");
    });
  });

  describe("Attestation Block Parsing & Validation", () => {
    it("parses valid TERRA_REVIEW_ATTESTATION_V1 in YAML format", () => {
      const text = `
<!-- TERRA_REVIEW_ATTESTATION_V1 -->
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
<!-- /TERRA_REVIEW_ATTESTATION_V1 -->
      `;
      const attestations = extractAttestationsFromCommentText(text);
      expect(attestations).toHaveLength(1);
      expect(attestations[0].malformed).toBe(false);
      expect(attestations[0].verdict).toBe("RECOMMEND_PASS");
      expect(attestations[0].p0).toBe(0);
      expect(attestations[0].p1).toBe(0);
      expect(attestations[0].reviewed_at_utc).toBe(VALID_TIMESTAMP);
    });

    it("parses valid TERRA_REVIEW_ATTESTATION_V1 in JSON format", () => {
      const text = `
<!-- TERRA_REVIEW_ATTESTATION_V1 -->
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
<!-- /TERRA_REVIEW_ATTESTATION_V1 -->
      `;
      const attestations = extractAttestationsFromCommentText(text);
      expect(attestations).toHaveLength(1);
      expect(attestations[0].malformed).toBe(false);
      expect(attestations[0].verdict).toBe("RECOMMEND_PASS");
    });

    it("rejects attestation with invalid calendar date (2026-02-29)", () => {
      const text = `
<!-- TERRA_REVIEW_ATTESTATION_V1 -->
reviewer_model: terra-xhigh
head_sha: ${VALID_HEAD_SHA}
pr_number: ${PR_NUMBER}
control_issue: ${CONTROL_ISSUE}
scope_revision: ${SCOPE_REVISION}
verdict: RECOMMEND_PASS
p0: 0
p1: 0
material_findings_resolved: true
reviewed_at_utc: 2026-02-29T00:00:00Z
<!-- /TERRA_REVIEW_ATTESTATION_V1 -->
      `;
      const found = extractAttestationsFromCommentText(text);
      expect(found[0].malformed).toBe(true);
      expect(found[0].error).toContain("reviewed_at_utc must be a valid full ISO-8601 UTC timestamp");
    });

    it("rejects duplicate keys in JSON attestation", () => {
      const text = `
<!-- TERRA_REVIEW_ATTESTATION_V1 -->
{
  "reviewer_model": "terra-xhigh",
  "reviewer_model": "gemini",
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
<!-- /TERRA_REVIEW_ATTESTATION_V1 -->
      `;
      const found = extractAttestationsFromCommentText(text);
      expect(found[0].malformed).toBe(true);
      expect(found[0].error).toContain("Duplicate key");
    });

    it("rejects conflicting non-identical blocks in single comment", () => {
      const comment: GitHubIssueComment = {
        id: 1,
        user: { login: "Banhtalon", id: 105797112 },
        author_association: "OWNER",
        body: `
<!-- TERRA_REVIEW_ATTESTATION_V1 -->
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
<!-- /TERRA_REVIEW_ATTESTATION_V1 -->

<!-- TERRA_REVIEW_ATTESTATION_V1 -->
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
<!-- /TERRA_REVIEW_ATTESTATION_V1 -->
        `,
        created_at: "2026-09-04T00:00:00Z",
      };

      const found = extractOwnerAttestationsFromComments([comment]);
      expect(found).toHaveLength(1);
      expect(found[0].conflicting).toBe(true);
    });

    it("accepts identical duplicated blocks in single comment", () => {
      const comment: GitHubIssueComment = {
        id: 1,
        user: { login: "Banhtalon", id: 105797112 },
        author_association: "OWNER",
        body: `
<!-- TERRA_REVIEW_ATTESTATION_V1 -->
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
<!-- /TERRA_REVIEW_ATTESTATION_V1 -->

<!-- TERRA_REVIEW_ATTESTATION_V1 -->
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
<!-- /TERRA_REVIEW_ATTESTATION_V1 -->
        `,
        created_at: "2026-09-04T00:00:00Z",
      };

      const found = extractOwnerAttestationsFromComments([comment]);
      expect(found).toHaveLength(1);
      expect(found[0].conflicting).toBeUndefined();
      expect(found[0].verdict).toBe("RECOMMEND_PASS");
    });
  });

  describe("End-to-End Review Gate Evaluation", () => {
    it("passes with valid attestation, valid control issue, and valid scope reset", () => {
      const issue: GitHubIssue = {
        number: 7,
        title: "Control Issue",
        body: createValidControlBlockMarkdown(),
        state: "open",
        labels: ["ready-for-review"],
        user: { login: "Banhtalon", id: 105797112 },
      };
      const scopeReset = createValidScopeResetComment();
      const attestation = createValidAttestation();

      const res = validateReviewGate({
        attestations: [attestation],
        expectedHeadSha: VALID_HEAD_SHA,
        expectedPrNumber: PR_NUMBER,
        expectedControlIssue: CONTROL_ISSUE,
        expectedScopeRevision: SCOPE_REVISION,
        controlIssueData: issue,
        scopeResetCommentData: scopeReset,
      });

      expect(res.valid).toBe(true);
      expect(res.reason).toBe("OK");
    });

    it("fails when PR head SHA does not match attestation (stale head)", () => {
      const issue: GitHubIssue = {
        number: 7,
        title: "Control Issue",
        body: createValidControlBlockMarkdown(),
        state: "open",
        labels: ["ready-for-review"],
        user: { login: "Banhtalon", id: 105797112 },
      };
      const scopeReset = createValidScopeResetComment();
      const attestation = createValidAttestation(); // head is VALID_HEAD_SHA

      const res = validateReviewGate({
        attestations: [attestation],
        expectedHeadSha: STALE_HEAD_SHA, // current head is different
        expectedPrNumber: PR_NUMBER,
        expectedControlIssue: CONTROL_ISSUE,
        expectedScopeRevision: SCOPE_REVISION,
        controlIssueData: issue,
        scopeResetCommentData: scopeReset,
      });

      expect(res.valid).toBe(false);
      expect(res.reason).toBe("STALE_HEAD_SHA");
    });

    it("fails when p0 or p1 is non-zero", () => {
      const issue: GitHubIssue = {
        number: 7,
        title: "Control Issue",
        body: createValidControlBlockMarkdown(),
        state: "open",
        labels: ["ready-for-review"],
        user: { login: "Banhtalon", id: 105797112 },
      };
      const scopeReset = createValidScopeResetComment();

      const resP0 = validateReviewGate({
        attestations: [createValidAttestation({ p0: 1 })],
        expectedHeadSha: VALID_HEAD_SHA,
        expectedPrNumber: PR_NUMBER,
        expectedControlIssue: CONTROL_ISSUE,
        expectedScopeRevision: SCOPE_REVISION,
        controlIssueData: issue,
        scopeResetCommentData: scopeReset,
      });
      expect(resP0.valid).toBe(false);
      expect(resP0.reason).toBe("UNRESOLVED_P0_FINDINGS");

      const resP1 = validateReviewGate({
        attestations: [createValidAttestation({ p1: 1 })],
        expectedHeadSha: VALID_HEAD_SHA,
        expectedPrNumber: PR_NUMBER,
        expectedControlIssue: CONTROL_ISSUE,
        expectedScopeRevision: SCOPE_REVISION,
        controlIssueData: issue,
        scopeResetCommentData: scopeReset,
      });
      expect(resP1.valid).toBe(false);
      expect(resP1.reason).toBe("UNRESOLVED_P1_FINDINGS");
    });

    it("fails when material_findings_resolved is false", () => {
      const issue: GitHubIssue = {
        number: 7,
        title: "Control Issue",
        body: createValidControlBlockMarkdown(),
        state: "open",
        labels: ["ready-for-review"],
        user: { login: "Banhtalon", id: 105797112 },
      };
      const scopeReset = createValidScopeResetComment();

      const res = validateReviewGate({
        attestations: [createValidAttestation({ material_findings_resolved: false })],
        expectedHeadSha: VALID_HEAD_SHA,
        expectedPrNumber: PR_NUMBER,
        expectedControlIssue: CONTROL_ISSUE,
        expectedScopeRevision: SCOPE_REVISION,
        controlIssueData: issue,
        scopeResetCommentData: scopeReset,
      });
      expect(res.valid).toBe(false);
      expect(res.reason).toBe("MATERIAL_FINDINGS_NOT_RESOLVED");
    });
  });
});
