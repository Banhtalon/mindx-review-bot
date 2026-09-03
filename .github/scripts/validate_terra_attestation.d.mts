export interface TerraAttestation {
  readonly malformed: boolean;
  readonly error?: string;
  readonly reviewer_model?: string;
  readonly head_sha?: string;
  readonly pr_number?: number;
  readonly control_issue?: number;
  readonly scope_revision?: number;
  readonly verdict?: string;
  readonly p0?: number;
  readonly p1?: number;
  readonly material_findings_resolved?: boolean;
  readonly reviewed_at_utc?: string;
  readonly conflicting?: boolean;
  readonly commentId?: number | string;
  readonly createdAt?: string;
  readonly raw?: Record<string, unknown>;
}

export interface ValidationParams {
  readonly attestations: readonly (TerraAttestation | Record<string, unknown>)[];
  readonly expectedHeadSha?: string;
  readonly expectedPrNumber?: number;
  readonly expectedControlIssue?: number;
  readonly expectedScopeRevision?: number;
}

export interface ValidationResult {
  readonly valid: boolean;
  readonly reason: string;
  readonly details?: string;
  readonly attestation?: TerraAttestation;
}

export interface GitHubComment {
  readonly id?: number | string;
  readonly body?: string;
  readonly created_at?: string;
  readonly submitted_at?: string;
  readonly user?: { readonly login?: string };
}

export function parseTerraAttestationBlock(content: string): TerraAttestation;

export function extractAttestationsFromText(text: string): TerraAttestation[];

export function parseAttestationsFromComments(comments: readonly GitHubComment[]): TerraAttestation[];

export function validateTerraAttestation(params: ValidationParams): ValidationResult;

export function parseControlBlock(text: string): Record<string, string>;
