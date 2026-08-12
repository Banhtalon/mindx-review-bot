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
});
