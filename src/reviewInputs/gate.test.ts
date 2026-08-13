import { describe, expect, it } from "vitest";

import type { SyntheticReviewInput } from "./contracts";
import { evaluateReviewInputGate } from "./gate";

const reviewInput = (
  overrides: Partial<SyntheticReviewInput> = {},
): SyntheticReviewInput => ({
  rowKey: "synthetic-review-001",
  attendance: "unknown",
  level: "unknown",
  noteDraft: "",
  ...overrides,
});

describe("evaluateReviewInputGate", () => {
  it("blocks when attendance is unknown and reports its stable row key", () => {
    const result = evaluateReviewInputGate([
      reviewInput(),
      reviewInput({
        rowKey: "synthetic-review-002",
        attendance: "present",
      }),
    ]);

    expect(result).toEqual({
      ready: false,
      reasonCode: "ATTENDANCE_UNKNOWN",
      unknownAttendanceRowKeys: ["synthetic-review-001"],
    });
  });

  it("is ready when every attendance value is explicit", () => {
    const result = evaluateReviewInputGate([
      reviewInput({ attendance: "present" }),
      reviewInput({
        rowKey: "synthetic-review-002",
        attendance: "absent",
        level: "unknown",
        noteDraft: "",
      }),
    ]);

    expect(result).toEqual({
      ready: true,
      reasonCode: "ATTENDANCE_COMPLETE",
      unknownAttendanceRowKeys: [],
    });
  });
});
