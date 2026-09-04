import { describe, expect, it } from "vitest";
import { isValidStrictUtcCalendarIsoTimestamp } from "../src/calendar.ts";

describe("Strict Calendar UTC Timestamp Validator", () => {
  it("accepts valid UTC timestamps ending in Z", () => {
    expect(isValidStrictUtcCalendarIsoTimestamp("2026-09-04T01:23:45Z")).toBe(true);
    expect(isValidStrictUtcCalendarIsoTimestamp("2026-09-04T00:00:00Z")).toBe(true);
    expect(isValidStrictUtcCalendarIsoTimestamp("2026-12-31T23:59:59Z")).toBe(true);
    expect(isValidStrictUtcCalendarIsoTimestamp("2026-09-04T01:23:45.123Z")).toBe(true);
    expect(isValidStrictUtcCalendarIsoTimestamp("2026-09-04T01:23:45.5Z")).toBe(true);
  });

  it("handles leap years correctly", () => {
    // 2024 is a leap year (divisible by 4, not 100)
    expect(isValidStrictUtcCalendarIsoTimestamp("2024-02-29T12:00:00Z")).toBe(true);
    // 2000 is a leap year (divisible by 400)
    expect(isValidStrictUtcCalendarIsoTimestamp("2000-02-29T12:00:00Z")).toBe(true);

    // 2026 is NOT a leap year
    expect(isValidStrictUtcCalendarIsoTimestamp("2026-02-29T00:00:00Z")).toBe(false);
    expect(isValidStrictUtcCalendarIsoTimestamp("2026-02-28T23:59:59Z")).toBe(true);
    // 1900 is NOT a leap year (divisible by 100 but not 400)
    expect(isValidStrictUtcCalendarIsoTimestamp("1900-02-29T12:00:00Z")).toBe(false);
    // 2100 is NOT a leap year
    expect(isValidStrictUtcCalendarIsoTimestamp("2100-02-29T12:00:00Z")).toBe(false);
  });

  it("rejects impossible month days", () => {
    // April has 30 days
    expect(isValidStrictUtcCalendarIsoTimestamp("2026-04-31T00:00:00Z")).toBe(false);
    expect(isValidStrictUtcCalendarIsoTimestamp("2026-04-30T23:59:59Z")).toBe(true);

    // June has 30 days
    expect(isValidStrictUtcCalendarIsoTimestamp("2026-06-31T00:00:00Z")).toBe(false);

    // September has 30 days
    expect(isValidStrictUtcCalendarIsoTimestamp("2026-09-31T00:00:00Z")).toBe(false);

    // November has 30 days
    expect(isValidStrictUtcCalendarIsoTimestamp("2026-11-31T00:00:00Z")).toBe(false);

    // Day 0
    expect(isValidStrictUtcCalendarIsoTimestamp("2026-01-00T00:00:00Z")).toBe(false);
    // Day 32
    expect(isValidStrictUtcCalendarIsoTimestamp("2026-01-32T00:00:00Z")).toBe(false);
  });

  it("rejects invalid months", () => {
    expect(isValidStrictUtcCalendarIsoTimestamp("2026-00-01T00:00:00Z")).toBe(false);
    expect(isValidStrictUtcCalendarIsoTimestamp("2026-13-01T00:00:00Z")).toBe(false);
    expect(isValidStrictUtcCalendarIsoTimestamp("2026-99-01T00:00:00Z")).toBe(false);
  });

  it("rejects invalid time components (hour 24, min 60, sec 60)", () => {
    expect(isValidStrictUtcCalendarIsoTimestamp("2026-09-04T24:00:00Z")).toBe(false);
    expect(isValidStrictUtcCalendarIsoTimestamp("2026-09-04T25:00:00Z")).toBe(false);
    expect(isValidStrictUtcCalendarIsoTimestamp("2026-09-04T12:60:00Z")).toBe(false);
    expect(isValidStrictUtcCalendarIsoTimestamp("2026-09-04T12:00:60Z")).toBe(false);
  });

  it("rejects timezone offsets and non-Z local times", () => {
    expect(isValidStrictUtcCalendarIsoTimestamp("2026-09-04T01:23:45+07:00")).toBe(false);
    expect(isValidStrictUtcCalendarIsoTimestamp("2026-09-04T01:23:45-05:00")).toBe(false);
    expect(isValidStrictUtcCalendarIsoTimestamp("2026-09-04T01:23:45")).toBe(false);
    expect(isValidStrictUtcCalendarIsoTimestamp("2026-09-04")).toBe(false);
  });

  it("rejects non-string and whitespace-contaminated inputs", () => {
    expect(isValidStrictUtcCalendarIsoTimestamp(" 2026-09-04T01:23:45Z ")).toBe(false);
    expect(isValidStrictUtcCalendarIsoTimestamp("2026-09-04T01:23:45Z\n")).toBe(false);
    expect(isValidStrictUtcCalendarIsoTimestamp(null)).toBe(false);
    expect(isValidStrictUtcCalendarIsoTimestamp(undefined)).toBe(false);
    expect(isValidStrictUtcCalendarIsoTimestamp(123456789)).toBe(false);
    expect(isValidStrictUtcCalendarIsoTimestamp({})).toBe(false);
    expect(isValidStrictUtcCalendarIsoTimestamp("")).toBe(false);
  });
});
