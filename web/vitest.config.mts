import { defineConfig } from "vitest/config";

export default defineConfig({
  // Vite resolves the "@/*" alias from tsconfig.json; JSX is transformed by Vite itself.
  resolve: { tsconfigPaths: true },
  test: {
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
