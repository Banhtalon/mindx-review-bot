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
      // Pinned QQ Workflow v10 core is validated byte-for-byte against the
      // template source and by workflow:v10-check. Do not rewrite it to fit
      // this app's browser-oriented ESLint policy.
      "scripts/bridge.mjs",
      "scripts/fast-lane.mjs",
      "scripts/workflow.mjs",
      "scripts/lib/**/*.mjs",
    ],
  },
  eslint.configs.recommended,
  {
    files: ["scripts/check-workflow-v10.mjs", "scripts/qq-auto.mjs"],
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
