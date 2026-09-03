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
} from "../.github/scripts/validate_terra_attestation.mjs";

const VALID_HEAD_SHA = "7074b025458d63e009da12e5e85f891852108004";
const STALE_HEAD_SHA = "1111111111111111111111111111111111111111";
const PR_NUMBER = 6;
const CONTROL_ISSUE = 7;
const SCOPE_REVISION = 2;

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
    ...overrides,
  };
}

describe("Terra Attestation Validator", () => {
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
  "material_findings_resolved": true
}
\`\`\`
      `;
      const found = extractAttestationsFromText(text);
      expect(found).toHaveLength(1);
      expect(found[0].malformed).toBe(false);
      expect(found[0].verdict).toBe("RECOMMEND_PASS");
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
-->
      `;
      const found = extractAttestationsFromText(text);
      expect(found).toHaveLength(1);
      expect(found[0].malformed).toBe(false);
      expect(found[0].verdict).toBe("RECOMMEND_PASS");
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
reviewed_at_utc: 2026-09-03T20:00:00Z
<!-- /TERRA_REVIEW_ATTESTATION_V1 -->
      `;
      const found = extractAttestationsFromText(text);
      expect(found).toHaveLength(1);
      expect(found[0].malformed).toBe(false);
      expect(found[0].reviewed_at_utc).toBe("2026-09-03T20:00:00Z");
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
\`\`\`
      `;
      const found = extractAttestationsFromText(text);
      expect(found).toHaveLength(1);
      expect(found[0].malformed).toBe(true);
      expect(found[0].error).toContain("40-character hexadecimal SHA");
    });

    it("flags invalid reviewed_at_utc timestamp as malformed", () => {
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
reviewed_at_utc: not-a-date
\`\`\`
      `;
      const found = extractAttestationsFromText(text);
      expect(found).toHaveLength(1);
      expect(found[0].malformed).toBe(true);
      expect(found[0].error).toContain("valid ISO-8601 date string");
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
      `);
      expect(parsed.malformed).toBe(false);
      expect(parsed.reviewer_model).toBe("terra-xhigh");
    });

    it("parses control blocks from issue/PR markdown", () => {
      const markdown = `
## Agent Control Block
\`\`\`text
state: implementing
scope_revision: 2
fix_reentries: 0
\`\`\`
      `;
      const control = parseControlBlock(markdown);
      expect(control.state).toBe("implementing");
      expect(control.scope_revision).toBe("2");
      expect(control.fix_reentries).toBe("0");
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

    it("rejects when p0 > 0", () => {
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

    it("rejects when p1 > 0", () => {
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
  });

  describe("Precedence and duplicate handling across comments", () => {
    it("deduplicates identical attestations in a single comment", () => {
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

    it("rejects conflicting attestations within the same comment", () => {
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

    it("applies later-attestation precedence when fix is verified", () => {
      const comments = [
        {
          id: 1,
          created_at: "2026-09-03T10:00:00Z",
          body: `
\`\`\`terra-attestation
reviewer_model: terra-xhigh
head_sha: ${STALE_HEAD_SHA}
pr_number: ${PR_NUMBER}
control_issue: ${CONTROL_ISSUE}
scope_revision: ${SCOPE_REVISION}
verdict: NEEDS_FIX
p0: 1
p1: 0
material_findings_resolved: false
\`\`\`
          `,
        },
        {
          id: 2,
          created_at: "2026-09-03T11:00:00Z",
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
\`\`\`
          `,
        },
      ];

      const attestations = parseAttestationsFromComments(comments);
      expect(attestations).toHaveLength(2);

      const result = validateTerraAttestation({
        attestations,
        expectedHeadSha: VALID_HEAD_SHA,
        expectedPrNumber: PR_NUMBER,
        expectedControlIssue: CONTROL_ISSUE,
        expectedScopeRevision: SCOPE_REVISION,
      });

      expect(result.valid).toBe(true);
      expect(result.attestation?.verdict).toBe("RECOMMEND_PASS");
      expect(result.attestation?.head_sha).toBe(VALID_HEAD_SHA);
    });

    it("applies later-attestation precedence when newer review reports findings", () => {
      const comments = [
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
\`\`\`
          `,
        },
        {
          id: 2,
          created_at: "2026-09-03T11:00:00Z",
          body: `
\`\`\`terra-attestation
reviewer_model: terra-xhigh
head_sha: ${VALID_HEAD_SHA}
pr_number: ${PR_NUMBER}
control_issue: ${CONTROL_ISSUE}
scope_revision: ${SCOPE_REVISION}
verdict: NEEDS_FIX
p0: 0
p1: 1
material_findings_resolved: false
\`\`\`
          `,
        },
      ];

      const attestations = parseAttestationsFromComments(comments);
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
    it("succeeds with exit code 0 on valid attestation file", () => {
      const tmpFile = join(tmpdir(), `terra-valid-${Date.now()}.md`);
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

        expect(proc.status).toBe(0);
        expect(proc.stdout).toContain("[PASS]");
      } finally {
        unlinkSync(tmpFile);
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
