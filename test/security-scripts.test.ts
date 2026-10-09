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

  it("does not exempt a copied fake assignment outside the frozen historical bytes", () => {
    const assignment = ['SUPABASE_SECRET_KEY', '="synthetic-unused-local-value"'].join("");
    for (const path of [
      ".workflow-local/phase2-api-chain-implementation/local_chromium_check.py",
      ".workflow-local/other/local_chromium_check.py",
      "src/copied.py",
    ]) {
      const result = runScript("verify_no_secrets.mjs", { [path]: assignment });
      expect(result.status).not.toBe(0);
      expect(result.stderr).toContain("[secret-env-value]");
      expect(result.stderr).not.toContain("synthetic-unused-local-value");
    }
  });

  it("still detects secret assignments and private keys at the historical path", () => {
    const result = runScript("verify_no_secrets.mjs", {
      ".workflow-local/phase2-api-chain-implementation/local_chromium_check.py": [
        ['SUPABASE_SECRET_KEY', '=synthetic-changed-secret'].join(""),
        ['-----BEGIN PRIVATE', ' KEY-----'].join(""),
      ].join("\n"),
    });
    expect(result.status).not.toBe(0);
    expect(result.stderr).toContain("[secret-env-value]");
    expect(result.stderr).toContain("[private-key]");
    expect(result.stderr).not.toContain("synthetic-changed-secret");
  });

  it("rejects a save action in production source", () => {
    const result = runScript("verify_no_live_write.mjs", {
      "src/navigation.ts": "await page.getByRole('button', { name: 'Save' }).click();",
    });

    expect(result.status).not.toBe(0);
  });

  it("rejects multiline save actions in production source", () => {
    const result = runScript("verify_no_live_write.mjs", {
      "src/navigation.ts": [
        "const saveButton = page.getByRole(",
        '  "button",',
        '  { name: "Save" },',
        ");",
        "await saveButton.click();",
      ].join("\n"),
    });

    expect(result.status).not.toBe(0);
  });
});
