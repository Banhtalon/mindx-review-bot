export default {
  test: {
    environment: "node",
    pool: "threads",
    fileParallelism: false,
    include: [
      "src/**/*.test.ts",
      "src/**/*.test.tsx",
      "test/**/*.test.ts"
    ],
    setupFiles: ["./test/setup.ts"],
  },
};
