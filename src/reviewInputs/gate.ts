import type { ReviewInputGate, SyntheticReviewInput } from "./contracts";

export function evaluateReviewInputGate(
  inputs: readonly SyntheticReviewInput[],
): ReviewInputGate {
  const unknownAttendanceRowKeys = inputs
    .filter((input) => input.attendance === "unknown")
    .map((input) => input.rowKey);

  if (unknownAttendanceRowKeys.length > 0) {
    return {
      ready: false,
      reasonCode: "ATTENDANCE_UNKNOWN",
      unknownAttendanceRowKeys,
    };
  }

  return {
    ready: true,
    reasonCode: "ATTENDANCE_COMPLETE",
    unknownAttendanceRowKeys: [],
  };
}
