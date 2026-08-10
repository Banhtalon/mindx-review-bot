import { mkdtempSync, rmSync, writeFileSync, mkdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { spawnSync } from "node:child_process";
import { describe, expect, it } from "vitest";

const projectRoot = resolve(process.cwd());

function runScript(scriptName: string, files: Record<string, string>) {
  const fixtureRoot = mkdtempSync(join(tmpdir(), "mindx-security-"));
  try {
    for (const [relativePath, content] of Object.entries(files)) {
      const absolutePath = join(fixtureRoot, relativePath);
      mkdirSync(resolve(absolutePath, ".."), { recursive: true });
      writeFileSync(absolutePath, content, "utf8");
    }

    return spawnSync(
      process.execPath,
      [resolve(projectRoot, "scripts", scriptName), "--root", fixtureRoot],
      { encoding: "utf8" },
    );
  } finally {
    rmSync(fixtureRoot, { recursive: true, force: true });
  }
}

describe("repository safety checks", () => {
  it("accepts synthetic files without secrets", () => {
    const result = runScript("verify_no_secrets.mjs", {
      "src/synthetic.ts": "export const fixture = 'synthetic-only';",
      ".env.example": ["GITHUB_DISPATCH_TOKEN", "=", "\n", "GEMINI_API_KEY", "=", "\n"].join(""),
    });

    expect(result.status).toBe(0);
  });

  it("rejects a private key without printing its contents", () => {
    const secret = ["-----BEGIN PRIVATE", " KEY-----", "\nsynthetic-secret\n"].join("");
    const result = runScript("verify_no_secrets.mjs", {
      "src/unsafe.txt": secret,
    });

    expect(result.status).not.toBe(0);
    expect(`${result.stdout}${result.stderr}`).not.toContain("synthetic-secret");
  });

  it("accepts read-only browser navigation code", () => {
    const result = runScript("verify_no_live_write.mjs", {
      "src/navigation.ts": "await page.goto('https://lms.mindx.edu.vn/class');",
    });

    expect(result.status).toBe(0);
  });

  it("rejects a save action in production source", () => {
    const result = runScript("verify_no_live_write.mjs", {
      "src/navigation.ts": "await page.getByRole('button', { name: 'Save' }).click();",
    });

    expect(result.status).not.toBe(0);
  });
});
