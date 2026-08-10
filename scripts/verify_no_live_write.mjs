/* global console, process */

import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join, relative, resolve } from "node:path";

const SOURCE_DIRECTORIES = ["src", "apps/browser-runner/src", "supabase/functions"];
const IGNORED_DIRECTORIES = new Set([".git", ".venv", "node_modules", "__pycache__"]);
const MUTATION_PATTERNS = [
  [
    "write-flag",
    /\bMVP_LMS_WRITE_ENABLED\s*(?:=|:)\s*(?:true|"true"|'true')\b/i,
  ],
  [
    "save-or-submit-click",
    /(?:\b(?:save|submit)\b[\s\S]{0,240}\.(?:click|fill|type|press)\s*\(|\b(?:save|submit)[A-Za-z0-9_]*\b\s*\.\s*(?:click|fill|type|press)\s*\()/i,
  ],
  [
    "save-or-submit-call",
    /\b(?:save|submit)(?:[A-Za-z0-9_]*(?:Comment|Review|Feedback)?)\s*\(/i,
  ],
];

function parseRoot(argv) {
  const rootIndex = argv.indexOf("--root");
  return resolve(rootIndex === -1 ? process.cwd() : argv[rootIndex + 1]);
}

function collectFiles(root, current) {
  const files = [];
  for (const entry of readdirSync(current, { withFileTypes: true })) {
    if (entry.isDirectory() && IGNORED_DIRECTORIES.has(entry.name)) continue;
    const absolutePath = join(current, entry.name);
    if (entry.isDirectory()) {
      files.push(...collectFiles(root, absolutePath));
    } else if (entry.isFile() && statSync(absolutePath).size <= 2_000_000) {
      files.push(absolutePath);
    }
  }
  return files;
}

function findViolations(root) {
  const violations = [];
  for (const sourceDirectory of SOURCE_DIRECTORIES) {
    const directory = join(root, sourceDirectory);
    if (!existsSync(directory)) continue;
    for (const file of collectFiles(root, directory)) {
      const content = readFileSync(file, "utf8");
      for (const [kind, pattern] of MUTATION_PATTERNS) {
        const match = pattern.exec(content);
        if (match && match.index !== undefined) {
          const line = content.slice(0, match.index).split("\n").length;
          violations.push({ file: relative(root, file), kind, line });
        }
      }
    }
  }
  return violations;
}

export { findViolations };

const invokedPath = process.argv[1] ? resolve(process.argv[1]) : "";
const scriptPath = resolve(dirname(fileURLToPath(import.meta.url)), "verify_no_live_write.mjs");

if (invokedPath === scriptPath) {
  const root = parseRoot(process.argv.slice(2));
  const violations = findViolations(root);
  if (violations.length > 0) {
    for (const violation of violations) {
      console.error(`${violation.file}:${violation.line} [${violation.kind}]`);
    }
    console.error(`Live LMS write check failed: ${violations.length} violation(s).`);
    process.exitCode = 1;
  } else {
    console.log("Live LMS write check passed.");
  }
}
