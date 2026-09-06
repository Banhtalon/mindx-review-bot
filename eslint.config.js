import eslint from "@eslint/js";
import tseslint from "typescript-eslint";

export default tseslint.config(
  {
    ignores: [
      ".worktrees/**",
      "dist/**",
      "node_modules/**",
      "coverage/**",
      "**/.venv/**",
      "supabase/.temp/**",
    ],
  },
  eslint.configs.recommended,
  {
    files: ["scripts/qq-ai-workflow/**/*.mjs", "test/workflow-v9.test.mjs"],
    languageOptions: {
      globals: {
        clearTimeout: "readonly",
        console: "readonly",
        process: "readonly",
        setTimeout: "readonly"
      }
    }
  },
  ...tseslint.configs.recommended,
);
