export const TRUSTED_OWNER_LOGIN = "Banhtalon";
export const TRUSTED_OWNER_ID = 105797112;
export const TRUSTED_CHECK_NAME = "terra-review-gate";

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
] as const;

export type CanonicalWorkflowState = (typeof CANONICAL_WORKFLOW_STATES)[number];

export const REVIEWABLE_CONTROL_STATES = [
  "ready-for-review",
  "ready-for-verify",
] as const;

export type ReviewableControlState = (typeof REVIEWABLE_CONTROL_STATES)[number];

export interface AgentControlBlock {
  state: CanonicalWorkflowState;
  scope_revision: number;
  fix_reentries: number;
  owner_scope_reset: string;
}

export interface OwnerScopeResetApproval {
  old_scope_revision: number;
  new_scope_revision: number;
  reason: string;
  material_scope_change: string;
  owner_decision: "APPROVED";
  approved_by: "Banhtalon";
}

export interface TerraAttestation {
  reviewer_model: "terra-xhigh";
  head_sha: string;
  pr_number: number;
  control_issue: number;
  scope_revision: number;
  verdict: "RECOMMEND_PASS" | "NEEDS_FIX" | "BLOCKED";
  p0: number;
  p1: number;
  material_findings_resolved: boolean;
  reviewed_at_utc: string;
  commentId?: number | string;
  createdAt?: string;
  malformed?: boolean;
  conflicting?: boolean;
  error?: string;
}

export interface ValidationSuccess {
  valid: true;
  reason: "OK";
  attestation: TerraAttestation;
  controlBlock: AgentControlBlock;
  scopeResetApproval?: OwnerScopeResetApproval;
}

export interface ValidationFailure {
  valid: false;
  reason: string;
  details: string;
}

export type ValidationResult = ValidationSuccess | ValidationFailure;

export interface GitHubUser {
  login: string;
  id: number;
}

export interface GitHubIssueComment {
  id: number;
  user: GitHubUser;
  author_association?: string;
  body: string;
  created_at: string;
  updated_at?: string;
}

export interface GitHubLabel {
  id?: number;
  name: string;
}

export interface GitHubIssue {
  number: number;
  title: string;
  body: string;
  state: string;
  labels: (string | GitHubLabel)[];
  user: GitHubUser;
}

export interface GitHubPullRequest {
  number: number;
  title: string;
  body: string;
  state: string;
  head: {
    sha: string;
    ref: string;
  };
  base: {
    sha: string;
    ref: string;
  };
}

export interface GitHubCheckRunOutput {
  title: string;
  summary: string;
  text?: string;
}

export interface GitHubCheckRunPayload {
  name: string;
  head_sha: string;
  status: "queued" | "in_progress" | "completed";
  conclusion?: "success" | "failure" | "neutral" | "cancelled" | "timed_out" | "action_required";
  output: GitHubCheckRunOutput;
}
