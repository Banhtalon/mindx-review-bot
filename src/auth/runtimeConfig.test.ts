import { describe, expect, it } from "vitest";

import { resolveAuthRuntimeConfig } from "./runtimeConfig";

describe("resolveAuthRuntimeConfig", () => {
  it("uses synthetic mode only when every auth variable is blank", () => {
    expect(
      resolveAuthRuntimeConfig({
        url: "",
        publishableKey: "",
        workspaceId: "",
      }),
    ).toEqual({ mode: "synthetic" });
  });

  it("returns an authenticated config when all required values are present", () => {
    expect(
      resolveAuthRuntimeConfig({
        url: "https://example.supabase.co",
        publishableKey: "publishable-key",
        workspaceId: "workspace-1",
      }),
    ).toEqual({
      mode: "authenticated",
      url: "https://example.supabase.co",
      publishableKey: "publishable-key",
      workspaceId: "workspace-1",
    });
  });

  it.each([
    { url: "https://example.supabase.co", publishableKey: "", workspaceId: "workspace-1" },
    { url: "", publishableKey: "publishable-key", workspaceId: "workspace-1" },
    { url: "https://example.supabase.co", publishableKey: "publishable-key", workspaceId: "" },
  ])("fails closed for a partial Auth configuration: %o", (input) => {
    expect(resolveAuthRuntimeConfig(input)).toEqual({
      mode: "invalid",
      reason: "INCOMPLETE_AUTH_CONFIG",
    });
  });
});
