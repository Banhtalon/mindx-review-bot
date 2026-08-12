import { describe, expect, it } from "vitest";
import {
  loadDispatchEnvironment,
  type EnvironmentReader,
} from "../supabase/functions/_shared/environment";

const BASE_ENVIRONMENT: Record<string, string> = {
  SUPABASE_URL: "https://synthetic.supabase.invalid/",
  GITHUB_REPOSITORY: "synthetic-owner/synthetic-repo",
  GITHUB_WORKFLOW_ID: "spike0-dispatch-probe.yml",
  GITHUB_DISPATCH_TOKEN: "synthetic-github-token",
  CRON_DISPATCH_SECRET: "synthetic-cron-secret",
  CRON_ACTOR_USER_ID: "00000000-0000-0000-0000-0000000000c1",
  CRON_WORKSPACE_ID: "00000000-0000-0000-0000-0000000000cc",
};

function environment(
  overrides: Record<string, string> = {},
): EnvironmentReader {
  const values = { ...BASE_ENVIRONMENT, ...overrides };
  return { get: (name) => values[name] };
}

describe("dispatch Edge Function environment", () => {
  it("reads the default hosted publishable and secret keys from JSON maps", () => {
    const config = loadDispatchEnvironment(environment({
      SUPABASE_PUBLISHABLE_KEYS: JSON.stringify({ default: "hosted-publishable" }),
      SUPABASE_SECRET_KEYS: JSON.stringify({ default: "hosted-secret" }),
    }));

    expect(config.publishableKey).toBe("hosted-publishable");
    expect(config.serviceKey).toBe("hosted-secret");
    expect(config.supabaseUrl).toBe("https://synthetic.supabase.invalid");
  });

  it("falls back to singular local keys", () => {
    const config = loadDispatchEnvironment(environment({
      SUPABASE_URL: "http://127.0.0.1:55021",
      SUPABASE_PUBLISHABLE_KEY: "local-publishable",
      SUPABASE_SECRET_KEY: "local-secret",
    }));

    expect(config.publishableKey).toBe("local-publishable");
    expect(config.serviceKey).toBe("local-secret");
  });

  it("fails closed when a hosted key map has no default key", () => {
    expect(() => loadDispatchEnvironment(environment({
      SUPABASE_PUBLISHABLE_KEYS: "{}",
      SUPABASE_SECRET_KEYS: JSON.stringify({ default: "hosted-secret" }),
    }))).toThrow("DISPATCH_FUNCTION_MISCONFIGURED");
  });

  it("fails closed when a hosted key map is malformed", () => {
    expect(() => loadDispatchEnvironment(environment({
      SUPABASE_PUBLISHABLE_KEYS: "not-json",
      SUPABASE_SECRET_KEYS: JSON.stringify({ default: "hosted-secret" }),
    }))).toThrow("DISPATCH_FUNCTION_MISCONFIGURED");
  });

  it("fails closed when the hosted secret map has no default key", () => {
    expect(() => loadDispatchEnvironment(environment({
      SUPABASE_PUBLISHABLE_KEYS: JSON.stringify({ default: "hosted-publishable" }),
      SUPABASE_SECRET_KEYS: "{}",
      SUPABASE_SECRET_KEY: "local-secret-fallback",
    }))).toThrow("DISPATCH_FUNCTION_MISCONFIGURED");
  });

  it("does not fall back when a hosted publishable map is malformed", () => {
    expect(() => loadDispatchEnvironment(environment({
      SUPABASE_PUBLISHABLE_KEYS: "not-json",
      SUPABASE_PUBLISHABLE_KEY: "local-publishable-fallback",
      SUPABASE_SECRET_KEYS: JSON.stringify({ default: "hosted-secret" }),
    }))).toThrow("DISPATCH_FUNCTION_MISCONFIGURED");
  });
});
