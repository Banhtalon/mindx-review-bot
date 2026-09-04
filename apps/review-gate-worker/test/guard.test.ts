import { describe, expect, it } from "vitest";
import { InMemoryEvaluationGuard } from "../src/guard.ts";

describe("InMemoryEvaluationGuard", () => {
  it("acquires monotonically increasing version numbers per repo and pr", async () => {
    const guard = new InMemoryEvaluationGuard();
    const claim1 = await guard.acquireVersion("Banhtalon/mindx-review-bot", 6);
    expect(claim1.version).toBe(1);
    expect(claim1.repo).toBe("Banhtalon/mindx-review-bot");
    expect(claim1.prNumber).toBe(6);

    const claim2 = await guard.acquireVersion("Banhtalon/mindx-review-bot", 6);
    expect(claim2.version).toBe(2);

    // Other repo or PR has its own sequence
    const claimOtherPr = await guard.acquireVersion("Banhtalon/mindx-review-bot", 7);
    expect(claimOtherPr.version).toBe(1);

    const claimOtherRepo = await guard.acquireVersion("Other/repo", 6);
    expect(claimOtherRepo.version).toBe(1);
  });

  it("identifies latest version and rejects stale claims", async () => {
    const guard = new InMemoryEvaluationGuard();
    const claim1 = await guard.acquireVersion("Banhtalon/mindx-review-bot", 6);
    expect(await guard.isLatestVersion(claim1)).toBe(true);

    const claim2 = await guard.acquireVersion("Banhtalon/mindx-review-bot", 6);
    expect(await guard.isLatestVersion(claim1)).toBe(false); // claim1 is now stale
    expect(await guard.isLatestVersion(claim2)).toBe(true);
  });
});
