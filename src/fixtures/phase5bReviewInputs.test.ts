import { describe, expect, it } from "vitest";

import {
  createInitialReviewInputs,
  PHASE5B_SYNTHETIC_LEARNERS,
} from "./phase5bReviewInputs";

describe("Phase 5B synthetic review fixtures", () => {
  it("contains exactly three explicit synthetic learners with unique stable keys", () => {
    expect(PHASE5B_SYNTHETIC_LEARNERS).toHaveLength(3);

    const rowKeys = PHASE5B_SYNTHETIC_LEARNERS.map((learner) => learner.rowKey);

    expect(rowKeys).toEqual([
      "synthetic-review-001",
      "synthetic-review-002",
      "synthetic-review-003",
    ]);
    expect(new Set(rowKeys).size).toBe(3);
    expect(PHASE5B_SYNTHETIC_LEARNERS).toEqual([
      { rowKey: "synthetic-review-001", displayName: "Synthetic learner 01" },
      { rowKey: "synthetic-review-002", displayName: "Synthetic learner 02" },
      { rowKey: "synthetic-review-003", displayName: "Synthetic learner 03" },
    ]);
  });

  it("creates a fresh unknown attendance draft for every learner", () => {
    const firstDraft = createInitialReviewInputs(PHASE5B_SYNTHETIC_LEARNERS);
    const secondDraft = createInitialReviewInputs(PHASE5B_SYNTHETIC_LEARNERS);

    expect(firstDraft).toEqual([
      {
        rowKey: "synthetic-review-001",
        attendance: "unknown",
        level: "unknown",
        noteDraft: "",
      },
      {
        rowKey: "synthetic-review-002",
        attendance: "unknown",
        level: "unknown",
        noteDraft: "",
      },
      {
        rowKey: "synthetic-review-003",
        attendance: "unknown",
        level: "unknown",
        noteDraft: "",
      },
    ]);
    expect(secondDraft).not.toBe(firstDraft);
    expect(firstDraft[0]).not.toBe(secondDraft[0]);
  });

  it("freezes fixture and draft containers to prevent accidental mutation", () => {
    const draft = createInitialReviewInputs(PHASE5B_SYNTHETIC_LEARNERS);

    expect(Object.isFrozen(PHASE5B_SYNTHETIC_LEARNERS)).toBe(true);
    expect(PHASE5B_SYNTHETIC_LEARNERS.every(Object.isFrozen)).toBe(true);
    expect(Object.isFrozen(draft)).toBe(true);
    expect(draft.every(Object.isFrozen)).toBe(true);
  });
});
