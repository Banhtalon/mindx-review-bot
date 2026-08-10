/* global console, process */

import { readFileSync, readdirSync, statSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join, relative, resolve } from "node:path";

const IGNORED_DIRECTORIES = new Set([
  ".git",
  ".venv",
  ".vite",
  "coverage",
  "dist",
  "node_modules",
  "__pycache__",
  ".pytest_cache",
  ".mypy_cache",
  ".ruff_cache",
  "scripts",
  ".temp",
]);

const SECRET_PATTERNS = [
  ["private-key", /-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----/i],
  ["github-token", /\b(?:ghp|github_pat|gho|ghs|ghr)_[A-Za-z0-9_]{10,}\b/],
  ["provider-token", /\b(?:xox[baprs]-|sk-)[A-Za-z0-9_-]{10,}\b/],
  ["provider-key", /\bAIza[A-Za-z0-9_-]{20,}\b/],
  ["jwt", /\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b/],
  [
    "secret-env-value",
    /\b(?:SUPABASE_(?:SERVICE_ROLE|SECRET)_KEY|GITHUB_DISPATCH_TOKEN|BROWSER_STATE_ENCRYPTION_KEY|GEMINI_API_KEY)[ \t]*=[ \t]*[^\s#][^\r\n]*/i,
  ],
];

function parseRoot(argv) {
  const rootIndex = argv.indexOf("--root");
  return resolve(rootIndex === -1 ? process.cwd() : argv[rootIndex + 1]);
}

function collectFiles(root, current = root) {
  const files = [];
  for (const entry of readdirSync(current, { withFileTypes: true })) {
    if (entry.isDirectory() && IGNORED_DIRECTORIES.has(entry.name)) continue;
    const absolutePath = join(current, entry.name);
    if (entry.isDirectory()) {
      files.push(...collectFiles(root, absolutePath));
      continue;
    }
    if (entry.isFile() && statSync(absolutePath).size <= 2_000_000) {
      files.push(absolutePath);
    }
  }
  return files;
}

function findViolations(root) {
  const violations = [];
  for (const file of collectFiles(root)) {
    const content = readFileSync(file, "utf8");
    for (const [kind, pattern] of SECRET_PATTERNS) {
      const match = pattern.exec(content);
      if (match === null) continue;
      const line = content.slice(0, match.index).split("\n").length;
      violations.push({ file: relative(root, file), kind, line });
    }
  }
  return violations;
}

export { findViolations };

const invokedPath = process.argv[1] ? resolve(process.argv[1]) : "";
const scriptPath = resolve(dirname(fileURLToPath(import.meta.url)), "verify_no_secrets.mjs");

if (invokedPath === scriptPath) {
  const root = parseRoot(process.argv.slice(2));
  const violations = findViolations(root);
  if (violations.length > 0) {
    for (const violation of violations) {
      console.error(`${violation.file}:${violation.line} [${violation.kind}]`);
    }
    console.error(`Secrets check failed: ${violations.length} violation(s).`);
    process.exitCode = 1;
  } else {
    console.log("Secrets check passed.");
  }
}
