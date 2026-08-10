import { describe, expect, it } from "vitest";
import {
  assertLmsReadOnly,
  assertAllowedDomain,
  canRunAutomation,
} from "./guards";

describe("runtime safety guards", () => {
  it("blocks automation when the kill switch is disabled", () => {
    expect(canRunAutomation({ automationEnabled: false })).toBe(false);
  });

  it("allows automation only when the kill switch is enabled", () => {
    expect(canRunAutomation({ automationEnabled: true })).toBe(true);
  });

  it("rejects any configuration that enables LMS mutation", () => {
    expect(() => assertLmsReadOnly({ lmsWriteEnabled: true })).toThrow(
      "LMS read-only guard violated",
    );
  });

  it("rejects malformed write configuration instead of failing open", () => {
    expect(() => assertLmsReadOnly({
      lmsWriteEnabled: "true" as unknown as boolean,
    })).toThrow("LMS read-only guard violated");
  });

  it("allows only production or synthetic fixture domains", () => {
    expect(() => assertAllowedDomain("https://lms.mindx.edu.vn/class"))
      .not.toThrow();
    expect(() => assertAllowedDomain("https://example.invalid"))
      .toThrow("Domain is not allowlisted");
    expect(() => assertAllowedDomain("http://127.0.0.1:4173/fixture", "synthetic"))
      .not.toThrow();
  });
});
