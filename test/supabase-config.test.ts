import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

describe("Supabase Edge Function configuration", () => {
  it("lets dispatch-job apply its own JWT or Cron authentication", () => {
    const config = readFileSync(resolve(process.cwd(), "supabase/config.toml"), "utf8");
    const section = config.match(
      /\[functions\.dispatch-job\]([\s\S]*?)(?=\n\[|$)/,
    )?.[1];

    expect(section).toMatch(/verify_jwt\s*=\s*false/);
  });

  it("keeps the local synthetic seed deterministic as a file contract", () => {
    const seed = readFileSync(resolve(process.cwd(), "supabase/seed.sql"), "utf8");

    expect(seed).toContain("owner@example.invalid");
    expect(seed).toContain("'2026-01-01T00:00:00+00:00'::timestamptz");
    expect(seed).not.toMatch(/\bnow\(\)/i);
  });

  it("keeps security-definer workspace helpers on an empty search_path", () => {
    const migration = readFileSync(
      resolve(process.cwd(), "supabase/migrations/20260810000000_spike0_foundation.sql"),
      "utf8",
    );

    expect(migration).toMatch(
      /create or replace function public\.is_workspace_member[\s\S]*?set search_path = ''/,
    );
    expect(migration).toMatch(
      /create or replace function public\.has_workspace_role[\s\S]*?set search_path = ''/,
    );
  });
});
