import { describe, expect, it } from "vitest";
import {
  assertLmsContext,
  assignStudent,
  canContinueReview,
  getMappingStatus,
  type LmsContext,
  type LmsRosterRow,
} from "./manualMapping";

const expected: LmsContext = {
  classCode: "SYN-ROBOTICS-01",
  sessionNumber: 3,
  scheduledDate: "2026-08-11",
  startTime: "19:00",
  endTime: "20:30",
};

const unresolvedRow: LmsRosterRow = {
  rowKey: "beta",
  fullName: "Student Beta",
  attendance: "online",
  identityStatus: "unresolvable",
};

describe("Phase 4B manual mapping contract", () => {
  it("accepts exact context after safe class-code normalization", () => {
    expect(assertLmsContext(expected, {
      ...expected,
      classCode: " syn-robotics-01 ",
    })).toEqual({
      matched: true,
      reasonCode: "LMS_CONTEXT_MATCH",
      manualFallback: false,
    });
  });

  it("fails closed when the observed class differs", () => {
    expect(assertLmsContext(expected, {
      ...expected,
      classCode: "SYN-ROBOTICS-01B",
    })).toEqual({
      matched: false,
      reasonCode: "LMS_CLASS_MISMATCH",
      manualFallback: true,
    });
  });

  it("rejects wrong session, date, and time without fuzzy matching", () => {
    expect(assertLmsContext(expected, { ...expected, sessionNumber: 4 }).reasonCode)
      .toBe("LMS_SESSION_MISMATCH");
    expect(assertLmsContext(expected, { ...expected, scheduledDate: "2026-08-12" }).reasonCode)
      .toBe("LMS_DATE_MISMATCH");
    expect(assertLmsContext(expected, { ...expected, startTime: "19:30" }).reasonCode)
      .toBe("LMS_TIME_MISMATCH");
  });

  it("does not resolve an ambiguous row without an explicit assignment", () => {
    expect(getMappingStatus({
      ...unresolvedRow,
      rowKey: "gamma",
      fullName: "Student Gamma",
      identityStatus: "ambiguous",
    }, {})).toBe("ambiguous");
  });

  it("returns a new assignment and resolves only the selected row", () => {
    const before = { alpha: "internal-001" };
    const after = assignStudent(before, "beta", "internal-002", new Set([
      "internal-001",
      "internal-002",
    ]));

    expect(after).toEqual({ alpha: "internal-001", beta: "internal-002" });
    expect(before).toEqual({ alpha: "internal-001" });
    expect(getMappingStatus(unresolvedRow, after)).toBe("resolved");
  });

  it("rejects an internal ID outside the allowed synthetic set", () => {
    expect(() => assignStudent({}, "beta", "unknown", new Set(["internal-002"])))
      .toThrow("Internal student is not an allowed mapping target");
  });

  it("allows continuation only after exact context and every row resolve", () => {
    const assertion = assertLmsContext(expected, expected);
    expect(canContinueReview(assertion, ["resolved", "resolved"])).toBe(true);
    expect(canContinueReview(assertion, ["resolved", "unresolvable"])).toBe(false);
    expect(canContinueReview({
      matched: false,
      reasonCode: "LMS_CLASS_MISMATCH",
      manualFallback: true,
    }, ["resolved", "resolved"])).toBe(false);
  });

  it("keeps mapping status stable when roster order changes", () => {
    const rows = [
      { ...unresolvedRow, rowKey: "alpha", identityStatus: "resolved" as const },
      unresolvedRow,
    ];
    const assignments = { beta: "internal-002" };
    const first = rows.map((row) => getMappingStatus(row, assignments));
    const second = [...rows].reverse().map((row) => getMappingStatus(row, assignments));

    expect(first.sort()).toEqual(second.sort());
    expect(first).toEqual(["resolved", "resolved"]);
  });
});
