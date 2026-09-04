/**
 * Evaluation serialization and version guard for review gate evaluations.
 * Ensures that stale out-of-order evaluations cannot overwrite newer authority results with success.
 */

export interface EvaluationVersionClaim {
  repo: string;
  prNumber: number;
  version: number;
  token: string;
  createdAt: number;
}

export interface EvaluationGuard {
  /**
   * Acquires a new monotonically increasing evaluation version claim for repo + prNumber.
   */
  acquireVersion(repo: string, prNumber: number): Promise<EvaluationVersionClaim>;

  /**
   * Checks if this claim is still the latest acquired version for repo + prNumber.
   */
  isLatestVersion(claim: EvaluationVersionClaim): Promise<boolean>;

  /**
   * Finalizes the claim (optional cleanup or state tracking).
   */
  finalizeVersion?(claim: EvaluationVersionClaim): Promise<void>;
}

/**
 * In-memory implementation of EvaluationGuard.
 * Maintains monotonic per-PR versioning to detect stale concurrent evaluations.
 */
export class InMemoryEvaluationGuard implements EvaluationGuard {
  private versions = new Map<string, number>();
  private activeTokens = new Map<string, string>();

  private key(repo: string, prNumber: number): string {
    return `${repo.toLowerCase()}#${prNumber}`;
  }

  async acquireVersion(repo: string, prNumber: number): Promise<EvaluationVersionClaim> {
    const k = this.key(repo, prNumber);
    const current = this.versions.get(k) || 0;
    const next = current + 1;
    this.versions.set(k, next);
    const token = `${Date.now()}-${Math.random().toString(36).slice(2)}-v${next}`;
    this.activeTokens.set(k, token);

    return {
      repo,
      prNumber,
      version: next,
      token,
      createdAt: Date.now(),
    };
  }

  async isLatestVersion(claim: EvaluationVersionClaim): Promise<boolean> {
    const k = this.key(claim.repo, claim.prNumber);
    const current = this.versions.get(k) || 0;
    const activeToken = this.activeTokens.get(k);
    return current === claim.version && activeToken === claim.token;
  }

  async finalizeVersion(_claim: EvaluationVersionClaim): Promise<void> {
    void _claim;
  }
}
