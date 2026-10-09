import eslint from "@eslint/js";
import tseslint from "typescript-eslint";

export default tseslint.config(
  {
    ignores: [
      ".worktrees/**",
      ".workflow-local/**",
      "dist/**",
      "node_modules/**",
      "coverage/**",
      "**/.venv/**",
      "supabase/.temp/**",
      // Existing session helpers are separately covered by test:session.
      "scripts/lib/app_session.mjs",
      "scripts/lib/app_session.test.mjs",
    ],
  },
  eslint.configs.recommended,
  {
    files: [
      "scripts/lib/redact.mjs",
    ],
    languageOptions: {
      globals: {
        Buffer: "readonly",
        clearTimeout: "readonly",
        console: "readonly",
        process: "readonly",
        setTimeout: "readonly",
        structuredClone: "readonly",
        URL: "readonly",
      },
    },
  },
  ...tseslint.configs.recommended,
);
