import { describe, expect, it } from "vitest";
import { buildSafeModelPayload } from "./redaction";

describe("model payload redaction", () => {
  it("uses aliases and drops forbidden personal fields", () => {
    const payload = buildSafeModelPayload({
      studentName: "Synthetic Student Alpha",
      parentName: "Synthetic Parent",
      email: "student@example.invalid",
      phone: "0900000000",
      address: "Synthetic address",
      healthNote: "Synthetic health note",
      performance: "good",
      evidenceId: "V4-S0-07-fixture",
    });

    expect(payload).toMatchObject({
      anonymousId: expect.stringMatching(/^SYN-[A-Z0-9]{6}$/),
      performance: "good",
      evidenceId: "V4-S0-07-fixture",
    });
    expect(JSON.stringify(payload)).not.toContain("Synthetic Student Alpha");
    expect(JSON.stringify(payload)).not.toContain("Synthetic Parent");
    expect(JSON.stringify(payload)).not.toContain("student@example.invalid");
    expect(JSON.stringify(payload)).not.toContain("0900000000");
    expect(JSON.stringify(payload)).not.toContain("Synthetic health note");
  });

  it("removes personal values embedded in performance text", () => {
    const payload = buildSafeModelPayload({
      studentName: "Synthetic Student Alpha",
      parentName: "Synthetic Parent",
      email: "student@example.invalid",
      phone: "0900000000",
      address: "Synthetic address",
      healthNote: "Synthetic health note",
      performance: "Synthetic Student Alpha contacted Synthetic Parent at student@example.invalid 0900000000",
      evidenceId: "V4-S0-10-fixture",
    });

    expect(payload.performance).not.toContain("Synthetic Student Alpha");
    expect(payload.performance).not.toContain("Synthetic Parent");
    expect(payload.performance).not.toContain("student@example.invalid");
    expect(payload.performance).not.toContain("0900000000");
  });

  it("rejects an evidence id that is not a synthetic evidence key", () => {
    expect(() => buildSafeModelPayload({
      studentName: "Synthetic Student Alpha",
      parentName: "Synthetic Parent",
      email: "student@example.invalid",
      phone: "0900000000",
      address: "Synthetic address",
      healthNote: "Synthetic health note",
      performance: "good",
      evidenceId: "V4-S0-07-studentalpha",
    })).toThrow("Evidence ID is not safe");
  });

  it("rejects residual personal markers that were not supplied as known values", () => {
    expect(() => buildSafeModelPayload({
      studentName: "Synthetic Student Alpha",
      parentName: "Synthetic Parent",
      email: "student@example.invalid",
      phone: "0900000000",
      address: "Synthetic address",
      healthNote: "Synthetic health note",
      performance: "Student Beta contacted beta@example.invalid at 0912345678",
      evidenceId: "V4-S0-10-fixture",
    })).toThrow("Performance text contains unredacted personal data");
  });
});
