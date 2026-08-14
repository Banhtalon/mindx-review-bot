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

  it("keeps the workspace helper functions on a fixed empty search_path", () => {
    const foundation = readFileSync(
      resolve(process.cwd(), "supabase/migrations/20260810000000_spike0_foundation.sql"),
      "utf8",
    );

    expect(foundation).toMatch(
      /create or replace function public\.is_workspace_member\(target_workspace uuid\)[\s\S]*?security definer[\s\S]*?set search_path = ''/,
    );
    expect(foundation).toMatch(
      /create or replace function public\.has_workspace_role\([\s\S]*?security definer[\s\S]*?set search_path = ''/,
    );
  });
});
