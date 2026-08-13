import type { SyntheticLearner, SyntheticReviewInput } from "../reviewInputs/contracts";

export const PHASE5B_SYNTHETIC_LEARNERS: readonly SyntheticLearner[] = Object.freeze(
  [
    { rowKey: "synthetic-review-001", displayName: "Synthetic learner 01" },
    { rowKey: "synthetic-review-002", displayName: "Synthetic learner 02" },
    { rowKey: "synthetic-review-003", displayName: "Synthetic learner 03" },
  ].map((learner) => Object.freeze(learner)),
);

export function createInitialReviewInputs(
  learners: readonly SyntheticLearner[],
): readonly SyntheticReviewInput[] {
  return Object.freeze(
    learners.map((learner) =>
      Object.freeze({
        rowKey: learner.rowKey,
        attendance: "unknown" as const,
        level: "unknown" as const,
        noteDraft: "",
      }),
    ),
  );
}
