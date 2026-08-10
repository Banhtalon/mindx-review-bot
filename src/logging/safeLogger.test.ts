import { describe, expect, it } from "vitest";
import { sanitizeLogMetadata } from "./safeLogger";

describe("safe log metadata", () => {
  it("redacts credentials, tokens, cookies and personal text", () => {
    const safe = sanitizeLogMetadata({
      jobId: "00000000-0000-0000-0000-000000000001",
      password: "not-a-real-password",
      accessToken: "not-a-real-token",
      cookie: "not-a-real-cookie",
      studentName: "Synthetic Student Alpha",
      note: "Synthetic private note",
      recordsRead: 1,
    });
    const serialized = JSON.stringify(safe);

    expect(safe).toMatchObject({
      jobId: "00000000-0000-0000-0000-000000000001",
      recordsRead: 1,
    });
    expect(serialized).not.toContain("not-a-real-password");
    expect(serialized).not.toContain("not-a-real-token");
    expect(serialized).not.toContain("not-a-real-cookie");
    expect(serialized).not.toContain("Synthetic Student Alpha");
    expect(serialized).not.toContain("Synthetic private note");
  });

  it("drops unknown fields that could hide personal text", () => {
    const safe = sanitizeLogMetadata({
      status: "failed",
      diagnostic: "Synthetic Student Alpha email student@example.invalid",
      nested: { recordsRead: 1 },
    });

    expect(safe).toEqual({ status: "failed" });
  });

  it("keeps only typed values for allowlisted metadata keys", () => {
    const safe = sanitizeLogMetadata({
      jobId: "00000000-0000-0000-0000-000000000001",
      status: "Synthetic Student Alpha",
      jobType: "sync_teaching",
      errorCode: "AUTH_EXPIRED",
      recordsRead: "1",
      durationMs: 42,
    });

    expect(safe).toEqual({
      jobId: "00000000-0000-0000-0000-000000000001",
      jobType: "sync_teaching",
      errorCode: "AUTH_EXPIRED",
      durationMs: 42,
    });
  });
});
