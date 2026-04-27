/// <reference types="vitest" />
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// ---------------------------------------------------------------------------
// Vitest config — Module T (smoke tests).
//
// Kept separate from `vite.config.ts` so the production build chunking
// logic doesn't interfere with the test harness.  Tests run under jsdom
// with React Testing Library + jest-dom matchers loaded from
// `tests/setup.ts`.
//
// Test discovery:
//   * Co-located `*.test.ts(x)` next to source.
//   * Standalone fixtures live under `tests/`.
// ---------------------------------------------------------------------------

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./__tests__/setup.ts"],
    include: ["__tests__/**/*.test.{ts,tsx}", "src/**/*.test.{ts,tsx}"],
    css: true,
    // The simulator uses sonner toasts which mount portals; jsdom is
    // happy to host them but we want to clean up the body between runs.
    restoreMocks: true,
    clearMocks: true,
  },
});
